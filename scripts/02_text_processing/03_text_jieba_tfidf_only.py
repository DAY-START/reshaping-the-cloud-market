# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import json 
import re 
import jieba 
from sklearn .feature_extraction .text import TfidfVectorizer 

# ======================== Path configuration [Strictly follow your document definition] ========================
INPUT_JSONL =r"D:\study\test1\dict_updated_corpus.jsonl"
DOMAIN_DICT_TXT =r"D:\study\test1\domain_dict_full.txt"
STOPWORD_TXT =r"D:\study\test1\hit_stopwords.txt"

OUT_SEGMENT_JSONL =r"D:\study\test1\segment_tfidf_corpus.jsonl"
OUT_VOCAB_IDF_JSON =r"D:\study\test1\tfidf_vocab_weight.json"

# ======================== 1. Load the domain dictionary (adapted to your txt title, comma separated format) ========================
def load_domain_dict (filepath ):
    word_bank ={
    "gpu":set (),
    "cpu":set (),
    "compete":set (),
    "sentiment":set ()
    }
    current_type =None 
    with open (filepath ,"r",encoding ="utf-8")as f :
        for line in f :
            line =line .strip ()
            if not line :
                continue 
            if "[1 GPU track vocabulary]"in line :
                current_type ="gpu"
                continue 
            elif "[2 Traditional CPU track vocabulary]"in line :
                current_type ="cpu"
                continue 
            elif "[3 Alternative competitive relationship vocabulary]"in line :
                current_type ="compete"
                continue 
            elif "[4 Industry Supply and Demand Emotional Vocabulary]"in line :
                current_type ="sentiment"
                continue 
            if line .startswith ("=====")or "new words"in line :
                continue 
            if current_type is not None :
                word_list =[w .strip ()for w in line .split ("、")if w .strip ()]
                for w in word_list :
                    word_bank [current_type ].add (w )
    return word_bank 

    # ======================== 2. Load stop words ========================
def load_stopwords (filepath ):
    stop_set =set ()
    with open (filepath ,"r",encoding ="utf-8")as f :
        for line in f :
            w =line .strip ()
            if w :
                stop_set .add (w )
    return stop_set 

    # ======================== 3. Regular precompilation ========================
def build_pattern (word_set ):
    word_list =[re .escape (w )for w in word_set ]
    return re .compile ("|".join (word_list ),re .IGNORECASE )


def main ():
    print ("【1/5】加载领域词典 domain_dict_full.txt ...")
    domain_words =load_domain_dict (DOMAIN_DICT_TXT )
    gpu_words =domain_words ["gpu"]
    cpu_words =domain_words ["cpu"]
    compete_words =domain_words ["compete"]
    sentiment_words =domain_words ["sentiment"]
    print (f"GPU vocabulary: {len (gpu_words )} | CPU vocabulary: {len (cpu_words )} | Competitive substitution: {len (compete_words )} | Emotional words: {len (sentiment_words )}")

    print ("【2/5】加载停用词 hit_stopwords.txt ...")
    stop_words =load_stopwords (STOPWORD_TXT )

    pat_gpu =build_pattern (gpu_words )
    pat_cpu =build_pattern (cpu_words )
    pat_compete =build_pattern (compete_words )
    pat_sentiment =build_pattern (sentiment_words )

    all_seg_texts =[]
    news_buffer =[]
    count =0 

    print ("【3/5】读取清洗后语料 dict_updated_corpus.jsonl 并分词...")
    with open (INPUT_JSONL ,"r",encoding ="utf-8-sig")as f_in :
        for line in f_in :
            line =line .strip ()
            if not line :
                continue 
                # ==========Fix core bug: use json.loads, abandon pd.read_json single-line parsing==========
            item =json .loads (line )
            stock_code =str (item ["id"])
            date =str (item ["date"])
            title =str (item ["title"])
            content =str (item ["content"])
            raw_text =title +" "+content 

            # jieba word segmentation + stop word filtering
            seg_raw =jieba .lcut (raw_text )
            seg_list =[w for w in seg_raw if w not in stop_words and len (w .strip ())>=1 ]
            seg_str =" ".join (seg_list )
            all_seg_texts .append (seg_str )

            # Four types of vocabulary matching
            hit_gpu =pat_gpu .findall (raw_text )
            hit_cpu =pat_cpu .findall (raw_text )
            hit_compete =pat_compete .findall (raw_text )
            hit_sentiment =pat_sentiment .findall (raw_text )

            temp_record ={
            "stock_code":stock_code ,
            "date":date ,
            "raw_text":raw_text ,
            "seg_word_list":seg_list ,
            "gpu_word_count":len (hit_gpu ),
            "cpu_word_count":len (hit_cpu ),
            "gpu_words_list":hit_gpu ,
            "cpu_words_list":hit_cpu ,
            "compete_word_count":len (hit_compete ),
            "compete_words_list":hit_compete ,
            "sentiment_word_count":len (hit_sentiment ),
            "sentiment_words_list":hit_sentiment ,
            "replace_word_count":0 ,
            "text_tfidf_weight":{}
            }
            news_buffer .append (temp_record )
            count +=1 
            if count %5000 ==0 :
                print (f"Cached news read: {count }")

    print (f"\nAll news reading is completed, a total of {count } items, [4/5] Training TF-IDF model...")
    tfidf_vec =TfidfVectorizer ()
    tfidf_matrix =tfidf_vec .fit_transform (all_seg_texts )
    vocab_array =tfidf_vec .get_feature_names_out ()

    # Output: global IDF weights
    vocab_idf_dict ={}
    for word ,idf_val in zip (vocab_array ,tfidf_vec .idf_ ):
        vocab_idf_dict [word ]=float (idf_val )
    with open (OUT_VOCAB_IDF_JSON ,"w",encoding ="utf-8")as f :
        json .dump (vocab_idf_dict ,f ,ensure_ascii =False ,indent =2 )
    print (f"✅ Global IDF vocabulary saved: {OUT_VOCAB_IDF_JSON }")

    # Optimize sparse matrix reading without converting toarray() to prevent stuck
    out_f =open (OUT_SEGMENT_JSONL ,"w",encoding ="utf-8")
    for idx ,record in enumerate (news_buffer ):
        tfidf_dict ={}
        row_sp =tfidf_matrix [idx ]
        non_zero_idx =row_sp .indices 
        non_zero_wgt =row_sp .data 
        for wid ,wgt in zip (non_zero_idx ,non_zero_wgt ):
            tfidf_dict [vocab_array [wid ]]=float (wgt )
        record ["text_tfidf_weight"]=tfidf_dict 

        json .dump (record ,out_f ,ensure_ascii =False )
        out_f .write ("\n")
        if (idx +1 )%5000 ==0 :
            print (f"✅ Features written: {idx +1 }/{count }")
    out_f .close ()

    print (f"\n✅ All tasks completed!")
    print (f"Feature file: {OUT_SEGMENT_JSONL }")
    print (f"Global IDF file: {OUT_VOCAB_IDF_JSON }")

if __name__ =="__main__":
    main ()
