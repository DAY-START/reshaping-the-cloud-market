# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""v6_s06_regressions.py
=====================
Step 6: All econometric tests of hypotheses H1–H5.

  H1/H3 Formula (8) two-way fixed effect + enterprise × date two-way clustering standard error + Wald(βG−βC=0)
  H2 Formula (9) pays extreme attention to triple interactions, quadratic terms, piecewise regression and upper tail quantiles
  H5 formula (10) local projection of three frequencies of day/week/month
  Event Study 5%/10% Trading Day [−5,+20] CAR (GPU High Exposure/CPU High Exposure/Difference) on UGCS
  Topic heterogeneity Each topic UGCS Repeat (8)
  H4 CSMAR investor sentiment later verification
  Robustness Nine categories of substitution index, placebo, exposure caliber replacement

Input: d05_panel_dataset/panel_{daily,weekly,monthly}.csv
       d04_index_gcs_ugcs/gcs_alt_daily.csv, gcs_topic_daily.csv
       investor_sentiment_data_v1_initial/total_sentiment_clean.csv
Output: d06_regression_results/*.csv and s06_report.json"""
import json ,sys ,time ,warnings 

import numpy as np 
import pandas as pd 

warnings .filterwarnings ("ignore")
sys .path .insert (0 ,str (__import__ ("pathlib").Path (__file__ ).parent ))
from v6_cfg_paths import (D04_INDEX ,D05_PANEL ,D06_REG ,D08_TAB ,
RAW_SENT_CLEAN )

CTRL =["L_ret_w","L_turnover_w","L_size_w","L_pe_w","L_pb_w","L_ps_w"]


# ============================================================ Measuring Tools
def _gmean (X ,codes ,K ):
    """By group mean (codes are integer codes 0..K-1)"""
    s =np .zeros ((K ,X .shape [1 ]))
    c =np .zeros (K )
    np .add .at (s ,codes ,X )
    np .add .at (c ,codes ,1 )
    return (s /np .maximum (c ,1 )[:,None ])[codes ]


def twoway_demean (X ,c1 ,c2 ,K1 ,K2 ,iters =12 ):
    X =X .astype (float ).copy ()
    for _ in range (iters ):
        X -=_gmean (X ,c1 ,K1 )
        X -=_gmean (X ,c2 ,K2 )
    return X 


def felm (df ,yvar ,xvars ,fe1 ="thscode",fe2 ="date",cluster =True ):
    """Two-way fixed effects OLS + two-way clustered robust standard errors (Cameron-Gelbach-Miller)."""
    d =df [[yvar ]+xvars +[fe1 ,fe2 ]].dropna ()
    if len (d )<200 :
        return None 
    c1 ,u1 =pd .factorize (d [fe1 ]);c2 ,u2 =pd .factorize (d [fe2 ])
    K1 ,K2 =len (u1 ),len (u2 )
    M =twoway_demean (d [[yvar ]+xvars ].to_numpy (float ),c1 ,c2 ,K1 ,K2 )
    y ,X =M [:,0 ],M [:,1 :]
    XtX =X .T @X 
    try :
        XtXi =np .linalg .inv (XtX )
    except np .linalg .LinAlgError :
        XtXi =np .linalg .pinv (XtX )
    beta =XtXi @(X .T @y )
    e =y -X @beta 
    N ,K =X .shape 
    if cluster :
        def meat (codes ,G ):
            S =np .zeros ((K ,K ))
            Xe =X *e [:,None ]
            acc =np .zeros ((G ,K ))
            np .add .at (acc ,codes ,Xe )
            for g in range (G ):
                S +=np .outer (acc [g ],acc [g ])
            return S 
        c12 =pd .factorize (pd .Series (c1 ).astype (str )+"_"+
        pd .Series (c2 ).astype (str ))[0 ]
        S =meat (c1 ,K1 )+meat (c2 ,K2 )-meat (c12 ,c12 .max ()+1 )
        dfc =(N -1 )/max (N -K -K1 -K2 +1 ,1 )
        V =XtXi @S @XtXi *dfc 
        V =V +np .eye (K )*1e-18 
        if np .any (np .diag (V )<0 ):# Non-positive timed return one-way enterprise clustering
            S =meat (c1 ,K1 )
            V =XtXi @S @XtXi *dfc 
    else :
        s2 =(e @e )/max (N -K ,1 )
        V =XtXi *s2 
    se =np .sqrt (np .maximum (np .diag (V ),1e-30 ))
    t =beta /se 
    from scipy import stats 
    p =2 *(1 -stats .t .cdf (np .abs (t ),max (N -K -1 ,1 )))
    r2 =1 -(e @e )/max (((y -y .mean ())**2 ).sum (),1e-12 )
    return {"vars":xvars ,"beta":beta ,"se":se ,"t":t ,"p":p ,
    "V":V ,"N":N ,"n_firm":K1 ,"n_date":K2 ,"within_r2":float (r2 )}


def wald_diff (res ,i ,j ):
    """Test β_i − β_j = 0"""
    from scipy import stats 
    d =res ["beta"][i ]-res ["beta"][j ]
    v =res ["V"][i ,i ]+res ["V"][j ,j ]-2 *res ["V"][i ,j ]
    if v <=0 :
        return d ,np .nan ,np .nan 
    chi =d **2 /v 
    return d ,float (chi ),float (1 -stats .chi2 .cdf (chi ,1 ))


def res_rows (res ,tag ,extra =None ):
    rows =[]
    for k ,v in enumerate (res ["vars"]):
        rows .append (dict (spec =tag ,var =v ,
        coef =res ["beta"][k ],se =res ["se"][k ],
        t =res ["t"][k ],p =res ["p"][k ],
        ci_lo =res ["beta"][k ]-1.96 *res ["se"][k ],
        ci_hi =res ["beta"][k ]+1.96 *res ["se"][k ],
        N =res ["N"],n_firm =res ["n_firm"],
        n_date =res ["n_date"],within_r2 =res ["within_r2"],
        **(extra or {})))
    return rows 


    # ============================================================ Main process
def main ():
    t0 =time .time ()
    pan =pd .read_csv (D05_PANEL /"panel_daily.csv",parse_dates =["date"])
    pan =pan [pan ["UGCS"].notna ()&pan ["L_GPUExposure"].notna ()].copy ()
    pan ["uG"]=pan ["UGCS_std"]*pan ["L_GPUExposure"]
    pan ["uC"]=pan ["UGCS_std"]*pan ["L_CPUExposure"]
    print (f"[i] Daily panel effective observation {len (pan ):,} Date {pan ['date'].nunique ()} Company {pan ['thscode'].nunique ()}")

    report ={}
    all_rows =[]

    # ----------------------------------------------- H1/H3 Formula (8)
    print ("\n[*] H1/H3 基准双向固定效应 …")
    main_rows ,wald_rows =[],[]
    for h in [0 ,1 ,3 ,5 ,10 ,20 ]:
        for dep ,dname in [(f"AR_h{h }","AR"),(f"MAR_h{h }","MAR")]:
            if dep not in pan :
                continue 
            r =felm (pan ,dep ,["uG","uC"]+CTRL )
            if r is None :
                continue 
            d ,chi ,pv =wald_diff (r ,0 ,1 )
            main_rows +=res_rows (r ,f"{dname }_h{h }",{"h":h ,"dep":dname })
            wald_rows .append (dict (dep =dname ,h =h ,diff =d ,chi2 =chi ,p =pv ,
            betaG =r ["beta"][0 ],betaC =r ["beta"][1 ],
            seG =r ["se"][0 ],seC =r ["se"][1 ],
            tG =r ["t"][0 ],tC =r ["t"][1 ],N =r ["N"]))
            if dname =="AR":
                print (f"    h={h :2d}  βG={r ['beta'][0 ]*1e4 :7.2f}bp"
                f" (t={r ['t'][0 ]:5.2f})  βC={r ['beta'][1 ]*1e4 :7.2f}bp"
                f" (t={r ['t'][1 ]:5.2f})  Wald p={pv :.4f}")
    pd .DataFrame (main_rows ).to_csv (D06_REG /"h1_main_fe.csv",index =False )
    wd =pd .DataFrame (wald_rows )
    wd .to_csv (D06_REG /"h1_wald_diff.csv",index =False )
    base =wd [(wd .dep =="AR")&(wd .h ==1 )].iloc [0 ]
    report ["H1"]={"h1_betaG_bp":round (base .betaG *1e4 ,2 ),
    "h1_betaC_bp":round (base .betaC *1e4 ,2 ),
    "h1_tG":round (base .tG ,3 ),"h1_tC":round (base .tC ,3 ),
    "wald_p":round (float (base .p ),5 ),"N":int (base .N )}

    # ----------------------------------------------- H2 Formula (9)
    print ("\n[*] H2 极端关注与非线性 …")
    h2_rows =[]
    for thr ,col in [("top10","HighUGCS10"),("top05","HighUGCS05")]:
        pan ["hi"]=pan [col ]
        pan ["uGh"]=pan ["uG"]*pan ["hi"]
        pan ["uCh"]=pan ["uC"]*pan ["hi"]
        for h in [1 ,5 ,10 ,20 ]:
            r =felm (pan ,f"AR_h{h }",["uG","uC","uGh","uCh"]+CTRL )
            if r is None :
                continue 
            d ,chi ,pv =wald_diff (r ,2 ,3 )
            h2_rows +=res_rows (r ,f"{thr }_h{h }",
            {"h":h ,"thr":thr ,"theta_diff":d ,
            "theta_diff_p":pv })
            print (f"    {thr } h={h :2d}  θG={r ['beta'][2 ]*1e4 :7.2f}bp"
            f" (t={r ['t'][2 ]:5.2f})  θC={r ['beta'][3 ]*1e4 :7.2f}bp"
            f"  diff p={pv :.4f}")
            # quadratic term
    pan ["u2G"]=(pan ["UGCS_std"].clip (lower =0 )**2 )*pan ["L_GPUExposure"]
    pan ["u2C"]=(pan ["UGCS_std"].clip (lower =0 )**2 )*pan ["L_CPUExposure"]
    for h in [1 ,5 ,10 ]:
        r =felm (pan ,f"AR_h{h }",["uG","uC","u2G","u2C"]+CTRL )
        if r :
            h2_rows +=res_rows (r ,f"quad_h{h }",{"h":h ,"thr":"quadratic"})
    pd .DataFrame (h2_rows ).to_csv (D06_REG /"h2_nonlinear.csv",index =False )

    # Quantile (upper tail)
    from scipy import stats as sstat 
    qrows =[]
    for q in [0.50 ,0.75 ,0.90 ,0.95 ]:
        sub =pan [pan ["UGCS_std"]>=pan ["UGCS_std"].quantile (q )]
        r =felm (sub ,"AR_h1",["uG","uC"]+CTRL )
        if r :
            qrows .append (dict (q =q ,betaG =r ["beta"][0 ],betaC =r ["beta"][1 ],
            tG =r ["t"][0 ],tC =r ["t"][1 ],N =r ["N"],
            diff =r ["beta"][0 ]-r ["beta"][1 ],
            diff_p =wald_diff (r ,0 ,1 )[2 ]))
    pd .DataFrame (qrows ).to_csv (D06_REG /"h2_quantile_slices.csv",index =False )
    report ["H2"]={"top10_thetaG_bp_h5":None ,"quantile_slices":len (qrows )}
    tmp =pd .DataFrame (h2_rows )
    sel =tmp [(tmp .spec =="top10_h5")&(tmp ["var"]=="uGh")]
    if len (sel ):
        report ["H2"]["top10_thetaG_bp_h5"]=round (float (sel .coef .iloc [0 ])*1e4 ,2 )
        report ["H2"]["top10_thetaG_p_h5"]=round (float (sel .p .iloc [0 ]),5 )

        # ----------------------------------------------- Event Research
    print ("\n[*] 事件研究 CAR …")
    gd =pd .read_csv (D04_INDEX /"gcs_daily.csv")
    gd ["date"]=pd .to_datetime (gd ["bucket"])
    tdays =np .sort (pan ["date"].unique ())
    tpos ={d :i for i ,d in enumerate (tdays )}
    car_rows =[]
    for thr ,col in [("top10","HighUGCS10"),("top05","HighUGCS05")]:
        ev =gd .loc [gd [col ]==1 ,"date"].tolist ()
        ev =[d for d in ev if d in tpos ]
        # Adjacent events are merged into event clusters (interval < 3 trading days, only the first day is retained)
        ev_s ,last =[],-99 
        for d in sorted (ev ):
            if tpos [d ]-last >=3 :
                ev_s .append (d )
            last =tpos [d ]
        med =pan ["L_GPUExposure"].median ()
        gpu_hi =pan .loc [pan ["L_GPUExposure"]>pan ["L_GPUExposure"]
        .quantile (0.7 ),"thscode"].unique ()
        cpu_hi =pan .loc [pan ["L_CPUExposure"]>pan ["L_CPUExposure"]
        .quantile (0.7 ),"thscode"].unique ()
        wide =pan .pivot_table (index ="date",columns ="thscode",values ="ar")
        for tau in range (-5 ,21 ):
            vals_g ,vals_c =[],[]
            for d in ev_s :
                i =tpos [d ]+tau 
                if 0 <=i <len (tdays ):
                    dd =tdays [i ]
                    if dd in wide .index :
                        row =wide .loc [dd ]
                        vg =row .reindex (gpu_hi ).mean ()
                        vc =row .reindex (cpu_hi ).mean ()
                        if np .isfinite (vg ):
                            vals_g .append (vg )
                        if np .isfinite (vc ):
                            vals_c .append (vc )
            if not vals_g :
                continue 
            car_rows .append (dict (thr =thr ,tau =tau ,n_event =len (ev_s ),
            ar_gpu =np .mean (vals_g ),ar_cpu =np .mean (vals_c ),
            se_gpu =np .std (vals_g ,ddof =1 )/np .sqrt (len (vals_g )),
            se_cpu =np .std (vals_c ,ddof =1 )/np .sqrt (len (vals_c )),
            ar_diff =np .mean (vals_g )-np .mean (vals_c ),
            se_diff =np .sqrt (np .var (vals_g ,ddof =1 )/len (vals_g )
            +np .var (vals_c ,ddof =1 )/len (vals_c ))))
        print (f"{thr }: {len (ev_s )} independent events")
    car =pd .DataFrame (car_rows )
    for thr in car ["thr"].unique ():
        m =car ["thr"]==thr 
        for c in ["gpu","cpu","diff"]:
            car .loc [m ,f"car_{c }"]=car .loc [m ,f"ar_{c }"].cumsum ()
            car .loc [m ,f"carse_{c }"]=np .sqrt (
            (car .loc [m ,f"se_{c }"]**2 ).cumsum ())
    car .to_csv (D06_REG /"event_study_car.csv",index =False )
    w =car [(car .thr =="top05")]
    report ["event_study"]={
    "n_event_top05":int (w ["n_event"].iloc [0 ])if len (w )else 0 ,
    "CAR_diff_0_20":round (float (w .loc [w .tau ==20 ,"car_diff"].iloc [0 ]
    -w .loc [w .tau ==-1 ,"car_diff"].iloc [0 ])*100 ,3 )
    if len (w )else None }

    # ----------------------------------------------- H5 local projection (three frequencies)
    print ("\n[*] H5 局部投影 …")
    lp_rows =[]
    for h in [0 ,1 ,3 ,5 ,10 ,20 ]:
        r =felm (pan ,f"AR_h{h }",["uG","uC"]+CTRL )
        if r :
            d ,chi ,pv =wald_diff (r ,0 ,1 )
            lp_rows .append (dict (freq ="daily",h =h ,betaG =r ["beta"][0 ],
            betaC =r ["beta"][1 ],seG =r ["se"][0 ],
            seC =r ["se"][1 ],diff =d ,diff_p =pv ,N =r ["N"]))
    for freq ,fname ,hs in [("weekly","weekly",[0 ,1 ,2 ,4 ]),
    ("monthly","monthly",[0 ,1 ,2 ,3 ])]:
        p2 =pd .read_csv (D05_PANEL /f"panel_{fname }.csv")
        p2 =p2 [p2 ["UGCS"].notna ()&p2 ["L_GPUExposure"].notna ()].copy ()
        p2 ["uG"]=p2 ["UGCS_std"]*p2 ["L_GPUExposure"]
        p2 ["uC"]=p2 ["UGCS_std"]*p2 ["L_CPUExposure"]
        p2 ["date"]=p2 ["bucket"]
        for h in hs :
            dep =f"AR_h{h }"
            if dep not in p2 :
                continue 
            r =felm (p2 ,dep ,["uG","uC"]+CTRL )
            if r :
                d ,chi ,pv =wald_diff (r ,0 ,1 )
                lp_rows .append (dict (freq =freq ,h =h ,betaG =r ["beta"][0 ],
                betaC =r ["beta"][1 ],seG =r ["se"][0 ],
                seC =r ["se"][1 ],diff =d ,diff_p =pv ,
                N =r ["N"]))
    lp =pd .DataFrame (lp_rows )
    lp .to_csv (D06_REG /"h5_local_projection.csv",index =False )
    print (lp .assign (betaG_bp =lambda x :(x .betaG *1e4 ).round (2 ),
    betaC_bp =lambda x :(x .betaC *1e4 ).round (2 ),
    diff_bp =lambda x :(x ['diff']*1e4 ).round (2 ))
    [["freq","h","betaG_bp","betaC_bp","diff_bp","diff_p","N"]]
    .to_string (index =False ))
    report ["H5"]={"daily_diff_h5_bp":round (float (
    lp [(lp .freq =="daily")&(lp .h ==5 )]["diff"].iloc [0 ])*1e4 ,2 ),
    "monthly_diff_h1_bp":round (float (
    lp [(lp .freq =="monthly")&(lp .h ==1 )]["diff"].iloc [0 ])*1e4 ,2 )
    if len (lp [(lp .freq =="monthly")&(lp .h ==1 )])else None }

    # -------------------------------------------------- Topic Heterogeneity
    print ("\n[*] 主题异质性 …")
    tp =pd .read_csv (D04_INDEX /"gcs_topic_daily.csv")
    tp ["date"]=pd .to_datetime (tp ["bucket"])
    th_rows =[]
    for tid ,g in tp .groupby ("topic"):
        g =g [["date","UGCS","topic_name"]].dropna ()
        if len (g )<200 :
            continue 
        s =g ["UGCS"]
        g ["u_std"]=(s -s .mean ())/s .std ()
        m =pan .merge (g [["date","u_std","topic_name"]],on ="date",how ="inner")
        m ["uG"]=m ["u_std"]*m ["L_GPUExposure"]
        m ["uC"]=m ["u_std"]*m ["L_CPUExposure"]
        r =felm (m ,"AR_h1",["uG","uC"]+CTRL )
        if r :
            d ,chi ,pv =wald_diff (r ,0 ,1 )
            th_rows .append (dict (topic =int (tid ),
            topic_name =g ["topic_name"].iloc [0 ],
            betaG =r ["beta"][0 ],betaC =r ["beta"][1 ],
            tG =r ["t"][0 ],tC =r ["t"][1 ],
            diff =d ,diff_p =pv ,N =r ["N"]))
    pd .DataFrame (th_rows ).to_csv (D06_REG /"topic_heterogeneity.csv",index =False )
    for r_ in th_rows :
        print (f"    {r_ ['topic_name']:12s} βG={r_ ['betaG']*1e4 :7.2f}bp"
        f" (t={r_ ['tG']:5.2f})  βC={r_ ['betaC']*1e4 :7.2f}bp"
        f"  diff p={r_ ['diff_p']:.3f}")

        # ----------------------------------------------- Robustness: Alternative Index
    print ("\n[*] 稳健性 —— 替代文本指数 …")
    alt =pd .read_csv (D04_INDEX /"gcs_alt_daily.csv")
    alt ["date"]=pd .to_datetime (alt ["bucket"])
    rb_rows =[]
    for c in [c for c in alt .columns if c .startswith ("alt_")]:
        a =alt [["date",c ]].dropna ().copy ()
        # Perform the same AR(5) residualization on the alternative index to ensure consistent caliber.
        s =a [c ].to_numpy (float )
        u =np .full (len (s ),np .nan )
        for t in range (260 ,len (s )):
            Z =np .column_stack ([np .ones (252 )]+
            [s [t -252 -p :t -p ]for p in range (1 ,6 )])
            yv =s [t -252 :t ]
            ok =np .isfinite (Z ).all (1 )&np .isfinite (yv )
            if ok .sum ()<120 :
                continue 
            b ,*_ =np .linalg .lstsq (Z [ok ],yv [ok ],rcond =None )
            zt =np .array ([1.0 ]+[s [t -p ]for p in range (1 ,6 )])
            if np .isfinite (zt ).all ():
                u [t ]=s [t ]-zt @b 
        a ["u"]=(u -np .nanmean (u ))/np .nanstd (u )
        m =pan .merge (a [["date","u"]],on ="date",how ="inner")
        m ["uG"]=m ["u"]*m ["L_GPUExposure"]
        m ["uC"]=m ["u"]*m ["L_CPUExposure"]
        r =felm (m ,"AR_h1",["uG","uC"]+CTRL )
        if r :
            d ,chi ,pv =wald_diff (r ,0 ,1 )
            rb_rows .append (dict (index =c ,betaG =r ["beta"][0 ],betaC =r ["beta"][1 ],
            tG =r ["t"][0 ],tC =r ["t"][1 ],diff =d ,
            diff_p =pv ,N =r ["N"]))
            print (f"    {c :16s} βG={r ['beta'][0 ]*1e4 :7.2f}bp (t={r ['t'][0 ]:5.2f})"
            f"  diff p={pv :.3f}")
    pd .DataFrame (rb_rows ).to_csv (D06_REG /"robust_alt_index.csv",index =False )

    # ----------------------------------------------- Robustness: exposure + placebo
    print ("\n[*] 稳健性 —— 暴露口径与安慰剂 …")
    rb2 =[]
    # Concept plate virtual caliber: G1 is high GPU exposure, G2 is high general computing power exposure
    pan ["dG1"]=(pan ["category"]=="G1").astype (float )
    pan ["dG2"]=(pan ["category"]=="G2").astype (float )
    pan ["uG_dum"]=pan ["UGCS_std"]*pan ["dG1"]
    pan ["uC_dum"]=pan ["UGCS_std"]*pan ["dG2"]
    r =felm (pan ,"AR_h1",["uG_dum","uC_dum"]+CTRL )
    if r :
        d ,chi ,pv =wald_diff (r ,0 ,1 )
        rb2 .append (dict (spec ="category_dummy_exposure",betaG =r ["beta"][0 ],
        betaC =r ["beta"][1 ],tG =r ["t"][0 ],tC =r ["t"][1 ],
        diff_p =pv ,N =r ["N"]))
        # Fixed base period exposure (first available value)
    first_exp =(pan .sort_values ("date").groupby ("thscode")
    [["L_GPUExposure","L_CPUExposure"]].first ()
    .rename (columns ={"L_GPUExposure":"fixG",
    "L_CPUExposure":"fixC"}).reset_index ())
    pm =pan .merge (first_exp ,on ="thscode",how ="left")
    pm ["uG_fix"]=pm ["UGCS_std"]*pm ["fixG"]
    pm ["uC_fix"]=pm ["UGCS_std"]*pm ["fixC"]
    r =felm (pm ,"AR_h1",["uG_fix","uC_fix"]+CTRL )
    if r :
        d ,chi ,pv =wald_diff (r ,0 ,1 )
        rb2 .append (dict (spec ="fixed_base_exposure",betaG =r ["beta"][0 ],
        betaC =r ["beta"][1 ],tG =r ["t"][0 ],tC =r ["t"][1 ],
        diff_p =pv ,N =r ["N"]))
        # Placebo 1: Scramble the date labels of UGCS
    rng =np .random .default_rng (20260802 )
    ug_map =pan [["date","UGCS_std"]].drop_duplicates ("date")
    pl_stats =[]
    for b in range (200 ):
        sh =ug_map .copy ()
        sh ["UGCS_std"]=rng .permutation (sh ["UGCS_std"].to_numpy ())
        m =pan .drop (columns =["UGCS_std"]).merge (sh ,on ="date")
        m ["uG"]=m ["UGCS_std"]*m ["L_GPUExposure"]
        m ["uC"]=m ["UGCS_std"]*m ["L_CPUExposure"]
        r =felm (m ,"AR_h1",["uG","uC"],cluster =False )
        if r :
            pl_stats .append (r ["beta"][0 ]-r ["beta"][1 ])
    pl_stats =np .array (pl_stats )
    real_diff =float (base ["diff"])# Note: base.diff cannot be written (the Series.diff method will be obtained)
    p_placebo =float ((np .abs (pl_stats )>=abs (real_diff )).mean ())
    rb2 .append (dict (spec ="placebo_shuffle_ugcs",betaG =np .nan ,betaC =np .nan ,
    tG =np .nan ,tC =np .nan ,diff_p =p_placebo ,N =len (pl_stats )))
    pd .DataFrame (rb2 ).to_csv (D06_REG /"robust_exposure_placebo.csv",index =False )
    pd .DataFrame ({"placebo_diff":pl_stats }).to_csv (
    D06_REG /"placebo_distribution.csv",index =False )
    print (f"Placebo: Proportion of |diff| exceeding the true value = {p_placebo :.3f}")
    report ["placebo_p"]=p_placebo 

    # ----------------------------------------------- H4 CSMAR Sentiment Verification
    print ("\n[*] H4 投资者情绪校验 …")
    try :
        svars =["TotalUsers","TotalPosts","AvgComments","BearishPosts",
        "BullishPosts","BullishSentIndexA","BullishSentIndexB",
        "SentConformIndex"]
        pan ["code6"]=pan ["thscode"].str [:6 ]
        keep6 =set (pan ["code6"].unique ())
        # The original sentiment library covers 5,500+ stocks and 7.8 million rows, and is filtered into 66 samples by 6-digit code blocks
        parts =[]
        for chunk in pd .read_csv (RAW_SENT_CLEAN ,encoding ="utf-8-sig",
        usecols =["PostDate","Stockcode"]+svars ,
        dtype =str ,chunksize =500_000 ):
            chunk .columns =[c .strip ().lstrip ("\ufeff")for c in chunk .columns ]
            chunk =chunk [chunk ["Stockcode"].notna ()]
            c6 =chunk ["Stockcode"].astype (str ).str .extract (r"(\d{6})")[0 ]
            chunk =chunk .assign (code6 =c6 )
            chunk =chunk [chunk ["code6"].isin (keep6 )]
            if len (chunk ):
                parts .append (chunk )
        sen =pd .concat (parts ,ignore_index =True )
        print (f"After filtering the emotion library {len (sen ):,} row / {sen ['code6'].nunique ()} only")
        sen ["date"]=pd .to_datetime (sen ["PostDate"],errors ="coerce")
        for c in svars :
            sen [c ]=pd .to_numeric (sen [c ],errors ="coerce")
        sm =pan .merge (sen [["code6","date"]+svars ],on =["code6","date"],
        how ="inner")
        print (f"Sentiment Matching Observation {len (sm ):,} Stocks {sm ['thscode'].nunique ()}")
        s_rows =[]
        for c in svars :
            y =c +"_t"
            sm [y ]=np .log1p (sm [c ])if c in ("TotalUsers","TotalPosts",
            "BearishPosts","BullishPosts",
            "AvgComments")else sm [c ]
            r =felm (sm ,y ,["uG","uC"]+CTRL )
            if r :
                d ,chi ,pv =wald_diff (r ,0 ,1 )
                s_rows .append (dict (sent_var =c ,betaG =r ["beta"][0 ],
                betaC =r ["beta"][1 ],tG =r ["t"][0 ],
                tC =r ["t"][1 ],diff =d ,diff_p =pv ,N =r ["N"]))
                print (f"    {c :20s} βG={r ['beta'][0 ]:8.4f} (t={r ['t'][0 ]:5.2f})"
                f"  βC={r ['beta'][1 ]:8.4f}  diff p={pv :.3f}")
        pd .DataFrame (s_rows ).to_csv (D06_REG /"h4_sentiment.csv",index =False )
        # Does the core coefficient change after emotion is added to the income model?
        sm ["senti"]=sm ["BullishSentIndexA"]
        r0 =felm (sm ,"AR_h1",["uG","uC"]+CTRL )
        r1 =felm (sm ,"AR_h1",["uG","uC","senti"]+CTRL )
        if r0 and r1 :
            pd .DataFrame ([
            dict (spec ="without_sentiment",betaG =r0 ["beta"][0 ],
            betaC =r0 ["beta"][1 ],N =r0 ["N"]),
            dict (spec ="with_sentiment",betaG =r1 ["beta"][0 ],
            betaC =r1 ["beta"][1 ],N =r1 ["N"])]).to_csv (
            D06_REG /"h4_sentiment_control.csv",index =False )
            report ["H4"]={"betaG_no_sent":round (r0 ["beta"][0 ]*1e4 ,2 ),
            "betaG_with_sent":round (r1 ["beta"][0 ]*1e4 ,2 ),
            "n_obs":int (r1 ["N"])}
    except Exception as e :
        print (f"[!] Sentiment verification failed: {e }")
        report ["H4"]={"error":str (e )}

    report ["elapsed_sec"]=round (time .time ()-t0 ,1 )
    json .dump (report ,open (D06_REG /"s06_report.json","w",encoding ="utf-8"),
    ensure_ascii =False ,indent =2 ,default =float )
    print (f"\n[i] S06 Complete {time .time ()-t0 :.0f}s")


if __name__ =="__main__":
    main ()
