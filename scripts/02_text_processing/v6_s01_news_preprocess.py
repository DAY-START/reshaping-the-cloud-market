# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s01_news_preprocess.py
=========================
Step 1: News cleaning, market comment elimination, event-level deduplication, source standardization and trading day mapping.

Input: news_data_v1_initial/news with content_merged summary_0802_202107_202606.jsonl (read-only)
       stock_data_v1_initial/all_66stock_final.csv (read-only, used to get the trading calendar)
Output: data_v2_experiment/d01_text_processed/news_meta.csv
       data_v2_experiment/d01_text_processed/s01_clean_report.json

Corresponds to the first half of Section 3.4 of the paper "News Cleaning, Object Direction and Tone"."""
import json ,re ,hashlib ,csv ,sys ,time 
from collections import Counter ,defaultdict 
from urllib .parse import urlparse 
from datetime import datetime ,timedelta 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import (RAW_NEWS_FILE ,RAW_STOCK_FILE ,D01_TEXT ,
SAMPLE_START ,SAMPLE_END )

# --------------------------------------------------------------- Regular
RE_HTML =re .compile (r"<[^>]{1,200}>")
RE_SPACE =re .compile (r"[\s\u3000\xa0]+")
RE_CTRL =re .compile (r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
RE_CJK =re .compile (r"[\u4e00-\u9fff]")
RE_MOJIBAKE =re .compile (r"[\ufffd]|[ãæåèéçÃ¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿]{2,}")

# Market comments/stock recommendations/disk recaps - need to be eliminated (to avoid reverse causality)
MARKET_TALK =re .compile (
r"涨停|跌停|龙虎榜|盘中异动|收评|午评|早evening|复盘|涨幅榜|跌幅榜|主力资金|"
r"竞价|北向资金|游资|连板|大宗交易|机构席位|买入评级|目标价|强烈推荐|增持评级|"
r"股价异动|股票代码|尾盘|集合竞价|超跌反弹|概念股午后|个股点评"
)
# Industry information (orders, capital expenditures, supplies, products, policies...) - need to be retained
INDUSTRY_SIG =re .compile (
r"订单|中标|采购|招标|出货|量产|投产|扩产|产能|资本开支|投资建设|签约|交付|"
r"发布|上市新品|流片|良率|封装|制程|产线|数据中心|智算中心|算力中心|超算|"
r"政策|规划|试点|标准|白皮书|部署|东数西算|出口管制|禁令|实体清单|"
r"缺货|紧缺|涨价|降价|供不应求|排产|库存|电力|能耗|绿电|液冷|散热"
)
# AI computing power correlation core words (minimum threshold for correlation)
AI_COMPUTE_CORE =re .compile (
r"算力|GPU|显卡|加速卡|AI服务器|智算|超算|大模型|人工智能|AI芯片|"
r"英伟达|NVIDIA|H100|H800|A100|A800|H20|B200|GB200|昇腾|寒武纪|"
r"CPU|服务器|数据中心|IDC|云计算|光模块|HBM|推理|训练集群|TPU|DPU|NPU",
re .IGNORECASE )

RE_TITLE_NORM =re .compile (r"[^\u4e00-\u9fffA-Za-z0-9]+")
RE_DATE =re .compile (r"(\d{4})\D{0,2}(\d{1,2})\D{0,2}(\d{1,2})")


def norm_date (raw :str ):
    """Unify various writing methods (2021-7-9 / 2021/07/09 / July 9, 2021 / with timestamp) into YYYY-MM-DD.
    Returns None for an unparsable or illegal date."""
    if not raw :
        return None 
    m =RE_DATE .search (raw .strip ()[:24 ])
    if not m :
        return None 
    y ,mo ,dy =int (m .group (1 )),int (m .group (2 )),int (m .group (3 ))
    if not (1990 <=y <=2100 and 1 <=mo <=12 and 1 <=dy <=31 ):
        return None 
    try :
        return datetime (y ,mo ,dy ).strftime ("%Y-%m-%d")
    except ValueError :
        return None 


def norm_title (t :str )->str :
    return RE_TITLE_NORM .sub ("",t or "").lower ()


def clean_text (s :str )->str :
    if not s :
        return ""
    s =RE_CTRL .sub (" ",s )
    s =RE_HTML .sub (" ",s )
    s =s .replace ("\u200b","").replace ("&nbsp;"," ")
    s =RE_SPACE .sub (" ",s ).strip ()
    return s 


def load_trading_days ():
    days =set ()
    with open (RAW_STOCK_FILE ,encoding ="utf-8-sig")as f :
        for row in csv .DictReader (f ):
            days .add (row ["time"])
    return sorted (days )


def build_next_trading_map (tdays ):
    """Any natural day -> next (including the current) trading day. Returns None outside the sample period."""
    tset =set (tdays )
    d0 =datetime .strptime (SAMPLE_START ,"%Y-%m-%d")
    d1 =datetime .strptime (SAMPLE_END ,"%Y-%m-%d")
    mapping ={}
    nxt =None 
    d =d1 
    while d >=d0 :
        ds =d .strftime ("%Y-%m-%d")
        if ds in tset :
            nxt =ds 
        mapping [ds ]=nxt 
        d -=timedelta (days =1 )
    return mapping 


def main ():
    t0 =time .time ()
    tdays =load_trading_days ()
    nt_map =build_next_trading_map (tdays )
    print (f"[i] Trading day {len (tdays )} day {tdays [0 ]} ~ {tdays [-1 ]}")

    stat =Counter ()
    seen_hash =set ()# Repeat exactly
    title_date =set ()# Title+Date Nearly Duplicate
    event_first ={}# Event cluster -> first nid
    event_seq =defaultdict (int )# Serial number within the event cluster (reprinting with decreasing weight)
    src_counter =Counter ()

    out_path =D01_TEXT /"news_meta.csv"
    txt_path =D01_TEXT /"news_text.jsonl"
    fo =open (out_path ,"w",encoding ="utf-8",newline ="")
    ft =open (txt_path ,"w",encoding ="utf-8")
    w =csv .writer (fo )
    w .writerow (["nid","date","trade_date","iso_week","month",
    "source_std","event_id","dup_rank","dup_weight",
    "n_char","title"])

    with open (RAW_NEWS_FILE ,encoding ="utf-8")as f :
        for nid ,line in enumerate (f ):
            stat ["total"]+=1 
            try :
                d =json .loads (line )
            except Exception :
                stat ["json_error"]+=1 
                continue 

            date =norm_date (d .get ("date")or "")
            if date is None :
                stat ["drop_bad_date"]+=1 
                continue 
            if not (SAMPLE_START <=date <=SAMPLE_END ):
                stat ["out_of_range"]+=1 
                continue 

            title =clean_text (d .get ("title")or "")
            content =clean_text (d .get ("content")or "")
            full =title +" "+content 

            # ---- Garbled code removal
            cjk =len (RE_CJK .findall (full [:800 ]))
            if len (full )>100 and cjk /max (len (full [:800 ]),1 )<0.15 :
                stat ["drop_non_cjk"]+=1 
                continue 
            if len (RE_MOJIBAKE .findall (full [:2000 ]))>=3 :
                stat ["drop_mojibake"]+=1 
                continue 

                # ----Length threshold
            if len (full )<150 :
                stat ["drop_short"]+=1 
                continue 

                # ----The minimum threshold for AI computing power correlation
            if not AI_COMPUTE_CORE .search (full [:3000 ]):
                stat ["drop_not_ai_compute"]+=1 
                continue 

                # ----Market comments are eliminated (mainly market retellings and lack of industry information)
            n_mkt =len (MARKET_TALK .findall (full [:3000 ]))
            n_ind =len (INDUSTRY_SIG .findall (full [:3000 ]))
            if n_mkt >=2 and n_mkt >n_ind :
                stat ["drop_market_talk"]+=1 
                continue 

                # ----Exactly repeat
            h =hashlib .md5 (RE_TITLE_NORM .sub ("",full [:1200 ]).encode ()).hexdigest ()
            if h in seen_hash :
                stat ["drop_exact_dup"]+=1 
                continue 
            seen_hash .add (h )

            nt =norm_title (title )
            # ---- Title + Date Nearly Duplicate
            key_td =(nt [:40 ],date )
            if nt and key_td in title_date :
                stat ["drop_title_date_dup"]+=1 
                continue 
            title_date .add (key_td )

            # ---- Event cluster: the first 24 characters of the normalized title + the ISO week
            iso_y ,iso_w ,_ =datetime .strptime (date ,"%Y-%m-%d").isocalendar ()
            week_key =f"{iso_y }-W{iso_w :02d}"
            ev_key =(nt [:24 ]if len (nt )>=12 else h [:16 ],week_key )
            eid =event_first .setdefault (ev_key ,nid )
            event_seq [ev_key ]+=1 
            rank =event_seq [ev_key ]
            dup_weight =1.0 /rank # Reprint weight decreases

            # ---- Source standardization
            src =(d .get ("source")or "").strip ()
            if not src :
                host =urlparse (d .get ("url")or "").netloc 
                if host :
                    src =host .lower ().replace ("www.","")
                else :
                    ds =(d .get ("dataset")or "unknown").replace ("\\","/")
                    src ="corpus:"+ds .split ("/")[0 ][:24 ]
            src_counter [src ]+=1 

            trade_date =nt_map .get (date )
            if trade_date is None :
                stat ["drop_no_trade_day"]+=1 
                continue 

            w .writerow ([nid ,date ,trade_date ,week_key ,date [:7 ],src ,
            eid ,rank ,f"{dup_weight :.4f}",len (full ),title [:120 ]])
            ft .write (json .dumps ({"nid":nid ,"title":title [:200 ],
            "body":content [:1500 ]},ensure_ascii =False )+"\n")
            stat ["kept"]+=1 

            if stat ["total"]%50000 ==0 :
                print (f"    processed {stat ['total']:,}  kept {stat ['kept']:,}"
                f"  ({time .time ()-t0 :.0f}s)")

    fo .close ()
    ft .close ()

    report ={
    "input_file":str (RAW_NEWS_FILE ),
    "output_file":str (out_path ),
    "text_file":str (txt_path ),
    "counts":dict (stat ),
    "n_articles_kept":stat ["kept"],
    "n_events":len (event_first ),
    "n_sources":len (src_counter ),
    "top_sources":src_counter .most_common (30 ),
    "elapsed_sec":round (time .time ()-t0 ,1 ),
    }
    with open (D01_TEXT /"s01_clean_report.json","w",encoding ="utf-8")as f :
        json .dump (report ,f ,ensure_ascii =False ,indent =2 )

    print ("\n===== S01 清洗汇总 =====")
    for k ,v in stat .most_common ():
        print (f"  {k :24s} {v :,}")
    print (f"Number of event clusters {len (event_first ):,}")
    print (f"Number of normalized sources {len (src_counter ):,}")
    print (f"Time consuming {time .time ()-t0 :.0f}s -> {out_path }")


if __name__ =="__main__":
    main ()
