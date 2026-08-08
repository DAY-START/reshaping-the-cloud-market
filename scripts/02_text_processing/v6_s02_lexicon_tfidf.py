# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s02_lexicon_tfidf.py
=======================
Step 2: Dictionary construction in the field of AI computing power, jieba word segmentation, TF-IDF weight,
        Article-level Orientation / Tone / Intensity / Relation / Topic weak supervision tags,
        and the transparent dictionary of equation (4)—the intonation baseline news score gcs_lex.

Input: data_v2_experiment/d01_text_processed/news_text.jsonl
       data_v2_experiment/d01_text_processed/news_meta.csv
Output: data_v2_experiment/d02_lexicon/domain_lexicon.json domain dictionary
       data_v2_experiment/d02_lexicon/idf_lexicon.json dictionary word IDF
       data_v2_experiment/d02_lexicon/news_hits.jsonl Each article hit cache (middleware)
       data_v2_experiment/d02_lexicon/news_scores.csv article-level scores and weak tags
       data_v2_experiment/d02_lexicon/s02_report.json

Corresponds to equation (1)(2)(3)(4) in section 3.4 of the paper and multi-task weakly supervised label construction in section 3.5."""
import json ,math ,re ,sys ,time ,csv 
from collections import Counter ,defaultdict 

import jieba 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import D01_TEXT ,D02_LEX 

# ============================================================ 1. Domain Dictionary
GPU_WORDS =[
"GPU","显卡","加速卡","图形处理器","英伟达","NVIDIA","AI芯片","智能芯片",
"H100","H800","A100","A800","H20","L40S","B200","GB200","GH200",
"昇腾","寒武纪","思元","壁仞","燧原","摩尔线程","沐曦","天数智芯","海光DCU",
"AI服务器","智算中心","智算","算力中心","超算","训练集群","推理卡","训练卡",
"大模型","生成式AI","AIGC","深度学习","神经网络","GPU云","算力租赁",
"HBM","高带宽内存","CoWoS","NVLink","光模块","液冷","GPGPU","NPU","TPU",
"算力芯片","并行计算","异构计算","AI算力","智能算力","万卡集群","千卡集群",
]
CPU_WORDS =[
"CPU","中央处理器","x86","至强","Xeon","英特尔","Intel","AMD","EPYC",
"海光","龙芯","飞腾","兆芯","申威","鲲鹏","ARM服务器","通用服务器",
"通用算力","服务器CPU","处理器芯片","主板","内存条","机架服务器",
"国产处理器","信创","整机","刀片服务器","存储服务器","云主机","虚拟机",
"通用计算","传统服务器","x86服务器","服务器整机","白牌服务器",
]
# Industry related words
REL_SUB =["替代","取代","挤出","转向","迁移","腾挪","让位","被替换",
"预算转移","份额下滑","结构性转移","此消彼长","分流"]
REL_COMP =["配套","互补","协同","搭配","配比","组合部署","相辅",
"同步升级","带动","拉动","配套需求"]
REL_COEXP =["共同增长","双双增长","齐增","全面扩张","整体扩容","同步扩产",
"共振","全线增长","同步增长"]
REL_CONSTR =["缺货","紧缺","供不应求","产能受限","交付延期","断供","禁运",
"出口管制","实体清单","限制出口","涨价","价格上涨","排产紧张",
"电力不足","能耗指标","并网受限","供应紧张"]
# Event word (order/policy/constraint)
EVENT_WORDS =["订单","中标","采购","招标","签约","交付","出货","量产",
"投产","扩产","资本开支","投资建设","开工","落地","政策",
"规划","试点","标准","白皮书","东数西算","补贴","专项"]
# intonation words
POS_WORDS =["增长","上升","提升","创新高","超预期","大涨","放量","旺盛",
"强劲","突破","领先","扩张","利好","受益","改善","回暖",
"翻倍","激增","爆发","满产","供不应求","加速","新高","中标",
"获批","达成","签署","扩容","提速","创纪录"]
NEG_WORDS =["下滑","下降","减少","低于预期","不及预期","亏损","萎缩",
"疲软","承压","放缓","利空","受限","受挫","取消","推迟",
"延期","下调","裁员","停产","退出","风险","禁令","制裁",
"限制","衰退","过剩","降价","减记","停摆"]
# Intensity words (scale magnitude)
INTENSITY_UNIT =re .compile (
r"(\d+(?:\.\d+)?)\s*(亿元|亿美元|万元|万美元|亿|万台|万块|万卡|万张|"
r"千卡|万套|GW|MW|EB|PB|P|万平方米|万吨)")
INTENSITY_WORDS =["大规模","巨额","创纪录","史上最大","首个","全球最大",
"全国最大","重大","百亿","千亿","万亿"]
# Topic (Topic task, category 6)
TOPIC_DEF ={
# Topic names should be in English for direct reference in figures and text tables (journal formatting requirements)
0 :("Orders & Shipments",["订单","中标","采购","招标","出货","交付",
"签约","供货"]),
1 :("Capacity & Capex",["扩产","投产","量产","产能","资本开支","投资建设",
"开工","产线","工厂","扩容"]),
2 :("Policy & Regulation",["政策","规划","试点","标准","白皮书","东数西算",
"出口管制","实体清单","禁令","制裁","补贴","监管"]),
3 :("Product & Technology",["发布","新品","架构","制程","流片","良率","封装",
"性能","参数","升级","迭代","技术突破"]),
4 :("Supply & Pricing",["缺货","紧缺","涨价","降价","库存","排产","价格",
"供应","交期","产能利用率"]),
5 :("Earnings & Market",["营收","净利","业绩","财报","毛利","市场份额",
"出货量","市占率","指引","预告"]),
}

ALL_GROUPS ={
"GPU":GPU_WORDS ,"CPU":CPU_WORDS ,
"SUB":REL_SUB ,"COMP":REL_COMP ,"COEXP":REL_COEXP ,"CONSTR":REL_CONSTR ,
"EVENT":EVENT_WORDS ,"POS":POS_WORDS ,"NEG":NEG_WORDS ,
"INTW":INTENSITY_WORDS ,
}
for i ,(nm ,ws )in TOPIC_DEF .items ():
    ALL_GROUPS [f"TOPIC{i }"]=ws 

    # Word -> set of groups it belongs to
WORD2GRP =defaultdict (set )
for g ,ws in ALL_GROUPS .items ():
    for w in ws :
        WORD2GRP [w ].add (g )
VOCAB =set (WORD2GRP )

for w in VOCAB :# Ensure domain words are not shredded
    jieba .add_word (w ,freq =100000 )
jieba .initialize ()

NEG_PREFIX =re .compile (r"(不|未|无|没有|难以|尚未|停止|取消)$")


def count_hits (text :str ):
    """Return {word: count} (dictionary words only) and the total token count, with simple negation flipping."""
    toks =[t for t in jieba .lcut (text )if t .strip ()]
    hits =Counter ()
    n =len (toks )
    for i ,t in enumerate (toks ):
        if t in VOCAB :
            prev =toks [i -1 ]if i >0 else ""
            if (t in POS_WORDS or t in NEG_WORDS )and NEG_PREFIX .search (prev ):
                flip ="NEGFLIP::"+t # negative flip tag
                hits [flip ]+=1 
            else :
                hits [t ]+=1 
    return hits ,n 


def intensity_of (text :str )->float :
    """Scale intensity: magnitude + intensity word. Returns a real number >=0."""
    v =0.0 
    for num ,unit in INTENSITY_UNIT .findall (text [:2000 ]):
        try :
            x =float (num )
        except ValueError :
            continue 
        scale ={"亿元":1e8 ,"亿美元":7e8 ,"万元":1e4 ,"万美元":7e4 ,"亿":1e8 ,
        "万台":1e4 ,"万块":1e4 ,"万卡":1e4 ,"万张":1e4 ,"千卡":1e3 ,
        "万套":1e4 ,"GW":1e6 ,"MW":1e3 ,"EB":1e6 ,"PB":1e3 ,"P":1e2 ,
        "万平方米":1e4 ,"万吨":1e4 }.get (unit ,1.0 )
        v =max (v ,x *scale )
    lvl =math .log10 (v +1.0 )if v >0 else 0.0 
    lvl +=0.5 *sum (text [:2000 ].count (w )>0 for w in INTENSITY_WORDS )
    return round (lvl ,4 )


    # ============================================================ 2. Main process
def main ():
    t0 =time .time ()

    # ---------- pass 1: word segmentation + hit cache + DF statistics
    # pass1 is the most time-consuming part of the whole process (about 870s). If the hit cache already exists, it will be reused directly.
    # It is convenient to quickly rerun after adjusting only the scoring/weak tag rules of pass2.
    df =Counter ()
    N =0 
    hits_path =D02_LEX /"news_hits.jsonl"
    idf_path =D02_LEX /"idf_lexicon.json"
    resume =hits_path .exists ()and idf_path .exists ()and "--force"not in sys .argv 

    if resume :
        with open (idf_path ,encoding ="utf-8")as f :
            cache =json .load (f )
        N ,df ,idf =cache ["N_docs"],Counter (cache ["df"]),cache ["idf"]
        print (f"[i] pass1 reuse cache {N :,} (if you need to recalculate, add --force)")
    else :
        with open (D01_TEXT /"news_text.jsonl",encoding ="utf-8")as fi ,open (hits_path ,"w",encoding ="utf-8")as fo :
            for line in fi :
                d =json .loads (line )
                text =(d ["title"]+"。"+d ["body"])[:1600 ]
                hits ,ntok =count_hits (text )
                inten =intensity_of (text )
                N +=1 
                for w in hits :
                    df [w ]+=1 
                fo .write (json .dumps ({"nid":d ["nid"],"h":dict (hits ),
                "nt":ntok ,"it":inten },
                ensure_ascii =False )+"\n")
                if N %20000 ==0 :
                    print (f"    tokenized {N :,}  ({time .time ()-t0 :.0f}s)")
        print (f"[i] pass1 completed {N :,} Article {time .time ()-t0 :.0f}s")

        idf ={w :round (math .log ((1 +N )/(1 +c ))+1.0 ,6 )
        for w ,c in df .items ()}
        with open (idf_path ,"w",encoding ="utf-8")as f :
            json .dump ({"N_docs":N ,"df":dict (df ),"idf":idf },f ,
            ensure_ascii =False ,indent =1 )

            # ---------- pass 2: Article-level scores and weak tags
    def grp_weight (hits ,group ):
        """TF-IDF weighted sum of the words in the group (negative flipped terms are counted in the opposite group and are handled by the caller)"""
        s =0.0 
        for w ,c in hits .items ():
            base =w .replace ("NEGFLIP::","")
            if group in WORD2GRP .get (base ,())and not w .startswith ("NEGFLIP::"):
                s +=c *idf .get (w ,1.0 )
        return s 

    out =open (D02_LEX /"news_scores.csv","w",encoding ="utf-8",newline ="")
    w_csv =csv .writer (out )
    w_csv .writerow (["nid","W_G","W_C","orientation","tone","intensity",
    "rel","y_rel","y_object","y_tone","y_relation",
    "y_topic","gcs_lex","conf"])

    stat =Counter ()
    eps =1e-4 
    with open (hits_path ,encoding ="utf-8")as f :
        for line in f :
            r =json .loads (line )
            hits =r ["h"]
            nid ,ntok ,inten =r ["nid"],max (r ["nt"],1 ),r ["it"]

            WG =grp_weight (hits ,"GPU")
            WC =grp_weight (hits ,"CPU")
            orientation =(WG -WC )/(WG +WC +eps )

            # Intonation (including negative inversion)
            pos =grp_weight (hits ,"POS")
            neg =grp_weight (hits ,"NEG")
            for w ,c in hits .items ():
                if w .startswith ("NEGFLIP::"):
                    base =w [9 :]
                    if base in POS_WORDS :
                        neg +=c *idf .get (w ,1.0 )
                    elif base in NEG_WORDS :
                        pos +=c *idf .get (w ,1.0 )
            tone =(pos -neg )/(pos +neg +eps )

            # Relevance Rel: domain word density
            dom =WG +WC 
            rel =min (1.0 ,dom /(0.02 *ntok +3.0 ))

            # Four categories of relationships
            rmap ={"SUB":grp_weight (hits ,"SUB"),
            "COMP":grp_weight (hits ,"COMP"),
            "COEXP":grp_weight (hits ,"COEXP"),
            "CONSTR":grp_weight (hits ,"CONSTR")}
            rbest =max (rmap ,key =rmap .get )
            # Documents without any relationship clues are marked -1 (unmarked) in S03 multitasking fine-tuning
            # Masked by the loss function to avoid forcing 86% of the unevidenced samples into the "complementary" class.
            y_relation ={"SUB":0 ,"COMP":1 ,"COEXP":2 ,"CONSTR":3 }[rbest ]if rmap [rbest ]>0 else -1 
            # Six categories of topics; similarly, hits without topic words are recorded as unmarked
            tmap ={i :grp_weight (hits ,f"TOPIC{i }")for i in TOPIC_DEF }
            y_topic =max (tmap ,key =tmap .get )if max (tmap .values ())>0 else -1 

            # Object three categories: 0=GPU 1=CPU 2=Bidirectional/Neutral
            if orientation >0.30 :
                y_object =0 
            elif orientation <-0.30 :
                y_object =1 
            else :
                y_object =2 
                # Three categories of intonation: 0=positive 1=negative 2=medium
            if tone >0.20 :
                y_tone =0 
            elif tone <-0.20 :
                y_tone =1 
            else :
                y_tone =2 
            y_rel =1 if rel >=0.35 else 0 

            gcs_lex =rel *math .log1p (max (inten ,0 ))*orientation *tone 

            # Weak label confidence: the higher the hit intensity and the clearer the direction, the more credible it is
            conf =min (1.0 ,(abs (orientation )+abs (tone ))/2 *min (1.0 ,dom /8.0 )
            +0.15 *(rel >0.5 ))
            stat [f"obj{y_object }"]+=1 
            stat [f"tone{y_tone }"]+=1 
            stat [f"rel{y_rel }"]+=1 
            stat ["rlt_unlabeled"if y_relation <0 else f"rlt{y_relation }"]+=1 
            stat ["top_unlabeled"if y_topic <0 else f"top{y_topic }"]+=1 

            w_csv .writerow ([nid ,f"{WG :.4f}",f"{WC :.4f}",f"{orientation :.4f}",
            f"{tone :.4f}",f"{inten :.4f}",f"{rel :.4f}",
            y_rel ,y_object ,y_tone ,y_relation ,y_topic ,
            f"{gcs_lex :.6f}",f"{conf :.4f}"])
    out .close ()

    report ={
    "n_docs":N ,
    "n_lexicon_words":len (VOCAB ),
    "lexicon_group_size":{g :len (ws )for g ,ws in ALL_GROUPS .items ()},
    "label_distribution":dict (stat ),
    "topic_names":{i :nm for i ,(nm ,_ )in TOPIC_DEF .items ()},
    "elapsed_sec":round (time .time ()-t0 ,1 ),
    }
    with open (D02_LEX /"s02_report.json","w",encoding ="utf-8")as f :
        json .dump (report ,f ,ensure_ascii =False ,indent =2 )
    with open (D02_LEX /"domain_lexicon.json","w",encoding ="utf-8")as f :
        json .dump ({g :ws for g ,ws in ALL_GROUPS .items ()},f ,
        ensure_ascii =False ,indent =1 )

    print ("\n===== S02 汇总 =====")
    print (f"Number of documents {N :,} Dictionary words {len (VOCAB )}")
    for k ,v in sorted (stat .items ()):
        print (f"  {k :8s} {v :,}")
    print (f"Time consumption{time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
