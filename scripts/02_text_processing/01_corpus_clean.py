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

# Original data set path
INPUT_PATH =r"D:\study\test1\news_dataset_2018_to_2023.jsonl"
# Standard corpus output after cleaning
OUTPUT_CLEAN =r"D:\study\test1\clean_corpus_2018_2023.jsonl"

# Filtering rules: stock quotation blacklist (avoiding reverse causality)
stock_black ={"股价","涨停","跌停","市值","基金","大盘","沪指","估值","涨幅","龙虎榜"}
stock_pattern =re .compile ("|".join (stock_black ))
# HTML tag cleaning
html_pattern =re .compile (r"<.*?>")

valid_count =0 
error_count =0 

with open (INPUT_PATH ,"r",encoding ="utf-8")as fr ,open (OUTPUT_CLEAN ,"w",encoding ="utf-8")as fw :
    for line in fr :
        line =line .strip ()
        if not line :
            continue 
        try :
            data =json .loads (line )
            title =str (data ["title"])
            content =str (data ["content"])
            full_text =title +content 
            # Filter 1: Text containing stock market quotes is discarded directly.
            if stock_pattern .search (full_text ):
                continue 
                # Filter 2: Remove HTML tags
            clean_content =html_pattern .sub ("",content )
            clean_title =html_pattern .sub ("",title )
            # Filter 3: Eliminate if the total number of words is less than 200
            total_len =len (clean_title +clean_content )
            if total_len <200 :
                continue 
                # Rewrite standardized text
            new_item ={
            "id":data ["id"],
            "date":data ["date"],
            "title":clean_title ,
            "content":clean_content ,
            "raw_text":clean_title +" "+clean_content 
            }
            fw .write (json .dumps (new_item ,ensure_ascii =False )+"\n")
            valid_count +=1 
        except Exception as e :
            error_count +=1 

print (f"Cleaning completed, valid news: {valid_count }, parsing failed rows: {error_count }")
print (f"The path to save the corpus after cleaning: {OUTPUT_CLEAN }")