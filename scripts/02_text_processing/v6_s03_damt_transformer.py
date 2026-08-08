# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s03_damt_transformer.py
==========================
Step 3: DA-MT-FinTransformer (Domain Adaptive Multi-task Financial Transformer)
        ——Completely implement thesis-style (T1)~(T12), execute B0/B1/B2/B3/Full five-speed ablation
           Verified outside of time (2025-01 ~ 2026-06).

Input: d01_text_processed/news_text.jsonl, news_meta.csv
       d02_lexicon_tfidf/news_scores.csv, domain_lexicon.json
Output: d03_model_damt/tokens_seq.txt word segmentation sequence cache
       d03_model_damt/vocab.json vocabulary
       d03_model_damt/enc_X.npy, enc_tag.npy encoding matrix and domain tag
       d03_model_damt/split_idx.npz Fixed training/validation/out-of-time sampling index
       d03_model_damt/ablation_metrics.json Five levels of ablation indicators (Table 4)
       d03_model_damt/confusion_matrices.json confusion matrix
       d03_model_damt/news_damt_scores.csv Full sample multi-task probability and gcs_DA (Formula T12)

Operating environment
--------
Python 3.11 + torch 2.5.1+cpu, must be run with PowerShell (torch segfaults under bash).

Phased execution (the time taken for a single call is controlled within 10 minutes, and breakpoint continuation is supported)
--------------------------------------------------------
    python v6_s03_damt_transformer.py prep # word segmentation + vocabulary + encoding
    python v6_s03_damt_transformer.py dapt # Formula (T8) domain continues pre-training
    python v6_s03_damt_transformer.py ft B0 # Five levels of ablation, executed step by step
    python v6_s03_damt_transformer.py ft B1
    python v6_s03_damt_transformer.py ft B2
    python v6_s03_damt_transformer.py ft B3
    python v6_s03_damt_transformer.py ft Full
    python v6_s03_damt_transformer.py infer 0 2 # Full sample inference, slice 0/2 slices in total
    python v6_s03_damt_transformer.py infer 1 2
    python v6_s03_damt_transformer.py finalize # Merge shards + summary report
    python v6_s03_damt_transformer.py all # Run in one go (about 50 minutes)"""
import json ,math ,os ,sys ,time ,csv ,random 
from collections import Counter 

import numpy as np 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import D01_TEXT ,D02_LEX ,D03_MODEL ,TRAIN_END ,VALID_END 

SEED =20260802 
random .seed (SEED );np .random .seed (SEED )

# ---- Architecture hyperparameters (Formula T1~T7)
# Note: N_LAYER is reduced from 4 to 2, Pre-LN and mean pooling are used, based on convergence diagnosis
# (v6_diag_train.py / v6_diag_train2.py) Confirmed - in 20,000-level weakly supervised samples,
# Under pure CPU training from scratch, 4-layer Post-LN + lr 3e-4 will degenerate into only predicting category priors
# (MacroF1≈0.23, equal to label distribution entropy), 2-layer Pre-LN + lr 1e-3 + warmup can converge normally.
L_SEQ =96 # Sequence length: attention O(L²), 96 covered news title + first paragraph of core information
D_MODEL =192 
N_LAYER =2 
N_HEAD =6 
D_FF =384 
VOCAB_MAX =24000 
PAD ,UNK ,CLS ,MASK =0 ,1 ,2 ,3 

# ---- Training hyperparameters (scale in CPU environment, taking into account sufficient convergence and runnability)
# The number of DAPT steps is determined by diagnosis: at 500 steps, the MLM confusion is still high (about 1.3e3), and the characterization is immature.
# Used as downstream initialization, it is inferior to random initialization; it must be trained until the representation converges to reflect the domain adaptation gain.
# Weight binding (mlm reuse token embedding) is not used in actual measurement because it will cause loss explosion due to scale mismatch.
DAPT_N =96000 
DAPT_EPOCH =1 
DAPT_BATCH =64 # The output dimension of the MLM head is V, and the batch size is smaller to control the memory.
DAPT_STEPS =1500 # The upper limit of steps (stop when reached), controls the length of a single run
FT_N =20000 
FT_EPOCH =4 
BATCH =128 # The downstream task header dimension is small, and the batch size is increased to improve CPU throughput.
INFER_BATCH =512 
LR =1e-3 
WARMUP_FRAC =0.1 # Linear warmup accounts for the proportion of total steps, and then cosine decays
KAPPA =0.5 # Formula (T12) Relationship adjustment coefficient
LAMBDA_BIAS =1.0 # Formula (T4) Domain bias strength
ETA_ANCHOR =1e-3 # Formula (T11) Parameter deviation penalty (mean square deviation after normalizing the parameter quantity)
GAMMA_FOCAL =1.5 

CFG ={
"B0":dict (dapt =False ,bias =False ,mt =False ,focal =False ,
desc ="Standard FinBERT (no domain adaptation) - tone only"),
"B1":dict (dapt =True ,bias =False ,mt =False ,focal =False ,
desc ="DAPT-FinBERT"),
"B2":dict (dapt =True ,bias =True ,mt =False ,focal =False ,
desc ="DAPT + domain-guided attention"),
"B3":dict (dapt =True ,bias =False ,mt =True ,focal =False ,
desc ="DAPT + multi-task heads"),
"Full":dict (dapt =True ,bias =True ,mt =True ,focal =True ,
desc ="DA-MT-FinTransformer (full)"),
}
W_TASK ={"tone":1.0 ,"rel":0.6 ,"obj":1.0 ,"rlt":0.8 ,"top":0.4 }


# ==================================================== 1. Word segmentation and encoding
def _jieba_init (words ):
    """Subprocess initialization: load domain words to ensure that proper nouns are not chopped up."""
    import jieba 
    jieba .initialize ()
    for w in words :
        jieba .add_word (w ,freq =100000 )


def _jieba_cut (item ):
    import jieba 
    nid ,text =item 
    toks =[t for t in jieba .lcut (text )if t .strip ()][:L_SEQ -1 ]
    return f"{nid }\t"+" ".join (toks )


def _iter_docs ():
    with open (D01_TEXT /"news_text.jsonl",encoding ="utf-8")as fi :
        for line in fi :
            d =json .loads (line )
            yield d ["nid"],(d ["title"]+"。"+d ["body"])[:900 ]


def build_tokens ():
    """Multi-process jieba tokenization -> tokens_seq.txt. If it already exists, skip it."""
    seq_path =D03_MODEL /"tokens_seq.txt"
    if seq_path .exists ():
        print ("[i] tokens_seq.txt 已存在，跳过分词")
        return seq_path 
    lex =json .load (open (D02_LEX /"domain_lexicon.json",encoding ="utf-8"))
    words =sorted ({w for ws in lex .values ()for w in ws })
    nproc =max (2 ,(os .cpu_count ()or 4 )-2 )
    print (f"[i] Multi-process word segmentation: {nproc } Process, domain word {len (words ):,}")
    t0 =time .time ();n =0 
    from multiprocessing import Pool 
    with Pool (nproc ,initializer =_jieba_init ,initargs =(words ,))as pool ,open (seq_path ,"w",encoding ="utf-8")as fo :
        for line in pool .imap (_jieba_cut ,_iter_docs (),chunksize =400 ):
            fo .write (line +"\n")
            n +=1 
            if n %25000 ==0 :
                print (f"    tokenize {n :,} ({time .time ()-t0 :.0f}s)")
    print (f"[i] Word participle completion {n :,} Article {time .time ()-t0 :.0f}s")
    return seq_path 


def build_vocab_and_encode (seq_path ):
    """Build a vocabulary and encode it as an int32 matrix + domain tag matrix."""
    xp ,tp ,np_ =(D03_MODEL /"enc_X.npy",D03_MODEL /"enc_tag.npy",
    D03_MODEL /"enc_nid.npy")
    if xp .exists ()and tp .exists ()and np_ .exists ():
        X =np .load (xp ,mmap_mode ="r")
        if X .shape [1 ]==L_SEQ :
            print (f"[i] The encoding matrix already exists X{X .shape }, load it directly")
            return (X ,np .load (tp ,mmap_mode ="r"),np .load (np_ ),
            json .load (open (D03_MODEL /"vocab.json",encoding ="utf-8")))
        print (f"[!] The existing code L={X .shape [1 ]} does not match the current L_SEQ={L_SEQ }, re-code")

    cnt =Counter ()
    with open (seq_path ,encoding ="utf-8")as f :
        for line in f :
            cnt .update (line .split ("\t",1 )[1 ].split ())
    itos =["[PAD]","[UNK]","[CLS]","[MASK]"]+[w for w ,_ in cnt .most_common (VOCAB_MAX -4 )]
    stoi ={w :i for i ,w in enumerate (itos )}
    json .dump ({"itos":itos },open (D03_MODEL /"vocab.json","w",
    encoding ="utf-8"),ensure_ascii =False )
    cover =sum (c for w ,c in cnt .items ()if w in stoi )/max (sum (cnt .values ()),1 )
    print (f"[i] Vocabulary {len (itos ):,} Corpus word type {len (cnt ):,} token coverage {cover :.2%}")

    # Domain tags: 1=GPU 2=CPU 3=Relation 4=Event (segment embedding of Equation T1 + indicator vector of Equation T3)
    lex =json .load (open (D02_LEX /"domain_lexicon.json",encoding ="utf-8"))
    tagmap ={}
    for w in lex ["GPU"]:
        tagmap [w ]=1 
    for w in lex ["CPU"]:
        tagmap [w ]=2 
    for g in ("SUB","COMP","COEXP","CONSTR"):
        for w in lex [g ]:
            tagmap .setdefault (w ,3 )
    for w in lex ["EVENT"]+lex ["CONSTR"]:
        tagmap .setdefault (w ,4 )

    rows =sum (1 for _ in open (seq_path ,encoding ="utf-8"))
    X =np .zeros ((rows ,L_SEQ ),dtype =np .int32 )
    TG =np .zeros ((rows ,L_SEQ ),dtype =np .int8 )
    NID =np .zeros (rows ,dtype =np .int64 )
    with open (seq_path ,encoding ="utf-8")as f :
        for i ,line in enumerate (f ):
            nid ,rest =line .rstrip ("\n").split ("\t",1 )
            NID [i ]=int (nid )
            toks =rest .split ()[:L_SEQ -1 ]
            ids =[CLS ]+[stoi .get (t ,UNK )for t in toks ]
            tg =[0 ]+[tagmap .get (t ,0 )for t in toks ]
            X [i ,:len (ids )]=ids 
            TG [i ,:len (tg )]=tg 
    np .save (xp ,X );np .save (tp ,TG );np .save (np_ ,NID )
    ntok =int ((X !=PAD ).sum (1 ).mean ())
    print (f"[i] Encoding completed X{X .shape } Average valid token {ntok }")
    return X ,TG ,NID ,{"itos":itos }


    # ==================================================== 2. Model (Formula T1~T7)
def build_model_classes ():
    import torch 
    import torch .nn as nn 
    import torch .nn .functional as F 

    class DomainBiasedMHA (nn .Module ):
        """Formula (T2)(T3)(T4)(T5): Domain bias-guided multi-head self-attention."""

        def __init__ (self ,d ,h ,use_bias ):
            super ().__init__ ()
            self .h ,self .dk =h ,d //h 
            self .q =nn .Linear (d ,d );self .k =nn .Linear (d ,d )
            self .v =nn .Linear (d ,d );self .o =nn .Linear (d ,d )
            self .use_bias =use_bias 
            if use_bias :
            # w_G, w_C, w_R, w_E - learnable, softplus corrected to maintain interpretability
                self .wb =nn .Parameter (torch .tensor ([0.5 ,0.5 ,0.5 ,0.5 ]))

        def forward (self ,x ,pad_mask ,bias4 =None ):
            B ,L ,D =x .shape 
            q =self .q (x ).view (B ,L ,self .h ,self .dk ).transpose (1 ,2 )
            k =self .k (x ).view (B ,L ,self .h ,self .dk ).transpose (1 ,2 )
            v =self .v (x ).view (B ,L ,self .h ,self .dk ).transpose (1 ,2 )
            att =q @k .transpose (-1 ,-2 )/math .sqrt (self .dk )
            if self .use_bias and bias4 is not None :
                w =F .softplus (self .wb )
                BD =torch .einsum ("c,bcij->bij",w ,bias4 )# Formula(T3)(T4)
                att =att +LAMBDA_BIAS *BD .unsqueeze (1 )
            att =att .masked_fill (pad_mask [:,None ,None ,:],-1e4 )
            p =torch .softmax (att ,-1 )
            out =(p @v ).transpose (1 ,2 ).contiguous ().view (B ,L ,D )
            return self .o (out )

    class Block (nn .Module ):
        """Formula (T6)(T7): Residual + LayerNorm + Feedforward GELU.

        Using Pre-LN normalized position (LayerNorm is placed in front of the sub-layer), training from scratch on a small scale
        Gradient scale is more stable; Post-LN can cause optimization to stall at the scale of this paper (see diagnostic script)."""

        def __init__ (self ,d ,h ,dff ,use_bias ,p =0.1 ):
            super ().__init__ ()
            self .att =DomainBiasedMHA (d ,h ,use_bias )
            self .n1 =nn .LayerNorm (d );self .n2 =nn .LayerNorm (d )
            self .ff =nn .Sequential (nn .Linear (d ,dff ),nn .GELU (),nn .Linear (dff ,d ))
            self .dp =nn .Dropout (p )

        def forward (self ,x ,pm ,b4 ):
            x =x +self .dp (self .att (self .n1 (x ),pm ,b4 ))
            x =x +self .dp (self .ff (self .n2 (x )))
            return x 

    class DAMT (nn .Module ):
        """DA-MT-FinTransformer. When multi_task=False, only the Tone single task header is retained."""

        def __init__ (self ,V ,use_bias =True ,multi_task =True ):
            super ().__init__ ()
            self .tok =nn .Embedding (V ,D_MODEL ,padding_idx =PAD )
            self .pos =nn .Embedding (L_SEQ ,D_MODEL )
            self .seg =nn .Embedding (5 ,D_MODEL )# Segment = domain tag (Formula T1)
            self .dp =nn .Dropout (0.1 )
            self .use_bias =use_bias 
            self .multi_task =multi_task 
            self .blocks =nn .ModuleList (
            [Block (D_MODEL ,N_HEAD ,D_FF ,use_bias )for _ in range (N_LAYER )])
            self .nf =nn .LayerNorm (D_MODEL )# Final normalization of Pre-LN architecture
            self .mlm =nn .Linear (D_MODEL ,V )# Formula (T8) DAPT head
            self .h_tone =nn .Linear (D_MODEL ,3 )# Formula (T9)
            if multi_task :
                self .h_rel =nn .Linear (D_MODEL ,2 )
                self .h_obj =nn .Linear (D_MODEL ,3 )
                self .h_rlt =nn .Linear (D_MODEL ,4 )
                self .h_top =nn .Linear (D_MODEL ,6 )

        def encode (self ,x ,tag ):
            B ,L =x .shape 
            pm =x .eq (PAD )
            seg =torch .clamp (tag ,0 ,4 )
            e =self .tok (x )+self .pos (torch .arange (L ,device =x .device ))[None ]+self .seg (seg )
            e =self .dp (e )
            b4 =None 
            if self .use_bias :
            # Outer product matching matrix of I^G, I^C, I^R, I^E (Formula T3)
                ms =[(tag ==t ).float ()for t in (1 ,2 ,3 ,4 )]
                b4 =torch .stack ([m .unsqueeze (2 )*m .unsqueeze (1 )for m in ms ],1 )
            for blk in self .blocks :
                e =blk (e ,pm ,b4 )
            return self .nf (e ),pm 

        def forward (self ,x ,tag ,mode ="task",mlm_pos =None ):
            e ,pm =self .encode (x ,tag )
            if mode =="mlm":
            # Only calculate V-dimensional logits at the occluded position to avoid the huge graphics memory/computing power overhead of B×L×V
                h =e [mlm_pos ]if mlm_pos is not None else e 
                return self .mlm (h )
                # Formula (T9) document indicates h_n: non-filled position mean pooling.
                # On a small model trained from scratch [CLS] without pre-training for NSP-type tasks, the discriminant signal is weaker than mean pooling.
            m =(~pm ).float ().unsqueeze (-1 )
            h =(e *m ).sum (1 )/m .sum (1 ).clamp (min =1 )
            out ={"tone":self .h_tone (h )}
            if self .multi_task :
                out .update (rel =self .h_rel (h ),obj =self .h_obj (h ),
                rlt =self .h_rlt (h ),top =self .h_top (h ))
            return out 

    def focal_loss (logit ,y ,alpha ,gamma =GAMMA_FOCAL ):
        """Formula (T10) Category balance Focal Loss; y<0 indicates that weak labels are missing and should be blocked."""
        keep =y >=0 
        if not bool (keep .any ()):
            return logit .sum ()*0.0 
        logit ,y =logit [keep ],y [keep ]
        logp =F .log_softmax (logit ,-1 )
        p =logp .exp ()
        lp =logp .gather (1 ,y [:,None ]).squeeze (1 )
        pt =p .gather (1 ,y [:,None ]).squeeze (1 )
        a =alpha [y ]
        return (-a *(1 -pt ).pow (gamma )*lp ).mean ()

    def ce_loss (logit ,y ,alpha =None ):
        """Standard cross-entropy; unlabeled samples with y<0 do not participate in the loss.

        alpha is the category weight: the distribution of weak labels is highly uneven (most categories account for nearly 70%),
        Without weighting, the model will converge to the degenerate solution of "full predict majority class"."""
        keep =y >=0 
        if not bool (keep .any ()):
            return logit .sum ()*0.0 
        return F .cross_entropy (logit [keep ],y [keep ],weight =alpha )

    return torch ,nn ,F ,DAMT ,focal_loss ,ce_loss 


    # ==================================================== 3. Shared context
def load_context (need_torch =True ):
    """Loading encoding matrices, weak labels, time division and fixed sampling index - common to all stages."""
    import pandas as pd 
    X ,TG ,NID ,vb =build_vocab_and_encode (D03_MODEL /"tokens_seq.txt")
    V =len (vb ["itos"])

    sc =pd .read_csv (D02_LEX /"news_scores.csv")
    meta =pd .read_csv (D01_TEXT /"news_meta.csv",
    usecols =["nid","date","trade_date"])
    df =meta .merge (sc ,on ="nid",how ="inner")
    order =pd .DataFrame ({"nid":NID ,"row":np .arange (len (NID ))})
    df =df .merge (order ,on ="nid",how ="inner").sort_values ("row")

    rows =df ["row"].to_numpy ()
    Y ={k :df [f"y_{k2 }"].to_numpy ()for k ,k2 in 
    [("rel","rel"),("obj","object"),("tone","tone"),
    ("rlt","relation"),("top","topic")]}
    conf =df ["conf"].to_numpy ()
    date =df ["date"].to_numpy ().astype (str )

    is_tr =date <=TRAIN_END 
    is_va =(date >TRAIN_END )&(date <=VALID_END )
    is_te =date >VALID_END # Outside time 2025-01~2026-06

    # The sampling index is fixed and saved to ensure that each stage (which may be run in multiple processes) is completely consistent.
    sp =D03_MODEL /"split_idx.npz"
    if sp .exists ():
        z =np .load (sp )
        tr_idx ,va_idx ,te_idx =z ["tr"],z ["va"],z ["te"]
    else :
        rng =np .random .RandomState (SEED )
        # The coverage rate of weak tags in the relationship header/topic header is low, and extra weight is given to "tagged" documents when sampling.
        # Ensure that the sparse task head gets enough training signals without destroying the time division.
        lab_cov =((Y ["rlt"]>=0 ).astype (float )+
        (Y ["top"]>=0 ).astype (float ))/2.0 

        def sample_idx (mask ,n ,prefer_conf =True ):
            idx =np .where (mask )[0 ]
            if len (idx )<=n :
                return idx 
            if prefer_conf :# High confidence weak labels are given priority (distant supervision)
                p =(conf [idx ]+0.05 )*(1.0 +1.5 *lab_cov [idx ])
                p =p /p .sum ()
                return np .sort (rng .choice (idx ,n ,replace =False ,p =p ))
            return np .sort (rng .choice (idx ,n ,replace =False ))

        tr_idx =sample_idx (is_tr ,FT_N )
        va_idx =sample_idx (is_va ,8000 )
        te_idx =sample_idx (is_te ,12000 ,prefer_conf =False )# No confidence filtering outside of time
        np .savez (sp ,tr =tr_idx ,va =va_idx ,te =te_idx )

    print (f"[i] Alignment sample {len (df ):,} | train {is_tr .sum ():,} valid {is_va .sum ():,} oos {is_te .sum ():,}")
    print (f"[i] sampling ft {len (tr_idx ):,} | valid {len (va_idx ):,} | oos-eval {len (te_idx ):,}")

    ctx =dict (X =X ,TG =TG ,NID =NID ,V =V ,df =df ,rows =rows ,Y =Y ,conf =conf ,
    date =date ,is_tr =is_tr ,is_va =is_va ,is_te =is_te ,
    tr_idx =tr_idx ,va_idx =va_idx ,te_idx =te_idx )

    if need_torch :
        torch ,nn ,F ,DAMT ,focal_loss ,ce_loss =build_model_classes ()
        torch .manual_seed (SEED )
        torch .set_num_threads (max (2 ,(os .cpu_count ()or 4 )-2 ))
        ctx .update (torch =torch ,F =F ,DAMT =DAMT ,
        focal_loss =focal_loss ,ce_loss =ce_loss )

        # Category weights are only counted based on "labeled" samples (y<0 means weak labels are missing, see S02)
        alphas ={}
        for k ,y in Y .items ():
            ytr =y [tr_idx ]
            ytr =ytr [ytr >=0 ]
            n_cls =max (int (y .max ())+1 ,2 )
            c =np .bincount (ytr ,minlength =n_cls ).astype (float )
            a =(c .sum ()/(len (c )*np .maximum (c ,1 )))
            alphas [k ]=torch .tensor (np .clip (a ,0.2 ,5.0 ),dtype =torch .float32 )
        ctx ["alphas"]=alphas 
    return ctx 


def batch_of (ctx ,idx ):
    torch =ctx ["torch"]
    r =np .asarray (ctx ["rows"])[idx ]
    o =np .argsort (r )# mmap reads faster by line number in ascending order
    ro =r [o ]
    xb =torch .from_numpy (np .asarray (ctx ["X"][ro ]).astype (np .int64 ))
    tb =torch .from_numpy (np .asarray (ctx ["TG"][ro ]).astype (np .int64 ))
    inv =np .argsort (o )
    return xb [inv ],tb [inv ]


    # ==================================================== 4. Each stage
def stage_prep ():
    print ("="*64 ,"\n[STAGE] prep —— 分词 / 词表 / 编码\n","="*64 )
    t0 =time .time ()
    sp =build_tokens ()
    build_vocab_and_encode (sp )
    print (f"[i] prep completed {time .time ()-t0 :.0f}s")


def stage_dapt (ctx ,run_steps =None ):
    """Formula (T8): Domain-Adaptive Pre-Training.

    Supports breakpoint continuation of training: each call can run up to run_steps steps and save the progress.
    Repeat the call until the accumulation reaches DAPT_STEPS. This way the duration of a single run can be controlled."""
    print ("="*64 ,"\n[STAGE] dapt —— 式(T8) 领域继续预训练\n","="*64 )
    torch ,F ,DAMT =ctx ["torch"],ctx ["F"],ctx ["DAMT"]
    dapt_path =D03_MODEL /"dapt_state.pt"
    ck_path =D03_MODEL /"dapt_ckpt.pt"
    rep_path =D03_MODEL /"dapt_report.json"

    if dapt_path .exists ():
        print (f"[i] dapt_state.pt already exists ({DAPT_STEPS } steps completed), skip")
        return 

    base =DAMT (ctx ["V"],use_bias =True ,multi_task =True )
    opt =torch .optim .AdamW (base .parameters (),lr =LR ,weight_decay =0.01 )
    warm =max (10 ,int (DAPT_STEPS *WARMUP_FRAC ))
    sch =torch .optim .lr_scheduler .LambdaLR (
    opt ,lambda s :min (1.0 ,(s +1 )/warm )*
    (0.5 *(1 +math .cos (math .pi *min (s /DAPT_STEPS ,1.0 )))))

    done ,hist =0 ,[]
    if ck_path .exists ():
        ck =torch .load (ck_path ,weights_only =False )
        base .load_state_dict (ck ["model"]);opt .load_state_dict (ck ["opt"])
        sch .load_state_dict (ck ["sch"]);done =ck ["step"];hist =ck ["hist"]
        print (f"[i] Continue training from the checkpoint, completed {done }/{DAPT_STEPS } step")

    n_par =sum (p .numel ()for p in base .parameters ())
    run_steps =run_steps or 500 
    todo =min (run_steps ,DAPT_STEPS -done )
    print (f"[i] Parameter amount {n_par /1e6 :.2f}M thread {torch .get_num_threads ()} batch {DAPT_BATCH } This training {todo } steps")

    rng =np .random .RandomState (SEED +1 +done )
    pool =np .where (ctx ["is_tr"]|ctx ["is_va"])[0 ]
    base .train ()
    t0 =time .time ();losses =[]
    for i in range (todo ):
        bi =pool [rng .choice (len (pool ),DAPT_BATCH ,replace =False )]
        xb ,tb =batch_of (ctx ,bi )
        prob =torch .rand (xb .shape )
        msk =(prob <0.15 )&(xb !=PAD )&(xb !=CLS )
        if not bool (msk .any ()):
            continue 
        tgt =xb [msk ]
        xin =xb .clone ();xin [msk ]=MASK 
        logit =base (xin ,tb ,mode ="mlm",mlm_pos =msk )# Only masked bits
        loss =F .cross_entropy (logit ,tgt )
        opt .zero_grad ();loss .backward ()
        torch .nn .utils .clip_grad_norm_ (base .parameters (),1.0 )
        opt .step ();sch .step ()
        losses .append (float (loss ))
        if (i +1 )%50 ==0 :
            print (f"    DAPT step {done +i +1 }/{DAPT_STEPS }  "
            f"loss {np .mean (losses [-50 :]):.3f}  "
            f"PPL {math .exp (min (np .mean (losses [-50 :]),20 )):.0f}  "
            f"lr {sch .get_last_lr ()[0 ]:.2e}  ({time .time ()-t0 :.0f}s)")

    done +=todo 
    hist .extend ([round (float (x ),4 )for x in losses [::10 ]])
    torch .save ({"model":base .state_dict (),"opt":opt .state_dict (),
    "sch":sch .state_dict (),"step":done ,"hist":hist },ck_path )

    ppl =math .exp (min (float (np .mean (losses [-50 :])),20 ))if losses else None 
    if done >=DAPT_STEPS :
        torch .save (base .state_dict (),dapt_path )
        json .dump ({"steps":done ,"loss_first":hist [0 ]if hist else None ,
        "loss_last":round (float (np .mean (losses [-50 :])),4 ),
        "final_ppl":round (ppl ,1 )if ppl else None ,
        "loss_curve":hist ,
        "n_pool":int (len (pool )),"batch":DAPT_BATCH ,"lr":LR },
        open (rep_path ,"w",encoding ="utf-8"),
        ensure_ascii =False ,indent =2 )
        print (f"[i] DAPT All Completed {done } Step Final PPL {ppl :.0f}")
    else :
        print (f"[i] This section is completed, accumulative {done }/{DAPT_STEPS } steps current PPL {ppl :.0f} —— Please run dapt again to continue")


def evaluate (ctx ,model ,idx ,multi ):
    """Unlabeled samples (y<0) are not counted in any metric."""
    from sklearn .metrics import f1_score ,roc_auc_score ,recall_score ,confusion_matrix 
    torch ,Y =ctx ["torch"],ctx ["Y"]
    model .eval ()
    keys =["tone"]+(["rel","obj","rlt","top"]if multi else [])
    preds ={k :[]for k in keys }
    probs ={k :[]for k in keys }
    with torch .inference_mode ():
        for s in range (0 ,len (idx ),256 ):
            bi =idx [s :s +256 ]
            xb ,tb =batch_of (ctx ,bi )
            o =model (xb ,tb )
            for k in keys :
                p =torch .softmax (o [k ],-1 ).numpy ()
                probs [k ].append (p )
                preds [k ].append (p .argmax (1 ))
    res ,cms ={},{}
    for k in keys :
        yp =np .concatenate (preds [k ]);pp =np .vstack (probs [k ])
        yt =Y [k ][idx ]
        m =yt >=0 
        n_lab =int (m .sum ())
        res [f"{k }_n"]=n_lab 
        if n_lab <20 :
            res [f"{k }_macroF1"]=res [f"{k }_acc"]=res [f"{k }_auroc"]=None 
            continue 
        ytm ,ypm ,ppm =yt [m ],yp [m ],pp [m ]
        res [f"{k }_macroF1"]=round (float (f1_score (ytm ,ypm ,average ="macro")),4 )
        res [f"{k }_acc"]=round (float ((ytm ==ypm ).mean ()),4 )
        try :
            if ppm .shape [1 ]==2 :
                au =roc_auc_score (ytm ,ppm [:,1 ])
            else :
                au =roc_auc_score (ytm ,ppm ,multi_class ="ovr",average ="macro")
            res [f"{k }_auroc"]=round (float (au ),4 )
        except Exception :
            res [f"{k }_auroc"]=None 
        cms [k ]=confusion_matrix (ytm ,ypm ).tolist ()
        if k =="obj":# GPU/CPU object recall
            rc =recall_score (ytm ,ypm ,average =None ,labels =[0 ,1 ,2 ],
            zero_division =0 )
            res ["recall_GPU"]=round (float (rc [0 ]),4 )
            res ["recall_CPU"]=round (float (rc [1 ]),4 )
    return res ,cms 


def stage_ft (ctx ,name ):
    """Single-level ablation fine-tuning (B0/B1/B2/B3/Full)."""
    cfg =CFG [name ]
    print ("="*64 ,f"\n[STAGE] ft {name } —— {cfg ['desc']}\n","="*64 )
    torch ,DAMT =ctx ["torch"],ctx ["DAMT"]
    focal_loss ,ce_loss =ctx ["focal_loss"],ctx ["ce_loss"]
    Y ,alphas ,tr_idx =ctx ["Y"],ctx ["alphas"],ctx ["tr_idx"]

    m =DAMT (ctx ["V"],use_bias =cfg ["bias"],multi_task =cfg ["mt"])
    anchor =None 
    if cfg ["dapt"]:
        dp =D03_MODEL /"dapt_state.pt"
        if not dp .exists ():
            raise SystemExit ("[x] dapt_state.pt is missing, please run stage dapt first")
        sd =torch .load (dp ,weights_only =True )
        m .load_state_dict (sd ,strict =False )
        # Formula (T11): Taking DAPT weight as the anchor point to punish excessive deviation in the fine-tuning stage
        anchor ={k :v .clone ()for k ,v in m .state_dict ().items ()
        if k in sd and v .shape ==sd [k ].shape and v .dtype .is_floating_point }
        print ("[i] DAPT weight has been loaded and the anchor point of formula (T11) has been set")

    opt =torch .optim .AdamW (m .parameters (),lr =LR ,weight_decay =0.01 )
    lossfn =focal_loss if cfg ["focal"]else ce_loss 
    keys =["tone"]+(["rel","obj","rlt","top"]if cfg ["mt"]else [])
    for k in keys :
        n_lab =int ((Y [k ][tr_idx ]>=0 ).sum ())
        print (f"Task {k :5s} has been tagged {n_lab :,}/{len (tr_idx ):,} ({n_lab /max (len (tr_idx ),1 ):.1%})")

    n_step_total =max (1 ,(len (tr_idx )//BATCH )*FT_EPOCH )
    warm =max (10 ,int (n_step_total *WARMUP_FRAC ))
    sch =torch .optim .lr_scheduler .LambdaLR (
    opt ,lambda s :min (1.0 ,(s +1 )/warm )*
    (0.5 *(1 +math .cos (math .pi *min (s /n_step_total ,1.0 )))))
    print (f"plan {n_step_total } step (warmup {warm }), lr {LR }")

    rng =np .random .RandomState (SEED +7 )
    t0 =time .time ();step =0 ;losses =[]
    for ep in range (FT_EPOCH ):
        m .train ()
        perm =rng .permutation (len (tr_idx ))
        for s in range (0 ,len (perm )-BATCH +1 ,BATCH ):
            bi =tr_idx [perm [s :s +BATCH ]]
            xb ,tb =batch_of (ctx ,bi )
            o =m (xb ,tb )
            loss =0.0 
            for k in keys :
                yk =torch .from_numpy (Y [k ][bi ].astype (np .int64 ))
                loss =loss +W_TASK [k ]*lossfn (o [k ],yk ,alphas [k ])
            if anchor is not None :
            # Formula (T11) deviation penalty: normalized to "mean square deviation" according to the parameter amount,
            # Otherwise, the penalty term will expand linearly with the model scale (this model has nearly 10 million parameters),
            # It will overwhelm the task loss and lock the weight near the initial value of DAPT (the actual measured B1 is therefore worse than B0).
                pen =sum (((p -anchor [n ])**2 ).mean ()
                for n ,p in m .named_parameters ()if n in anchor )
                loss =loss +ETA_ANCHOR *pen 
            opt .zero_grad ();loss .backward ()
            torch .nn .utils .clip_grad_norm_ (m .parameters (),1.0 )
            opt .step ();sch .step ()
            step +=1 ;losses .append (float (loss ))
            if step %50 ==0 :
                print (f"    {name } ep{ep } step {step } "
                f"loss {np .mean (losses [-50 :]):.3f} "
                f"lr {sch .get_last_lr ()[0 ]:.2e} ({time .time ()-t0 :.0f}s)")
    tr_sec =time .time ()-t0 

    r_va ,_ =evaluate (ctx ,m ,ctx ["va_idx"],cfg ["mt"])
    r_te ,cm =evaluate (ctx ,m ,ctx ["te_idx"],cfg ["mt"])
    rec ={"desc":cfg ["desc"],"cfg":{k :v for k ,v in cfg .items ()if k !="desc"},
    "valid":r_va ,"oos":r_te ,"train_sec":round (tr_sec ,1 ),
    "steps":step ,
    "loss_first50":round (float (np .mean (losses [:50 ])),4 ),
    "loss_last50":round (float (np .mean (losses [-50 :])),4 )}
    json .dump (rec ,open (D03_MODEL /f"metrics_{name }.json","w",
    encoding ="utf-8"),ensure_ascii =False ,indent =2 )
    json .dump (cm ,open (D03_MODEL /f"cm_{name }.json","w",
    encoding ="utf-8"),ensure_ascii =False ,indent =2 )
    torch .save (m .state_dict (),D03_MODEL /f"model_{name }.pt")
    print (f"[i] {name } Complete {tr_sec :.0f}s -> OOS tone MacroF1 {r_te .get ('tone_macroF1')} | obj MacroF1 {r_te .get ('obj_macroF1')}")


def stage_merge ():
    """ablation_metrics.json required to merge five levels of metrics into Table 4."""
    print ("="*64 ,"\n[STAGE] merge —— 汇总五档消融指标\n","="*64 )
    metrics ,confusions ={},{}
    for name in CFG :
        mp ,cp =D03_MODEL /f"metrics_{name }.json",D03_MODEL /f"cm_{name }.json"
        if not mp .exists ():
            print (f"[!] Missing {name }, skipped")
            continue 
        metrics [name ]=json .load (open (mp ,encoding ="utf-8"))
        confusions [name ]=json .load (open (cp ,encoding ="utf-8"))
        o =metrics [name ]["oos"]
        print (f"    {name :5s} OOS tone F1 {o .get ('tone_macroF1')}  "
        f"obj F1 {o .get ('obj_macroF1')}  "
        f"recall_GPU {o .get ('recall_GPU')}  recall_CPU {o .get ('recall_CPU')}")
    json .dump (metrics ,open (D03_MODEL /"ablation_metrics.json","w",
    encoding ="utf-8"),ensure_ascii =False ,indent =2 )
    json .dump (confusions ,open (D03_MODEL /"confusion_matrices.json","w",
    encoding ="utf-8"),ensure_ascii =False ,indent =2 )
    print (f"[i] ablation_metrics.json has been written ({len (metrics )} file)")


def stage_infer (ctx ,part ,nparts ):
    """Full model full sample inference -> Formula (T12) gcs_DA. Sharded execution."""
    print ("="*64 ,f"\n[STAGE] infer {part }/{nparts }——Formula (T12) Full sample inference\n",
    "="*64 )
    torch ,DAMT ,df =ctx ["torch"],ctx ["DAMT"],ctx ["df"]
    mp =D03_MODEL /"model_Full.pt"
    if not mp .exists ():
        raise SystemExit ("[x] model_Full.pt is missing, please run stage ft Full first")
    m =DAMT (ctx ["V"],use_bias =True ,multi_task =True )
    m .load_state_dict (torch .load (mp ,weights_only =True ))
    m .eval ()

    rows =ctx ["rows"]
    inten =df ["intensity"].to_numpy ()
    nid_arr =df ["nid"].to_numpy ()
    n =len (rows )
    lo =n *part //nparts 
    hi =n *(part +1 )//nparts 
    print (f"[i] This film [{lo :,}, {hi :,}) has a total of {hi -lo :,} articles")

    out =open (D03_MODEL /f"damt_part{part }.csv","w",encoding ="utf-8",
    newline ="")
    w =csv .writer (out )
    w .writerow (["nid","p_rel","p_gpu","p_cpu","p_obj_neu","p_pos","p_neg",
    "p_tone_neu","p_sub","p_comp","p_coexp","p_constr",
    "topic_pred","gcs_da"])
    t0 =time .time ()
    with torch .inference_mode ():
        for s in range (lo ,hi ,INFER_BATCH ):
            e =min (s +INFER_BATCH ,hi )
            r =rows [s :e ]
            o_ =np .argsort (r );ro =r [o_ ];inv =np .argsort (o_ )
            xb =torch .from_numpy (np .asarray (ctx ["X"][ro ]).astype (np .int64 ))[inv ]
            tb =torch .from_numpy (np .asarray (ctx ["TG"][ro ]).astype (np .int64 ))[inv ]
            o =m (xb ,tb )
            prel =torch .softmax (o ["rel"],-1 ).numpy ()
            pobj =torch .softmax (o ["obj"],-1 ).numpy ()
            pton =torch .softmax (o ["tone"],-1 ).numpy ()
            prlt =torch .softmax (o ["rlt"],-1 ).numpy ()
            ptop =torch .softmax (o ["top"],-1 ).numpy ().argmax (1 )
            it =inten [s :e ]
            # Formula (T12)
            gcs =(prel [:,1 ]*np .log1p (np .maximum (it ,0 ))*
            (pobj [:,0 ]-pobj [:,1 ])*(pton [:,0 ]-pton [:,1 ])*
            (1 +KAPPA *(prlt [:,0 ]-prlt [:,1 ])))
            for j in range (e -s ):
                w .writerow ([nid_arr [s +j ],
                f"{prel [j ,1 ]:.5f}",f"{pobj [j ,0 ]:.5f}",
                f"{pobj [j ,1 ]:.5f}",f"{pobj [j ,2 ]:.5f}",
                f"{pton [j ,0 ]:.5f}",f"{pton [j ,1 ]:.5f}",
                f"{pton [j ,2 ]:.5f}",f"{prlt [j ,0 ]:.5f}",
                f"{prlt [j ,1 ]:.5f}",f"{prlt [j ,2 ]:.5f}",
                f"{prlt [j ,3 ]:.5f}",int (ptop [j ]),
                f"{gcs [j ]:.6f}"])
            if (s -lo )%(INFER_BATCH *40 )==0 :
                done =max (s -lo ,1 )
                eta =(time .time ()-t0 )/done *(hi -s )
                print (f"    infer {s -lo :,}/{hi -lo :,} "
                f"({time .time ()-t0 :.0f}s, eta {eta :.0f}s)")
    out .close ()
    print (f"[i] Sharding {part } Completed {time .time ()-t0 :.0f}s")


def stage_finalize (ctx ,nparts ):
    """Merge the inference shards and write a general report."""
    print ("="*64 ,"\n[STAGE] finalize —— 合并分片 + 汇总报告\n","="*64 )
    import pandas as pd 
    parts =[]
    for i in range (nparts ):
        p =D03_MODEL /f"damt_part{i }.csv"
        if not p .exists ():
            raise SystemExit (f"[x] Missing inference shards {p .name }")
        parts .append (pd .read_csv (p ))
    allp =pd .concat (parts ,ignore_index =True )
    allp =allp .drop_duplicates (subset =["nid"],keep ="first")
    allp .to_csv (D03_MODEL /"news_damt_scores.csv",index =False )
    print (f"[i] news_damt_scores.csv {len (allp ):,} row")
    print (f"    gcs_da  mean {allp ['gcs_da'].mean ():.4f} "
    f"sd {allp ['gcs_da'].std ():.4f} "
    f"min {allp ['gcs_da'].min ():.4f} max {allp ['gcs_da'].max ():.4f}")
    print (f"p_gpu mean {allp ['p_gpu'].mean ():.4f} | p_cpu mean {allp ['p_cpu'].mean ():.4f} | p_rel mean {allp ['p_rel'].mean ():.4f}")

    rep ={"n_docs":int (len (allp )),"vocab":int (ctx ["V"]),
    "arch":dict (L_SEQ =L_SEQ ,D_MODEL =D_MODEL ,N_LAYER =N_LAYER ,
    N_HEAD =N_HEAD ,D_FF =D_FF ,vocab_max =VOCAB_MAX ),
    "train_cfg":dict (dapt_n =DAPT_N ,dapt_batch =DAPT_BATCH ,
    ft_n =FT_N ,ft_epoch =FT_EPOCH ,batch =BATCH ,lr =LR ),
    "split":{"train":int (ctx ["is_tr"].sum ()),
    "valid":int (ctx ["is_va"].sum ()),
    "oos":int (ctx ["is_te"].sum ()),
    "ft_n":int (len (ctx ["tr_idx"])),
    "oos_eval_n":int (len (ctx ["te_idx"]))},
    "kappa":KAPPA ,"lambda_bias":LAMBDA_BIAS ,
    "eta_anchor":ETA_ANCHOR ,"gamma_focal":GAMMA_FOCAL ,
    "gcs_da_stat":{"mean":round (float (allp ["gcs_da"].mean ()),6 ),
    "sd":round (float (allp ["gcs_da"].std ()),6 )}}
    dp =D03_MODEL /"dapt_report.json"
    if dp .exists ():
        rep ["dapt"]=json .load (open (dp ,encoding ="utf-8"))
    json .dump (rep ,open (D03_MODEL /"s03_report.json","w",encoding ="utf-8"),
    ensure_ascii =False ,indent =2 )
    print ("[i] s03_report.json 已写出")


    # ==================================================== 5. Entrance
def main ():
    args =sys .argv [1 :]or ["all"]
    stage =args [0 ]
    t0 =time .time ()

    if stage =="prep":
        stage_prep ()
    elif stage =="dapt":
        rs =int (args [1 ])if len (args )>1 else 500 
        stage_dapt (load_context (),run_steps =rs )
    elif stage =="ft":
        name =args [1 ]if len (args )>1 else "Full"
        stage_ft (load_context (),name )
    elif stage =="merge":
        stage_merge ()
    elif stage =="infer":
        part =int (args [1 ])if len (args )>1 else 0 
        nparts =int (args [2 ])if len (args )>2 else 2 
        stage_infer (load_context (),part ,nparts )
    elif stage =="finalize":
        nparts =int (args [1 ])if len (args )>1 else 2 
        stage_finalize (load_context (need_torch =False ),nparts )
    elif stage =="all":
        stage_prep ()
        ctx =load_context ()
        while not (D03_MODEL /"dapt_state.pt").exists ():
            stage_dapt (ctx ,run_steps =DAPT_STEPS )
        for name in CFG :
            stage_ft (ctx ,name )
        stage_merge ()
        for i in range (2 ):
            stage_infer (ctx ,i ,2 )
        stage_finalize (ctx ,2 )
    else :
        raise SystemExit (f"Unknown stage: {stage }")

    print (f"\n[i] stage '{stage }' ends, takes {time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
