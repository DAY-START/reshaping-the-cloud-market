# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Consolidate AI computing power news and perform auditable and accurate deduplication."""

from __future__ import annotations 

import argparse 
import hashlib 
import json 
import re 
from collections import Counter 
from pathlib import Path 


START ="2021-07-01"
END ="2026-06-30"


def normalized_hash (text :str )->str :
    normalized =re .sub (r"[\W_]+","",text .lower ())
    return hashlib .sha256 (normalized .encode ("utf-8")).hexdigest ()


def normalize_record (item :dict ,origin :str )->dict |None :
    day =str (item .get ("date")or item .get ("publish_date")or "")[:10 ]
    if not (START <=day <=END ):
        return None 
    title =str (item .get ("title")or "").strip ()
    content =str (item .get ("content")or item .get ("raw_text")or "").strip ()
    if not content :
        return None 
    item ["date"]=day 
    item ["title"]=title 
    item ["content"]=content 
    item ["source"]=str (item .get ("source")or "")
    item ["url"]=str (item .get ("url")or "")
    item ["data_origin"]=str (item .get ("data_origin")or origin )
    hits =item .get ("keyword_hits",item .get ("_keyword_hits",[]))
    item ["keyword_hits"]=hits if isinstance (hits ,list )else [str (hits )]
    return item 


def main (output :Path ,report :Path ,inputs :list [tuple [Path ,str ]])->None :
    output .parent .mkdir (parents =True ,exist_ok =True )
    seen_ids :set [str ]=set ()
    seen_urls :set [str ]=set ()
    seen_hashes :set [str ]=set ()
    stats =Counter ()
    months =Counter ()

    with output .open ("w",encoding ="utf-8")as out :
        for path ,origin in inputs :
            if not path .exists ():
                stats [f"missing:{path .name }"]+=1 
                continue 
            with path .open (encoding ="utf-8",errors ="ignore")as handle :
                for line in handle :
                    stats [f"read:{path .name }"]+=1 
                    try :
                        raw =json .loads (line )
                    except json .JSONDecodeError :
                        stats [f"json_error:{path .name }"]+=1 
                        continue 
                    item =normalize_record (raw ,origin )
                    if item is None :
                        stats [f"out_of_scope:{path .name }"]+=1 
                        continue 
                    news_id =str (item .get ("id")or "").strip ()
                    url =item ["url"]
                    fingerprint =normalized_hash (item ["title"]+item ["content"])
                    if news_id and news_id in seen_ids :
                        stats ["duplicate_id"]+=1 
                        continue 
                    if url and url in seen_urls :
                        stats ["duplicate_url"]+=1 
                        continue 
                    if fingerprint in seen_hashes :
                        stats ["duplicate_exact_text"]+=1 
                        continue 
                    if news_id :
                        seen_ids .add (news_id )
                    if url :
                        seen_urls .add (url )
                    seen_hashes .add (fingerprint )
                    out .write (json .dumps (item ,ensure_ascii =False )+"\n")
                    stats [f"saved:{origin }"]+=1 
                    stats ["saved_total"]+=1 
                    months [item ["date"][:7 ]]+=1 

    with report .open ("w",encoding ="utf-8")as handle :
        handle .write ("AI算力新闻合并与精确去重报告\n")
        handle .write (f"Research period: {START } to {END }\n\n")
        for key in sorted (stats ):
            handle .write (f"{key }: {stats [key ]}\n")
        handle .write ("\n按月数量:\n")
        for month in sorted (months ):
            handle .write (f"{month }: {months [month ]}\n")


if __name__ =="__main__":
    parser =argparse .ArgumentParser ()
    parser .add_argument ("--output",type =Path ,required =True )
    parser .add_argument ("--report",type =Path ,required =True )
    parser .add_argument ("--input",action ="append",nargs =2 ,metavar =("PATH","ORIGIN"),required =True )
    args =parser .parse_args ()
    main (args .output ,args .report ,[(Path (path ),origin )for path ,origin in args .input ])
