# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Flush News and Public Opinion Interface: AI computing power news breakpoint downloader.

Features:
- Study period 2021-07-01 to 2026-06-30;
- Cloud computing and artificial intelligence are two conceptual sections. After downloading, filter them carefully according to the keywords of AI computing power;
- A query window every 7 days to avoid data leakage caused by the upper limit of interface show_total;
- A maximum of 20,000 interface records can be read per calendar day;
- SQLite persistent deduplication, state files are saved atomically, and the original page is continued the next day;
- Daily JSONL, unified JSONL, failure log, operation log, monthly statistics."""

from __future__ import annotations 

import argparse 
import csv 
import hashlib 
import importlib .util 
import json 
import logging 
import os 
import re 
import sqlite3 
import time 
from datetime import date ,datetime ,timedelta 
from pathlib import Path 
from typing import Any 

import requests 


TOKEN_URL ="https://b2b-api.10jqka.com.cn/gateway/service-mana/app/login-appkey"
NEWS_URL ="https://b2b-api.10jqka.com.cn/gateway/arsenal/yq_qdc/info/v1/information/industry_concept_news"

START_DATE =date (2021 ,7 ,1 )
END_DATE =date (2026 ,6 ,30 )
WINDOW_DAYS =7 
PAGE_SIZE =20 
DAILY_API_LIMIT =20_000 
DAILY_REQUEST_LIMIT =990 
SLEEP_SECONDS =0.8 

CONCEPTS ={
"885362":"云计算",
"885728":"人工智能",
}

CORE_KEYWORDS =[
"算力","AI算力","人工智能算力","智能算力","计算力","智算",
"智算中心","智能计算中心","人工智能计算中心","算力中心","算力网络",
"算力枢纽","算力调度","算力集群","算力基础设施","算力租赁",
"云算力","异构算力","通用算力","先进算力","训练算力","推理算力",
"东数西算","高性能计算","超级计算","超算中心","超算互联网",
"AI服务器","人工智能服务器","GPU服务器","加速服务器","万卡集群",
"千卡集群","训练集群","推理集群","大模型训练","大模型推理",
"模型训练","模型推理","GPU云","GPU租赁","AI基础设施",
"人工智能基础设施","AIDC",
]

TECH_KEYWORDS =[
"GPU","NVIDIA","英伟达","A100","H100","H200","B100","B200",
"GH200","GB200","昇腾","寒武纪","摩尔线程","壁仞","沐曦",
"燧原","天数智芯","昆仑芯","海光","AI芯片","AI加速卡",
"计算卡","HBM","液冷服务器","服务器集群","数据中心",
]

AI_CONTEXT =[
"人工智能","AI","大模型","生成式人工智能","AIGC","深度学习",
"机器学习","训练","推理","云计算","云服务",
]


def load_credentials (reference_script :Path )->tuple [str ,str ]:
    env_key =os .getenv ("THS_APP_KEY")
    env_secret =os .getenv ("THS_APP_SECRET")
    if env_key and env_secret :
        return env_key ,env_secret 
    spec =importlib .util .spec_from_file_location ("credential_source",reference_script )
    if not spec or not spec .loader :
        raise RuntimeError ("Unable to read credentials script")
    module =importlib .util .module_from_spec (spec )
    spec .loader .exec_module (module )
    key =getattr (module ,"APP_KEY","")
    secret =getattr (module ,"APP_SECRET","")
    if not key or not secret :
        raise RuntimeError ("APP_KEY/APP_SECRET not found in credentials script")
    return key ,secret 


def timestamp_start (day :date )->int :
    return int (datetime (day .year ,day .month ,day .day ,0 ,0 ,0 ).timestamp ())


def timestamp_end (day :date )->int :
    return int (datetime (day .year ,day .month ,day .day ,23 ,59 ,59 ).timestamp ())


def make_tasks ()->list [dict [str ,Any ]]:
    tasks =[]
    for concept_code ,concept_name in CONCEPTS .items ():
        cursor =START_DATE 
        while cursor <=END_DATE :
            window_end =min (cursor +timedelta (days =WINDOW_DAYS -1 ),END_DATE )
            tasks .append ({
            "concept_code":concept_code ,
            "concept_name":concept_name ,
            "start":cursor .isoformat (),
            "end":window_end .isoformat (),
            })
            cursor =window_end +timedelta (days =1 )
    return tasks 


def default_state ()->dict [str ,Any ]:
    return {
    "task_index":0 ,
    "next_page":1 ,
    "completed":False ,
    "total_api_rows":0 ,
    "total_saved":0 ,
    "last_run_date":"",
    "today_api_rows":0 ,
    "today_requests":0 ,
    }


def load_state (path :Path )->dict [str ,Any ]:
    if not path .exists ():
        return default_state ()
    state =default_state ()
    state .update (json .loads (path .read_text (encoding ="utf-8")))
    today =date .today ().isoformat ()
    if state .get ("last_run_date")!=today :
        state ["last_run_date"]=today 
        state ["today_api_rows"]=0 
        state ["today_requests"]=0 
    return state 


def save_state (path :Path ,state :dict [str ,Any ])->None :
    temp =path .with_suffix (path .suffix +".tmp")
    temp .write_text (json .dumps (state ,ensure_ascii =False ,indent =2 ),encoding ="utf-8")
    os .replace (temp ,path )


def open_database (path :Path )->sqlite3 .Connection :
    conn =sqlite3 .connect (path )
    conn .execute ("PRAGMA journal_mode=WAL")
    conn .execute ("""
        CREATE TABLE IF NOT EXISTS news (
            uuid TEXT PRIMARY KEY,
            url TEXT,
            text_hash TEXT,
            publish_date TEXT,
            source TEXT,
            title TEXT,
            concept_code TEXT,
            saved_at TEXT
        )
    """)
    conn .execute ("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_url ON news(url) WHERE url <> ''")
    conn .execute ("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_hash ON news(text_hash)")
    conn .commit ()
    return conn 


def clean_html (text :str )->str :
    text =re .sub (r"<[^>]+>"," ",str (text or ""))
    return re .sub (r"\s+"," ",text ).strip ()


def find_hits (text :str )->list [str ]:
    low =text .lower ()
    core =[word for word in CORE_KEYWORDS if word .lower ()in low ]
    tech =[word for word in TECH_KEYWORDS if word .lower ()in low ]
    context =[word for word in AI_CONTEXT if word .lower ()in low ]
    return sorted (set (core +(tech if tech and context else [])))


def text_hash (title :str ,content :str )->str :
    normalized =re .sub (r"[\W_]+","",(title +content ).lower ())
    return hashlib .sha256 (normalized .encode ("utf-8")).hexdigest ()


def get_token (session :requests .Session ,key :str ,secret :str )->str :
    response =session .get (
    TOKEN_URL ,
    params ={"appKey":key ,"appSecret":secret },
    timeout =30 ,
    )
    response .raise_for_status ()
    payload =response .json ()
    if payload .get ("flag")!=0 :
        raise RuntimeError (f"Token acquisition failed: {payload .get ('msg')}")
    return payload ["data"]["access_token"]


def fetch_page (
session :requests .Session ,
token :str ,
task :dict [str ,Any ],
page :int ,
)->dict [str ,Any ]:
    response =session .get (
    NEWS_URL ,
    headers ={"open-authorization":f"Bearer{token }"},
    params ={
    "news_concept":task ["concept_code"],
    "stime":timestamp_start (date .fromisoformat (task ["start"])),
    "etime":timestamp_end (date .fromisoformat (task ["end"])),
    "page":page ,
    "page_size":PAGE_SIZE ,
    },
    timeout =30 ,
    )
    response .raise_for_status ()
    return response .json ()


def normalize (item :dict [str ,Any ],task :dict [str ,Any ])->dict [str ,Any ]|None :
    title =clean_html (item .get ("title",""))
    content =clean_html (item .get ("content",""))
    concepts =item .get ("concepts",[])
    industries =item .get ("industries",[])
    combined =" ".join ([title ,content ," ".join (concepts or [])," ".join (industries or [])])
    hits =find_hits (combined )
    if not hits :
        return None 
    publish_timestamp =item .get ("publish_time")or item .get ("display_time")
    try :
        publish_date =datetime .fromtimestamp (int (publish_timestamp )).date ().isoformat ()
    except (TypeError ,ValueError ,OSError ):
        return None 
    if not (START_DATE .isoformat ()<=publish_date <=END_DATE .isoformat ()):
        return None 
    return {
    "uuid":str (item .get ("uuid")or ""),
    "date":publish_date ,
    "title":title ,
    "content":content ,
    "source":str (item .get ("publish_source")or item .get ("host_source")or ""),
    "url":str (item .get ("url")or ""),
    "data_origin":"ths_news_api",
    "keyword_hits":hits ,
    "sentiment":item .get ("sentiment"),
    "importance":item .get ("importance"),
    "publish_time":item .get ("publish_time"),
    "display_time":item .get ("display_time"),
    "concepts":concepts or [],
    "industries":industries or [],
    "query_concept_code":task ["concept_code"],
    "query_concept_name":task ["concept_name"],
    }


def insert_if_new (conn :sqlite3 .Connection ,record :dict [str ,Any ])->bool :
    uid =record ["uuid"]or "hash:"+text_hash (record ["title"],record ["content"])
    fingerprint =text_hash (record ["title"],record ["content"])
    try :
        conn .execute (
        """INSERT INTO news
               (uuid, url, text_hash, publish_date, source, title, concept_code, saved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
        uid ,record ["url"],fingerprint ,record ["date"],record ["source"],
        record ["title"],record ["query_concept_code"],
        datetime .now ().isoformat (timespec ="seconds"),
        ),
        )
        conn .commit ()
        return True 
    except sqlite3 .IntegrityError :
        return False 


def write_monthly_counts (conn :sqlite3 .Connection ,output :Path )->None :
    rows =conn .execute (
    """SELECT substr(publish_date, 1, 7) AS month, count(*)
           FROM news GROUP BY month ORDER BY month"""
    ).fetchall ()
    with output .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .writer (handle )
        writer .writerow (["month","count"])
        writer .writerows (rows )


def main (output_dir :Path ,reference_script :Path ,run_limit :int ,sleep_seconds :float )->int :
    output_dir .mkdir (parents =True ,exist_ok =True )
    state_path =output_dir /"download_state.json"
    db_path =output_dir /"download_index.sqlite3"
    master_path =output_dir /"AI_Computing_News_THS_20210701_20260630.jsonl"
    daily_path =output_dir /f"daily_{date .today ().isoformat ()}.jsonl"
    failure_path =output_dir /"failures.jsonl"
    log_path =output_dir /"download.log"
    monthly_path =output_dir /"monthly_counts.csv"

    logging .basicConfig (
    level =logging .INFO ,
    format ="%(asctime)s %(levelname)s %(message)s",
    handlers =[logging .FileHandler (log_path ,encoding ="utf-8"),logging .StreamHandler ()],
    )
    app_key ,app_secret =load_credentials (reference_script )
    session =requests .Session ()
    session .headers .update ({"User-Agent":"AIComputingAcademicResearch/1.0"})
    token =get_token (session ,app_key ,app_secret )
    logging .info ("Token obtained successfully")

    tasks =make_tasks ()
    state =load_state (state_path )
    if state ["completed"]:
        logging .info ("The entire time window has been completed, no need to continue downloading")
        return 0 
    conn =open_database (db_path )

    with master_path .open ("a",encoding ="utf-8")as master ,daily_path .open ("a",encoding ="utf-8")as daily ,failure_path .open ("a",encoding ="utf-8")as failures :
        while state ["task_index"]<len (tasks ):
            if state ["today_requests"]>=DAILY_REQUEST_LIMIT :
                logging .info (
                "The maximum security request limit for today has been reached %d. The status has been saved and will continue tomorrow.",
                state ["today_requests"],
                )
                break 
            if state ["today_api_rows"]>=min (DAILY_API_LIMIT ,run_limit ):
                logging .info ("The reading limit for today has been reached %d, the status has been saved, and will continue tomorrow.",state ["today_api_rows"])
                break 
            task =tasks [state ["task_index"]]
            page =int (state ["next_page"])
            state ["today_requests"]+=1 
            state ["last_run_date"]=date .today ().isoformat ()
            save_state (state_path ,state )
            try :
                payload =fetch_page (session ,token ,task ,page )
            except Exception as exc :
                failures .write (json .dumps ({
                "time":datetime .now ().isoformat (),"task":task ,"page":page ,
                "error":str (exc ),
                },ensure_ascii =False )+"\n")
                failures .flush ()
                save_state (state_path ,state )
                logging .error ("Request failed, status saved: %s",exc )
                break 

            flag =payload .get ("flag")
            status =payload .get ("status_code")
            message =str (payload .get ("msg")or payload .get ("status_msg")or "")
            if (flag is not None and flag !=0 )or status !=0 :
                if flag ==4000 or status ==4000 :
                    logging .warning ("The request frequency is too high, wait 30 seconds and try again.")
                    time .sleep (30 )
                    continue 
                failures .write (json .dumps ({
                "time":datetime .now ().isoformat (),"task":task ,"page":page ,
                "flag":flag ,"status_code":status ,"message":message ,
                },ensure_ascii =False )+"\n")
                failures .flush ()
                save_state (state_path ,state )
                logging .error ("Interface stopped: %s",message )
                break 

            data =payload .get ("data")or {}
            records =data .get ("list")or []
            state ["today_api_rows"]+=len (records )
            state ["total_api_rows"]+=len (records )
            new_count =0 
            for item in records :
                record =normalize (item ,task )
                if record is None :
                    continue 
                if insert_if_new (conn ,record ):
                    line =json .dumps (record ,ensure_ascii =False )+"\n"
                    master .write (line )
                    daily .write (line )
                    new_count +=1 
                    state ["total_saved"]+=1 
            master .flush ()
            daily .flush ()

            logging .info (
            "%s %s~%s page=%d rows=%d new=%d day_rows=%d total_saved=%d",
            task ["concept_name"],task ["start"],task ["end"],page ,len (records ),
            new_count ,state ["today_api_rows"],state ["total_saved"],
            )

            if not records or len (records )<PAGE_SIZE :
                state ["task_index"]+=1 
                state ["next_page"]=1 
            else :
                state ["next_page"]=page +1 
            state ["last_run_date"]=date .today ().isoformat ()
            save_state (state_path ,state )
            time .sleep (sleep_seconds )

        if state ["task_index"]>=len (tasks ):
            state ["completed"]=True 
            save_state (state_path ,state )
            logging .info ("All concepts and time windows have been downloaded")

    write_monthly_counts (conn ,monthly_path )
    conn .close ()
    logging .info (
    "End of this round: Today’s request = %d, Today’s interface record = %d, Cumulative interface record = %d, Cumulative save = %d, Task = %d/%d",
    state ["today_requests"],state ["today_api_rows"],state ["total_api_rows"],state ["total_saved"],
    state ["task_index"],len (tasks ),
    )
    return 0 


if __name__ =="__main__":
    parser =argparse .ArgumentParser ()
    parser .add_argument ("--output-dir",type =Path ,required =True )
    parser .add_argument ("--reference-script",type =Path ,required =True )
    parser .add_argument ("--run-limit",type =int ,default =DAILY_API_LIMIT )
    parser .add_argument ("--sleep",type =float ,default =SLEEP_SECONDS )
    args =parser .parse_args ()
    raise SystemExit (main (args .output_dir ,args .reference_script ,args .run_limit ,args .sleep ))
