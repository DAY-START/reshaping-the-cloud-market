# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import json 
import jieba 
from sklearn .feature_extraction .text import TfidfVectorizer 
from transformers import BertTokenizer ,BertModel ,BertForSequenceClassification 
import torch 

# ====================== Global path configuration (matches the file name you define) ======================
CORPUS_PATH =r"D:\study\test1\dict_updated_corpus.jsonl"
DICT_PATH =r"D:\study\test1\domain_dict_full.txt"
STOPWORD_PATH =r"D:\study\test1\hit_stopwords.txt"
SEG_OUT_PATH =r"D:\study\test1\segment_tfidf_corpus.jsonl"
BERT_OUT_PATH =r"D:\study\test1\finbert_sent_corpus.jsonl"
TFIDF_WEIGHT_PATH =r"D:\study\test1\tfidf_vocab_weight.json"

# ====================== Tool function 1: Load stop words ======================
def load_stopwords (file_path ):
    stop_set =set ()
    with open (file_path ,"r",encoding ="utf-8")as f :
        for line in f :
            word =line .strip ()
            if word :
                stop_set .add (word )
    return stop_set 

STOP_WORDS =load_stopwords (STOPWORD_PATH )

# ====================== Tool function 2: Load hierarchical track words for counting ======================
def load_domain_words (dict_path ):
    gpu_words =[]
    cpu_words =[]
    replace_words =[]
    sentiment_words =set ()
    with open (dict_path ,"r",encoding ="utf-8")as f :
        tag =""
        for line in f :
            line =line .strip ()
            if "[GPU track vocabulary]"in line :
                tag ="gpu"
            elif "[CPU track vocabulary]"in line :
                tag ="cpu"
            elif "【Alternative Competitive Vocabulary】"in line :
                tag ="replace"
            elif "[Industry Emotional Vocabulary]"in line :
                tag ="sentiment"
            elif line and "【"not in line :
                if tag =="gpu":
                    gpu_words .append (line )
                elif tag =="cpu":
                    cpu_words .append (line )
                elif tag =="replace":
                    replace_words .append (line )
                elif tag =="sentiment":
                    sentiment_words .add (line )
    return set (gpu_words ),set (cpu_words ),set (replace_words ),sentiment_words 

GPU_WORDS ,CPU_WORDS ,REPLACE_WORDS ,SENT_WORDS =load_domain_words (DICT_PATH )

# ====================== Branch A: Jieba word segmentation initialization ======================
jieba .load_userdict (DICT_PATH )
def seg_clean_text (raw_text ):
    seg_raw =jieba .cut (raw_text ,cut_all =False )
    seg_res =[w for w in seg_raw if len (w )>=2 and not w .isdigit ()and w not in STOP_WORDS ]
    return seg_res 

def count_track_words (seg_list ):
    gpu_cnt =sum (1 for w in seg_list if w in GPU_WORDS )
    cpu_cnt =sum (1 for w in seg_list if w in CPU_WORDS )
    rep_cnt =sum (1 for w in seg_list if w in REPLACE_WORDS )
    sent_cnt =sum (1 for w in seg_list if w in SENT_WORDS )
    return gpu_cnt ,cpu_cnt ,rep_cnt ,sent_cnt 

    # ====================== Branch B: FinBERT model initialization ======================
model_name ="uer/roberta-base-finance-chinese"
tokenizer =BertTokenizer .from_pretrained (model_name )
bert_model =BertModel .from_pretrained (model_name )
sent_model =BertForSequenceClassification .from_pretrained (model_name ,num_labels =2 )
device =torch .device ("cuda"if torch .cuda .is_available ()else "cpu")
bert_model .to (device )
sent_model .to (device )

@torch .no_grad ()
def get_finbert_feature (text ):
    inputs =tokenizer (
    text ,
    max_length =512 ,
    padding ="max_length",
    truncation =True ,
    return_tensors ="pt"
    ).to (device )
    out =bert_model (**inputs )
    cls_vec =out .last_hidden_state [:,0 ,:].squeeze (0 ).cpu ().numpy ().tolist ()
    sent_out =sent_model (**inputs )
    prob =torch .softmax (sent_out .logits ,dim =1 ).squeeze (0 ).cpu ().numpy ()
    pos_prob =float (prob [1 ])
    neg_prob =float (prob [0 ])
    return cls_vec ,pos_prob ,neg_prob 

    # ====================== Main process ======================
def main ():
    all_seg_texts =[]
    seg_temp =[]# Cache word segmentation data, and then backfill TF-IDF weights
    seg_writer =open (SEG_OUT_PATH ,"w",encoding ="utf-8")
    bert_writer =open (BERT_OUT_PATH ,"w",encoding ="utf-8")

    # The first round of traversal: word segmentation, BERT reasoning, saving basic features
    with open (CORPUS_PATH ,"r",encoding ="utf-8")as f :
        for line_idx ,line in enumerate (f ):
            line =line .strip ()
            if not line :
                continue 
            try :
                data =json .loads (line )
                raw_text =data ["raw_text"]
                news_date =data ["date"]
                code =data .get ("stock_code","")

                # word segmentation track
                seg_list =seg_clean_text (raw_text )
                g ,c ,r ,s =count_track_words (seg_list )
                seg_data ={
                "stock_code":code ,
                "date":news_date ,
                "raw_text":raw_text ,
                "seg_words":seg_list ,
                "gpu_word_count":g ,
                "cpu_word_count":c ,
                "replace_word_count":r ,
                "sentiment_word_count":s 
                }
                seg_temp .append (seg_data )
                seg_writer .write (json .dumps (seg_data ,ensure_ascii =False )+"\n")
                all_seg_texts .append (" ".join (seg_list ))

                # BERT track
                vec ,pos ,neg =get_finbert_feature (raw_text )
                bert_data ={
                "stock_code":code ,
                "date":news_date ,
                "pos_prob":pos ,
                "neg_prob":neg ,
                "sentence_vector":vec 
                }
                bert_writer .write (json .dumps (bert_data ,ensure_ascii =False )+"\n")
                if line_idx %100 ==0 :
                    print (f"{line_idx } news processed")
            except Exception as e :
                print (f"Skip exception text, error message: {str (e )}")
                continue 
    seg_writer .close ()
    bert_writer .close ()
    print ("Word segmentation and BERT basic files are generated, and global TF-IDF training begins.")

    # Training global TF-IDF
    tfidf =TfidfVectorizer ()
    tfidf_matrix =tfidf .fit_transform (all_seg_texts )
    vocab_idf =dict (zip (tfidf .get_feature_names_out (),tfidf .idf_ .tolist ()))
    # Save vocabulary global weights
    with open (TFIDF_WEIGHT_PATH ,"w",encoding ="utf-8")as f :
        json .dump (vocab_idf ,f ,ensure_ascii =False ,indent =2 )

        # Second round: Append the TF-IDF word weight of each text to overwrite the output file
    final_writer =open (SEG_OUT_PATH ,"w",encoding ="utf-8")
    for idx ,item in enumerate (seg_temp ):
        text =" ".join (item ["seg_words"])
        vec =tfidf .transform ([text ])
        word_weight ={}
        for word ,wid in tfidf .vocabulary_ .items ():
            w =vec [0 ,wid ]
            if w >1e-6 :
                word_weight [word ]=float (w )
        item ["tfidf_word_weight"]=word_weight 
        final_writer .write (json .dumps (item ,ensure_ascii =False )+"\n")
    final_writer .close ()

    print (f"✅ Total vocabulary of TF-IDF: {len (tfidf .vocabulary_ )}")
    print ("🎉 The second stage of dual-track text representation is completed and the output file is:")
    print (f"1. {SEG_OUT_PATH } Word segmentation, track counting, single text TF-IDF weight")
    print (f"2. {BERT_OUT_PATH } FinBERT sentiment score + 768-dimensional semantic vector")
    print (f"3. {TFIDF_WEIGHT_PATH } Global vocabulary IDF weight, used for the third stage of fusion")

if __name__ =="__main__":
    main ()