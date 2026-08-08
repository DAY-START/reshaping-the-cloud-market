# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================


"""AI computing power news text completion program v2

Input:
AI_Computing_News_THS_20210701_20260630.jsonl

Output:
AI_Computing_News_THS_Fulltext.jsonl

Function:
1. Automatic completion of news text
2. SQLite breakpoint resume
3. Record of failure reasons
4. Enhanced analysis of domestic news stations
5. Support limit testing"""

from __future__ import annotations 

import argparse 
import hashlib 
import json 
import random 
import re 
import sqlite3 
import time 

from datetime import datetime 
from pathlib import Path 
from urllib .parse import urlparse 

import requests 
from bs4 import BeautifulSoup 


# ===============================
# Path configuration
# ===============================

BASE_DIR =Path (__file__ ).resolve ().parent 


INPUT_FILE =(
BASE_DIR /
"AI_Computing_News_THS_20210701_20260630.jsonl"
)


OUTPUT_FILE =(
BASE_DIR /
"AI_Computing_News_THS_Fulltext.jsonl"
)


FAIL_FILE =(
BASE_DIR /
"fulltext_failures.jsonl"
)


STATE_FILE =(
BASE_DIR /
"fulltext_state.sqlite3"
)



# ===============================
# Request configuration
# ===============================

USER_AGENT =(
"Mozilla/5.0 "
"(Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 "
"(KHTML, like Gecko) "
"Chrome/131 Safari/537.36"
)


REQUEST_HEADERS ={

"User-Agent":
USER_AGENT ,

"Accept":
(
"text/html,"
"application/xhtml+xml,"
"application/xml;q=0.9,"
"*/*;q=0.8"
),

"Accept-Language":
"zh-CN,zh;q=0.9",

"Connection":
"keep-alive"

}



RETRY_TIMES =5 

TIMEOUT =30 



SLEEP_MIN =1.5 

SLEEP_MAX =3.5 



# ===============================
# Basic functions
# ===============================

def clean_text (text ):

    if not text :

        return ""


    text =str (text )


    text =(
    text 
    .replace ("\u3000"," ")
    .replace ("\xa0"," ")
    )


    text =re .sub (
    r"\s+",
    " ",
    text 
    )


    return text .strip ()



def md5_id (text ):

    return hashlib .md5 (
    text .encode (
    "utf-8"
    )
    ).hexdigest ()



def get_field (data ,names ):

    for name in names :

        if (
        name in data 
        and data [name ]
        ):

            return data [name ]


    return ""



def get_url (data ):

    return clean_text (
    get_field (
    data ,
    [
    "url",
    "news_url",
    "article_url",
    "link"
    ]
    )
    )



    # ===============================
    # SQLite state management
    # ===============================

class StateDB :


    def __init__ (self ,path ):

        self .conn =sqlite3 .connect (
        path 
        )

        self .init ()



    def init (self ):

        self .conn .execute (
        """
            CREATE TABLE IF NOT EXISTS state
            (
                url TEXT PRIMARY KEY,
                status TEXT,
                update_time TEXT
            )
            """
        )

        self .conn .commit ()



    def checked (self ,url ):

        cur =self .conn .execute (
        "SELECT url FROM state WHERE url=?",
        (url ,)
        )

        return (
        cur .fetchone ()
        is not None 
        )



    def save (self ,url ,status ):

        self .conn .execute (
        """
            INSERT OR REPLACE
            INTO state
            VALUES (?,?,?)
            """,
        (
        url ,
        status ,
        datetime .now ()
        .strftime (
        "%Y-%m-%d %H:%M:%S"
        )
        )
        )

        self .conn .commit ()



        # ===============================
        # HTTP access
        # ===============================

class NewsClient :


    def __init__ (self ):

        self .session =requests .Session ()

        self .session .headers .update (
        REQUEST_HEADERS 
        )


    def get (self ,url ):

    # WeChat public account is temporarily skipped

        if (
        "mp.weixin.qq.com"
        in url 
        ):

            raise Exception (
            "WeChat public accounts are not crawled yet"
            )



        last_error =""


        for i in range (
        RETRY_TIMES 
        ):

            try :

                r =self .session .get (
                url ,
                timeout =TIMEOUT ,
                allow_redirects =True 
                )


                if r .status_code !=200 :

                    raise Exception (
                    f"HTTP {r .status_code }"
                    )


                r .encoding =(
                r .apparent_encoding 
                or 
                r .encoding 
                )


                return r .text 



            except Exception as e :

                last_error =str (e )


                time .sleep (
                2 +i 
                )


        raise Exception (
        last_error 
        )
        # ===============================
        # HTML text parsing
        # ===============================

def extract_title (html ,old_title =""):

    if old_title :

        return clean_text (
        old_title 
        )


    soup =BeautifulSoup (
    html ,
    "lxml"
    )


    # meta title

    for attrs in [

    {"property":"og:title"},

    {"name":"title"}

    ]:

        tag =soup .find (
        "meta",
        attrs =attrs 
        )

        if tag :

            value =tag .get (
            "content",
            ""
            )

            if value :

                return clean_text (
                value 
                )



    h1 =soup .find (
    "h1"
    )


    if h1 :

        return clean_text (
        h1 .get_text ()
        )



    if soup .title :

        return clean_text (
        soup .title .text 
        )


    return ""



def extract_date (
html ,
old_date =""
):

    if old_date :

        return clean_text (
        old_date 
        )


    text =BeautifulSoup (
    html ,
    "lxml"
    ).get_text (
    " ",
    strip =True 
    )


    patterns =[

    r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}",

    r"20\d{2}年\d{1,2}月\d{1,2}日"

    ]


    for p in patterns :

        m =re .search (
        p ,
        text 
        )

        if m :

            return m .group ()



    return ""



def extract_source (url ,old =""):

    if old :

        return old 


    return urlparse (
    url 
    ).netloc .replace (
    "www.",
    ""
    )



def extract_content (html ):

    soup =BeautifulSoup (
    html ,
    "lxml"
    )


    # Delete invalid area

    for tag in soup .find_all (
    [
    "script",
    "style",
    "iframe",
    "nav",
    "footer",
    "header"
    ]
    ):

        tag .decompose ()



    selectors =[

    "article",

    ".article",

    ".article-content",

    ".article_body",

    ".article-body",

    ".content",

    ".news-content",

    ".detail-content",

    ".TRS_Editor",

    ".xl-main",

    "#content",

    "#article"

    ]



    contents =[]


    for selector in selectors :

        for node in soup .select (
        selector 
        ):

            text =clean_text (
            node .get_text (
            "\n"
            )
            )


            if len (text )>100 :

                contents .append (
                text 
                )



    if contents :

        return max (
        contents ,
        key =len 
        )



        # Alternate: all paragraphs

    paragraphs =[]


    for p in soup .find_all (
    "p"
    ):

        text =clean_text (
        p .get_text ()
        )

        if len (text )>20 :

            paragraphs .append (
            text 
            )



    return clean_text (
    "\n".join (
    paragraphs 
    )
    )



    # ===============================
    # AI keywords
    # ===============================

AI_KEYWORDS =[

"算力",
"智能算力",
"智算中心",
"数据中心",
"云计算",
"人工智能",
"AI",
"大模型",
"生成式人工智能",
"GPU",
"AI芯片",
"服务器",
"高性能计算",
"超级计算",
"超算中心",
"东数西算",
"算力网络",
"算力基础设施",
"AIGC",
"英伟达",
"NVIDIA",
"昇腾",
"寒武纪",
"国产GPU"

]



def keyword_hits (text ):

    result =[]


    text =text .lower ()


    for k in AI_KEYWORDS :

        if k .lower ()in text :

            result .append (
            k 
            )


    return result 



    # ===============================
    # Single news processing
    # ===============================

def process_news (
item ,
client 
):


    url =get_url (
    item 
    )


    if not url :

        raise Exception (
        "URL is empty"
        )


    html =client .get (
    url 
    )


    content =extract_content (
    html 
    )


    if len (content )<80 :

        raise Exception (
        "Text too short"
        )



    title =extract_title (
    html ,
    get_field (
    item ,
    [
    "title",
    "news_title"
    ]
    )
    )



    date =extract_date (
    html ,
    get_field (
    item ,
    [
    "date",
    "publish_time"
    ]
    )
    )



    source =extract_source (
    url ,
    get_field (
    item ,
    [
    "source",
    "media"
    ]
    )
    )



    text =(
    title 
    +
    "\n"
    +
    content 
    )



    return {

    "uuid":
    item .get (
    "uuid",
    md5_id (url )
    ),

    "url":
    url ,

    "title":
    title ,

    "date":
    date ,

    "source":
    source ,

    "content":
    content ,

    "keyword_hits":
    keyword_hits (
    text 
    ),

    "crawl_time":
    datetime .now ()
    .strftime (
    "%Y-%m-%d %H:%M:%S"
    )

    }
    # ===============================
    # JSONL reading
    # ===============================

def read_jsonl (path ):

    with open (
    path ,
    "r",
    encoding ="utf-8-sig"
    )as f :

        for line in f :

            line =line .strip ()

            if not line :
                continue 

            try :

                yield json .loads (
                line 
                )

            except Exception :

                continue 



                # ===============================
                # Save JSONL
                # ===============================

def append_jsonl (path ,data ):

    with open (
    path ,
    "a",
    encoding ="utf-8"
    )as f :

        f .write (
        json .dumps (
        data ,
        ensure_ascii =False 
        )
        +
        "\n"
        )



        # ===============================
        # Run in batches
        # ===============================

def run (
input_file ,
output_file ,
fail_file ,
state_file ,
limit =None 
):


    state =StateDB (
    state_file 
    )


    client =NewsClient ()


    total =0 

    success =0 

    failed =0 



    for item in read_jsonl (
    input_file 
    ):


        if limit and total >=limit :

            break 



        url =get_url (
        item 
        )


        if not url :

            continue 



            # Already processed

        if state .checked (
        url 
        ):

            continue 



        total +=1 


        try :

            result =process_news (
            item ,
            client 
            )


            append_jsonl (
            output_file ,
            result 
            )


            state .save (
            url ,
            "success"
            )


            success +=1 


            print (
            f"[Save] {success } {result .get ('date','')} {result .get ('title','')[:60 ]}"
            )



        except Exception as e :


            error ={

            "uuid":
            item .get (
            "uuid",
            ""
            ),

            "url":
            url ,

            "title":
            item .get (
            "title",
            ""
            ),

            "error":
            str (e ),

            "time":
            datetime .now ()
            .strftime (
            "%Y-%m-%d %H:%M:%S"
            )

            }



            append_jsonl (
            fail_file ,
            error 
            )


            state .save (
            url ,
            "failed"
            )


            failed +=1 


            print (
            f"[Failure]{url }{e }"
            )



        time .sleep (
        random .uniform (
        SLEEP_MIN ,
        SLEEP_MAX 
        )
        )



    print (
    "\n=============================="
    )

    print (
    f"Processing this round = {total }"
    )

    print (
    f"Add new text={success }"
    )

    print (
    f"New addition failed={failed }"
    )

    print (
    "=============================="
    )



    # ===============================
    # main program
    # ===============================

def main ():


    parser =argparse .ArgumentParser (
    description =
    "AI computing power news text completion program"
    )


    parser .add_argument (
    "--input",
    type =Path ,
    default =INPUT_FILE 
    )


    parser .add_argument (
    "--output",
    type =Path ,
    default =OUTPUT_FILE 
    )


    parser .add_argument (
    "--failures",
    type =Path ,
    default =FAIL_FILE 
    )


    parser .add_argument (
    "--state",
    type =Path ,
    default =STATE_FILE 
    )


    parser .add_argument (
    "--limit",
    type =int ,
    default =None 
    )


    args =parser .parse_args ()



    print (
    "=============================="
    )

    print (
    "AI computing power news text completion v2"
    )

    print (
    "enter:",
    args .input 
    )

    print (
    "Output:",
    args .output 
    )

    print (
    "=============================="
    )



    run (

    args .input ,

    args .output ,

    args .failures ,

    args .state ,

    args .limit 

    )



if __name__ =="__main__":

    main ()
