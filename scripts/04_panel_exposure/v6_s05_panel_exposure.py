# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s05_panel_exposure.py
========================
Step 5: 66-stock panel construction, four-category research classification (Table 2), ex-ante GPU/CPU business exposure
        (Text substitution caliber of Equation 7), returns and abnormal returns, control variable shrinkage,
        and merging with daily/weekly/monthly GCS-UGCS.

Input: stock_data_v1_initial/all_66stock_final.csv
       d01_text_processed/news_text.jsonl, news_meta.csv
       d02_lexicon_tfidf/news_scores.csv
       d03_model_damt/news_damt_scores.csv
       d04_index_gcs_ugcs/gcs_{daily,weekly,monthly}.csv
Output: d05_panel_dataset/firm_master.csv company master data and four types of labels
       d05_panel_dataset/firm_news_hits.csv Company—News co-occurrence details
       d05_panel_dataset/exposure_daily.csv rolling ex-ante exposure
       d05_panel_dataset/panel_daily.csv main panel
       d05_panel_dataset/panel_weekly.csv / panel_monthly.csv
       d05_panel_dataset/s05_report.json"""
import json ,sys ,time 
from collections import defaultdict 

import numpy as np 
import pandas as pd 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import (RAW_STOCK_FILE ,D01_TEXT ,D02_LEX ,D03_MODEL ,
D04_INDEX ,D05_PANEL )

# ================================================================ Company Master Data
# category: G1 GPU Core Industry Chain / G2 Cloud and Intelligent Computing Center / G3 Semiconductor and Computing Power Support /
# G4 AI software and application ecosystem. Determine based on the main business and product structure that have been disclosed before the impact.
FIRMS =[
("000034.SZ","神州数码",["神州数码","神码"],"G2"),
("000063.SZ","中兴通讯",["中兴通讯","中兴"],"G1"),
("000066.SZ","中国长城",["中国长城","长城电脑"],"G1"),
("000158.SZ","常山北明",["常山北明"],"G4"),
("000555.SZ","神州信息",["神州信息"],"G4"),
("000938.SZ","紫光股份",["紫光股份","新华三","H3C"],"G1"),
("000977.SZ","浪潮信息",["浪潮信息","浪潮电子信息"],"G1"),
("000988.SZ","华工科技",["华工科技"],"G3"),
("002065.SZ","东华软件",["东华软件"],"G4"),
("002261.SZ","拓维信息",["拓维信息","湘江鲲鹏"],"G1"),
("002281.SZ","光迅科技",["光迅科技"],"G3"),
("002335.SZ","科华数据",["科华数据","科华恒盛"],"G3"),
("002364.SZ","中恒电气",["中恒电气"],"G3"),
("002368.SZ","太极股份",["太极股份","太极计算机"],"G4"),
("002410.SZ","广联达",["广联达"],"G4"),
("002518.SZ","科士达",["科士达"],"G3"),
("002837.SZ","英维克",["英维克"],"G3"),
("002929.SZ","润建股份",["润建股份"],"G2"),
("300017.SZ","网宿科技",["网宿科技"],"G2"),
("300168.SZ","万达信息",["万达信息"],"G4"),
("300212.SZ","易华录",["易华录"],"G2"),
("300245.SZ","天玑科技",["天玑科技"],"G2"),
("300253.SZ","卫宁健康",["卫宁健康"],"G4"),
("300302.SZ","同有科技",["同有科技"],"G3"),
("300308.SZ","中际旭创",["中际旭创","旭创科技"],"G3"),
("300339.SZ","润和软件",["润和软件"],"G4"),
("300376.SZ","易事特",["易事特"],"G3"),
("300383.SZ","光环新网",["光环新网"],"G2"),
("300394.SZ","天孚通信",["天孚通信"],"G3"),
("300442.SZ","润泽科技",["润泽科技","润泽智算"],"G2"),
("300474.SZ","景嘉微",["景嘉微"],"G1"),
("300499.SZ","高澜股份",["高澜股份"],"G3"),
("300502.SZ","新易盛",["新易盛"],"G3"),
("300603.SZ","立昂技术",["立昂技术"],"G2"),
("300608.SZ","思特奇",["思特奇"],"G4"),
("300738.SZ","奥飞数据",["奥飞数据"],"G2"),
("300846.SZ","首都在线",["首都在线"],"G2"),
("300990.SZ","同飞股份",["同飞股份"],"G3"),
("301165.SZ","锐捷网络",["锐捷网络","锐捷"],"G3"),
("600050.SH","中国联通",["中国联通","联通云"],"G2"),
("600100.SH","同方股份",["同方股份"],"G3"),
("600410.SH","华胜天成",["华胜天成"],"G2"),
("600498.SH","烽火通信",["烽火通信"],"G3"),
("600536.SH","中国软件",["中国软件","中软麒麟","麒麟软件"],"G4"),
("600570.SH","恒生电子",["恒生电子"],"G4"),
("600588.SH","用友网络",["用友网络","用友"],"G4"),
("600602.SH","云赛智联",["云赛智联"],"G2"),
("600718.SH","东软集团",["东软集团"],"G4"),
("600756.SH","浪潮软件",["浪潮软件"],"G4"),
("600797.SH","浙大网新",["浙大网新"],"G4"),
("600845.SH","宝信软件",["宝信软件"],"G2"),
("600850.SH","华东电脑",["华东电脑"],"G2"),
("600941.SH","中国移动",["中国移动","移动云"],"G2"),
("601138.SH","工业富联",["工业富联"],"G1"),
("601728.SH","中国电信",["中国电信","天翼云"],"G2"),
("603019.SH","中科曙光",["中科曙光","曙光信息"],"G1"),
("603083.SH","剑桥科技",["剑桥科技"],"G3"),
("603496.SH","恒为科技",["恒为科技"],"G3"),
("603881.SH","数据港",["数据港"],"G2"),
("603912.SH","佳力图",["佳力图"],"G3"),
("603927.SH","中科软",["中科软"],"G4"),
("688041.SH","海光信息",["海光信息","海光"],"G1"),
("688047.SH","龙芯中科",["龙芯中科","龙芯"],"G3"),
("688158.SH","优刻得",["优刻得","UCloud"],"G2"),
("688256.SH","寒武纪",["寒武纪"],"G1"),
("688316.SH","青云科技",["青云科技","青云QingCloud"],"G2"),
]
CAT_NAME ={"G1":"GPU Core Industrial Chain",
"G2":"Cloud / Intelligent Computing Centers",
"G3":"Semiconductor & Compute-Supporting Infrastructure",
"G4":"AI Software & Application Ecosystem"}

EXP_WIN =250 # Ex ante exposure rolling window (trading days)
EXP_MIN_DOC =20 # Minimum number of mentions, if insufficient, fall back to the average of similar categories
HORIZONS =[0 ,1 ,3 ,5 ,10 ,20 ]


def winsorize_by_year (s ,year ,lo =0.01 ,hi =0.99 ):
    out =s .copy ()
    for y ,idx in pd .Series (range (len (s )),index =s .index ).groupby (year ).groups .items ():
        v =s .loc [idx ]
        if v .notna ().sum ()<20 :
            continue 
        a ,b =v .quantile (lo ),v .quantile (hi )
        out .loc [idx ]=v .clip (a ,b )
    return out 


    # ================================================================ 1. Company-news co-occurrence
def build_firm_news ():
    out_path =D05_PANEL /"firm_news_hits.csv"
    if out_path .exists ():
        print ("[i] firm_news_hits.csv 已存在，跳过匹配")
        return pd .read_csv (out_path )
    alias2code ={}
    for code ,name ,aliases ,_ in FIRMS :
        for a in aliases :
            alias2code [a ]=code 
    keys =sorted (alias2code ,key =len ,reverse =True )
    print (f"[i] Company alias {len (keys )}, start scanning news text…")

    rows =[]
    t0 =time .time ();n =0 
    with open (D01_TEXT /"news_text.jsonl",encoding ="utf-8")as f :
        for line in f :
            d =json .loads (line )
            txt =d ["title"]+" "+d ["body"]
            hit =set ()
            for k in keys :
                if k in txt :
                    hit .add (alias2code [k ])
            for c in hit :
                rows .append ((d ["nid"],c ))
            n +=1 
            if n %50000 ==0 :
                print (f"    scan {n :,}  hits {len (rows ):,} ({time .time ()-t0 :.0f}s)")
    fh =pd .DataFrame (rows ,columns =["nid","thscode"])
    fh .to_csv (out_path ,index =False )
    print (f"[i] Co-occurred in {len (fh ):,} items, covering {fh ['thscode'].nunique ()} companies")
    return fh 


    # ================================================================ 2. Main process
def main ():
    t0 =time .time ()
    master =pd .DataFrame (FIRMS ,columns =["thscode","name","alias","category"])
    master ["alias"]=master ["alias"].map (lambda x :"|".join (x ))
    master ["category_name"]=master ["category"].map (CAT_NAME )
    master .to_csv (D05_PANEL /"firm_master.csv",index =False ,encoding ="utf-8-sig")
    print ("[i] 四类分布:\n",master ["category"].value_counts ().sort_index ().to_string ())

    # ---------- Stock panel
    st =pd .read_csv (RAW_STOCK_FILE ,encoding ="utf-8-sig",dtype =str )
    num_cols =["high","low","close","changeRatio","volume","amount",
    "turnoverRatio","totalCapital","floatSharesOfAShares",
    "pe","pb","ps"]
    for c in num_cols :
        st [c ]=pd .to_numeric (st [c ].replace ("--",np .nan ),errors ="coerce")
    st ["date"]=pd .to_datetime (st ["time"])
    st =st .sort_values (["thscode","date"]).reset_index (drop =True )
    st ["ret"]=st .groupby ("thscode")["close"].pct_change ()# Formula (1)
    st .loc [st ["ret"].abs ()>0.5 ,"ret"]=np .nan # Eliminate obvious anomalies
    # Consistency check with changeRatio
    chk =st .dropna (subset =["ret","changeRatio"])
    consist =float (np .corrcoef (chk ["ret"],chk ["changeRatio"]/100 )[0 ,1 ])
    print (f"[i] Ret and changeRatio/100 correlation coefficient {consist :.4f}")

    mkt =st .groupby ("date")["ret"].mean ().rename ("mktret").reset_index ()
    st =st .merge (mkt ,on ="date",how ="left")

    # Market model abnormal returns (rolling 120-day beta)
    st ["ar"]=np .nan 
    for code ,g in st .groupby ("thscode"):
        g =g .sort_values ("date")
        y ,x =g ["ret"].to_numpy (),g ["mktret"].to_numpy ()
        ar =np .full (len (y ),np .nan )
        for i in range (120 ,len (y )):
            ys ,xs =y [i -120 :i ],x [i -120 :i ]
            ok =np .isfinite (ys )&np .isfinite (xs )
            if ok .sum ()<60 or not np .isfinite (y [i ])or not np .isfinite (x [i ]):
                continue 
            X =np .column_stack ([np .ones (ok .sum ()),xs [ok ]])
            b ,*_ =np .linalg .lstsq (X ,ys [ok ],rcond =None )
            ar [i ]=y [i ]-(b [0 ]+b [1 ]*x [i ])
        st .loc [g .index ,"ar"]=ar 
    st ["mar"]=st ["ret"]-st ["mktret"]# market adjusted return
    print (f"[i] Abnormal return coverage {st ['ar'].notna ().sum ():,} / {len (st ):,}")

    # control variables
    st ["size"]=np .log (st ["totalCapital"].replace (0 ,np .nan ))
    st ["turnover"]=st ["turnoverRatio"]
    st ["logamount"]=np .log1p (st ["amount"])
    st ["year"]=st ["date"].dt .year 
    for c in ["ret","turnover","size","pe","pb","ps","logamount"]:
        st [c +"_w"]=winsorize_by_year (st [c ],st ["year"])
        # hysteresis control
    for c in ["ret_w","turnover_w","size_w","pe_w","pb_w","ps_w",
    "logamount_w"]:
        st ["L_"+c ]=st .groupby ("thscode")[c ].shift (1 )

        # Forward cumulative abnormal returns
    for h in HORIZONS :
        if h ==0 :
            st ["AR_h0"]=st ["ar"]
            st ["MAR_h0"]=st ["mar"]
        else :
            st ["AR_h%d"%h ]=(st .groupby ("thscode")["ar"]
            .transform (lambda s :s .shift (-1 )
            .rolling (h ,min_periods =max (1 ,h //2 ))
            .sum ().shift (-(h -1 ))))
            st ["MAR_h%d"%h ]=(st .groupby ("thscode")["mar"]
            .transform (lambda s :s .shift (-1 )
            .rolling (h ,min_periods =max (1 ,h //2 ))
            .sum ().shift (-(h -1 ))))

            # ---------- Pre-exposure (Equation 7 Text Alternative Caliber)
    fh =build_firm_news ()
    meta =pd .read_csv (D01_TEXT /"news_meta.csv",
    usecols =["nid","trade_date","dup_weight"])
    dam =pd .read_csv (D03_MODEL /"news_damt_scores.csv",
    usecols =["nid","p_rel","p_gpu","p_cpu"])
    fn =fh .merge (meta ,on ="nid").merge (dam ,on ="nid")
    fn ["trade_date"]=pd .to_datetime (fn ["trade_date"])
    fn ["wg"]=fn ["dup_weight"]*fn ["p_rel"]*fn ["p_gpu"]
    fn ["wc"]=fn ["dup_weight"]*fn ["p_rel"]*fn ["p_cpu"]

    daily_fn =(fn .groupby (["thscode","trade_date"])
    .agg (wg =("wg","sum"),wc =("wc","sum"),
    w =("dup_weight","sum"),ndoc =("nid","count"))
    .reset_index ())
    tdays =pd .DataFrame ({"date":sorted (st ["date"].unique ())})
    exp_rows =[]
    for code in master ["thscode"]:
        g =daily_fn [daily_fn ["thscode"]==code ].rename (
        columns ={"trade_date":"date"})
        gg =tdays .merge (g ,on ="date",how ="left").fillna (
        {"wg":0 ,"wc":0 ,"w":0 ,"ndoc":0 })
        r =gg [["wg","wc","w","ndoc"]].rolling (EXP_WIN ,min_periods =60 ).sum ()
        r =r .shift (1 )# strictly in advance
        gpu_e =r ["wg"]/(r ["w"]+1e-6 )
        cpu_e =r ["wc"]/(r ["w"]+1e-6 )
        exp_rows .append (pd .DataFrame ({
        "thscode":code ,"date":gg ["date"],
        "GPUExposure_raw":gpu_e ,"CPUExposure_raw":cpu_e ,
        "exp_ndoc":r ["ndoc"]}))
    expo =pd .concat (exp_rows ,ignore_index =True )
    expo =expo .merge (master [["thscode","category"]],on ="thscode",how ="left")
    # Fall back to the same-day average of the same category when mentioning deficiencies
    grp_mean =(expo [expo ["exp_ndoc"]>=EXP_MIN_DOC ]
    .groupby (["category","date"])[["GPUExposure_raw",
    "CPUExposure_raw"]]
    .mean ().reset_index ()
    .rename (columns ={"GPUExposure_raw":"gpu_grp",
    "CPUExposure_raw":"cpu_grp"}))
    expo =expo .merge (grp_mean ,on =["category","date"],how ="left")
    thin =expo ["exp_ndoc"]<EXP_MIN_DOC 
    expo ["GPUExposure"]=np .where (thin ,expo ["gpu_grp"],expo ["GPUExposure_raw"])
    expo ["CPUExposure"]=np .where (thin ,expo ["cpu_grp"],expo ["CPUExposure_raw"])
    expo ["fallback"]=thin .astype (int )
    # Cross-sectional standardization (to facilitate coefficient interpretation: one standard deviation exposure)
    for c in ["GPUExposure","CPUExposure"]:
        m =expo .groupby ("date")[c ].transform ("mean")
        s =expo .groupby ("date")[c ].transform ("std")
        expo [c +"_z"]=(expo [c ]-m )/s .replace (0 ,np .nan )
    expo .to_csv (D05_PANEL /"exposure_daily.csv",index =False )
    print (f"[i] Exposure: Fallback ratio {thin .mean ():.1%} Coverage {expo ['GPUExposure'].notna ().mean ():.1%}")

    # ---------- Merger Index
    gd =pd .read_csv (D04_INDEX /"gcs_daily.csv")
    gd ["date"]=pd .to_datetime (gd ["bucket"])
    keep =["date","GCS","UGCS","UGCS_std","HighUGCS10","HighUGCS05",
    "n_news","n_src"]
    panel =(st .merge (expo [["thscode","date","GPUExposure","CPUExposure",
    "GPUExposure_z","CPUExposure_z","exp_ndoc",
    "fallback"]],on =["thscode","date"],how ="left")
    .merge (gd [keep ],on ="date",how ="left")
    .merge (master [["thscode","name","category"]],on ="thscode",
    how ="left"))
    panel ["L_GPUExposure"]=panel .groupby ("thscode")["GPUExposure_z"].shift (1 )
    panel ["L_CPUExposure"]=panel .groupby ("thscode")["CPUExposure_z"].shift (1 )
    panel .to_csv (D05_PANEL /"panel_daily.csv",index =False )
    print (f"[i] Japanese panel {panel .shape }")

    # ---------- Weekly / Monthly Panel
    iso =panel ["date"].dt .isocalendar ()
    panel ["bucket_W"]=iso ["year"].astype (str )+"-W"+iso ["week"].astype (int ).map ("{:02d}".format )
    panel ["bucket_M"]=panel ["date"].dt .strftime ("%Y-%m")

    for freq ,bcol ,fname in [("W","bucket_W","weekly"),
    ("M","bucket_M","monthly")]:
        gg =pd .read_csv (D04_INDEX /f"gcs_{fname }.csv")
        agg =(panel .groupby (["thscode",bcol ])
        .agg (ret =("ret","sum"),ar =("ar","sum"),
        mar =("mar","sum"),
        L_GPUExposure =("L_GPUExposure","last"),
        L_CPUExposure =("L_CPUExposure","last"),
        L_turnover_w =("L_turnover_w","mean"),
        L_size_w =("L_size_w","last"),
        L_pe_w =("L_pe_w","last"),L_pb_w =("L_pb_w","last"),
        L_ps_w =("L_ps_w","last"),
        L_ret_w =("L_ret_w","sum"),
        category =("category","first"),
        name =("name","first"),
        date =("date","last"))
        .reset_index ().rename (columns ={bcol :"bucket"}))
        agg =agg .sort_values (["thscode","bucket"])
        hs =[0 ,1 ,2 ,4 ]if freq =="W"else [0 ,1 ,2 ,3 ]
        for h in hs :
            if h ==0 :
                agg [f"AR_h{h }"]=agg ["ar"]
            else :
                agg [f"AR_h{h }"]=(agg .groupby ("thscode")["ar"]
                .transform (lambda s :s .shift (-1 )
                .rolling (h ,min_periods =1 ).sum ()
                .shift (-(h -1 ))))
        agg =agg .merge (gg [["bucket","GCS","UGCS","UGCS_std",
        "HighUGCS10","HighUGCS05","n_news"]],
        on ="bucket",how ="left")
        agg .to_csv (D05_PANEL /f"panel_{fname }.csv",index =False )
        print (f"[i] {fname } Panel {agg .shape }")

    rep ={
    "n_firms":int (len (master )),
    "category_counts":master ["category"].value_counts ().to_dict (),
    "ret_changeRatio_corr":round (consist ,4 ),
    "n_obs_daily":int (len (panel )),
    "ar_coverage":round (float (st ["ar"].notna ().mean ()),4 ),
    "exposure_fallback_rate":round (float (thin .mean ()),4 ),
    "firm_news_hits":int (len (fh )),
    "firms_with_news":int (fh ["thscode"].nunique ()),
    "exposure_window":EXP_WIN ,
    "elapsed_sec":round (time .time ()-t0 ,1 ),
    }
    json .dump (rep ,open (D05_PANEL /"s05_report.json","w",encoding ="utf-8"),
    ensure_ascii =False ,indent =2 )
    print (f"\n[i] S05 completed {time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
