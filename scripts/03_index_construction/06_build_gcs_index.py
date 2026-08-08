# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import json 
import pandas as pd 
import numpy as np 

INPUT_PATH =r"D:\study\test1\segment_tfidf_corpus.jsonl"
OUTPUT_PATH =r"D:\study\test1\daily_gcs_index.csv"

def calc_gcs_index ():
    data_list =[]
    with open (INPUT_PATH ,"r",encoding ="utf-8")as f :
        for line in f :
            line =line .strip ()
            if not line :
                continue 
            item =json .loads (line )
            date =item ["date"]
            gpu_cnt =item ["gpu_word_count"]
            cpu_cnt =item ["cpu_word_count"]
            gpu_word_list =item ["gpu_words_list"]
            cpu_word_list =item ["cpu_words_list"]
            # Adapt your 03 real field text_tfidf_weight
            tfidf_dict =item ["text_tfidf_weight"]

            # 1 word frequency GCS
            total_cnt =gpu_cnt +cpu_cnt 
            base_gcs =np .nan 
            if total_cnt >0 :
                base_gcs =(gpu_cnt -cpu_cnt )/total_cnt 

                # 2 All uppercase and lowercase letters match TFIDF
            sum_gpu_tf =0.0 
            sum_cpu_tf =0.0 
            tf_lower ={k .lower ():v for k ,v in tfidf_dict .items ()}
            for w in gpu_word_list :
                sum_gpu_tf +=tf_lower .get (w .lower (),0.0 )
            for w in cpu_word_list :
                sum_cpu_tf +=tf_lower .get (w .lower (),0.0 )

            total_tf =sum_gpu_tf +sum_cpu_tf 
            tf_gcs =np .nan 
            if total_tf >0 :
                tf_gcs =(sum_gpu_tf -sum_cpu_tf )/total_tf 

            data_list .append ({
            "date":date ,
            "gpu_cnt":gpu_cnt ,
            "cpu_cnt":cpu_cnt ,
            "gcs_base":base_gcs ,
            "gcs_tfidf_weighted":tf_gcs 
            })

    df =pd .DataFrame (data_list )
    df ["date"]=pd .to_datetime (df ["date"])
    df =df .sort_values ("date").reset_index (drop =True )
    df .to_csv (OUTPUT_PATH ,index =False ,encoding ="utf-8-sig")

    print (f"Total number of news items: {len (df )}")
    print (f"gcs_base is valid and not empty: {df ['gcs_base'].count ()}")
    print (f"gcs_tfidf_weighted is valid and not empty: {df ['gcs_tfidf_weighted'].count ()}")

if __name__ =="__main__":
    calc_gcs_index ()