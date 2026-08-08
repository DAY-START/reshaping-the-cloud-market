#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Chinese AI computing power news collector (2023-2026)
=================================
Data principles:
1. Do not generate news, do not translate foreign languages and pretend to be Chinese news.
2. Only save records with accessible original links, parsable dates, sources, and Chinese text excerpts.
3. Remove duplication through three levels of URL, title + date, and text hashing.
4. By default, "original excerpts" of no more than 1,200 Chinese characters are saved to avoid bulk redistribution of the full copyrighted text.
5. Data discovery uses GDELT DOC API (no API Key required), and the text comes from the original news webpage.

Output fields:
title, link, news_date, source, content, content_type, language,
retrieved_at, domain, relevance_score, content_sha256, discovery_source"""

from __future__ import annotations 

import argparse 
import concurrent .futures as cf 
import contextlib 
import datetime as dt 
import hashlib 
import html 
import json 
import os 
import random 
import re 
import sqlite3 
import sys 
import threading 
import time 
import unicodedata 
from collections import defaultdict 
from dataclasses import dataclass 
from pathlib import Path 
from typing import Any ,Iterable 
from urllib .parse import parse_qsl ,urlencode ,urlparse ,urlunparse 

import requests 
import trafilatura 
from bs4 import BeautifulSoup 
from dateutil import parser as date_parser 
from tqdm import tqdm 


GDELT_ENDPOINT ="https://api.gdeltproject.org/api/v2/doc/doc"

# The discovery phase uses multiple complementary queries. Each final record must still pass review for textual relevance.
DISCOVERY_QUERIES =[
'"AI算力"','"人工智能算力"','"智能算力"','"智算中心"','"算力中心"',
'"AI芯片"','"人工智能芯片"','"算力芯片"','"GPU服务器"','"AI服务器"',
'"大模型训练" 算力','"大模型推理" 算力','"生成式AI" 算力',
'"AI基础设施"','"人工智能基础设施"','"算力基础设施"',
'"万卡集群"','"十万卡集群"','"算力集群"','"异构计算" AI',
'"算力租赁"','"算力调度"','"算力网络"','"算力一体机"',
'"数据中心" AI GPU','"数据中心" 人工智能 芯片',
'"液冷" AI 数据中心','"HBM" AI 芯片','"光模块" AI 数据中心',
'"CPO" AI 数据中心','"RDMA" AI 集群','"NVLink" AI',
'"英伟达" 算力','"NVIDIA" 算力','"AMD" AI 芯片',
'"华为昇腾"','"昇腾" 算力','"寒武纪" 算力','"海光" 算力',
'"壁仞科技"','"摩尔线程" GPU','"沐曦" GPU','"燧原科技"',
'"昆仑芯"','"百度昆仑芯"','"阿里含光"','"腾讯" 算力',
'"阿里云" AI 基础设施','"百度智能云" 算力','"华为云" 算力',
'"火山引擎" 算力','"中国移动" 智算中心','"中国电信" 智算中心',
'"中国联通" 智算中心','"东数西算" 人工智能',
'"超级计算机" 人工智能','"超算中心" 大模型',
'"推理算力"','"训练算力"','"国产算力"','"算力国产化"',
]

STRONG_PHRASES ={
"AI算力","人工智能算力","智能算力","智算中心","AI芯片",
"人工智能芯片","算力芯片","AI服务器","GPU服务器",
"AI基础设施","人工智能基础设施","推理算力","训练算力",
"万卡集群","十万卡集群","算力租赁","算力网络",
}

AI_TERMS ={
"人工智能","生成式AI","生成式人工智能","大模型","基础模型",
"语言模型","多模态","机器学习","深度学习","AI","AIGC",
}

COMPUTE_TERMS ={
"算力","GPU","NPU","TPU","加速卡","芯片","服务器",
"数据中心","智算","超算","集群","训练","推理","云计算",
"云服务","HBM","显存","液冷","互联","RDMA","NVLINK",
"CPO","光模块","网络交换机","算力调度","算力租赁",
"异构计算","超级计算机","AI FACTORY","AI工厂",
}

INFRA_TERMS ={
"数据中心","智算中心","超算中心","服务器","集群","机房",
"云平台","云服务","基础设施","加速卡","互联","液冷",
"机架","交换机","存储","网络","电力","能耗","功耗",
}

LOW_QUALITY_PATTERNS =[
r"彩票",r"博彩",r"成人视频",r"色情",r"代写",r"培训班",
r"软件下载",r"破解",r"网盘资源",r"招聘.{0,5}算力",
]

TRACKING_KEYS ={
"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
"spm","from","source","ref","refer","share_token","sharefrom",
"track","tracking","mc_cid","mc_eid",
}

DATE_META_KEYS =(
"article:published_time","og:published_time","datePublished",
"datepublished","publishdate","pubdate","date","sailthru.date",
"weibo:article:create_at",
)

SOURCE_META_KEYS =(
"og:site_name","application-name","publisher","source",
)


@dataclass (frozen =True )
class Candidate :
    url :str 
    title :str 
    seen_date :str 
    domain :str 
    language :str 
    source_country :str 
    query :str 


class HostRateLimiter :
    def __init__ (self ,seconds :float =0.7 )->None :
        self .seconds =max (0.0 ,seconds )
        self ._lock =threading .Lock ()
        self ._last :dict [str ,float ]={}

    def wait (self ,url :str )->None :
        host =urlparse (url ).netloc .lower ()
        if not host or self .seconds <=0 :
            return 
        with self ._lock :
            now =time .monotonic ()
            delay =self .seconds -(now -self ._last .get (host ,0.0 ))
            if delay >0 :
                time .sleep (delay )
            self ._last [host ]=time .monotonic ()


def normalize_text (value :str |None )->str :
    if not value :
        return ""
    value =html .unescape (value )
    value =unicodedata .normalize ("NFKC",value )
    value =value .replace ("\u200b","").replace ("\ufeff","")
    value =re .sub (r"\s+"," ",value ).strip ()
    return value 


def canonical_url (url :str )->str :
    url =normalize_text (url )
    if not url :
        return ""
    try :
        p =urlparse (url )
        if p .scheme not in {"http","https"}or not p .netloc :
            return ""
        query =[
        (k ,v )for k ,v in parse_qsl (p .query ,keep_blank_values =True )
        if k .lower ()not in TRACKING_KEYS and not k .lower ().startswith ("utm_")
        ]
        path =re .sub (r"/{2,}","/",p .path or "/")
        if path !="/":
            path =path .rstrip ("/")
        return urlunparse ((
        p .scheme .lower (),p .netloc .lower (),path ,"",urlencode (query ,doseq =True ),""
        ))
    except Exception :
        return ""


def chinese_ratio (text :str )->float :
    if not text :
        return 0.0 
    han =len (re .findall (r"[\u3400-\u4dbf\u4e00-\u9fff]",text ))
    letters =len (re .findall (r"[A-Za-z\u3400-\u4dbf\u4e00-\u9fff]",text ))
    return han /max (letters ,1 )


def term_count (text_upper :str ,terms :Iterable [str ])->int :
    return sum (1 for term in terms if term .upper ()in text_upper )


def relevance_score (title :str ,content :str )->int :
    title_n =normalize_text (title )
    content_n =normalize_text (content )
    combined =f"{title_n } {content_n [:8000 ]}"
    upper =combined .upper ()

    if any (re .search (p ,combined ,re .I )for p in LOW_QUALITY_PATTERNS ):
        return -100 

    strong_title =sum (1 for p in STRONG_PHRASES if p .upper ()in title_n .upper ())
    strong_all =sum (1 for p in STRONG_PHRASES if p .upper ()in upper )
    ai =term_count (upper ,AI_TERMS )
    compute =term_count (upper ,COMPUTE_TERMS )
    infra =term_count (upper ,INFRA_TERMS )

    score =strong_title *10 +strong_all *5 +ai *2 +compute *3 +infra 
    if "算力"in title_n :
        score +=8 
    if re .search (r"\b(GPU|NPU|TPU|HBM|CPO|RDMA)\b",title_n ,re .I ):
        score +=6 
    if len (content_n )<180 :
        score -=8 
    return score 


def is_relevant (title :str ,content :str ,min_score :int )->tuple [bool ,int ]:
    combined =f"{normalize_text (title )} {normalize_text (content [:10000 ])}"
    upper =combined .upper ()
    strong =any (p .upper ()in upper for p in STRONG_PHRASES )
    has_ai =any (t .upper ()in upper for t in AI_TERMS )
    has_compute =any (t .upper ()in upper for t in COMPUTE_TERMS )
    has_infra =any (t .upper ()in upper for t in INFRA_TERMS )
    score =relevance_score (title ,content )
    passed =score >=min_score and (strong or (has_ai and has_compute and has_infra ))
    return passed ,score 


def iter_month_windows (start_date :dt .date ,end_date :dt .date ):
    cur =start_date .replace (day =1 )
    while cur <=end_date :
        if cur .month ==12 :
            nxt =dt .date (cur .year +1 ,1 ,1 )
        else :
            nxt =dt .date (cur .year ,cur .month +1 ,1 )
        window_start =max (cur ,start_date )
        window_end =min (nxt -dt .timedelta (seconds =1 ),end_date )
        yield window_start ,window_end 
        cur =nxt 


def gdelt_datetime (d :dt .datetime |dt .date ,end :bool =False )->str :
    if isinstance (d ,dt .date )and not isinstance (d ,dt .datetime ):
        t =dt .time (23 ,59 ,59 )if end else dt .time (0 ,0 ,0 )
        d =dt .datetime .combine (d ,t )
    return d .strftime ("%Y%m%d%H%M%S")


def request_json (session :requests .Session ,params :dict [str ,Any ],retries :int =6 )->dict [str ,Any ]:
    last_error :Exception |None =None 
    for attempt in range (retries ):
        try :
            resp =session .get (GDELT_ENDPOINT ,params =params ,timeout =(15 ,90 ))
            if resp .status_code ==429 :
                time .sleep (min (60 ,2 **attempt +random .random ()))
                continue 
            resp .raise_for_status ()
            data =resp .json ()
            return data if isinstance (data ,dict )else {}
        except Exception as exc :
            last_error =exc 
            time .sleep (min (30 ,1.5 **attempt +random .random ()))
    raise RuntimeError (f"GDELT request failed: {last_error }")


def split_datetime_range (start :dt .datetime ,end :dt .datetime ):
    midpoint =start +(end -start )/2 
    return (start ,midpoint ),(midpoint +dt .timedelta (seconds =1 ),end )


def gdelt_search_recursive (
session :requests .Session ,
query :str ,
start :dt .datetime ,
end :dt .datetime ,
min_span_hours :int =6 ,
pause :float =0.18 ,
)->list [Candidate ]:
    params ={
    "query":f"({query }) sourcelang:Chinese",
    "mode":"artlist",
    "maxrecords":250 ,
    "format":"json",
    "sort":"datedesc",
    "startdatetime":gdelt_datetime (start ),
    "enddatetime":gdelt_datetime (end ,end =True ),
    }
    data =request_json (session ,params )
    time .sleep (pause )
    articles =data .get ("articles")or []
    if not isinstance (articles ,list ):
        return []

    span_hours =(end -start ).total_seconds ()/3600 
    # Split the time window when hitting the upper limit to avoid silent loss of results.
    if len (articles )>=250 and span_hours >min_span_hours :
        left ,right =split_datetime_range (start ,end )
        return (
        gdelt_search_recursive (session ,query ,left [0 ],left [1 ],min_span_hours ,pause )
        +gdelt_search_recursive (session ,query ,right [0 ],right [1 ],min_span_hours ,pause )
        )

    out :list [Candidate ]=[]
    for item in articles :
        if not isinstance (item ,dict ):
            continue 
        url =canonical_url (str (item .get ("url")or ""))
        if not url :
            continue 
        title =normalize_text (str (item .get ("title")or ""))
        seen =normalize_text (str (item .get ("seendate")or ""))
        domain =normalize_text (str (item .get ("domain")or urlparse (url ).netloc ))
        lang =normalize_text (str (item .get ("language")or ""))
        country =normalize_text (str (item .get ("sourcecountry")or ""))
        out .append (Candidate (url ,title ,seen ,domain ,lang ,country ,query ))
    return out 


def init_db (path :Path )->sqlite3 .Connection :
    conn =sqlite3 .connect (path )
    conn .execute ("PRAGMA journal_mode=WAL")
    conn .execute ("""
        CREATE TABLE IF NOT EXISTS candidates (
            url TEXT PRIMARY KEY,
            title TEXT,
            seen_date TEXT,
            domain TEXT,
            language TEXT,
            source_country TEXT,
            query TEXT,
            status TEXT DEFAULT 'pending',
            error TEXT
        )
    """)
    conn .execute ("""
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            news_date TEXT NOT NULL,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            content_type TEXT NOT NULL,
            language TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            domain TEXT NOT NULL,
            relevance_score INTEGER NOT NULL,
            content_sha256 TEXT NOT NULL UNIQUE,
            discovery_source TEXT NOT NULL
        )
    """)
    conn .execute ("CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)")
    conn .execute ("CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(news_date)")
    conn .commit ()
    return conn 


def insert_candidates (conn :sqlite3 .Connection ,candidates :Iterable [Candidate ])->int :
    before =conn .total_changes 
    conn .executemany (
    """INSERT OR IGNORE INTO candidates
        (url,title,seen_date,domain,language,source_country,query)
        VALUES (?,?,?,?,?,?,?)""",
    [(c .url ,c .title ,c .seen_date ,c .domain ,c .language ,c .source_country ,c .query )
    for c in candidates ],
    )
    conn .commit ()
    return conn .total_changes -before 


def extract_json_ld (soup :BeautifulSoup )->list [dict [str ,Any ]]:
    objects :list [dict [str ,Any ]]=[]
    for tag in soup .find_all ("script",attrs ={"type":re .compile (r"ld\+json",re .I )}):
        raw =tag .string or tag .get_text (" ",strip =True )
        if not raw :
            continue 
        with contextlib .suppress (Exception ):
            parsed =json .loads (raw )
            stack =parsed if isinstance (parsed ,list )else [parsed ]
            for obj in stack :
                if isinstance (obj ,dict )and isinstance (obj .get ("@graph"),list ):
                    objects .extend (x for x in obj ["@graph"]if isinstance (x ,dict ))
                elif isinstance (obj ,dict ):
                    objects .append (obj )
    return objects 


def parse_date_value (value :Any )->str :
    if isinstance (value ,list ):
        value =next ((x for x in value if x ),"")
    if not value :
        return ""
    try :
        parsed =date_parser .parse (str (value ),fuzzy =True )
        return parsed .date ().isoformat ()
    except Exception :
        return ""


def extract_page_metadata (soup :BeautifulSoup ,fallback_title :str ,fallback_date :str ,domain :str ):
    title =""
    source =""
    news_date =""

    json_ld =extract_json_ld (soup )
    for obj in json_ld :
        obj_type =str (obj .get ("@type")or "").lower ()
        if obj_type in {"newsarticle","article","reportagenewsarticle","blogposting"}:
            title =title or normalize_text (str (obj .get ("headline")or obj .get ("name")or ""))
            news_date =news_date or parse_date_value (
            obj .get ("datePublished")or obj .get ("dateCreated")or obj .get ("uploadDate")
            )
            publisher =obj .get ("publisher")
            if isinstance (publisher ,dict ):
                source =source or normalize_text (str (publisher .get ("name")or ""))
            elif publisher :
                source =source or normalize_text (str (publisher ))

    def meta_content (*keys :str )->str :
        for key in keys :
            tag =(
            soup .find ("meta",attrs ={"property":key })
            or soup .find ("meta",attrs ={"name":key })
            or soup .find ("meta",attrs ={"itemprop":key })
            )
            if tag and tag .get ("content"):
                return normalize_text (str (tag .get ("content")))
        return ""

    title =title or meta_content ("og:title","twitter:title")
    if not title :
        h1 =soup .find ("h1")
        title =normalize_text (h1 .get_text (" ",strip =True )if h1 else "")
    if not title and soup .title :
        title =normalize_text (soup .title .get_text (" ",strip =True ))
    title =title or normalize_text (fallback_title )

    news_date =news_date or parse_date_value (meta_content (*DATE_META_KEYS ))
    if not news_date :
        time_tag =soup .find ("time")
        if time_tag :
            news_date =parse_date_value (time_tag .get ("datetime")or time_tag .get_text (" ",strip =True ))
    news_date =news_date or parse_date_value (fallback_date )

    source =source or meta_content (*SOURCE_META_KEYS )
    source =source or domain .removeprefix ("www.")
    return title ,news_date ,source 


def fallback_paragraph_extract (soup :BeautifulSoup )->str :
    for bad in soup (["script","style","nav","footer","header","aside","form","noscript"]):
        bad .decompose ()
    paras =[]
    for p in soup .find_all ("p"):
        text =normalize_text (p .get_text (" ",strip =True ))
        if len (text )>=20 :
            paras .append (text )
    return "\n".join (paras )


def fetch_and_extract (
row :sqlite3 .Row ,
session_factory ,
limiter :HostRateLimiter ,
start_date :dt .date ,
end_date :dt .date ,
excerpt_chars :int ,
min_score :int ,
timeout :int ,
)->tuple [str ,dict [str ,Any ]|None ,str ]:
    url =row ["url"]
    limiter .wait (url )
    session =session_factory ()
    try :
        resp =session .get (url ,timeout =(15 ,timeout ),allow_redirects =True )
        resp .raise_for_status ()
        ctype =(resp .headers .get ("content-type")or "").lower ()
        if "text/html"not in ctype and "application/xhtml"not in ctype :
            return url ,None ,f"Non-HTML content: {ctype }"
        if len (resp .content )>8_000_000 :
            return url ,None ,"页面超过8MB"
        resp .encoding =resp .apparent_encoding or resp .encoding 
        raw_html =resp .text 
    except Exception as exc :
        return url ,None ,f"Download failed: {type (exc ).__name__ }: {exc }"

    try :
        soup =BeautifulSoup (raw_html ,"html.parser")
        final_url =canonical_url (resp .url )or url 
        domain =urlparse (final_url ).netloc .lower ()
        title ,news_date ,source =extract_page_metadata (
        soup ,row ["title"],row ["seen_date"],domain 
        )

        extracted =trafilatura .extract (
        raw_html ,
        url =final_url ,
        include_comments =False ,
        include_tables =False ,
        include_links =False ,
        favor_precision =True ,
        output_format ="txt",
        )or fallback_paragraph_extract (soup )
        extracted =normalize_text (extracted )

        if not extracted or len (extracted )<180 :
            return url ,None ,"正文过短或无法提取"
        if chinese_ratio (f"{title } {extracted [:3000 ]}")<0.48 :
            return url ,None ,"中文比例不足"
        if not news_date :
            return url ,None ,"无法解析新闻日期"
        parsed_date =dt .date .fromisoformat (news_date )
        if parsed_date <start_date or parsed_date >end_date :
            return url ,None ,f"Date out of range: {news_date }"

        passed ,score =is_relevant (title ,extracted ,min_score )
        if not passed :
            return url ,None ,f"Insufficient relevance: {score }"

        excerpt =extracted [:excerpt_chars ].rstrip ()
        digest =hashlib .sha256 (extracted .encode ("utf-8")).hexdigest ()
        record ={
        "title":title ,
        "link":final_url ,
        "news_date":news_date ,
        "source":source ,
        "content":excerpt ,
        "content_type":f"extractive_excerpt_first_{excerpt_chars }_chars",
        "language":"zh",
        "retrieved_at":dt .datetime .now (dt .timezone .utc ).isoformat (),
        "domain":domain ,
        "relevance_score":score ,
        "content_sha256":digest ,
        "discovery_source":"GDELT_DOC_API+original_webpage",
        }
        return url ,record ,""
    except Exception as exc :
        return url ,None ,f"Parsing failed: {type (exc ).__name__ }: {exc }"


def make_session ()->requests .Session :
    s =requests .Session ()
    s .headers .update ({
    "User-Agent":(
    "Mozilla/5.0 (compatible; AcademicNewsDatasetCollector/1.0; "
    "+https://www.gdeltproject.org/)"
    ),
    "Accept-Language":"zh-CN,zh;q=0.9,en;q=0.5",
    "Accept":"text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
    })
    adapter =requests .adapters .HTTPAdapter (pool_connections =32 ,pool_maxsize =32 ,max_retries =1 )
    s .mount ("http://",adapter )
    s .mount ("https://",adapter )
    return s 


_thread_local =threading .local ()


def thread_session ()->requests .Session :
    if not hasattr (_thread_local ,"session"):
        _thread_local .session =make_session ()
    return _thread_local .session 


def discover_candidates (
conn :sqlite3 .Connection ,
start_date :dt .date ,
end_date :dt .date ,
max_candidates :int ,
queries :list [str ],
)->None :
    session =make_session ()
    existing =conn .execute ("SELECT COUNT(*) FROM candidates").fetchone ()[0 ]
    if existing >=max_candidates :
        print (f"[Discover] There are {existing :,} candidate links, skip the discovery stage.")
        return 

    windows =list (iter_month_windows (start_date ,end_date ))
    jobs =[(q ,ws ,we )for q in queries for ws ,we in windows ]
    progress =tqdm (jobs ,desc ="Discover candidates",unit ="Query")
    for query ,ws ,we in progress :
        start_dt =dt .datetime .combine (ws ,dt .time .min )
        end_dt =dt .datetime .combine (we ,dt .time .max )
        try :
            found =gdelt_search_recursive (session ,query ,start_dt ,end_dt )
            insert_candidates (conn ,found )
        except Exception as exc :
            print (f"\n[Warning] Query failed {query } {ws }~{we }: {exc }",file =sys .stderr )
        count =conn .execute ("SELECT COUNT(*) FROM candidates").fetchone ()[0 ]
        progress .set_postfix (candidates =f"{count :,}")
        if count >=max_candidates :
            break 


def balanced_pending_rows (conn :sqlite3 .Connection ,limit :int )->list [sqlite3 .Row ]:
    conn .row_factory =sqlite3 .Row 
    rows =conn .execute (
    """SELECT * FROM candidates
           WHERE status='pending'
           ORDER BY seen_date DESC, domain, url
           LIMIT ?""",
    (limit *4 ,),
    ).fetchall ()

    by_year :dict [str ,list [sqlite3 .Row ]]=defaultdict (list )
    for row in rows :
        m =re .search (r"(20\d{2})",row ["seen_date"]or "")
        by_year [m .group (1 )if m else "unknown"].append (row )

    output :list [sqlite3 .Row ]=[]
    years =sorted (by_year .keys ())
    while len (output )<limit and any (by_year .values ()):
        for year in years :
            if by_year [year ]and len (output )<limit :
                output .append (by_year [year ].pop (0 ))
    return output 


def process_candidates (
conn :sqlite3 .Connection ,
target :int ,
workers :int ,
start_date :dt .date ,
end_date :dt .date ,
excerpt_chars :int ,
min_score :int ,
host_delay :float ,
timeout :int ,
)->None :
    limiter =HostRateLimiter (host_delay )
    while True :
        have =conn .execute ("SELECT COUNT(*) FROM articles").fetchone ()[0 ]
        if have >=target :
            return 
        batch_size =min (max (workers *20 ,100 ),max ((target -have )*8 ,200 ))
        rows =balanced_pending_rows (conn ,batch_size )
        if not rows :
            return 

        with cf .ThreadPoolExecutor (max_workers =workers )as pool :
            futures =[
            pool .submit (
            fetch_and_extract ,row ,thread_session ,limiter ,
            start_date ,end_date ,excerpt_chars ,min_score ,timeout 
            )
            for row in rows 
            ]
            with tqdm (total =len (futures ),desc =f"Verify the text (included {have :,})",unit ="Page")as bar :
                for future in cf .as_completed (futures ):
                    url ,record ,error =future .result ()
                    if record :
                        try :
                            conn .execute (
                            """INSERT OR IGNORE INTO articles
                                (url,title,news_date,source,content,content_type,language,
                                 retrieved_at,domain,relevance_score,content_sha256,discovery_source)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                            record ["link"],record ["title"],record ["news_date"],
                            record ["source"],record ["content"],record ["content_type"],
                            record ["language"],record ["retrieved_at"],record ["domain"],
                            record ["relevance_score"],record ["content_sha256"],
                            record ["discovery_source"],
                            ),
                            )
                            conn .execute (
                            "UPDATE candidates SET status='accepted', error=NULL WHERE url=?",
                            (url ,),
                            )
                        except sqlite3 .IntegrityError :
                            conn .execute (
                            "UPDATE candidates SET status='duplicate', error='内容哈希重复' WHERE url=?",
                            (url ,),
                            )
                    else :
                        conn .execute (
                        "UPDATE candidates SET status='rejected', error=? WHERE url=?",
                        (error [:500 ],url ),
                        )
                    conn .commit ()
                    have =conn .execute ("SELECT COUNT(*) FROM articles").fetchone ()[0 ]
                    bar .set_postfix (accepted =f"{have :,}/{target :,}")
                    bar .update (1 )
                    if have >=target :
                        for f in futures :
                            f .cancel ()
                        return 


def export_jsonl (conn :sqlite3 .Connection ,output :Path ,target :int )->int :
    conn .row_factory =sqlite3 .Row 
    rows =conn .execute (
    """SELECT title,url,news_date,source,content,content_type,language,
                  retrieved_at,domain,relevance_score,content_sha256,discovery_source
           FROM articles
           ORDER BY news_date, source, title
           LIMIT ?""",
    (target ,),
    ).fetchall ()
    output .parent .mkdir (parents =True ,exist_ok =True )
    with output .open ("w",encoding ="utf-8",newline ="\n")as f :
        for row in rows :
            obj =dict (row )
            obj ["link"]=obj .pop ("url")
            ordered ={
            "title":obj ["title"],
            "link":obj ["link"],
            "news_date":obj ["news_date"],
            "source":obj ["source"],
            "content":obj ["content"],
            "content_type":obj ["content_type"],
            "language":obj ["language"],
            "retrieved_at":obj ["retrieved_at"],
            "domain":obj ["domain"],
            "relevance_score":obj ["relevance_score"],
            "content_sha256":obj ["content_sha256"],
            "discovery_source":obj ["discovery_source"],
            }
            f .write (json .dumps (ordered ,ensure_ascii =False )+"\n")
    return len (rows )


def write_report (conn :sqlite3 .Connection ,path :Path ,output_count :int ,target :int )->None :
    stats ={
    "target":target ,
    "output_count":output_count ,
    "complete":output_count >=target ,
    "candidate_status":dict (conn .execute (
    "SELECT status, COUNT(*) FROM candidates GROUP BY status"
    ).fetchall ()),
    "articles_by_year":dict (conn .execute (
    "SELECT substr(news_date,1,4), COUNT(*) FROM articles GROUP BY 1 ORDER BY 1"
    ).fetchall ()),
    "top_sources":[
    {"source":s ,"count":c }
    for s ,c in conn .execute (
    "SELECT source, COUNT(*) c FROM articles GROUP BY source ORDER BY c DESC LIMIT 50"
    ).fetchall ()
    ],
    "generated_at":dt .datetime .now (dt .timezone .utc ).isoformat (),
    }
    path .write_text (json .dumps (stats ,ensure_ascii =False ,indent =2 ),encoding ="utf-8")


def parse_args ()->argparse .Namespace :
    p =argparse .ArgumentParser (description ="Collect and verify 2023-2026 Chinese AI computing power news")
    p .add_argument ("--target",type =int ,default =10_000 ,help ="Target number of news, default 10000")
    p .add_argument ("--start-date",default ="2023-01-01")
    p .add_argument ("--end-date",default ="2026-07-30")
    p .add_argument ("--output",default ="ai_compute_news_zh_2023_2026_10000.jsonl")
    p .add_argument ("--workdir",default ="collector_state")
    p .add_argument ("--workers",type =int ,default =8 )
    p .add_argument ("--max-candidates",type =int ,default =180_000 )
    p .add_argument ("--excerpt-chars",type =int ,default =1200 )
    p .add_argument ("--min-score",type =int ,default =18 )
    p .add_argument ("--host-delay",type =float ,default =0.7 )
    p .add_argument ("--timeout",type =int ,default =45 )
    p .add_argument ("--skip-discovery",action ="store_true")
    p .add_argument ("--queries-file",help ="Custom discovery keywords, one per line")
    return p .parse_args ()


def main ()->int :
    args =parse_args ()
    start_date =dt .date .fromisoformat (args .start_date )
    end_date =dt .date .fromisoformat (args .end_date )
    if start_date >end_date :
        raise SystemExit ("start-date cannot be later than end-date")
    if args .target <=0 :
        raise SystemExit ("target must be greater than 0")

    workdir =Path (args .workdir )
    workdir .mkdir (parents =True ,exist_ok =True )
    db_path =workdir /"collector.sqlite3"
    conn =init_db (db_path )

    queries =DISCOVERY_QUERIES 
    if args .queries_file :
        queries =[
        line .strip ()
        for line in Path (args .queries_file ).read_text (encoding ="utf-8").splitlines ()
        if line .strip ()and not line .lstrip ().startswith ("#")
        ]

    print (f"[Configuration] Date: {start_date } to {end_date }")
    print (f"[Configuration] Target: {args .target :,} items; the text is the excerpt of the original text of {args .excerpt_chars } characters")
    print (f"[Configuration] State library: {db_path .resolve ()}")

    if not args .skip_discovery :
        discover_candidates (
        conn ,start_date ,end_date ,args .max_candidates ,queries 
        )

    candidates =conn .execute ("SELECT COUNT(*) FROM candidates").fetchone ()[0 ]
    print (f"[Discover] Unique candidate link: {candidates :,}")

    process_candidates (
    conn =conn ,
    target =args .target ,
    workers =max (1 ,min (args .workers ,24 )),
    start_date =start_date ,
    end_date =end_date ,
    excerpt_chars =max (200 ,args .excerpt_chars ),
    min_score =args .min_score ,
    host_delay =max (0 ,args .host_delay ),
    timeout =max (15 ,args .timeout ),
    )

    output =Path (args .output )
    count =export_jsonl (conn ,output ,args .target )
    report =output .with_suffix (".report.json")
    write_report (conn ,report ,count ,args .target )

    print (f"[Complete] JSONL: {output .resolve ()}")
    print (f"[Complete] Verification record: {count :,}/{args .target :,}")
    print (f"[Complete] Quality report: {report .resolve ()}")
    if count <args .target :
        pending =conn .execute (
        "SELECT COUNT(*) FROM candidates WHERE status='pending'"
        ).fetchone ()[0 ]
        print (
        f"[Explanation] Target not reached yet. The remaining candidates to be verified are {pending :,}; You can run the same command again to continue, and the program will not collect processed records repeatedly."
        )
        return 2 
    return 0 


if __name__ =="__main__":
    raise SystemExit (main ())
