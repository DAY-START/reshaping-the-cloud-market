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

"""Support: resume uploading from breakpoints, additional writing, automatic deduplication, automatic suspension when the number of daily visits exceeds the limit"""

import requests 
import json 
import csv 
import time 
import os 
import sys 
from datetime import datetime 

# ==================== Configuration parameters ====================
APP_KEY ="6A63041F0146"
APP_SECRET ="1E768F54DD717C7339D6CDED0F48C5B7"
CONCEPT_CODE ="302035,308828,881125,885494,885705"
TIME_START =1625068800 # 2021-07-01 00:00:00 (10-digit timestamp)
TIME_END =1785628799 # 2026-07-31 23:59:59 (10-digit timestamp)
PAGE_SIZE =20 # The maximum interface limit is 20
TARGET_COUNT =5000 # Target number of downloads
SLEEP_SEC =0.8 # Request interval to prevent frequency limit (can be increased when encountering 4000 errors)

# Output file: unified prefix 001_download_, adapt to the naming convention
JSON_FILE ="001_download_ai_computing_news_202107_202607.jsonl"
CSV_FILE ="001_download_ai_computing_news_202107_202607.csv"
STATE_FILE ="001_download_compute_state.json"

# interface address
TOKEN_URL ="https://b2b-api.10jqka.com.cn/gateway/service-mana/app/login-appkey"
NEWS_URL ="https://b2b-api.10jqka.com.cn/gateway/arsenal/yq_qdc/info/v1/information/industry_concept_news"

# ==================== Function ====================

def get_token ():
    """Get access token (valid for 24 hours)"""
    params ={"appKey":APP_KEY ,"appSecret":APP_SECRET }
    try :
        resp =requests .get (TOKEN_URL ,params =params ,timeout =30 )
        data =resp .json ()
        if data .get ("flag")==0 :
            token =data ["data"]["access_token"]
            print (f"[✓] Token obtained successfully")
            return token 
        else :
            print (f"[✗] Token acquisition failed: {data .get ('msg')}")
            return None 
    except Exception as e :
        print (f"[✗] Token request exception: {e }")
        return None 


def load_state ():
    """Load download status, support breakpoint resume download"""
    if os .path .exists (STATE_FILE ):
        with open (STATE_FILE ,"r",encoding ="utf-8")as f :
            state =json .load (f )
        if isinstance (state .get ("uuids"),list ):
            state ["uuids"]=set (state ["uuids"])
        elif "uuids"not in state :
            state ["uuids"]=set ()
        return state 
    return {"next_page":1 ,"total_fetched":0 ,"uuids":set ()}


def save_state (state ):
    """Save download status locally"""
    state_copy =state .copy ()
    if isinstance (state_copy .get ("uuids"),set ):
        state_copy ["uuids"]=list (state_copy ["uuids"])
    with open (STATE_FILE ,"w",encoding ="utf-8")as f :
        json .dump (state_copy ,f ,ensure_ascii =False ,indent =2 )


def init_csv ():
    """Initialize the CSV file (write the header when running for the first time)"""
    if not os .path .exists (CSV_FILE ):
        headers =[
        "uuid","title","sentiment","content","host_source",
        "publish_source","publish_time","display_time","url",
        "importance","concepts","industries","fetch_time"
        ]
        with open (CSV_FILE ,"w",newline ="",encoding ="utf-8-sig")as f :
            writer =csv .writer (f )
            writer .writerow (headers )
        print (f"[✓] CSV file created: {CSV_FILE }")


def append_to_csv (records ):
    """Append records to CSV (append mode)"""
    with open (CSV_FILE ,"a",newline ="",encoding ="utf-8-sig")as f :
        writer =csv .writer (f )
        for r in records :
            concepts =r .get ("concepts",[])
            industries =r .get ("industries",[])
            writer .writerow ([
            r .get ("uuid",""),
            r .get ("title",""),
            r .get ("sentiment",""),
            r .get ("content",""),
            r .get ("host_source",""),
            r .get ("publish_source",""),
            r .get ("publish_time",""),
            r .get ("display_time",""),
            r .get ("url",""),
            r .get ("importance",""),
            ",".join (concepts )if isinstance (concepts ,list )else str (concepts ),
            ",".join (industries )if isinstance (industries ,list )else str (industries ),
            datetime .now ().strftime ("%Y-%m-%d %H:%M:%S")
            ])


def append_to_json (records ):
    """Append records to JSON (one JSON object per line, JSONL format, easy for streaming reading)"""
    with open (JSON_FILE ,"a",encoding ="utf-8")as f :
        for r in records :
            f .write (json .dumps (r ,ensure_ascii =False )+"\n")


def fetch_news_page (token ,page ):
    """Get single page news data"""
    headers ={"open-authorization":f"Bearer {token }"}
    params ={
    "news_concept":CONCEPT_CODE ,
    "stime":TIME_START ,
    "etime":TIME_END ,
    "page":page ,
    "page_size":PAGE_SIZE 
    }
    try :
        resp =requests .get (NEWS_URL ,headers =headers ,params =params ,timeout =30 )
        return resp .json ()
    except Exception as e :
        print (f"[✗] Page {page } request exception: {e }")
        return None 


        # ==================== Main program ====================

def main ():
    print ("="*65 )
    print ("Flush GPU/CPU computing power industry concept news and public opinion batch download tool")
    print (f"Time range: 2021-07-01 ~ 2026-07-31 | Target: {TARGET_COUNT } items")
    print ("="*65 )

    # 1. Get Token
    token =get_token ()
    if not token :
        print ("[✗] Unable to obtain Token, program terminated")
        return 

        # 2. Initialize the output file
    init_csv ()
    if not os .path .exists (JSON_FILE ):
        open (JSON_FILE ,"w",encoding ="utf-8").close ()
        print (f"[✓] JSON file created: {JSON_FILE }")

        # 3. Load breakpoint status
    state =load_state ()
    next_page =state ["next_page"]
    total_fetched =state ["total_fetched"]
    uuids =state ["uuids"]

    print (f"[→] Resume upload: Starting from page {next_page }, {total_fetched } items \n have been obtained")

    # 4. Circular paging download
    while total_fetched <TARGET_COUNT :
        print (f"[→] Request page {next_page }...",end =" ")
        data =fetch_news_page (token ,next_page )

        if data is None :
            print ("network error")
            save_state ({"next_page":next_page ,"total_fetched":total_fetched ,"uuids":uuids })
            break 

            # Handle gateway-level errors (such as token expiration, daily visits exceeding the limit)
        flag =data .get ("flag")
        if flag is not None and flag !=0 :
            msg =data .get ("msg","")
            print (f"Failed [{flag }] {msg }")
            if "Daily visits"in msg or "upper limit"in msg :
                print ("[!] The number of daily visits has exceeded the limit. Please try again tomorrow or contact Flush to increase the quota. Status saved.")
            elif flag ==4000 :
                print ("[!] The request frequency is too high, wait 30 seconds and try again...")
                time .sleep (30 )
                continue 
            save_state ({"next_page":next_page ,"total_fetched":total_fetched ,"uuids":uuids })
            break 

            # Handle business-level errors
        status_code =data .get ("status_code")
        if status_code !=0 :
            msg =data .get ("status_msg","")
            print (f"Business error [{status_code }] {msg }")
            if status_code ==4000 :
                print ("[!] The request frequency is too high, wait 30 seconds and try again...")
                time .sleep (30 )
                continue 
            save_state ({"next_page":next_page ,"total_fetched":total_fetched ,"uuids":uuids })
            break 

            # Parse data
        news_data =data .get ("data",{})
        total =news_data .get ("total",0 )
        show_total =news_data .get ("show_total",0 )
        news_list =news_data .get ("list",[])

        print (f"total={total }, show_total={show_total }, this page={len (news_list )}")

        if not news_list :
            print ("[✓] No more data, download completed")
            break 

            # Deduplication (prevent duplicate downloads)
        new_records =[]
        for item in news_list :
            uid =item .get ("uuid")
            if uid and uid not in uuids :
                uuids .add (uid )
                new_records .append (item )

        if new_records :
            append_to_csv (new_records )
            append_to_json (new_records )
            total_fetched +=len (new_records )
            print (f"[✓] Added {len (new_records )} items, accumulated {total_fetched } items")
        else :
            print (f"[!] This page is repeated, skip")

            # Save breakpoint status
        save_state ({"next_page":next_page +1 ,"total_fetched":total_fetched ,"uuids":uuids })

        # Check if the target is reached
        if total_fetched >=TARGET_COUNT :
            print (f"\n[✓] The target number of items {TARGET_COUNT } has been reached and the download is completed!")
            break 

            # Check if the last page has been reached
        if len (news_list )<PAGE_SIZE :
            print ("[✓] The last page has been reached and the download is completed.")
            break 

        next_page +=1 
        time .sleep (SLEEP_SEC )

    print ("\n"+"="*65 )
    print (f"Download is over! A total of {total_fetched } records obtained")
    print (f"JSONL file: {os .path .abspath (JSON_FILE )}")
    print (f"CSV file: {os .path .abspath (CSV_FILE )}")
    print (f"Breakpoint status file: {os .path .abspath (STATE_FILE )}")
    print ("="*65 )


if __name__ =="__main__":
    main ()