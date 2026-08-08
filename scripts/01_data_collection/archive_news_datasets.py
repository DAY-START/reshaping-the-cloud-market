# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Organize the AI ​​computing power news under D:/study/date, and generate a complete library, a library to be completed, and a data list."""

from __future__ import annotations 

import csv 
import hashlib 
import json 
import re 
from collections import Counter 
from datetime import datetime 
from pathlib import Path 
from urllib .parse import urlparse 


ROOT =Path (r"D:\study\date")
SRC =ROOT /"ai_computing_news"
OUT =ROOT /"news"
DATA_DIR =OUT /"data"
REPORT_DIR =OUT /"reports"

COMPLETE_FILE =DATA_DIR /"AI_Computing_News_Complete.jsonl"
INCOMPLETE_FILE =DATA_DIR /"AI_Computing_News_Needs_Completion.jsonl"
CATALOG_FILE =REPORT_DIR /"dataset_catalog.csv"
MISSING_FILE =REPORT_DIR /"missing_fields_summary.csv"
MONTH_FILE =REPORT_DIR /"complete_monthly_counts.csv"
README_FILE =OUT /"README.txt"

START ="2021-07-01"
END ="2026-06-30"

# Processed in order of quality from high to low; high-quality versions are archived first, and subsequent duplicate records are automatically skipped.
DATASETS =[
("workbuddy",SRC /"workbuddyai_compute_news_2023_2026.jsonl","jsonl"),
("yuanbao",SRC /"yuanbaoai_computing_power_news.jsonl","jsonl"),
("gpt_verified",SRC /"gptverified_seed_zh.jsonl","jsonl"),
(
"crawler",
SRC /"crawler_output"/"AI_Computing_News_Crawler_20230401_20260630.jsonl",
"jsonl",
),
(
"historical_web",
SRC /"ai_computing_web_collector"/"historical_ai_news_output"
/"AI_Computing_Historical_Web_News_20210701_20260630.jsonl",
"jsonl",
),
(
"web_collector",
SRC /"ai_computing_web_collector"/"web_ai_news_output"
/"AI_Computing_Web_News_20210701_20260630.jsonl",
"jsonl",
),
(
"ths_fulltext_deduplicated",
SRC /"ths_api_download"/"AI_Computing_News_THS_Fulltext_Deduplicated.jsonl",
"jsonl",
),
("ths_daily_2026_07_30",SRC /"ths_api_download"/"daily_2026-07-30.jsonl","jsonl"),
(
"ths_other_archive",
Path (r"D:\date新闻数据集\AI_Computing_News_THS_20210701_20260630.jsonl"),
"jsonl",
),
(
"test2_ai_computing_news",
Path (r"D:\study\test2\ai_computing_news_202107_202607.jsonl"),
"jsonl",
),
(
"legacy_filtered_compute_news",
Path (r"D:\软件\python\项目\news_work\final_output\compute_news_final.jsonl"),
"jsonl",
),
(
"external_verified_seed",
Path (r"D:\ai_compute_zh_collector\verified_seed_zh.jsonl"),
"jsonl",
),
("kimi",SRC /"kimiAI算力新闻数据集_2023-2026.json","json"),
("doubao",SRC /"doubao算力财经新闻数据集（2026年6-7月，3033条）.jsonl","jsonl"),
("datelab_raw",SRC /"AI_Computing_News_Raw_after_20210701.jsonl","jsonl"),
]

DATE_FIELDS =("date","news_date","publish_date","published_at","publish_time","time")
TITLE_FIELDS =("title","headline","news_title","article_title")
SOURCE_FIELDS =(
"source","publish_source","host_source","media","site",
"publisher","website",
)
URL_FIELDS =("url","link","news_url","article_url","source_url")
CONTENT_FIELDS =("content","raw_text","text","summary","description")


def clean (value )->str :
    if value is None :
        return ""
    text =str (value ).replace ("\u3000"," ").replace ("\xa0"," ")
    return re .sub (r"\s+"," ",text ).strip ()


def first (record :dict ,names :tuple [str ,...]):
    for name in names :
        value =record .get (name )
        if value is not None and clean (value ):
            return value 
    return ""


def normalize_date (value )->str :
    if value is None or value =="":
        return ""
    if isinstance (value ,(int ,float )):
        number =float (value )
        if number >10_000_000_000 :
            number /=1000 
        try :
            return datetime .fromtimestamp (number ).strftime ("%Y-%m-%d")
        except (ValueError ,OSError ,OverflowError ):
            return ""
    text =clean (value )
    match =re .search (r"(20\d{2})[年/\-.](\d{1,2})[月/\-.](\d{1,2})",text )
    if match :
        try :
            return datetime (
            int (match .group (1 )),int (match .group (2 )),int (match .group (3 ))
            ).strftime ("%Y-%m-%d")
        except ValueError :
            return ""
    if re .fullmatch (r"20\d{6}",text ):
        try :
            return datetime .strptime (text ,"%Y%m%d").strftime ("%Y-%m-%d")
        except ValueError :
            return ""
    return ""


def normalize_url (value )->str :
    url =clean (value )
    if url .startswith ("//"):
        url ="https:"+url 
    if not re .match (r"^https?://",url ,re .I ):
        return ""
    return url 


def source_from_url (url :str )->str :
    if not url :
        return ""
    host =urlparse (url ).netloc .lower ()
    return re .sub (r"^www\.","",host )


def generated_title (content :str )->str :
    text =clean (content )
    if not text :
        return ""
        # Prioritize the use of the first sentence of the text and avoid writing the entire text into the title.
    first_sentence =re .split (r"[。！？!?；;\n]",text ,maxsplit =1 )[0 ].strip ()
    if len (first_sentence )<6 :
        first_sentence =text [:80 ]
    return first_sentence [:120 ].strip ()


def is_corrupt (text :str )->bool :
    if not text :
        return False 
    return text .count ("\ufffd")>=2 or text .count ("?")>max (8 ,len (text )//5 )


def iter_records (path :Path ,kind :str ):
    if kind =="json":
        try :
            payload =json .loads (path .read_text (encoding ="utf-8-sig"))
        except (UnicodeDecodeError ,json .JSONDecodeError ):
            return 
        if isinstance (payload ,list ):
            yield from payload 
        elif isinstance (payload ,dict ):
            rows =payload .get ("data")or payload .get ("items")or payload .get ("records")
            if isinstance (rows ,list ):
                yield from rows 
            else :
                yield payload 
        return 
    with path .open ("r",encoding ="utf-8-sig",errors ="replace")as handle :
        for line_number ,line in enumerate (handle ,1 ):
            if not line .strip ():
                continue 
            try :
                row =json .loads (line )
            except json .JSONDecodeError :
                yield {"_parse_error":True ,"_line_number":line_number }
                continue 
            if isinstance (row ,dict ):
                yield row 


def make_key (url :str ,date_text :str ,title :str ,content :str )->str :
    if url :
        return "url:"+url .lower ().rstrip ("/")
    normalized =re .sub (r"\W+","",title ).lower ()
    if normalized :
        return f"title:{date_text }:{normalized }"
    digest =hashlib .sha1 (content [:1000 ].encode ("utf-8",errors ="ignore")).hexdigest ()
    return "content:"+digest 


def write_jsonl (handle ,record :dict )->None :
    handle .write (json .dumps (record ,ensure_ascii =False )+"\n")


def main ()->None :
    DATA_DIR .mkdir (parents =True ,exist_ok =True )
    REPORT_DIR .mkdir (parents =True ,exist_ok =True )

    seen :set [str ]=set ()
    catalog :list [dict ]=[]
    missing_global :Counter =Counter ()
    month_counts :Counter =Counter ()
    total_complete =total_incomplete =total_duplicates =0 

    with (
    COMPLETE_FILE .open ("w",encoding ="utf-8")as complete_out ,
    INCOMPLETE_FILE .open ("w",encoding ="utf-8")as incomplete_out ,
    ):
        for dataset_name ,path ,kind in DATASETS :
            stats =Counter ()
            min_date =""
            max_date =""
            if not path .exists ():
                catalog .append ({
                "dataset":dataset_name ,
                "path":str (path ),
                "status":"File does not exist",
                })
                continue 

            for original in iter_records (path ,kind ):
                stats ["rows"]+=1 
                if original .get ("_parse_error"):
                    stats ["parse_errors"]+=1 
                    continue 

                content =clean (first (original ,CONTENT_FIELDS ))
                title =clean (first (original ,TITLE_FIELDS ))
                title_origin ="original"
                if not title and content :
                    title =generated_title (content )
                    title_origin ="generated_from_content"

                date_text =normalize_date (first (original ,DATE_FIELDS ))
                url =normalize_url (first (original ,URL_FIELDS ))
                source =clean (first (original ,SOURCE_FIELDS ))
                if not source and url :
                    source =source_from_url (url )
                    source_origin ="derived_from_url"
                else :
                    source_origin ="original"if source else "missing"

                key =make_key (url ,date_text ,title ,content )
                if key in seen :
                    stats ["duplicates"]+=1 
                    total_duplicates +=1 
                    continue 
                seen .add (key )

                missing =[]
                if not date_text :
                    missing .append ("date")
                if not title :
                    missing .append ("title")
                if not source :
                    missing .append ("source")
                if not url :
                    missing .append ("url")
                if is_corrupt (title )or is_corrupt (source ):
                    missing .append ("encoding_corrupt")

                record ={
                "uuid":clean (original .get ("uuid")or original .get ("id"))
                or hashlib .md5 (key .encode ("utf-8")).hexdigest ()[:16 ],
                "date":date_text ,
                "title":title ,
                "content":content ,
                "source":source ,
                "url":url ,
                "data_origin":clean (original .get ("data_origin"))or dataset_name ,
                "keyword_hits":original .get ("keyword_hits")
                or original .get ("_keyword_hits")
                or original .get ("keywords")
                or [],
                "crawl_time":clean (original .get ("crawl_time")),
                "archive_source_dataset":dataset_name ,
                "title_origin":title_origin ,
                "source_origin":source_origin ,
                "missing_fields":missing ,
                }

                if date_text :
                    min_date =min (min_date ,date_text )if min_date else date_text 
                    max_date =max (max_date ,date_text )if max_date else date_text 
                    if not (START <=date_text <=END ):
                        stats ["outside_research_period"]+=1 

                if missing :
                    write_jsonl (incomplete_out ,record )
                    total_incomplete +=1 
                    stats ["incomplete"]+=1 
                    for field in set (missing ):
                        missing_global [(dataset_name ,field )]+=1 
                else :
                    write_jsonl (complete_out ,record )
                    total_complete +=1 
                    stats ["complete"]+=1 
                    month_counts [date_text [:7 ]]+=1 

            catalog .append ({
            "dataset":dataset_name ,
            "path":str (path ),
            "status":"Organized",
            "file_size_bytes":path .stat ().st_size ,
            "rows":stats ["rows"],
            "parse_errors":stats ["parse_errors"],
            "duplicates_skipped":stats ["duplicates"],
            "complete_records":stats ["complete"],
            "incomplete_records":stats ["incomplete"],
            "outside_research_period":stats ["outside_research_period"],
            "min_date":min_date ,
            "max_date":max_date ,
            })
            print (
            f"[Complete] {dataset_name }: Total={stats ['rows']} Complete={stats ['complete']} To be added={stats ['incomplete']} Repeat={stats ['duplicates']}"
            )

    fields =[
    "dataset","path","status","file_size_bytes","rows","parse_errors",
    "duplicates_skipped","complete_records","incomplete_records",
    "outside_research_period","min_date","max_date",
    ]
    with CATALOG_FILE .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .DictWriter (handle ,fieldnames =fields )
        writer .writeheader ()
        for row in catalog :
            writer .writerow ({field :row .get (field ,"")for field in fields })

    with MISSING_FILE .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .writer (handle )
        writer .writerow (["dataset","missing_or_problem","count"])
        for (dataset ,field ),count in sorted (missing_global .items ()):
            writer .writerow ([dataset ,field ,count ])

    with MONTH_FILE .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .writer (handle )
        writer .writerow (["month","count"])
        writer .writerows (sorted (month_counts .items ()))

    README_FILE .write_text (
    "\n".join ([
    "AI算力新闻数据归档",
    "="*40 ,
    f"Sorting time:{datetime .now ():%Y-%m-%d %H:%M:%S}",
    f"Thesis research period: {START } to {END }",
    "",
    f"Complete record: {total_complete }",
    f"Records to be completed: {total_incomplete }",
    f"Repeat skipping across data sets: {total_duplicates }",
    "",
    "完整记录要求：date、title、source、url 均非空，且标题/来源无明显乱码。",
    "缺失标题时，仅从正文首句生成，并用 title_origin 标记。",
    "缺失来源时，仅在有URL的情况下从域名推导，并用 source_origin 标记。",
    "不会伪造来源或链接；无法可靠补全的记录进入待补全库。",
    "",
    "文件：",
    f"- {COMPLETE_FILE .name }：The four required fields are complete",
    f"- {INCOMPLETE_FILE .name }: Fields are still missing or garbled characters exist",
    f"- reports\\{CATALOG_FILE .name }: Number and time range of each data set",
    f"- reports\\{MISSING_FILE .name }: Missing field statistics",
    f"- reports\\{MONTH_FILE .name }: complete record of monthly distribution",
    ]),
    encoding ="utf-8",
    )
    print (f"\nArchiving completed: Complete={total_complete } To be added={total_incomplete } Repeat={total_duplicates }")
    print (OUT )


if __name__ =="__main__":
    main ()
