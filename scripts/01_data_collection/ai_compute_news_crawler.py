# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Compliance collection of public AI computing power news.

The discovery portal uses only accessible sitemaps and manually provided public article URLs.
The program checks robots.txt before every request and does not access logins, captchas, paywalls, or banned paths."""

from __future__ import annotations 

import argparse 
import csv 
import hashlib 
import json 
import logging 
import re 
import time 
from collections import Counter 
from datetime import date ,datetime 
from pathlib import Path 
from urllib .parse import urljoin ,urlparse 
from urllib .robotparser import RobotFileParser 

import requests 
from bs4 import BeautifulSoup 


USER_AGENT ="AIComputingResearchBot/1.0 (academic corpus; respectful crawler)"
START_DATE =date (2023 ,4 ,1 )
END_DATE =date (2026 ,6 ,30 )

CORE_KEYWORDS =[
"算力","智能算力","人工智能算力","AI算力","计算力","智算中心",
"智能计算中心","人工智能计算中心","算力中心","算力网络","东数西算",
"高性能计算","超级计算","超算","云算力","算力租赁","GPU云",
"GPU服务器","AI服务器","人工智能服务器","大模型训练","模型推理",
]
CONTEXT_KEYWORDS =[
"人工智能","AI","大模型","生成式人工智能","AIGC","云计算",
"云服务","数据中心","服务器","训练","推理","深度学习",
]
TECH_KEYWORDS =[
"GPU","NVIDIA","英伟达","A100","H100","H200","B100","B200",
"GH200","昇腾","寒武纪","摩尔线程","壁仞","沐曦","燧原",
"天数智芯","AI芯片","AI加速卡","HBM",
]

SITEMAPS =[
"http://www.xinhuanet.com/fortune/news_sitemap.xml",
"http://www.xinhuanet.com/tech/news_sitemap.xml",
]

# Used to verify parsing and gap months; both are public article pages and are not in the robots prohibited directory.
TEST_SEEDS =[
"https://www.chinanews.com.cn/gn/2023/04-03/9983408.shtml",
"https://www.chinanews.com.cn/gn/2023/04-21/9994235.shtml",
"https://www.sh.chinanews.com.cn/chanjing/2023-04-21/110517.shtml",
"https://jl.people.com.cn/n2/2023/0614/c349771-40456277.html",
"https://www.hb.news.cn/20231226/503526ddf20a418bab0539d73f408573/c.html",
"https://www.xj.news.cn/20240316/0cb6591845a54a5d8a0993cb911f135d/c.html",
]

DATE_PATTERNS =[
re .compile (r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})"),
re .compile (r"(20\d{2})(\d{2})(\d{2})"),
]


class PoliteSession :
    def __init__ (self ,timeout :int =25 ):
        self .session =requests .Session ()
        self .session .headers .update ({"User-Agent":USER_AGENT })
        self .timeout =timeout 
        self .robots :dict [str ,RobotFileParser ]={}
        self .last_request :dict [str ,float ]={}
        self .delays ={"people.com.cn":120.0 }

    @staticmethod 
    def _site_key (url :str )->str :
        host =urlparse (url ).netloc .lower ()
        return host [4 :]if host .startswith ("www.")else host 

    def _robots (self ,url :str )->RobotFileParser :
        parsed =urlparse (url )
        origin =f"{parsed .scheme }://{parsed .netloc }"
        if origin not in self .robots :
            rp =RobotFileParser (urljoin (origin ,"/robots.txt"))
            try :
                response =self .session .get (rp .url ,timeout =self .timeout )
                response .raise_for_status ()
                rp .parse (response .text .splitlines ())
            except requests .RequestException :
            # Adopt a conservative strategy when rules cannot be confirmed: ban all.
                rp .parse (["User-agent: *","Disallow: /"])
            self .robots [origin ]=rp 
        return self .robots [origin ]

    def get (self ,url :str )->requests .Response :
        rp =self ._robots (url )
        if not rp .can_fetch (USER_AGENT ,url ):
            raise PermissionError (f"Robots.txt does not allow access: {url }")
        site =self ._site_key (url )
        delay =rp .crawl_delay (USER_AGENT )or rp .crawl_delay ("*")or self .delays .get (site ,1.5 )
        elapsed =time .monotonic ()-self .last_request .get (site ,0.0 )
        if elapsed <delay :
            time .sleep (delay -elapsed )
        response =self .session .get (url ,timeout =self .timeout )
        self .last_request [site ]=time .monotonic ()
        response .raise_for_status ()
        if response .encoding is None or response .encoding .lower ()=="iso-8859-1":
            response .encoding =response .apparent_encoding 
        return response 


def parse_date (text :str ,url :str ="")->date |None :
    for candidate in (text ,url ):
        for pattern in DATE_PATTERNS :
            match =pattern .search (candidate )
            if not match :
                continue 
            try :
                return date (*(int (x )for x in match .groups ()))
            except ValueError :
                pass 
    return None 


def keyword_hits (text :str )->list [str ]:
    low =text .lower ()
    core =[k for k in CORE_KEYWORDS if k .lower ()in low ]
    tech =[k for k in TECH_KEYWORDS if k .lower ()in low ]
    context =[k for k in CONTEXT_KEYWORDS if k .lower ()in low ]
    return sorted (set (core +(tech if tech and context else [])))


def clean_text (value :str )->str :
    return re .sub (r"\s+"," ",value ).strip ()


def extract_article (html :str ,url :str )->dict :
    soup =BeautifulSoup (html ,"lxml")
    for tag in soup (["script","style","noscript","iframe","form","nav","footer"]):
        tag .decompose ()

    title =""
    for selector in ("meta[property='og:title']","meta[name='ArticleTitle']","h1","title"):
        node =soup .select_one (selector )
        if node :
            title =clean_text (node .get ("content","")if node .name =="meta"else node .get_text (" "))
            if title :
                break 

    date_text =""
    for selector in (
    "meta[property='article:published_time']","meta[name='PubDate']",
    "meta[name='publishdate']","meta[name='publish-date']","time",
    ".time",".date",".pubtime",".source",
    ):
        node =soup .select_one (selector )
        if node :
            date_text +=" "+(node .get ("content","")or node .get_text (" "))

    candidates =[]
    for selector in (
    "article","#detail","#content","#article",".article",".content",
    ".article-content",".main-aticle",".main_text",".left_zw",
    ):
        for node in soup .select (selector ):
            paragraphs =[clean_text (p .get_text (" "))for p in node .select ("p")]
            text ="\n".join (p for p in paragraphs if len (p )>=15 )
            if text :
                candidates .append (text )
    if not candidates :
        paragraphs =[clean_text (p .get_text (" "))for p in soup .select ("p")]
        candidates .append ("\n".join (p for p in paragraphs if len (p )>=20 ))
    content =max (candidates ,key =len ,default ="")

    source =urlparse (url ).netloc 
    source_node =soup .select_one ("meta[name='source'], meta[property='article:author']")
    if source_node and source_node .get ("content"):
        source =clean_text (source_node ["content"])

    return {
    "date":parse_date (date_text ,url ),
    "title":title ,
    "content":content ,
    "source":source ,
    "url":url ,
    }


def sitemap_urls (client :PoliteSession ,sitemap :str )->list [str ]:
    response =client .get (sitemap )
    soup =BeautifulSoup (response .content ,"xml")
    return [loc .get_text (strip =True )for loc in soup .select ("url > loc")]


def content_fingerprint (title :str ,content :str )->str :
    normalized =re .sub (r"[\W_]+","",(title +content ).lower ())
    return hashlib .sha256 (normalized .encode ("utf-8")).hexdigest ()


def run (output_dir :Path ,test :bool ,max_articles :int |None )->None :
    output_dir .mkdir (parents =True ,exist_ok =True )
    log_path =output_dir /("crawl_test.log"if test else "crawl.log")
    logging .basicConfig (
    level =logging .INFO ,
    format ="%(asctime)s %(levelname)s %(message)s",
    handlers =[logging .FileHandler (log_path ,encoding ="utf-8"),logging .StreamHandler ()],
    )

    output_path =output_dir /("AI_Computing_News_Crawler_TEST.jsonl"if test else "AI_Computing_News_Crawler_20230401_20260630.jsonl")
    failure_path =output_dir /("crawl_failures_TEST.jsonl"if test else "crawl_failures.jsonl")
    monthly_path =output_dir /("monthly_counts_TEST.csv"if test else "monthly_counts.csv")

    client =PoliteSession ()
    urls =list (TEST_SEEDS )
    if not test :
        for sitemap in SITEMAPS :
            try :
                urls .extend (sitemap_urls (client ,sitemap ))
            except Exception as exc :
                logging .error ("Sitemap failed %s: %s",sitemap ,exc )

    seed_file =output_dir /"additional_seed_urls.txt"
    if seed_file .exists ():
        urls .extend (x .strip ()for x in seed_file .read_text (encoding ="utf-8").splitlines ()if x .strip ())
    urls =list (dict .fromkeys (urls ))
    if max_articles :
        urls =urls [:max_articles ]

    seen :set [str ]=set ()
    counts =Counter ()
    saved =failed =skipped =0 
    with output_path .open ("w",encoding ="utf-8")as out ,failure_path .open ("w",encoding ="utf-8")as failures :
        for index ,url in enumerate (urls ,1 ):
            try :
            # If the URL contains a clear date, filter it first to avoid requesting historical pages outside the research range.
                url_date =parse_date ("",url )
                if url_date and not (START_DATE <=url_date <=END_DATE ):
                    skipped +=1 
                    continue 
                response =client .get (url )
                item =extract_article (response .text ,url )
                article_date =item ["date"]
                if not article_date or not (START_DATE <=article_date <=END_DATE ):
                    skipped +=1 
                    continue 
                hits =keyword_hits (item ["title"]+"\n"+item ["content"])
                if not hits or len (item ["content"])<100 :
                    skipped +=1 
                    continue 
                fingerprint =content_fingerprint (item ["title"],item ["content"])
                if fingerprint in seen :
                    skipped +=1 
                    continue 
                seen .add (fingerprint )
                record ={
                **item ,
                "date":article_date .isoformat (),
                "data_origin":"crawler",
                "keyword_hits":hits ,
                }
                out .write (json .dumps (record ,ensure_ascii =False )+"\n")
                out .flush ()
                saved +=1 
                counts [article_date .strftime ("%Y-%m")]+=1 
                logging .info ("[%d/%d] Save %s %s",index ,len (urls ),article_date ,item ["title"][:50 ])
            except Exception as exc :
                failed +=1 
                failures .write (json .dumps ({"url":url ,"error":str (exc )},ensure_ascii =False )+"\n")
                failures .flush ()
                logging .warning ("[%d/%d] failed %s: %s",index ,len (urls ),url ,exc )

    with monthly_path .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .writer (handle )
        writer .writerow (["month","count"])
        for month in sorted (counts ):
            writer .writerow ([month ,counts [month ]])
    logging .info ("Completed: Candidate=%d Save=%d Skip=%d Fail=%d",len (urls ),saved ,skipped ,failed )


if __name__ =="__main__":
    parser =argparse .ArgumentParser ()
    parser .add_argument ("--output-dir",type =Path ,required =True )
    parser .add_argument ("--test",action ="store_true")
    parser .add_argument ("--max-articles",type =int )
    args =parser .parse_args ()
    run (args .output_dir ,args .test ,args .max_articles )
