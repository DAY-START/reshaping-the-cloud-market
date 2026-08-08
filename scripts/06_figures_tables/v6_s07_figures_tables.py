# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s07_figures_tables.py
========================
Step 7: Generate 300dpi English graphics according to Table 7 (graphic plan) and Table 8 (color scheme) of the paper,
        And output the text result table CSV.

Output graphics: d07_figures/Figure3_theme_composition.png
           d07_figures/Figure4_daily_gcs_ma_events.png
           d07_figures/Figure5_conditional_returns_ugcs.png
           d07_figures/Figure6_daily_weekly_monthly_response.png
           d07_figures/Figure7_event_study_car.png
           d07_figures/FigureA1_topic_corr_dendrogram.png
           d07_figures/FigureA2_confusion_matrices.png
           d07_figures/FigureA3_ablation_performance.png
           d07_figures/FigureA4_placebo_distribution.png
Output table: d08_tables/TableR1..R8*.csv"""
import json ,sys ,time 

import numpy as np 
import pandas as pd 
import matplotlib 
matplotlib .use ("Agg")
import matplotlib .pyplot as plt 
from matplotlib .ticker import FuncFormatter 

sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import (D02_LEX ,D03_MODEL ,D04_INDEX ,D05_PANEL ,
D06_REG ,D07_FIG ,D08_TAB ,PALETTE ,OKABE_ITO ,
FIG_DPI ,to_en_topic )


def _pick_font ():
    """All graphics use English labels, and sans-serif Western fonts commonly used in journals are preferred."""
    from matplotlib import font_manager 
    avail ={f .name for f in font_manager .fontManager .ttflist }
    for cand in ("Arial","Helvetica","Liberation Sans","DejaVu Sans"):
        if cand in avail :
            return cand 
    return "DejaVu Sans"


FIG_FONT =_pick_font ()
print (f"[i] figure font: {FIG_FONT }  (all labels in English)")

plt .rcParams .update ({
"font.family":[FIG_FONT ,"DejaVu Sans"],"font.size":9 ,
"axes.unicode_minus":False ,# Use ASCII for negative signs to avoid missing glyphs
"axes.linewidth":0.8 ,"axes.edgecolor":"#333333",
"axes.labelsize":9.5 ,"axes.titlesize":10.5 ,
"xtick.labelsize":8.5 ,"ytick.labelsize":8.5 ,
"legend.fontsize":8.5 ,"legend.frameon":False ,
"figure.dpi":110 ,"savefig.dpi":FIG_DPI ,"savefig.bbox":"tight",
})
C_GPU ,C_CPU =PALETTE .get ("gpu","#0072B2"),PALETTE .get ("cpu","#D55E00")
C_SPR =PALETTE .get ("spread","#7B2CBF")
C_HI ,C_NORM =PALETTE .get ("high","#E76F51"),PALETTE .get ("normal","#2A9D8F")
C_RAW ,C_TREND =PALETTE .get ("raw","#BDBDBD"),PALETTE .get ("trend","#000000")

BP =FuncFormatter (lambda v ,_ :f"{v *1e4 :.0f}")


def save (fig ,name ):
    p =D07_FIG /name 
    fig .savefig (p )
    plt .close (fig )
    print (f"    saved {name }")


    # ============================================================ Figure 3
def fig3_theme_composition ():
    tp =pd .read_csv (D04_INDEX /"gcs_topic_daily.csv")
    tp ["topic_name"]=to_en_topic (tp ["topic_name"])# Theme name English culture
    tp ["date"]=pd .to_datetime (tp ["bucket"])
    tp ["ym"]=tp ["date"].dt .to_period ("M").dt .to_timestamp ()
    piv =tp .pivot_table (index ="ym",columns ="topic_name",
    values ="n_news",aggfunc ="sum").fillna (0 )
    piv =piv [piv .sum ().sort_values (ascending =False ).index ]
    fig ,ax =plt .subplots (figsize =(7.2 ,3.4 ))
    ax .stackplot (piv .index ,piv .T .to_numpy (),
    labels =list (piv .columns ),
    colors =OKABE_ITO [:piv .shape [1 ]],alpha =0.92 ,lw =0.3 ,
    edgecolor ="white")
    ax .set_title ("Figure 3. Monthly AI-Compute News Composition by Theme")
    ax .set_xlabel ("Month");ax .set_ylabel ("Number of articles")
    ax .legend (loc ="upper left",ncol =2 ,fontsize =7.5 )
    ax .margins (x =0 )
    ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#CCCCCC")
    save (fig ,"Figure3_theme_composition.png")


    # ============================================================ Figure 4
def fig4_daily_gcs ():
    gd =pd .read_csv (D04_INDEX /"gcs_daily.csv")
    gd ["date"]=pd .to_datetime (gd ["bucket"])
    gd =gd .dropna (subset =["GCS"]).sort_values ("date")
    ma =gd ["GCS"].rolling (30 ,min_periods =10 ).mean ()
    fig ,ax =plt .subplots (figsize =(7.4 ,3.4 ))
    ax .scatter (gd ["date"],gd ["GCS"],s =3.2 ,c =C_RAW ,alpha =0.75 ,
    label ="Daily GCS",zorder =1 ,linewidths =0 )
    ax .plot (gd ["date"],ma ,color =C_TREND ,lw =1.5 ,
    label ="30-day moving average",zorder =3 )
    ax .axhline (0 ,color ="#888888",lw =0.6 ,ls ="-")
    events =[("2022-10-07","US export\ncontrols"),
    ("2022-11-30","ChatGPT\nrelease"),
    ("2023-10-17","Expanded\nchip curbs"),
    ("2025-01-27","DeepSeek\nshock")]
    ylim =ax .get_ylim ()
    for d ,lab in events :
        dt =pd .Timestamp (d )
        if gd ["date"].min ()<=dt <=gd ["date"].max ():
            ax .axvline (dt ,color ="#555555",ls ="--",lw =0.8 ,zorder =2 )
            ax .annotate (lab ,xy =(dt ,ylim [1 ]),xytext =(2 ,-4 ),
            textcoords ="offset points",fontsize =6.8 ,
            va ="top",ha ="left",color ="#333333",
            bbox =dict (boxstyle ="round,pad=0.22",fc ="white",
            ec ="#999999",lw =0.5 ,alpha =0.9 ))
    ax .set_title ("Figure 4. Daily GCS with 30-Day Moving Average and Major Events")
    ax .set_xlabel ("Date");ax .set_ylabel ("GCS (source-standardized)")
    ax .legend (loc ="lower left",ncol =2 )
    ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#DDDDDD")
    save (fig ,"Figure4_daily_gcs_ma_events.png")


    # ============================================================ Figure 5
def fig5_conditional_returns ():
    pan =pd .read_csv (D05_PANEL /"panel_daily.csv",parse_dates =["date"])
    pan =pan [pan ["UGCS_std"].notna ()&pan ["L_GPUExposure"].notna ()
    &pan ["AR_h5"].notna ()]
    hi =pan ["L_GPUExposure"]>pan ["L_GPUExposure"].quantile (0.7 )
    lo =pan ["L_CPUExposure"]>pan ["L_CPUExposure"].quantile (0.7 )
    qs =np .linspace (0.05 ,0.95 ,10 )
    edges =pan ["UGCS_std"].quantile (qs ).to_numpy ()
    xs ,g_m ,g_s ,c_m ,c_s =[],[],[],[],[]
    for i in range (len (edges )-1 ):
        m =(pan ["UGCS_std"]>=edges [i ])&(pan ["UGCS_std"]<edges [i +1 ])
        if m .sum ()<200 :
            continue 
        xs .append ((qs [i ]+qs [i +1 ])/2 *100 )
        a =pan .loc [m &hi ,"AR_h5"];b =pan .loc [m &lo ,"AR_h5"]
        g_m .append (a .mean ());g_s .append (a .std ()/np .sqrt (len (a )))
        c_m .append (b .mean ());c_s .append (b .std ()/np .sqrt (len (b )))
    xs =np .array (xs );g_m =np .array (g_m );g_s =np .array (g_s )
    c_m =np .array (c_m );c_s =np .array (c_s )
    fig ,ax =plt .subplots (figsize =(6.6 ,3.5 ))
    ax .fill_between (xs ,g_m -1.96 *g_s ,g_m +1.96 *g_s ,
    color =C_HI ,alpha =0.20 ,lw =0 )
    ax .plot (xs ,g_m ,color =C_HI ,lw =1.8 ,marker ="o",ms =3.6 ,
    label ="High GPU exposure (top 30%)")
    ax .fill_between (xs ,c_m -1.96 *c_s ,c_m +1.96 *c_s ,
    color =C_NORM ,alpha =0.20 ,lw =0 )
    ax .plot (xs ,c_m ,color =C_NORM ,lw =1.8 ,marker ="s",ms =3.4 ,ls ="--",
    label ="High general-compute exposure (top 30%)")
    ax .axhline (0 ,color ="#888888",lw =0.7 )
    ax .yaxis .set_major_formatter (BP )
    ax .set_title ("Figure 5. Conditional GPU-minus-CPU Returns across UGCS Percentiles")
    ax .set_xlabel ("UGCS percentile");ax .set_ylabel ("Mean CAR[0,+5] (bp)")
    ax .legend (loc ="upper left")
    ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#DDDDDD")
    save (fig ,"Figure5_conditional_returns_ugcs.png")


    # ============================================================ Figure 6
def fig6_three_frequency ():
    lp =pd .read_csv (D06_REG /"h5_local_projection.csv")
    fig ,axes =plt .subplots (1 ,3 ,figsize =(9.6 ,3.1 ))
    titles ={"daily":"(a) Daily (trading days)",
    "weekly":"(b) Weekly","monthly":"(c) Monthly"}
    xlabels ={"daily":"Horizon h (trading days)",
    "weekly":"Horizon h (weeks)","monthly":"Horizon h (months)"}
    for ax ,f in zip (axes ,["daily","weekly","monthly"]):
        d =lp [lp .freq ==f ].sort_values ("h")
        if not len (d ):
            ax .axis ("off");continue 
        h =d ["h"].to_numpy ()
        for col ,se ,c ,lab ,mk in [("betaG","seG",C_GPU ,"GPU exposure","o"),
        ("betaC","seC",C_CPU ,"CPU exposure","s")]:
            y ,s =d [col ].to_numpy (),d [se ].to_numpy ()
            ax .fill_between (h ,y -1.96 *s ,y +1.96 *s ,color =c ,
            alpha =0.16 ,lw =0 )
            ax .plot (h ,y ,color =c ,lw =1.6 ,marker =mk ,ms =3.6 ,label =lab )
        ax .plot (h ,d ["diff"].to_numpy (),color =C_SPR ,lw =1.5 ,ls ="-.",
        marker ="^",ms =3.4 ,label ="GPU − CPU spread")
        ax .axhline (0 ,color ="#888888",lw =0.7 )
        ax .yaxis .set_major_formatter (BP )
        ax .set_title (titles [f ]);ax .set_xlabel (xlabels [f ])
        ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#DDDDDD")
    axes [0 ].set_ylabel ("Coefficient (bp per 1 s.d. UGCS)")
    axes [0 ].legend (loc ="best")
    fig .suptitle ("Figure 6. Daily, Weekly, and Monthly GPU–CPU Responses",
    y =1.03 ,fontsize =10.5 )
    save (fig ,"Figure6_daily_weekly_monthly_response.png")


    # ============================================================ Figure 7
def fig7_event_study ():
    car =pd .read_csv (D06_REG /"event_study_car.csv")
    fig ,axes =plt .subplots (1 ,2 ,figsize =(9.0 ,3.3 ),sharey =True )
    for ax ,thr ,lab in zip (axes ,["top10","top05"],
    ["(a) Top 10% UGCS days","(b) Top 5% UGCS days"]):
        d =car [car .thr ==thr ].sort_values ("tau")
        if not len (d ):
            ax .axis ("off");continue 
        tau =d ["tau"].to_numpy ()
        for c ,se ,col ,name ,mk in [
        ("car_gpu","carse_gpu",C_GPU ,"High GPU exposure","o"),
        ("car_cpu","carse_cpu",C_CPU ,"High CPU exposure","s"),
        ("car_diff","carse_diff",C_SPR ,"GPU − CPU","^")]:
            y ,s =d [c ].to_numpy (),d [se ].to_numpy ()
            ax .fill_between (tau ,y -1.96 *s ,y +1.96 *s ,color =col ,
            alpha =0.15 ,lw =0 )
            ax .plot (tau ,y ,color =col ,lw =1.5 ,marker =mk ,ms =2.8 ,label =name )
        ax .axvline (0 ,color ="#555555",ls ="--",lw =0.8 )
        ax .axhline (0 ,color ="#888888",lw =0.7 )
        ax .set_title (f"{lab }  (n = {int (d ['n_event'].iloc [0 ])} events)")
        ax .set_xlabel ("Event time τ (trading days)")
        ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#DDDDDD")
        ax .yaxis .set_major_formatter (BP )
    axes [0 ].set_ylabel ("Cumulative abnormal return (bp)")
    axes [0 ].legend (loc ="upper left")
    fig .suptitle ("Figure 7. Cumulative Abnormal Returns around Extreme UGCS Events",
    y =1.04 ,fontsize =10.5 )
    save (fig ,"Figure7_event_study_car.png")


    # ============================================================ Figure A1
def figA1_topic_corr ():
    tp =pd .read_csv (D04_INDEX /"gcs_topic_daily.csv")
    tp ["topic_name"]=to_en_topic (tp ["topic_name"])# Theme name English culture
    piv =tp .pivot_table (index ="bucket",columns ="topic_name",values ="GCS")
    piv =piv .dropna (thresh =int (0.5 *piv .shape [1 ]))
    corr =piv .corr ()
    from scipy .cluster .hierarchy import linkage ,dendrogram 
    from scipy .spatial .distance import squareform 
    dist =1 -corr .to_numpy ()
    np .fill_diagonal (dist ,0 )
    Z =linkage (squareform (dist ,checks =False ),method ="average")
    fig =plt .figure (figsize =(8.4 ,3.6 ))
    gs =fig .add_gridspec (1 ,2 ,width_ratios =[1.0 ,1.25 ],wspace =0.32 )
    ax0 =fig .add_subplot (gs [0 ])
    dn =dendrogram (Z ,labels =list (corr .columns ),ax =ax0 ,
    color_threshold =0.6 *max (Z [:,2 ]),
    above_threshold_color ="#999999")
    ax0 .set_title ("(a) Hierarchical clustering of themes")
    ax0 .set_ylabel ("1 − correlation")
    ax0 .tick_params (axis ="x",rotation =42 ,labelsize =7 )
    for lb in ax0 .get_xticklabels ():
        lb .set_ha ("right")
    order =dn ["ivl"]
    cm =corr .loc [order ,order ]
    ax1 =fig .add_subplot (gs [1 ])
    im =ax1 .imshow (cm .to_numpy (),cmap ="Purples",vmin =-0.1 ,vmax =1.0 )
    ax1 .set_xticks (range (len (order )));ax1 .set_yticks (range (len (order )))
    ax1 .set_xticklabels (order ,rotation =42 ,ha ="right",fontsize =7 )
    ax1 .set_yticklabels (order ,fontsize =7 )
    for i in range (len (order )):
        for j in range (len (order )):
            v =cm .iloc [i ,j ]
            ax1 .text (j ,i ,f"{v :.2f}",ha ="center",va ="center",fontsize =6 ,
            color ="white"if v >0.55 else "#333333")
    ax1 .set_title ("(b) Theme GCS correlation heatmap")
    fig .colorbar (im ,ax =ax1 ,fraction =0.045 ,pad =0.03 )
    fig .suptitle ("Figure A1. Topic Correlation Heatmap and Hierarchical Clustering",
    y =1.05 ,fontsize =10.5 )
    save (fig ,"FigureA1_topic_corr_dendrogram.png")


    # ============================================================ Figure A2
def figA2_confusion ():
    cms =json .load (open (D03_MODEL /"confusion_matrices.json",encoding ="utf-8"))
    full =cms .get ("Full",{})
    names ={"rel":("Relevance",["Non-rel","Relevant"]),
    "obj":("Object",["GPU","CPU","Both/Neutral"]),
    "tone":("Tone",["Positive","Negative","Neutral"]),
    "rlt":("Relation",["Substitute","Complement",
    "Co-expansion","Constraint"])}
    keys =[k for k in ["rel","obj","tone","rlt"]if k in full ]
    fig ,axes =plt .subplots (1 ,len (keys ),figsize =(2.55 *len (keys ),2.9 ))
    if len (keys )==1 :
        axes =[axes ]
    for ax ,k in zip (axes ,keys ):
        M =np .array (full [k ],dtype =float )
        Mn =M /np .maximum (M .sum (1 ,keepdims =True ),1 )
        im =ax .imshow (Mn ,cmap ="Purples",vmin =0 ,vmax =1 )
        lab =names [k ][1 ][:M .shape [0 ]]
        ax .set_xticks (range (M .shape [1 ]));ax .set_yticks (range (M .shape [0 ]))
        ax .set_xticklabels (lab ,rotation =35 ,ha ="right",fontsize =6.5 )
        ax .set_yticklabels (lab ,fontsize =6.5 )
        for i in range (M .shape [0 ]):
            for j in range (M .shape [1 ]):
                ax .text (j ,i ,f"{Mn [i ,j ]:.2f}",ha ="center",va ="center",
                fontsize =6.2 ,
                color ="white"if Mn [i ,j ]>0.55 else "#333333")
        ax .set_title (names [k ][0 ],fontsize =9 )
        ax .set_xlabel ("Predicted",fontsize =7.5 )
    axes [0 ].set_ylabel ("Actual",fontsize =7.5 )
    fig .suptitle ("Figure A2. DA-MT-FinTransformer Confusion Matrices "
    "(out-of-time sample, row-normalized)",y =1.06 ,fontsize =10 )
    save (fig ,"FigureA2_confusion_matrices.png")


    # ============================================================ Figure A3
def figA3_ablation ():
    m =json .load (open (D03_MODEL /"ablation_metrics.json",encoding ="utf-8"))
    order =[k for k in ["B0","B1","B2","B3","Full"]if k in m ]
    tone =[m [k ]["oos"].get ("tone_macroF1",np .nan )for k in order ]
    obj =[m [k ]["oos"].get ("obj_macroF1",np .nan )for k in order ]
    auc =[m [k ]["oos"].get ("tone_auroc",np .nan )for k in order ]
    x =np .arange (len (order ));w =0.26 
    fig ,ax =plt .subplots (figsize =(6.4 ,3.2 ))
    ax .bar (x -w ,tone ,w ,color =C_GPU ,label ="Tone Macro-F1")
    ax .bar (x ,obj ,w ,color =C_CPU ,label ="Object Macro-F1")
    ax .bar (x +w ,auc ,w ,color =C_SPR ,label ="Tone AUROC")
    for xi ,v in zip (x -w ,tone ):
        if np .isfinite (v ):
            ax .text (xi ,v +0.008 ,f"{v :.3f}",ha ="center",fontsize =6.4 )
    for xi ,v in zip (x ,obj ):
        if np .isfinite (v ):
            ax .text (xi ,v +0.008 ,f"{v :.3f}",ha ="center",fontsize =6.4 )
    ax .set_xticks (x );ax .set_xticklabels (order )
    ax .set_ylim (0 ,1.05 )
    ax .set_title ("Figure A3. Out-of-Time Ablation Performance "
    "(2025-01 to 2026-06)")
    ax .set_xlabel ("Model specification");ax .set_ylabel ("Score")
    ax .legend (ncol =3 ,loc ="upper left")
    ax .grid (axis ="y",ls =":",lw =0.5 ,color ="#DDDDDD")
    save (fig ,"FigureA3_ablation_performance.png")


    # ============================================================ Figure A4
def figA4_placebo ():
    p =pd .read_csv (D06_REG /"placebo_distribution.csv")["placebo_diff"]*1e4 
    w =pd .read_csv (D06_REG /"h1_wald_diff.csv")
    real =float (w [(w .dep =="AR")&(w .h ==1 )]["diff"].iloc [0 ])*1e4 
    fig ,ax =plt .subplots (figsize =(6.2 ,3.0 ))
    ax .hist (p ,bins =32 ,color =C_RAW ,edgecolor ="white",lw =0.4 ,
    label ="Placebo (shuffled UGCS dates, 200 draws)")
    ax .axvline (real ,color =C_SPR ,lw =1.8 ,
    label =f"Actual βG − βC = {real :.1f} bp")
    ax .axvline (0 ,color ="#888888",lw =0.7 )
    ax .set_title ("Figure A4. Placebo Distribution of the GPU–CPU Coefficient Gap")
    ax .set_xlabel ("βG − βC (bp per 1 s.d. UGCS)");ax .set_ylabel ("Frequency")
    ax .legend (loc ="upper left")
    save (fig ,"FigureA4_placebo_distribution.png")


    # ============================================================ Table
def make_tables ():
# R1 descriptive statistics
    pan =pd .read_csv (D05_PANEL /"panel_daily.csv",parse_dates =["date"])
    v =["ret","ar","mar","turnover_w","size_w","pe_w","pb_w","ps_w",
    "GPUExposure_z","CPUExposure_z","UGCS_std","GCS"]
    v =[c for c in v if c in pan ]
    d =pan [v ].describe (percentiles =[0.25 ,0.5 ,0.75 ]).T 
    d ["skew"]=pan [v ].skew ();d ["kurt"]=pan [v ].kurt ()
    d .round (4 ).to_csv (D08_TAB /"TableR1_descriptive_stats.csv",
    encoding ="utf-8-sig")

    # R2 ablation
    m =json .load (open (D03_MODEL /"ablation_metrics.json",encoding ="utf-8"))
    rows =[]
    for k ,r in m .items ():
        row ={"Model":k ,"Specification":r ["desc"]}
        for stage in ["valid","oos"]:
            for mk ,mv in r [stage ].items ():
                row [f"{stage }_{mk }"]=mv 
        rows .append (row )
    pd .DataFrame (rows ).to_csv (D08_TAB /"TableR2_ablation.csv",
    index =False ,encoding ="utf-8-sig")

    # R3 main return
    w =pd .read_csv (D06_REG /"h1_wald_diff.csv")
    w2 =w [w .dep =="AR"].copy ()
    for c in ["betaG","betaC","diff","seG","seC"]:
        w2 [c +"_bp"]=(w2 [c ]*1e4 ).round (3 )
    w2 [["h","betaG_bp","seG_bp","tG","betaC_bp","seC_bp","tC",
    "diff_bp","chi2","p","N"]].to_csv (
    D08_TAB /"TableR3_h1_main.csv",index =False ,encoding ="utf-8-sig")

    # R4 non-linear
    h2 =pd .read_csv (D06_REG /"h2_nonlinear.csv")
    h2 [h2 ["var"].isin (["uG","uC","uGh","uCh","u2G","u2C"])].to_csv (
    D08_TAB /"TableR4_h2_nonlinear.csv",index =False ,encoding ="utf-8-sig")

    # R5 local projection
    lp =pd .read_csv (D06_REG /"h5_local_projection.csv")
    for c in ["betaG","betaC","diff","seG","seC"]:
        lp [c +"_bp"]=(lp [c ]*1e4 ).round (3 )
    lp .to_csv (D08_TAB /"TableR5_local_projection.csv",index =False ,
    encoding ="utf-8-sig")

    # R6 theme
    th =pd .read_csv (D06_REG /"topic_heterogeneity.csv")
    th ["topic_name"]=to_en_topic (th ["topic_name"])# Theme name English culture
    for c in ["betaG","betaC","diff"]:
        th [c +"_bp"]=(th [c ]*1e4 ).round (3 )
    th .to_csv (D08_TAB /"TableR6_topic_heterogeneity.csv",index =False ,
    encoding ="utf-8-sig")

    # R7 Robustness
    rb =pd .read_csv (D06_REG /"robust_alt_index.csv")
    rb2 =pd .read_csv (D06_REG /"robust_exposure_placebo.csv")
    for c in ["betaG","betaC","diff"]:
        if c in rb :
            rb [c +"_bp"]=(rb [c ]*1e4 ).round (3 )
    rb .to_csv (D08_TAB /"TableR7a_robust_alt_index.csv",index =False ,
    encoding ="utf-8-sig")
    rb2 .to_csv (D08_TAB /"TableR7b_robust_exposure_placebo.csv",index =False ,
    encoding ="utf-8-sig")

    # R8 emotions
    try :
        s =pd .read_csv (D06_REG /"h4_sentiment.csv")
        s .round (5 ).to_csv (D08_TAB /"TableR8_h4_sentiment.csv",index =False ,
        encoding ="utf-8-sig")
    except Exception :
        pass 

        # R9 event research key window
    car =pd .read_csv (D06_REG /"event_study_car.csv")
    wins =[(-1 ,1 ),(0 ,5 ),(0 ,10 ),(0 ,20 )]
    rows =[]
    for thr in car ["thr"].unique ():
        d =car [car .thr ==thr ].set_index ("tau")
        for a ,b in wins :
            sub =d .loc [a :b ]
            rows .append (dict (thr =thr ,window =f"[{a },{b }]",
            CAR_gpu_bp =sub ["ar_gpu"].sum ()*1e4 ,
            CAR_cpu_bp =sub ["ar_cpu"].sum ()*1e4 ,
            CAR_diff_bp =sub ["ar_diff"].sum ()*1e4 ,
            t_diff =sub ["ar_diff"].sum ()/
            np .sqrt ((sub ["se_diff"]**2 ).sum ())))
    pd .DataFrame (rows ).round (3 ).to_csv (D08_TAB /"TableR9_event_windows.csv",
    index =False ,encoding ="utf-8-sig")
    print ("    tables written")


def main ():
    t0 =time .time ()
    print ("[*] Generate graphics…")
    for fn in [fig3_theme_composition ,fig4_daily_gcs ,fig5_conditional_returns ,
    fig6_three_frequency ,fig7_event_study ,figA1_topic_corr ,
    figA2_confusion ,figA3_ablation ,figA4_placebo ]:
        try :
            fn ()
        except Exception as e :
            print (f"[!] {fn .__name__ } Failure: {e }")
    print ("[*] Generate table…")
    make_tables ()
    print (f"[i] S07 completed {time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
