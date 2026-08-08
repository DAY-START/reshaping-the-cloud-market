# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""AI computing power news history retrospective collector.

Candidate sources:
1. seed_file: The user already has a CSV/JSONL URL list (the most stable)
2. gdelt: GDELT DOC 2.0 public news index (only covers its current searchable window)
3. list: Public history list page that is allowed to be automatically accessed after confirmation

Body access always respects the target site's robots.txt and does not handle logins, CAPTCHAs, or paywalls."""

from __future__ import annotations 

import argparse 
import base64 
import csv 
import json 
import logging 
import re 
import sqlite3 
import sys 
import time 
from calendar import monthrange 
from collections import Counter 
from dataclasses import dataclass 
from datetime import date ,datetime ,timedelta 
from pathlib import Path 
from typing import Any ,Iterable ,Iterator 
from urllib .parse import parse_qs ,urlencode ,urljoin ,urlparse 

import yaml 
import feedparser 
from bs4 import BeautifulSoup 

from ai_computing_web_collector import (
PublicHttpClient ,
canonical_url ,
clean_text ,
extract_content ,
in_period ,
keyword_hits ,
metadata_from_html ,
normalize_date ,
normalized_title ,
stable_uuid ,
write_jsonl ,
)

# Windows consoles often have multiple code pages at the same time, and UTF-8 is explicitly fixed to prevent Chinese from becoming "Qi Jie Kui...".
if hasattr (sys .stdout ,"reconfigure"):
    sys .stdout .reconfigure (encoding ="utf-8",errors ="replace")
if hasattr (sys .stderr ,"reconfigure"):
    sys .stderr .reconfigure (encoding ="utf-8",errors ="replace")


@dataclass 
class Candidate :
    url :str 
    title :str =""
    date :str =""
    source :str =""
    provider :str =""


def month_windows (start_text :str ,end_text :str )->Iterator [tuple [str ,str ]]:
    start =datetime .strptime (start_text ,"%Y-%m-%d").date ()
    end =datetime .strptime (end_text ,"%Y-%m-%d").date ()
    cursor =start .replace (day =1 )
    while cursor <=end :
        last =date (cursor .year ,cursor .month ,monthrange (cursor .year ,cursor .month )[1 ])
        yield max (cursor ,start ).isoformat (),min (last ,end ).isoformat ()
        cursor =(last +timedelta (days =1 )).replace (day =1 )


class HistoryState :
    def __init__ (self ,path :Path ):
        self .conn =sqlite3 .connect (path )
        self .conn .execute ("""
            CREATE TABLE IF NOT EXISTS items(
                url TEXT PRIMARY KEY,
                title_key TEXT,
                status TEXT NOT NULL,
                error TEXT,
                provider TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        self .conn .execute (
        "CREATE INDEX IF NOT EXISTS idx_history_title ON items(title_key)"
        )
        self .conn .execute ("""
            CREATE TABLE IF NOT EXISTS provider_windows(
                provider TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, window_start, window_end)
            )
        """)
        self .conn .commit ()

    def seen_url (self ,url :str )->bool :
        return self .conn .execute (
        "SELECT 1 FROM items WHERE url=? AND status<>'candidate'",(url ,)
        ).fetchone ()is not None 

    def seen_title (self ,title :str )->bool :
        key =normalized_title (title )
        if not key :
            return False 
        return self .conn .execute (
        "SELECT 1 FROM items WHERE title_key=? AND status='success'",(key ,)
        ).fetchone ()is not None 

    def save_item (
    self ,url :str ,title :str ,status :str ,provider :str ,error :str =""
    )->None :
        self .conn .execute ("""
            INSERT OR REPLACE INTO items
            (url,title_key,status,error,provider,updated_at)
            VALUES(?,?,?,?,?,?)
        """,(
        url ,normalized_title (title ),status ,error ,provider ,
        datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
        ))
        self .conn .commit ()

    def window_done (self ,provider :str ,start :str ,end :str )->bool :
        return self .conn .execute ("""
            SELECT 1 FROM provider_windows
            WHERE provider=? AND window_start=? AND window_end=? AND status='done'
        """,(provider ,start ,end )).fetchone ()is not None 

    def save_window (self ,provider :str ,start :str ,end :str ,status :str )->None :
        self .conn .execute ("""
            INSERT OR REPLACE INTO provider_windows
            VALUES(?,?,?,?,?)
        """,(
        provider ,start ,end ,status ,
        datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
        ))
        self .conn .commit ()


def load_existing_dedup (paths :list [str ],base :Path )->tuple [set [str ],set [str ]]:
    urls :set [str ]=set ()
    titles :set [str ]=set ()
    for raw_path in paths :
        path =Path (raw_path )
        if not path .is_absolute ():
            path =(base /path ).resolve ()
        if not path .exists ():
            continue 
        print (f"[Load the deduplication library] {path }")
        with path .open ("r",encoding ="utf-8-sig",errors ="replace")as handle :
            for line in handle :
                try :
                    row =json .loads (line )
                except json .JSONDecodeError :
                    continue 
                url =canonical_url (row .get ("url",""))
                title =normalized_title (row .get ("title",""))
                if url :
                    urls .add (url )
                if title :
                    titles .add (title )
    print (f"[Removal of duplicate database completed] URL={len (urls )} Title={len (titles )}")
    return urls ,titles 


def discover_seed_file (provider :dict [str ,Any ],base :Path )->Iterable [Candidate ]:
    path =Path (provider ["path"])
    if not path .is_absolute ():
        path =(base /path ).resolve ()
    if not path .exists ():
        raise FileNotFoundError (f"The seed file does not exist: {path }")
    if path .suffix .lower ()==".csv":
        with path .open ("r",encoding ="utf-8-sig",newline ="")as handle :
            for row in csv .DictReader (handle ):
                url =canonical_url (
                row .get ("url")or row .get ("news_url")or row .get ("link")or ""
                )
                if url :
                    yield Candidate (
                    url =url ,
                    title =clean_text (row .get ("title","")),
                    date =normalize_date (row .get ("date")or row .get ("publish_time")),
                    source =clean_text (row .get ("source","")),
                    provider =provider ["name"],
                    )
    else :
        with path .open ("r",encoding ="utf-8-sig")as handle :
            for line in handle :
                try :
                    row =json .loads (line )
                except json .JSONDecodeError :
                    continue 
                url =canonical_url (
                row .get ("url")or row .get ("news_url")or row .get ("link")or ""
                )
                if url :
                    yield Candidate (
                    url =url ,
                    title =clean_text (row .get ("title","")),
                    date =normalize_date (row .get ("date")or row .get ("publish_time")),
                    source =clean_text (row .get ("source","")),
                    provider =provider ["name"],
                    )


def discover_gdelt (
provider :dict [str ,Any ],
client :PublicHttpClient ,
start :str ,
end :str ,
)->Iterable [Candidate ]:
    endpoint =provider .get (
    "endpoint","https://api.gdeltproject.org/api/v2/doc/doc"
    )
    max_records =min (int (provider .get ("max_records",250 )),250 )
    for query in provider ["queries"]:
        params ={
        "query":query ,
        "mode":"artlist",
        "format":"json",
        "maxrecords":max_records ,
        "sort":provider .get ("sort","DateAsc"),
        "startdatetime":start .replace ("-","")+"000000",
        "enddatetime":end .replace ("-","")+"235959",
        }
        url =endpoint +"?"+urlencode (params )
        response =client .get (url ,check_robots =False )
        try :
            payload =response .json ()
        except ValueError as exc :
            raise RuntimeError (f"GDELT returns non-JSON: {response .text [:200 ]}")from exc 
        for article in payload .get ("articles",[]):
            article_url =canonical_url (article .get ("url",""))
            if not article_url :
                continue 
            yield Candidate (
            url =article_url ,
            title =clean_text (article .get ("title","")),
            date =normalize_date (article .get ("seendate","")),
            source =clean_text (article .get ("domain","")),
            provider =provider ["name"],
            )


def discover_list (
provider :dict [str ,Any ],
client :PublicHttpClient ,
start :str ,
end :str ,
)->Iterable [Candidate ]:
    selectors =provider ["selectors"]
    start_page =int (provider .get ("start_page",1 ))
    end_page =int (provider .get ("end_page",start_page ))
    for page in range (start_page ,end_page +1 ):
        if page ==start_page and provider .get ("first_url"):
            list_url =provider ["first_url"]
        else :
            list_url =provider ["url_template"].format (
            page =page ,start =start ,end =end ,
            start_compact =start .replace ("-",""),
            end_compact =end .replace ("-",""),
            )
        try :
            response =client .get (
            list_url ,check_robots =provider .get ("check_robots",True )
            )
        except RuntimeError as exc :
            if "HTTP 404"in str (exc )and provider .get ("stop_on_empty",True ):
                print (f"[List stop] {provider ['name']} page={page } Return 404")
                break 
            raise 
        soup =BeautifulSoup (response .text ,"lxml")
        items =soup .select (selectors ["item"])
        print (f"[List page] {provider ['name']} page={page } Discovery={len (items )}")
        if not items and provider .get ("stop_on_empty",True ):
            break 
        page_dates :list [str ]=[]
        prepared :list [Candidate ]=[]
        for item in items :
            link_node =(
            item if getattr (item ,"name","")=="a"
            else item .select_one (selectors .get ("link","a"))
            )
            if not link_node :
                continue 
            url =canonical_url (urljoin (list_url ,link_node .get ("href","")))
            if not url :
                continue 
            title_node =(
            item if getattr (item ,"name","")=="a"
            else item .select_one (selectors .get ("title","a"))
            )
            date_node =item .select_one (selectors .get ("date","time"))
            item_date =normalize_date (
            date_node .get_text (" ",strip =True )if date_node else ""
            )
            if item_date :
                page_dates .append (item_date )
            prepared .append (Candidate (
            url =url ,
            title =clean_text (
            title_node .get_text (" ",strip =True )if title_node else ""
            ),
            date =item_date ,
            source =clean_text (provider .get ("source",provider ["name"])),
            provider =provider ["name"],
            ))
            # History list in reverse chronological order: Stop turning when the entire page is older than the study period.
        if page_dates and max (page_dates )<start :
            print (f"[List stopped] {provider ['name']} page={page } is earlier than {start }")
            break 
        for candidate in prepared :
            yield candidate 


def discover_bing_rss (
provider :dict [str ,Any ],
client :PublicHttpClient ,
start :str ,
end :str ,
)->Iterable [Candidate ]:
    """Discover public news links for a given website through Bing's public RSS search portal.

    Search results are only used to discover candidate URLs; the text is still provided by the target website's public page,
    and proceed with robots.txt, time, keyword, and deduplication checks."""
    endpoint =provider .get (
    "endpoint","https://www.bing.com/search"
    )
    domains =provider .get ("domains")or [provider .get ("domain","")]
    queries =provider .get ("queries")or [
    '算力 OR "智算中心" OR "AI服务器" OR "GPU服务器" OR "东数西算"'
    ]
    seen :set [str ]=set ()

    def unwrap_bing_url (value :str )->str :
        """Restore Bing RSS /ck/a jump link to the target website URL."""
        parsed =urlparse (value )
        if not parsed .netloc .lower ().endswith ("bing.com"):
            return value 
        encoded =parse_qs (parsed .query ).get ("u",[""])[0 ]
        if not encoded :
            return value 
        if encoded .startswith ("a1"):
            encoded =encoded [2 :]
        try :
            encoded +="="*(-len (encoded )%4 )
            decoded =base64 .urlsafe_b64decode (
            encoded .encode ("ascii")
            ).decode ("utf-8",errors ="strict")
            if decoded .startswith (("http://","https://")):
                return decoded 
        except (ValueError ,UnicodeDecodeError ):
            pass 
        return value 

    for domain in domains :
        if not domain :
            continue 
        for query in queries :
            search_query =f"site:{domain } ({query })"
            search_url =endpoint +"?"+urlencode ({
            "q":search_query ,
            "format":"rss",
            "setlang":"zh-Hans",
            "count":int (provider .get ("max_records",50 )),
            })
            response =client .get (search_url ,check_robots =False )
            feed =feedparser .parse (response .content )
            if getattr (feed ,"bozo",False )and not feed .entries :
                raise RuntimeError (
                f"Public RSS search and parsing failed: {getattr (feed ,'bozo_exception','')}"
                )
            print (
            f"[Site search] {provider ['name']} domain={domain } query={query } found={len (feed .entries )}"
            )
            for entry in feed .entries :
                url =canonical_url (unwrap_bing_url (entry .get ("link","")))
                if not url or url in seen :
                    continue 
                host =urlparse (url ).netloc .lower ()
                if domain .lower ()not in host :
                    continue 
                seen .add (url )
                published =(
                entry .get ("published")
                or entry .get ("updated")
                or entry .get ("pubDate")
                or ""
                )
                yield Candidate (
                url =url ,
                title =clean_text (entry .get ("title","")),
                date =normalize_date (published ),
                source =clean_text (
                provider .get ("source",provider ["name"])
                ),
                provider =provider ["name"],
                )


def append_stats (path :Path ,counter :Counter ,first_header :str )->None :
    with path .open ("w",encoding ="utf-8-sig",newline ="")as handle :
        writer =csv .writer (handle )
        writer .writerow ([first_header ,"count"])
        writer .writerows (sorted (counter .items ()))


def load_cumulative_stats (output_file :Path )->tuple [Counter ,Counter ]:
    """Recalculate cumulative source/monthly statistics from full output to avoid being overwritten by a single run."""
    source_counts :Counter =Counter ()
    month_counts :Counter =Counter ()
    if not output_file .exists ():
        return source_counts ,month_counts 
    with output_file .open ("r",encoding ="utf-8-sig",errors ="replace")as handle :
        for line in handle :
            try :
                record =json .loads (line )
            except json .JSONDecodeError :
                continue 
            source_counts [record .get ("source","")or "unknown"]+=1 
            date_text =record .get ("date","")
            if isinstance (date_text ,str )and len (date_text )>=7 :
                month_counts [date_text [:7 ]]+=1 
    return source_counts ,month_counts 


def run (
config_path :Path ,
start_override :str |None ,
end_override :str |None ,
limit :int |None ,
discover_only :bool ,
force_windows :bool ,
)->None :
    config =yaml .safe_load (config_path .read_text (encoding ="utf-8"))
    base =config_path .parent 
    start =start_override or config ["research_period"]["start"]
    end =end_override or config ["research_period"]["end"]
    datetime .strptime (start ,"%Y-%m-%d")
    datetime .strptime (end ,"%Y-%m-%d")
    if start >end :
        raise ValueError ("Start date cannot be later than end date")

    output_dir =Path (config ["output"]["directory"])
    if not output_dir .is_absolute ():
        output_dir =(base /output_dir ).resolve ()
    output_dir .mkdir (parents =True ,exist_ok =True )
    output_file =output_dir /config ["output"]["jsonl"]
    candidate_file =output_dir /"historical_candidates.jsonl"
    failure_file =output_dir /config ["output"]["failures"]
    state =HistoryState (output_dir /config ["output"]["state"])
    client =PublicHttpClient (config .get ("http",{}))
    groups =config ["keyword_groups"]
    min_length =int (config .get ("filters",{}).get ("min_content_length",100 ))
    existing_urls ,existing_titles =load_existing_dedup (
    config .get ("dedup_inputs",[]),base 
    )
    counters =Counter ()
    source_counts ,month_counts =load_cumulative_stats (output_file )

    logging .basicConfig (
    level =logging .INFO ,
    format ="%(asctime)s | %(levelname)s | %(message)s",
    handlers =[
    logging .FileHandler (output_dir /"historical_collector.log",encoding ="utf-8"),
    logging .StreamHandler (),
    ],
    )

    with (
    output_file .open ("a",encoding ="utf-8")as output_handle ,
    candidate_file .open ("a",encoding ="utf-8")as candidate_handle ,
    failure_file .open ("a",encoding ="utf-8")as failure_handle ,
    ):
        stop =False 
        first_window_start =next (month_windows (start ,end ))[0 ]
        for window_start ,window_end in month_windows (start ,end ):
            active_providers =[
            provider for provider in config ["providers"]
            if provider .get ("enabled",True )
            and (
            not provider .get ("run_once",False )
            or window_start ==first_window_start 
            )
            ]
            if not active_providers :
                continue 
            print (f"\n========== Month {window_start [:7 ]} ==========")
            for provider in active_providers :
                name =provider ["name"]
                run_once =bool (provider .get ("run_once",False ))
                provider_start =start if run_once else window_start 
                provider_end =end if run_once else window_end 
                if (
                not force_windows 
                and state .window_done (name ,provider_start ,provider_end )
                ):
                    print (f"[Window skip] {name } {provider_start }~{provider_end }")
                    continue 
                print (f"[Start from source] {name } {provider_start }~{provider_end }")
                try :
                    if provider ["type"]=="seed_file":
                        candidates =discover_seed_file (provider ,base )
                    elif provider ["type"]=="gdelt":
                        candidates =discover_gdelt (
                        provider ,client ,provider_start ,provider_end 
                        )
                    elif provider ["type"]=="list":
                        candidates =discover_list (
                        provider ,client ,provider_start ,provider_end 
                        )
                    elif provider ["type"]=="bing_rss":
                        candidates =discover_bing_rss (
                        provider ,client ,provider_start ,provider_end 
                        )
                    else :
                        raise ValueError (f"Unknown source type: {provider ['type']}")

                    discovered_here =0 
                    for candidate in candidates :
                        discovered_here +=1 
                        counters ["discovered"]+=1 
                        if limit is not None and counters ["processed"]>=limit :
                            stop =True 
                            break 
                        if (
                        candidate .date 
                        and not in_period (
                        candidate .date ,provider_start ,provider_end 
                        )
                        ):
                            counters ["outside_window"]+=1 
                            continue 
                        if (
                        provider .get ("require_discovery_keyword",True )
                        and not keyword_hits (candidate .title ,groups )
                        ):
                            counters ["irrelevant_discovery"]+=1 
                            state .save_item (
                            candidate .url ,candidate .title ,
                            "irrelevant_discovery",candidate .provider ,
                            )
                            continue 
                        if (
                        candidate .url in existing_urls 
                        or state .seen_url (candidate .url )
                        ):
                            counters ["duplicate_url"]+=1 
                            continue 
                        title_key =normalized_title (candidate .title )
                        if (
                        title_key 
                        and (title_key in existing_titles or state .seen_title (candidate .title ))
                        ):
                            counters ["duplicate_title"]+=1 
                            state .save_item (
                            candidate .url ,candidate .title ,
                            "duplicate_title",candidate .provider ,
                            )
                            continue 
                        counters ["processed"]+=1 
                        write_jsonl (candidate_handle ,candidate .__dict__ )
                        candidate_handle .flush ()
                        if discover_only :
                            state .save_item (
                            candidate .url ,candidate .title ,
                            "candidate",candidate .provider ,
                            )
                            continue 
                        try :
                            response =client .get (
                            candidate .url ,
                            check_robots =provider .get ("check_target_robots",True ),
                            )
                            html_title ,html_date ,html_source =metadata_from_html (
                            response .text 
                            )
                            title =candidate .title or html_title 
                            date_text =candidate .date or html_date 
                            source =(
                            candidate .source or html_source 
                            or urlparse (candidate .url ).netloc 
                            )
                            if not in_period (date_text ,provider_start ,provider_end ):
                                state .save_item (
                                candidate .url ,title ,"outside_window",
                                candidate .provider ,
                                )
                                counters ["outside_window"]+=1 
                                continue 
                            content =extract_content (
                            response .text ,candidate .url ,min_length 
                            )
                            hits =keyword_hits (f"{title }\n{content }",groups )
                            if len (content )<min_length :
                                raise ValueError (f"The text is less than {min_length } characters")
                            if not hits :
                                state .save_item (
                                candidate .url ,title ,"irrelevant",
                                candidate .provider ,
                                )
                                counters ["irrelevant"]+=1 
                                continue 
                            record ={
                            "uuid":stable_uuid (candidate .url ),
                            "date":date_text ,
                            "title":title ,
                            "content":content ,
                            "source":source ,
                            "url":candidate .url ,
                            "data_origin":f"historical_web:{candidate .provider }",
                            "keyword_hits":hits ,
                            "crawl_time":datetime .now ().strftime (
                            "%Y-%m-%d %H:%M:%S"
                            ),
                            }
                            write_jsonl (output_handle ,record )
                            output_handle .flush ()
                            state .save_item (
                            candidate .url ,title ,"success",candidate .provider 
                            )
                            existing_urls .add (candidate .url )
                            existing_titles .add (normalized_title (title ))
                            counters ["success"]+=1 
                            source_counts [source ]+=1 
                            month_counts [date_text [:7 ]]+=1 
                            print (
                            f"[Save] {counters ['success']} {date_text } {title [:60 ]}"
                            )
                        except Exception as exc :
                            error =str (exc )
                            write_jsonl (failure_handle ,{
                            **candidate .__dict__ ,
                            "error":error ,
                            "crawl_time":datetime .now ().strftime (
                            "%Y-%m-%d %H:%M:%S"
                            ),
                            })
                            failure_handle .flush ()
                            state .save_item (
                            candidate .url ,candidate .title ,"failed",
                            candidate .provider ,error ,
                            )
                            counters ["failed"]+=1 
                    if not stop :
                        state .save_window (
                        name ,provider_start ,provider_end ,
                        "discovered"if discover_only else "done",
                        )
                    print (
                    f"[Source completed] {name } Found={discovered_here } Accumulated processing={counters ['processed']} Saved={counters ['success']} Failed={counters ['failed']}"
                    )
                except Exception as exc :
                    counters ["provider_failed"]+=1 
                    state .save_window (name ,provider_start ,provider_end ,"failed")
                    logging .error (
                    "Source failed %s %s~%s | %s",
                    name ,provider_start ,provider_end ,exc ,
                    )
                    print (f"[Source failed] {name }: {exc }")
                if stop :
                    break 
            if stop :
                break 

    append_stats (output_dir /"historical_source_counts.csv",source_counts ,"source")
    append_stats (output_dir /"historical_monthly_counts.csv",month_counts ,"month")
    report ={
    "finished_at":datetime .now ().strftime ("%Y-%m-%d %H:%M:%S"),
    "period":{"start":start ,"end":end },
    "discover_only":discover_only ,
    "counts":dict (counters ),
    "output":str (output_file ),
    "candidates":str (candidate_file ),
    }
    (output_dir /"historical_run_report.json").write_text (
    json .dumps (report ,ensure_ascii =False ,indent =2 ),encoding ="utf-8"
    )
    print (json .dumps (report ,ensure_ascii =False ,indent =2 ))


def main ()->None :
    parser =argparse .ArgumentParser (description ="AI computing power news history retrospective collector")
    parser .add_argument (
    "--config",type =Path ,
    default =Path (__file__ ).with_name ("historical_sources.example.yaml"),
    )
    parser .add_argument ("--start",help ="YYYY-MM-DD")
    parser .add_argument ("--end",help ="YYYY-MM-DD")
    parser .add_argument ("--limit",type =int ,help ="How many candidate URLs can be processed at most in this round?")
    parser .add_argument (
    "--discover-only",action ="store_true",
    help ="Only candidate URLs are found and the target text page is not accessed.",
    )
    parser .add_argument (
    "--force-windows",action ="store_true",
    help ="Rescan mark completed source time window (still retain URL/title deduplication)",
    )
    args =parser .parse_args ()
    run (
    args .config .resolve (),args .start ,args .end ,
    args .limit ,args .discover_only ,args .force_windows ,
    )


if __name__ =="__main__":
    main ()
