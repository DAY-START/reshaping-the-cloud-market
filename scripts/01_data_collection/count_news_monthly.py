# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Recursively count the monthly news quantity of each data set in news/data and the merged and deduplicated data."""

import csv 
import hashlib 
import json 
import re 
from collections import Counter 
from datetime import datetime 
from pathlib import Path 

BASE_DIR =Path (__file__ ).resolve ().parent 
INPUT_FILES =[
Path (r"D:\study\date\ai_computing_news\workbuddyai_compute_news_2023_2026.jsonl"),
Path (r"D:\study\date\ai_computing_news\yuanbaoai_computing_power_news.jsonl"),
Path (r"D:\study\date\ai_computing_news\gptverified_seed_zh.jsonl"),
Path (r"D:\study\date\ai_computing_news\crawler_output\AI_Computing_News_Crawler_20230401_20260630.jsonl"),
Path (r"D:\study\date\ai_computing_news\ai_computing_web_collector\historical_ai_news_output\AI_Computing_Historical_Web_News_20210701_20260630.jsonl"),
Path (r"D:\study\date\ai_computing_news\ai_computing_web_collector\web_ai_news_output\AI_Computing_Web_News_20210701_20260630.jsonl"),
Path (r"D:\study\date\ai_computing_news\ths_api_download\AI_Computing_News_THS_Fulltext_Deduplicated.jsonl"),
Path (r"D:\study\date\ai_computing_news\ths_api_download\daily_2026-07-30.jsonl"),
Path (r"D:\date新闻数据集\AI_Computing_News_THS_20210701_20260630.jsonl"),
Path (r"D:\study\test2\ai_computing_news_202107_202607.jsonl"),
Path (r"D:\软件\python\项目\news_work\final_output\compute_news_final.jsonl"),
Path (r"D:\ai_compute_zh_collector\verified_seed_zh.jsonl"),
Path (r"D:\study\date\ai_computing_news\kimiAI算力新闻数据集_2023-2026.json"),
Path (r"D:\study\date\ai_computing_news\doubao算力财经新闻数据集（2026年6-7月，3033条）.jsonl"),
Path (r"D:\study\date\ai_computing_news\AI_Computing_News_Raw_after_20210701.jsonl"),
]
REPORT_DIR =BASE_DIR /"reports"
START_MONTH ="2021-07"
END_MONTH ="2026-07"# The statistical list also contains daily files from 2026-07-30

DATE_FIELDS =("date","publish_date","publishDate","pub_date","pub_time","publish_time","time","datetime")
TITLE_FIELDS =("title","news_title","name")
CONTENT_FIELDS =("content","raw_text","text","body","article")
URL_FIELDS =("url","news_url","link","source_url")
ID_FIELDS =("id","uuid","news_id")


def months_between (start ,end ):
    current =datetime .strptime (start ,"%Y-%m")
    finish =datetime .strptime (end ,"%Y-%m")
    result =[]
    while current <=finish :
        result .append (current .strftime ("%Y-%m"))
        current =datetime (current .year +(current .month ==12 ),current .month %12 +1 ,1 )
    return result 


MONTHS =months_between (START_MONTH ,END_MONTH )


def normalize_month (value ):
    if value is None :
        return None 
    if isinstance (value ,(int ,float )):
        try :
            timestamp =float (value )
            if timestamp >10_000_000_000 :
                timestamp /=1000 
            return datetime .fromtimestamp (timestamp ).strftime ("%Y-%m")
        except (ValueError ,OSError ,OverflowError ):
            return None 
    text =str (value ).strip ()
    match =re .search (r"(20\d{2})[-/.年](\d{1,2})",text )
    if not match :
        match =re .search (r"\b(20\d{2})(\d{2})\d{0,2}\b",text )
    if not match :
        return None 
    year ,month =int (match .group (1 )),int (match .group (2 ))
    if 1 <=month <=12 :
        return f"{year :04d}-{month :02d}"
    return None 


def first_value (item ,fields ):
    for field in fields :
        value =item .get (field )
        if value not in (None ,""):
            return value 
    return ""


def dedup_key (item ):
    item_id =str (first_value (item ,ID_FIELDS )).strip ()
    if item_id :
        return "id:"+item_id 
    url =str (first_value (item ,URL_FIELDS )).strip ().lower ()
    if url :
        return "url:"+url 
    title =re .sub (r"\s+","",str (first_value (item ,TITLE_FIELDS ))).lower ()
    content =re .sub (r"\s+","",str (first_value (item ,CONTENT_FIELDS ))).lower ()
    basis =title +"\n"+content 
    return "text:"+hashlib .sha1 (basis .encode ("utf-8",errors ="ignore")).hexdigest ()


def iter_records (path ):
    if path .suffix .lower ()==".jsonl":
        with path .open ("r",encoding ="utf-8-sig",errors ="replace")as handle :
            for line_no ,line in enumerate (handle ,1 ):
                if not line .strip ():
                    continue 
                try :
                    value =json .loads (line )
                    if isinstance (value ,dict ):
                        yield value 
                except json .JSONDecodeError :
                    yield {"__parse_error__":line_no }
    else :
        try :
            with path .open ("r",encoding ="utf-8-sig",errors ="replace")as handle :
                value =json .load (handle )
            records =value if isinstance (value ,list )else value .get ("data",value .get ("items",[]))if isinstance (value ,dict )else []
            for item in records :
                if isinstance (item ,dict ):
                    yield item 
        except (json .JSONDecodeError ,OSError ):
            yield {"__parse_error__":1 }


def main ():
    REPORT_DIR .mkdir (parents =True ,exist_ok =True )
    files =[path for path in INPUT_FILES if path .is_file ()]
    missing_files =[path for path in INPUT_FILES if not path .is_file ()]
    if not files :
        raise SystemExit ("None of the files in the input list exist.")

    if missing_files :
        print ("The following files do not exist and will be skipped:")
        for path in missing_files :
            print (f"  {path }")
        print ()

    per_file ={}
    combined =Counter ()
    seen =set ()
    summary =[]

    for path in files :
        counts =Counter ()
        total =valid_date =parse_errors =duplicates =0 
        display_name =str (path )
        print (f"Counting: {display_name }")
        for item in iter_records (path ):
            total +=1 
            if "__parse_error__"in item :
                parse_errors +=1 
                continue 
            month =normalize_month (first_value (item ,DATE_FIELDS ))
            if not month :
                continue 
            valid_date +=1 
            counts [month ]+=1 
            if START_MONTH <=month <=END_MONTH :
                key =dedup_key (item )
                if key in seen :
                    duplicates +=1 
                else :
                    seen .add (key )
                    combined [month ]+=1 
        per_file [display_name ]=counts 
        summary .append ((display_name ,total ,valid_date ,parse_errors ,duplicates ))

    monthly_path =REPORT_DIR /"news_monthly_counts_by_file.csv"
    with monthly_path .open ("w",newline ="",encoding ="utf-8-sig")as handle :
        writer =csv .writer (handle )
        writer .writerow (["month","within_research_period_20210701_20260630",*per_file .keys (),"combined_deduplicated"])
        for month in MONTHS :
            writer .writerow ([month ,"yes"if month <="2026-06"else "no",*(per_file [name ][month ]for name in per_file ),combined [month ]])

    summary_path =REPORT_DIR /"news_monthly_statistics_summary.csv"
    with summary_path .open ("w",newline ="",encoding ="utf-8-sig")as handle :
        writer =csv .writer (handle )
        writer .writerow (["file","records","valid_date","parse_errors","duplicates_in_combined_merge"])
        writer .writerows (summary )
        writer .writerow (["COMBINED_DEDUPLICATED_202107_202607",sum (combined .values ()),sum (combined .values ()),0 ,""])

    missing_path =REPORT_DIR /"news_missing_input_files.txt"
    with missing_path .open ("w",encoding ="utf-8-sig")as handle :
        if missing_files :
            handle .write ("\n".join (str (path )for path in missing_files ))
        else :
            handle .write ("全部指定文件均已找到。\n")

    print ("\n月份\t合并去重后数量")
    for month in MONTHS :
        print (f"{month }\t{combined [month ]}")
    print (f"\nComplete:{monthly_path }")
    print (f"Summary: {summary_path }")


if __name__ =="__main__":
    main ()
