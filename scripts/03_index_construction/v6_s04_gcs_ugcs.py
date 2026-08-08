# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s04_gcs_ugcs.py
==================
Step 4: Independently construct the daily/weekly/monthly frequencies of GCS (Equation 5) and UGCS (Equation 6) (Equations F1 and F2),
        and generates a thematic decomposition index and a nine-category robustness alternative index.

Input: d01_text_processed/news_meta.csv
       d02_lexicon_tfidf/news_scores.csv
       d03_model_damt/news_damt_scores.csv
       stock_data_v1_initial/all_66stock_final.csv (market return/volatility)
       news_data_v1_initial/*.jsonl (overall news feed count)
Output: d04_index_gcs_ugcs/gcs_daily.csv / gcs_weekly.csv / gcs_monthly.csv
       d04_index_gcs_ugcs/gcs_alt_daily.csv Category 9 alternative caliber
       d04_index_gcs_ugcs/gcs_topic_daily.csv topic breakdown
       d04_index_gcs_ugcs/s04_report.json"""
import json ,sys ,time ,math 
from collections import Counter 

import numpy as np 
import pandas as pd 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import (D01_TEXT ,D02_LEX ,D03_MODEL ,D04_INDEX ,
RAW_STOCK_FILE ,RAW_NEWS_FILE )

# Rolling normalization window (Equation 5)
STD_WIN ={"D":60 ,"W":26 ,"M":12 }
STD_MIN ={"D":20 ,"W":10 ,"M":6 }
# ARX ​​prediction window (Equation 6/F2)
ARX_WIN ={"D":252 ,"W":52 ,"M":36 }
ARX_LAG ={"D":5 ,"W":2 ,"M":1 }
ARX_MIN ={"D":120 ,"W":30 ,"M":24 }

MAINSTREAM =("xinhuanet","people","cctv","chinanews","cnstock","stcn",
"cs.com","yicai","jiemian","21jingji","nbd","eeo",
"thepaper","sina","163","qq","sohu","ifeng","huanqiu")
INDUSTRY =("techweb","cnbeta","eet-china","eefocus","ijiwei","laoyaoba",
"semi","ithome","36kr","leiphone","jiqizhixin","csdn",
"c114","dvbcn","idcquan","ccidnet","chinaidc","elecfans")


# ------------------------------------------------------------------ tool
def signed_sqrt (z ):
    return np .sign (z )*np .sqrt (np .abs (z ))


def source_standardize (df ,val_col ,freq ,wcol ="dup_weight"):
    """Equation (5): within-source rolling normalization -> source equal-weighted aggregation -> signed square root."""
    win ,mino =STD_WIN [freq ],STD_MIN [freq ]
    g =(df .groupby (["source_std","bucket"])
    .apply (lambda x :np .average (x [val_col ],weights =x [wcol ])
    if x [wcol ].sum ()>0 else x [val_col ].mean (),
    include_groups =False )
    .rename ("v").reset_index ())
    g =g .sort_values (["source_std","bucket"])
    grp =g .groupby ("source_std")["v"]
    mu =grp .transform (lambda s :s .shift (1 ).rolling (win ,min_periods =mino ).mean ())
    sd =grp .transform (lambda s :s .shift (1 ).rolling (win ,min_periods =mino ).std ())
    g ["z"]=(g ["v"]-mu )/sd .replace (0 ,np .nan )
    g ["z"]=g ["z"].clip (-6 ,6 )
    z =g .dropna (subset =["z"]).groupby ("bucket")["z"].agg (["mean","count"])
    out =pd .DataFrame ({"bucket":z .index ,
    "Z":z ["mean"].to_numpy (),
    "n_src_eff":z ["count"].to_numpy ()})
    out ["GCS"]=signed_sqrt (out ["Z"].to_numpy ())
    return out 


def simple_index (df ,val_col ,wcol ="dup_weight"):
    """Simple weighted mean index without source standardization (used as an alternative caliber comparison)."""
    g =df .groupby ("bucket").apply (
    lambda x :np .average (x [val_col ],weights =x [wcol ])
    if x [wcol ].sum ()>0 else x [val_col ].mean (),include_groups =False )
    return g .rename ("v").reset_index ()


def rolling_arx (series ,X ,freq ):
    """Formula (6)/(F2): Strict rolling ARX one-step forward prediction, returning UGCS and fitting information."""
    y =series .to_numpy (dtype =float )
    n =len (y )
    P ,win ,mino =ARX_LAG [freq ],ARX_WIN [freq ],ARX_MIN [freq ]
    Xa =X .to_numpy (dtype =float )if X is not None else np .zeros ((n ,0 ))
    ug =np .full (n ,np .nan )
    pred =np .full (n ,np .nan )
    r2s =[]
    # Design matrix: constant + AR(1..P) + X_{t-1}
    for t in range (P ,n ):
        lo =max (P ,t -win )
        if t -lo <mino :
            continue 
        rows =np .arange (lo ,t )
        Zr =[np .ones (len (rows ))]
        for p in range (1 ,P +1 ):
            Zr .append (y [rows -p ])
        for j in range (Xa .shape [1 ]):
            Zr .append (Xa [rows -1 ,j ])
        Z =np .column_stack (Zr )
        yr =y [rows ]
        ok =np .isfinite (Z ).all (1 )&np .isfinite (yr )
        if ok .sum ()<mino :
            continue 
        Z ,yr =Z [ok ],yr [ok ]
        try :
            beta ,*_ =np .linalg .lstsq (Z ,yr ,rcond =None )
        except np .linalg .LinAlgError :
            continue 
        zt =[1.0 ]+[y [t -p ]for p in range (1 ,P +1 )]+[Xa [t -1 ,j ]for j in range (Xa .shape [1 ])]
        zt =np .array (zt )
        if not np .isfinite (zt ).all ():
            continue 
        yhat =float (zt @beta )
        pred [t ]=yhat 
        ug [t ]=y [t ]-yhat 
        res =yr -Z @beta 
        sst =((yr -yr .mean ())**2 ).sum ()
        if sst >0 :
            r2s .append (1 -(res **2 ).sum ()/sst )
    return ug ,pred ,(float (np .mean (r2s ))if r2s else np .nan )


    # ------------------------------------------------------------------ Main process
def main ():
    t0 =time .time ()

    # ---------- Loading
    meta =pd .read_csv (D01_TEXT /"news_meta.csv",
    usecols =["nid","date","trade_date","month",
    "source_std","dup_rank","dup_weight"])
    lex =pd .read_csv (D02_LEX /"news_scores.csv",
    usecols =["nid","gcs_lex","orientation","tone",
    "W_G","W_C","rel","intensity"])
    dam =pd .read_csv (D03_MODEL /"news_damt_scores.csv",
    usecols =["nid","gcs_da","p_rel","p_gpu","p_cpu",
    "p_pos","p_neg","topic_pred"])
    df =meta .merge (lex ,on ="nid").merge (dam ,on ="nid")
    df ["trade_date"]=pd .to_datetime (df ["trade_date"])
    print (f"[i] News-level sample {len (df ):,}")

    # frequency bucket
    iso =df ["trade_date"].dt .isocalendar ()
    df ["bucket_D"]=df ["trade_date"].dt .strftime ("%Y-%m-%d")
    df ["bucket_W"]=iso ["year"].astype (str )+"-W"+iso ["week"].astype (int ).map ("{:02d}".format )
    df ["bucket_M"]=df ["trade_date"].dt .strftime ("%Y-%m")

    # ---------- Market variable (X of ARX)
    st =pd .read_csv (RAW_STOCK_FILE ,encoding ="utf-8-sig",
    usecols =["time","thscode","close","totalCapital"])
    st ["close"]=pd .to_numeric (st ["close"],errors ="coerce")
    st ["totalCapital"]=pd .to_numeric (st ["totalCapital"],errors ="coerce")
    st =st .sort_values (["thscode","time"])
    st ["ret"]=st .groupby ("thscode")["close"].pct_change ()
    mkt =st .groupby ("time").agg (mktret =("ret","mean")).reset_index ()
    mkt ["mktvol"]=mkt ["mktret"].rolling (20 ,min_periods =10 ).std ()
    # Market cap weighted (industry portfolio proxy)
    st ["mcap"]=st ["totalCapital"]
    vw =(st .dropna (subset =["ret","mcap"])
    .groupby ("time").apply (lambda x :np .average (x ["ret"],
    weights =x ["mcap"]),
    include_groups =False )
    .rename ("indret").reset_index ())
    mkt =mkt .merge (vw ,on ="time",how ="left")
    mkt ["date"]=pd .to_datetime (mkt ["time"])

    # ---------- Overall news supply (full amount calculated on a daily basis before cleaning)
    supply_path =D04_INDEX /"news_supply_daily.csv"
    if supply_path .exists ():
        supply =pd .read_csv (supply_path )
    else :
        c =Counter ()
        import re as _re 
        from datetime import date as _date 
        rex =_re .compile (r'"date"\s*:\s*"(\d{4})\D{0,2}(\d{1,2})\D{0,2}(\d{1,2})')
        n_bad =0 
        with open (RAW_NEWS_FILE ,encoding ="utf-8")as f :
            for line in f :
                m =rex .search (line )
                if not m :
                    continue 
                y ,mo ,dd =int (m .group (1 )),int (m .group (2 )),int (m .group (3 ))
                try :# Verify to a real existing calendar date
                    c [_date (y ,mo ,dd ).isoformat ()]+=1 
                except ValueError :# Malformed strings such as 2023-03-49
                    n_bad +=1 
        if n_bad :
            print (f"[!] The {n_bad :,} items with abnormal dates in the original news have been removed")
        supply =pd .DataFrame ({"date":list (c ),"n_all_news":list (c .values ())})
        supply .to_csv (supply_path ,index =False )
    supply ["date"]=pd .to_datetime (supply ["date"],errors ="coerce")
    supply =supply .dropna (subset =["date"])
    print (f"[i] Overall news supply calendar {len (supply ):,} days")

    report ={"n_news":int (len (df ))}
    freq_out ={}

    # =============================================== Three-frequency independent structure
    for freq ,bcol in [("D","bucket_D"),("W","bucket_W"),("M","bucket_M")]:
        sub =df .rename (columns ={bcol :"bucket"}).copy ()
        main_idx =source_standardize (sub ,"gcs_da",freq )

        cnt =sub .groupby ("bucket").agg (
        n_news =("nid","count"),
        n_src =("source_std","nunique"),
        mean_rel =("p_rel","mean"),
        mean_gcs_raw =("gcs_da","mean")).reset_index ()
        idx =main_idx .merge (cnt ,on ="bucket",how ="right").sort_values ("bucket")
        idx ["GCS"]=idx ["GCS"].astype (float )

        # ----Bucket-level X variable
        if freq =="D":
            key =pd .to_datetime (idx ["bucket"])
            xt =pd .DataFrame ({"bucket":idx ["bucket"],"date":key })
            xt =xt .merge (mkt [["date","mktret","mktvol","indret"]],
            on ="date",how ="left")
            xt =xt .merge (supply ,on ="date",how ="left")
            xt ["dow"]=xt ["date"].dt .dayofweek 
            X =pd .DataFrame ({
            "mktret":xt ["mktret"].fillna (0 ),
            "indret":xt ["indret"].fillna (0 ),
            "mktvol":xt ["mktvol"].fillna (xt ["mktvol"].median ()),
            "lognews":np .log1p (idx ["n_news"].to_numpy ()),
            "logsupply":np .log1p (xt ["n_all_news"].fillna (0 ).to_numpy ()),
            "d_mon":(xt ["dow"]==0 ).astype (float ),
            "d_fri":(xt ["dow"]==4 ).astype (float )})
        else :
            gm =mkt .copy ()
            if freq =="W":
                gi =gm ["date"].dt .isocalendar ()
                gm ["bucket"]=gi ["year"].astype (str )+"-W"+gi ["week"].astype (int ).map ("{:02d}".format )
                sp =supply .copy ()
                si =sp ["date"].dt .isocalendar ()
                sp ["bucket"]=si ["year"].astype (str )+"-W"+si ["week"].astype (int ).map ("{:02d}".format )
            else :
                gm ["bucket"]=gm ["date"].dt .strftime ("%Y-%m")
                sp =supply .copy ()
                sp ["bucket"]=sp ["date"].dt .strftime ("%Y-%m")
            agg =gm .groupby ("bucket").agg (mktret =("mktret","sum"),
            indret =("indret","sum"),
            mktvol =("mktret","std")).reset_index ()
            spa =sp .groupby ("bucket")["n_all_news"].sum ().reset_index ()
            xt =idx [["bucket"]].merge (agg ,on ="bucket",how ="left").merge (spa ,on ="bucket",how ="left")
            X =pd .DataFrame ({
            "mktret":xt ["mktret"].fillna (0 ),
            "indret":xt ["indret"].fillna (0 ),
            "mktvol":xt ["mktvol"].fillna (xt ["mktvol"].median ()),
            "lognews":np .log1p (idx ["n_news"].to_numpy ()),
            "logsupply":np .log1p (xt ["n_all_news"].fillna (0 ).to_numpy ())})

        ug ,pred ,r2 =rolling_arx (idx ["GCS"].reset_index (drop =True ),
        X .reset_index (drop =True ),freq )
        idx ["GCS_pred"]=pred 
        idx ["UGCS"]=ug 
        s =idx ["UGCS"].dropna ()
        idx ["HighUGCS10"]=(idx ["UGCS"]>=s .quantile (0.90 )).astype (int )
        idx ["HighUGCS05"]=(idx ["UGCS"]>=s .quantile (0.95 )).astype (int )
        idx ["UGCS_std"]=(idx ["UGCS"]-s .mean ())/s .std ()

        name ={"D":"daily","W":"weekly","M":"monthly"}[freq ]
        idx .to_csv (D04_INDEX /f"gcs_{name }.csv",index =False )
        freq_out [name ]=idx 
        report [f"{name }"]={
        "n_buckets":int (len (idx )),
        "n_ugcs":int (idx ["UGCS"].notna ().sum ()),
        "arx_mean_R2":None if not np .isfinite (r2 )else round (r2 ,4 ),
        "GCS_mean":round (float (idx ["GCS"].mean ()),4 ),
        "GCS_sd":round (float (idx ["GCS"].std ()),4 ),
        "UGCS_sd":round (float (s .std ()),4 ),
        "AR1_GCS":round (float (idx ["GCS"].autocorr (1 )),4 ),
        "AR1_UGCS":round (float (idx ["UGCS"].autocorr (1 )),4 ),
        }
        print (f"[i] {name }: buckets {len (idx ):,}  UGCS {idx ['UGCS'].notna ().sum ():,}"
        f"  ARX R2 {r2 :.3f}")

        # =============================================== Alternate Caliber (Daily)
    sub =df .rename (columns ={"bucket_D":"bucket"}).copy ()
    alt =freq_out ["daily"][["bucket","GCS","UGCS"]].rename (
    columns ={"GCS":"GCS_main","UGCS":"UGCS_main"})

    # 1 Pure news quantity
    cnt =sub .groupby ("bucket")["nid"].count ().rename ("alt_count").reset_index ()
    alt =alt .merge (cnt ,on ="bucket",how ="left")
    # 2 Word frequency GCS (formula 4 dictionary baseline)
    a2 =source_standardize (sub ,"gcs_lex","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_lex"})
    # 3 TF-IDF GCS (W_G-W_C normalization)
    sub ["tfidf_or"]=(sub ["W_G"]-sub ["W_C"])/(sub ["W_G"]+sub ["W_C"]+1e-4 )
    a3 =source_standardize (sub ,"tfidf_or","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_tfidf"})
    # 4 Orientation without Tone
    sub ["or_only"]=sub ["p_gpu"]-sub ["p_cpu"]
    a4 =source_standardize (sub ,"or_only","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_orient"})
    # 5 GPU per side / 6 CPU per side
    sub ["gpu_side"]=sub ["p_rel"]*sub ["p_gpu"]*(sub ["p_pos"]-sub ["p_neg"])
    sub ["cpu_side"]=sub ["p_rel"]*sub ["p_cpu"]*(sub ["p_pos"]-sub ["p_neg"])
    a5 =source_standardize (sub ,"gpu_side","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_gpu_only"})
    a6 =source_standardize (sub ,"cpu_side","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_cpu_only"})
    # 7 Original news index (first event cluster)
    a7 =source_standardize (sub [sub ["dup_rank"]==1 ],"gcs_da","D")[
    ["bucket","GCS"]].rename (columns ={"GCS":"alt_original"})
    # 8 Mainstream media / 9 Industry media
    ms =sub [sub ["source_std"].str .contains ("|".join (MAINSTREAM ),na =False )]
    ind =sub [sub ["source_std"].str .contains ("|".join (INDUSTRY ),na =False )]
    a8 =source_standardize (ms ,"gcs_da","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_mainstream"})if len (ms )>5000 else None 
    a9 =source_standardize (ind ,"gcs_da","D")[["bucket","GCS"]].rename (columns ={"GCS":"alt_industry"})if len (ind )>5000 else None 

    for a in [a2 ,a3 ,a4 ,a5 ,a6 ,a7 ,a8 ,a9 ]:
        if a is not None :
            alt =alt .merge (a ,on ="bucket",how ="left")
    alt .to_csv (D04_INDEX /"gcs_alt_daily.csv",index =False )
    cols =[c for c in alt .columns if c .startswith ("alt_")]
    corr =alt [["GCS_main"]+cols ].corr ().loc ["GCS_main",cols ].round (3 )
    report ["alt_corr_with_main"]=corr .to_dict ()
    print ("[i] 替代口径与主指数相关系数：\n",corr .to_string ())

    # =============================================== Topic Breakdown (Daily)
    tnames =json .load (open (D02_LEX /"s02_report.json",
    encoding ="utf-8"))["topic_names"]
    trows =[]
    for k in sorted (tnames ):
        s_k =sub [sub ["topic_pred"]==int (k )]
        if len (s_k )<3000 :
            continue 
        gi =source_standardize (s_k ,"gcs_da","D")
        ugk ,_ ,_ =rolling_arx (gi ["GCS"].reset_index (drop =True ),None ,"D")
        gi ["UGCS"]=ugk 
        gi ["topic"]=int (k )
        gi ["topic_name"]=tnames [k ]
        gi ["n_news"]=s_k .groupby ("bucket")["nid"].count ().reindex (gi ["bucket"]).to_numpy ()
        trows .append (gi )
    topic_df =pd .concat (trows ,ignore_index =True )
    topic_df .to_csv (D04_INDEX /"gcs_topic_daily.csv",index =False )
    report ["topics"]={int (k ):int ((topic_df ["topic"]==int (k )).sum ())
    for k in topic_df ["topic"].unique ()}
    print (f"[i] Topic index {topic_df ['topic'].nunique ()} topics")

    report ["elapsed_sec"]=round (time .time ()-t0 ,1 )
    json .dump (report ,open (D04_INDEX /"s04_report.json","w",
    encoding ="utf-8"),ensure_ascii =False ,indent =2 )
    print (f"\n[i] S04 completed {time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
