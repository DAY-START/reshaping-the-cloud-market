# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Step 11: Theme name English patch.

Replace the Chinese topic names in the placed intermediate results with English labels to make the graphics, text tables and
The intermediate data are consistent among the three. This script only changes string labels and does not touch any numerical columns, so
There is no need to rerun the calculation chain of S04/S06.

Processing objects:
    d02_lexicon_tfidf/domain_lexicon.json topic_names
    d04_index_gcs_ugcs/gcs_topic_daily.csv topic_name
    d06_regression_results/topic_heterogeneity.csv
    d08_tables/TableR6_topic_heterogeneity.csv"""
import json 
import sys 
from pathlib import Path 

import pandas as pd 

sys .path .insert (0 ,str (Path (__file__ ).parent ))
from v6_cfg_paths import (D02_LEX ,D04_INDEX ,D06_REG ,D08_TAB ,
TOPIC_EN ,to_en_topic )


def patch_json (path :Path )->None :
    if not path .exists ():
        print (f"[skip] {path .name } does not exist")
        return 
    obj =json .load (open (path ,encoding ="utf-8"))
    names =obj .get ("topic_names")
    if names is None :
        print (f"[skip] {path .name } No topic_names field")
        return 
    if isinstance (names ,dict ):
        new ={k :TOPIC_EN .get (v ,v )for k ,v in names .items ()}
    else :
        new =[TOPIC_EN .get (v ,v )for v in names ]
    obj ["topic_names"]=new 
    json .dump (obj ,open (path ,"w",encoding ="utf-8"),
    ensure_ascii =False ,indent =1 )
    print (f"    [ok] {path .name }  ->  {list (new .values ())if isinstance (new ,dict )else new }")


def patch_csv (path :Path ,col :str ="topic_name")->None :
    if not path .exists ():
        print (f"[skip] {path .name } does not exist")
        return 
    df =pd .read_csv (path )
    if col not in df .columns :
        print (f"[skip] {path .name } None {col } Column")
        return 
    before =sorted (set (df [col ].dropna ().astype (str )))
    df [col ]=to_en_topic (df [col ])
    after =sorted (set (df [col ].dropna ().astype (str )))
    enc ="utf-8-sig"if path .parent .name .startswith ("d08")else "utf-8"
    df .to_csv (path ,index =False ,encoding =enc )
    n_cjk =sum (any ("\u4e00"<=ch <="\u9fa5"for ch in v )for v in after )
    print (f"[ok] {path .name } rows={len (df ):,} {len (before )} class -> {after } Residual Chinese class {n_cjk }")


def main ():
    print ("="*64 )
    print ("[STAGE] topic name -> English")
    print ("="*64 )
    print (f"[i] Mapping table {len (TOPIC_EN )} item:")
    for k ,v in TOPIC_EN .items ():
        print (f"      {k }  ->  {v }")

    print ("[*] Dictionary report JSON (S04 topic decomposition is named from here)")
    patch_json (D02_LEX /"s02_report.json")

    print ("[*] Index and regression results CSV")
    for p in [D04_INDEX /"gcs_topic_daily.csv",
    D06_REG /"topic_heterogeneity.csv",
    D08_TAB /"TableR6_topic_heterogeneity.csv"]:
        patch_csv (p )

    print ("[i] Done. No changes were made to the numeric columns.")


if __name__ =="__main__":
    main ()
