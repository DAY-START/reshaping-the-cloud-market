# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Compliant public source collector of AI computing power news.

Support:
- RSS/Atom (including public news search RSS)
- Configurable public news list page
- robots.txt check, domain-level speed limit
- Filter by research period and keyword combinations
- Text extraction, SQLite breakpoint resumption
- URL/normalized title deduplication
- JSONL, failure log, source/monthly statistics"""

from __future__ import annotations 

import argparse 
import csv 
import hashlib 
import json 
import logging 
import random 
import re 
import sqlite3 
import time 
from collections import Counter 
from dataclasses import dataclass 
from datetime import datetime 
from pathlib import Path 
from typing import Any ,Iterable 
from urllib .parse import parse_qsl ,urlencode ,urljoin ,urlparse ,urlunparse 
from urllib .robotparser import RobotFileParser 

import feedparser 
import requests 
import yaml 
from bs4 import BeautifulSoup 
from dateutil import parser as date_parser 
from requests .adapters import HTTPAdapter 
from urllib3 .util .retry import Retry 

try :
    import trafilatura 
except ImportError :
    trafilatura =None 


DEFAULT_UA ="AIComputingAcademicResearch/1.0 (+public-source collector)"
TRACKING_PARAMS ={
"spm","from","source","src","ref","referer",
"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
}


def clean_text (value :Any )->str :
    text =""if value is None else str (value )
    text =text .replace ("\u3000"," ").replace ("\xa0"," ").replace ("\u200b","")
    text =re .sub (r"\r\n?","\n",text )
    text =re .sub (r"[ \t]+"," ",text )
    text =re .sub (r"\n[ \t]+","\n",text )
    text =re .sub (r"\n{3,}","\n\n",text )
    return text .strip ()


def normalized_title (value :str )->str :
    value =clean_text (value ).lower ()
    return re .sub (r"[\W_]+","",value ,flags =re .UNICODE )


def canonical_url (value :str )->str :
    value =clean_text (value )
    if value .startswith ("//"):
        value ="https:"+value 
    parsed =urlparse (value )
    if parsed .scheme not in {"http","https"}or not parsed .netloc :
        return ""
    query =[
    (key ,val )for key ,val in parse_qsl (parsed .query ,keep_blank_values =True )
    if key .lower ()not in TRACKING_PARAMS and not key .lower ().startswith ("utm_")
    ]
    return urlunparse ((
    parsed .scheme .lower (),parsed .netloc .lower (),parsed .path or "/",
    "",urlencode (query ,doseq =True ),""
    ))


def stable_uuid (url :str )->str :
    return hashlib .sha256 (url .encode ("utf-8")).hexdigest ()[:16 ]


def normalize_date (value :Any )->str :
    if value is None or value =="":
        return ""
    if isinstance (value ,(int ,float )):
        try :
            return datetime .fromtimestamp (value ).strftime ("%Y-%m-%d")
        except (ValueError ,OSError ):
            return ""
    text =clean_text (value )
    match =re .search (r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日",text )
    if match :
        try :
            return datetime (*map (int ,match .groups ())).strftime ("%Y-%m-%d")
        except ValueError :
            return ""
    try :
        return date_parser .parse (text ,fuzzy =True ).strftime ("%Y-%m-%d")
    except (ValueError ,TypeError ,OverflowError ):
        return ""


def in_period (date_text :str ,start :str ,end :str )->bool :
    return bool (date_text )and start <=date_text <=end 


def keyword_hits (text :str ,keyword_groups :list [dict [str ,Any ]])->list [str ]:
    lower =clean_text (text ).lower ()
    hits :list [str ]=[]
    for group in keyword_groups :
        required =group .get ("all",[])
        optional =group .get ("any",[])
        excluded =group .get ("exclude",[])
        if required and not all (str (word ).lower ()in lower for word in required ):
            continue 
        if optional and not any (str (word ).lower ()in lower for word in optional ):
            continue 
        if excluded and any (str (word ).lower ()in lower for word in excluded ):
            continue 
        for word in required +optional :
            if str (word ).lower ()in lower and word not in hits :
                hits .append (str (word ))
    return hits 


class StateDB :
    def __init__ (self ,path :Path ):
        self .conn =sqlite3 .connect (path )
        self .conn .execute ("""
            CREATE TABLE IF NOT EXISTS items(
                canonical_url TEXT PRIMARY KEY,
                title_key TEXT,
                status TEXT NOT NULL,
                error TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        self .conn .execute (
        "CREATE INDEX IF NOT EXISTS idx_items_title ON items(title_key)"
        )
        self .conn .commit ()

    def seen_url (self ,url :str )->bool :
        return self .conn .execute (
        "SELECT 1 FROM items WHERE canonical_url=?",(url ,)
        ).fetchone ()is not None 

    def seen_title (self ,title :str )->bool :
        key =normalized_title (title )
        if not key :
            return False 
        return self .conn .execute (
        "SELECT 1 FROM items WHERE title_key=? AND status='success'",(key ,)
        ).fetchone ()is not None 

    def save (self ,url :str ,title :str ,status :str ,error :str ="")->None :
        self .conn .execute ("""
            INSERT OR REPLACE INTO items
            (canonical_url,title_key,status,error,updated_at)
            VALUES(?,?,?,?,?)
        """,(
        url ,normalized_title (title ),status ,error ,
        datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
        ))
        self .conn .commit ()


class PublicHttpClient :
    def __init__ (self ,config :dict [str ,Any ]):
        self .user_agent =config .get ("user_agent",DEFAULT_UA )
        self .timeout =int (config .get ("timeout_seconds",25 ))
        self .min_delay =float (config .get ("min_delay_seconds",1.5 ))
        self .max_delay =float (config .get ("max_delay_seconds",3.0 ))
        self .robots_cache :dict [str ,RobotFileParser |None ]={}
        self .last_request :dict [str ,float ]={}
        self .session =requests .Session ()
        retries =Retry (
        total =int (config .get ("retries",3 )),
        backoff_factor =1.2 ,
        status_forcelist =[429 ,500 ,502 ,503 ,504 ],
        allowed_methods =["GET"],
        raise_on_status =False ,
        )
        adapter =HTTPAdapter (max_retries =retries ,pool_connections =10 ,pool_maxsize =10 )
        self .session .mount ("http://",adapter )
        self .session .mount ("https://",adapter )
        self .session .headers .update ({
        "User-Agent":self .user_agent ,
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"zh-CN,zh;q=0.9,en;q=0.6",
        })

    def _robots (self ,url :str )->RobotFileParser |None :
        parsed =urlparse (url )
        root =f"{parsed .scheme }://{parsed .netloc }"
        if root in self .robots_cache :
            return self .robots_cache [root ]
        rp =RobotFileParser ()
        rp .set_url (root +"/robots.txt")
        try :
            response =self .session .get (rp .url ,timeout =min (self .timeout ,10 ))
            if response .status_code ==200 :
                rp .parse (response .text .splitlines ())
                self .robots_cache [root ]=rp 
            else :
                self .robots_cache [root ]=None 
        except requests .RequestException :
            self .robots_cache [root ]=None 
        return self .robots_cache [root ]

    def get (self ,url :str ,*,check_robots :bool =True )->requests .Response :
        if check_robots :
            rp =self ._robots (url )
            if rp is not None and not rp .can_fetch (self .user_agent ,url ):
                raise PermissionError ("robots.txt 不允许该采集器访问")
        domain =urlparse (url ).netloc .lower ()
        elapsed =time .time ()-self .last_request .get (domain ,0 )
        target_delay =random .uniform (self .min_delay ,self .max_delay )
        if elapsed <target_delay :
            time .sleep (target_delay -elapsed )
        response =self .session .get (url ,timeout =self .timeout ,allow_redirects =True )
        self .last_request [domain ]=time .time ()
        if response .status_code !=200 :
            raise RuntimeError (f"HTTP {response .status_code }")
        content_type =response .headers .get ("Content-Type","").lower ()
        if content_type and not any (x in content_type for x in ("html","xml","rss","atom")):
            raise RuntimeError (f"Unsupported content types: {content_type }")
        response .encoding =response .apparent_encoding or response .encoding 
        return response 


@dataclass 
class Candidate :
    url :str 
    title :str =""
    date :str =""
    source :str =""
    summary :str =""


def discover_rss (source :dict [str ,Any ],client :PublicHttpClient )->Iterable [Candidate ]:
    response =client .get (source ["url"],check_robots =source .get ("check_robots",True ))
    feed =feedparser .parse (response .content )
    for entry in feed .entries :
        link =canonical_url (entry .get ("link",""))
        if not link :
            continue 
        yield Candidate (
        url =link ,
        title =clean_text (entry .get ("title","")),
        date =normalize_date (
        entry .get ("published")or entry .get ("updated")or entry .get ("created")
        ),
        source =clean_text (source .get ("name","")or feed .feed .get ("title","")),
        summary =clean_text (entry .get ("summary","")),
        )


def discover_list (source :dict [str ,Any ],client :PublicHttpClient )->Iterable [Candidate ]:
    response =client .get (source ["url"],check_robots =source .get ("check_robots",True ))
    soup =BeautifulSoup (response .text ,"lxml")
    item_selector =source ["selectors"]["item"]
    for item in soup .select (item_selector ):
        link_node =item .select_one (source ["selectors"].get ("link","a"))
        if not link_node :
            continue 
        link =canonical_url (urljoin (source ["url"],link_node .get ("href","")))
        if not link :
            continue 
        title_node =item .select_one (source ["selectors"].get ("title","a"))
        date_node =item .select_one (source ["selectors"].get ("date","time"))
        yield Candidate (
        url =link ,
        title =clean_text (title_node .get_text (" ",strip =True )if title_node else ""),
        date =normalize_date (date_node .get_text (" ",strip =True )if date_node else ""),
        source =clean_text (source .get ("name","")),
        )


def metadata_from_html (html :str )->tuple [str ,str ,str ]:
    soup =BeautifulSoup (html ,"lxml")
    title =""
    for attrs in (
    {"property":"og:title"},{"name":"twitter:title"},
    {"name":"title"},{"itemprop":"headline"},
    ):
        tag =soup .find ("meta",attrs =attrs )
        if tag and tag .get ("content"):
            title =clean_text (tag ["content"])
            break 
    if not title :
        h1 =soup .find ("h1")
        title =clean_text (h1 .get_text (" ",strip =True )if h1 else "")
    if not title and soup .title :
        title =clean_text (soup .title .get_text (" ",strip =True ))

    date_text =""
    for attrs in (
    {"property":"article:published_time"},{"name":"publishdate"},
    {"name":"pubdate"},{"name":"date"},{"itemprop":"datePublished"},
    ):
        tag =soup .find ("meta",attrs =attrs )
        if tag :
            date_text =normalize_date (tag .get ("content",""))
            if date_text :
                break 
    if not date_text :
        tag =soup .find ("time")
        if tag :
            date_text =normalize_date (tag .get ("datetime")or tag .get_text (" ",strip =True ))

    source =""
    tag =soup .find ("meta",attrs ={"property":"og:site_name"})
    if tag :
        source =clean_text (tag .get ("content",""))
    return title ,date_text ,source 


def extract_content (html :str ,url :str ,min_length :int )->str :
    if trafilatura is not None :
        text =trafilatura .extract (
        html ,url =url ,include_comments =False ,include_tables =False ,
        include_links =False ,favor_precision =True ,deduplicate =True ,
        )
        text =clean_text (text )
        if len (text )>=min_length :
            return text 
    soup =BeautifulSoup (html ,"lxml")
    for node in soup (["script","style","noscript","iframe","nav","footer","header","aside"]):
        node .decompose ()
    selectors =[
    "article",".article-content",".article_body",".article-body",
    ".news-content",".detail-content",".main-content",".TRS_Editor",
    "#articleContent","#article-content","#content",
    ]
    candidates =[
    clean_text (node .get_text ("\n",strip =True ))
    for selector in selectors for node in soup .select (selector )
    ]
    candidates =[text for text in candidates if len (text )>=min_length ]
    if candidates :
        return max (candidates ,key =len )
    paragraphs =[
    clean_text (node .get_text (" ",strip =True ))
    for node in soup .find_all ("p")
    ]
    return clean_text ("\n".join (text for text in paragraphs if len (text )>=15 ))


def write_jsonl (handle ,record :dict [str ,Any ])->None :
    handle .write (json .dumps (record ,ensure_ascii =False )+"\n")


def write_stats (output_dir :Path ,source_counts :Counter ,month_counts :Counter )->None :
    for filename ,header ,values in (
    ("source_counts.csv",("source","count"),source_counts ),
    ("monthly_counts.csv",("month","count"),month_counts ),
    ):
        with (output_dir /filename ).open ("w",encoding ="utf-8-sig",newline ="")as handle :
            writer =csv .writer (handle )
            writer .writerow (header )
            writer .writerows (sorted (values .items ()))


def load_existing_stats (output_file :Path )->tuple [Counter ,Counter ]:
    sources ,months =Counter (),Counter ()
    if not output_file .exists ():
        return sources ,months 
    with output_file .open ("r",encoding ="utf-8")as handle :
        for line in handle :
            try :
                row =json .loads (line )
                sources [row .get ("source","")or "unknown"]+=1 
                date_text =row .get ("date","")
                if len (date_text )>=7 :
                    months [date_text [:7 ]]+=1 
            except (json .JSONDecodeError ,TypeError ):
                continue 
    return sources ,months 


def run (
config_path :Path ,
limit :int |None ,
dry_run :bool ,
start_override :str |None =None ,
end_override :str |None =None ,
progress_every :int =10 ,
)->None :
    config =yaml .safe_load (config_path .read_text (encoding ="utf-8"))
    output_dir =(config_path .parent /config ["output"]["directory"]).resolve ()
    output_dir .mkdir (parents =True ,exist_ok =True )
    output_file =output_dir /config ["output"].get ("jsonl","AI_Computing_Web_News.jsonl")
    failure_file =output_dir /config ["output"].get ("failures","web_failures.jsonl")
    state =StateDB (output_dir /config ["output"].get ("state","web_state.sqlite3"))
    client =PublicHttpClient (config .get ("http",{}))
    start =start_override or config ["research_period"]["start"]
    end =end_override or config ["research_period"]["end"]
    if not re .fullmatch (r"\d{4}-\d{2}-\d{2}",start ):
        raise ValueError ("--start must be in YYYY-MM-DD format")
    if not re .fullmatch (r"\d{4}-\d{2}-\d{2}",end ):
        raise ValueError ("--end must be in YYYY-MM-DD format")
    if start >end :
        raise ValueError ("Start date cannot be later than end date")
    min_length =int (config .get ("filters",{}).get ("min_content_length",100 ))
    groups =config ["keyword_groups"]
    source_counts ,month_counts =load_existing_stats (output_file )
    counters =Counter ()

    logging .basicConfig (
    level =logging .INFO ,
    format ="%(asctime)s | %(levelname)s | %(message)s",
    handlers =[
    logging .FileHandler (output_dir /"web_collector.log",encoding ="utf-8"),
    logging .StreamHandler (),
    ],
    )

    with output_file .open ("a",encoding ="utf-8")as out ,failure_file .open ("a",encoding ="utf-8")as failures :
        stop =False 
        for source in config ["sources"]:
            if not source .get ("enabled",True ):
                continue 
            print (f"\n[Start from source] {source .get ('name','unnamed source')}")
            source_seen =0 
            try :
                discover =discover_rss if source ["type"]=="rss"else discover_list 
                candidates =discover (source ,client )
                for candidate in candidates :
                    source_seen +=1 
                    counters ["discovered"]+=1 
                    if source_seen ==1 or source_seen %max (progress_every ,1 )==0 :
                        print (
                        f"[Discovering progress] {source .get ('name')}: {source_seen } items; processing this round {counters ['processed']}; saving {counters ['success']}; out of time {counters ['outside_period']}; failure {counters ['failed']}"
                        )
                    if limit is not None and counters ["processed"]>=limit :
                        stop =True 
                        break 
                    if state .seen_url (candidate .url ):
                        counters ["skipped_url"]+=1 
                        continue 
                    discovery_hits =keyword_hits (
                    f"{candidate .title }\n{candidate .summary }",groups 
                    )
                    if not discovery_hits :
                        state .save (candidate .url ,candidate .title ,"irrelevant_discovery")
                        counters ["irrelevant_discovery"]+=1 
                        continue 
                    counters ["processed"]+=1 
                    try :
                        response =client .get (
                        candidate .url ,
                        check_robots =source .get ("check_robots",True ),
                        )
                        html =response .text 
                        html_title ,html_date ,html_source =metadata_from_html (html )
                        title =candidate .title or html_title 
                        date_text =candidate .date or html_date 
                        source_name =candidate .source or html_source or urlparse (candidate .url ).netloc 
                        if not in_period (date_text ,start ,end ):
                            state .save (candidate .url ,title ,"outside_period")
                            counters ["outside_period"]+=1 
                            continue 
                        if state .seen_title (title ):
                            state .save (candidate .url ,title ,"duplicate_title")
                            counters ["duplicate_title"]+=1 
                            continue 
                        content =extract_content (html ,candidate .url ,min_length )
                        hits =keyword_hits (f"{title }\n{content }",groups )
                        if len (content )<min_length :
                            raise ValueError (f"Text less than {min_length } characters")
                        if not hits :
                            state .save (candidate .url ,title ,"irrelevant_fulltext")
                            counters ["irrelevant_fulltext"]+=1 
                            continue 
                        record ={
                        "uuid":stable_uuid (candidate .url ),
                        "date":date_text ,
                        "title":title ,
                        "content":content ,
                        "source":source_name ,
                        "url":candidate .url ,
                        "data_origin":"public_web",
                        "keyword_hits":hits ,
                        "crawl_time":datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
                        }
                        if not dry_run :
                            write_jsonl (out ,record )
                            out .flush ()
                        state .save (candidate .url ,title ,"success")
                        counters ["success"]+=1 
                        source_counts [source_name ]+=1 
                        month_counts [date_text [:7 ]]+=1 
                        print (f"[Save] {counters ['success']} {date_text } {title [:60 ]}")
                    except Exception as exc :
                        error =str (exc )
                        failure ={
                        "url":candidate .url ,"title":candidate .title ,
                        "source":candidate .source ,"error":error ,
                        "crawl_time":datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
                        }
                        if not dry_run :
                            write_jsonl (failures ,failure )
                            failures .flush ()
                        state .save (candidate .url ,candidate .title ,"failed",error )
                        counters ["failed"]+=1 
                        logging .warning ("Failure %s | %s",candidate .url ,error )
            except Exception as exc :
                counters ["source_failed"]+=1 
                logging .error ("Source failed %s | %s",source .get ("name"),exc )
                print (f"[Source failed] {source .get ('name')}: {exc }")
            else :
                print (
                f"[Source completed] {source .get ('name')}: found {source_seen } items; accumulated {counters ['success']} items saved"
                )
            if stop :
                break 
    write_stats (output_dir ,source_counts ,month_counts )
    report ={
    "finished_at":datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
    "research_period":{"start":start ,"end":end },
    "dry_run":dry_run ,
    "counts":dict (counters ),
    "output":str (output_file ),
    }
    (output_dir /"run_report.json").write_text (
    json .dumps (report ,ensure_ascii =False ,indent =2 ),encoding ="utf-8"
    )
    print (json .dumps (report ,ensure_ascii =False ,indent =2 ))


def main ()->None :
    parser =argparse .ArgumentParser (description ="AI computing power public news collector")
    parser .add_argument ("--config",type =Path ,default =Path (__file__ ).with_name ("sources.example.yaml"))
    parser .add_argument ("--limit",type =int ,help ="The maximum number of candidate texts crawled in this round")
    parser .add_argument ("--dry-run",action ="store_true",help ="Test but not write formal JSONL/failure file")
    parser .add_argument ("--start",help ="Override the start date in the configuration, format YYYY-MM-DD")
    parser .add_argument ("--end",help ="Override the end date in the configuration, format YYYY-MM-DD")
    parser .add_argument ("--progress-every",type =int ,default =10 ,help ="Show progress every time how many items are found")
    args =parser .parse_args ()
    run (
    args .config .resolve (),
    args .limit ,
    args .dry_run ,
    args .start ,
    args .end ,
    args .progress_every ,
    )


if __name__ =="__main__":
    main ()
