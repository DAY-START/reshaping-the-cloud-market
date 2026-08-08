# -*- coding:utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================


"""Analysis of time distribution of AI computing power news

Input:
AI_Computing_News_Raw_after_20210701.jsonl

Output:
1. Annual statistics csv
2. Monthly statistics csv
3. Time trend chart"""


import os 
import json 
from collections import Counter 
import matplotlib .pyplot as plt 
import pandas as pd 



# ==============================
# file path
# ==============================


INPUT_FILE =r"D:\study\date\ai_computing_news\AI_Computing_News_Raw_after_20210701.jsonl"


OUTPUT_DIR =r"D:\study\date\ai_computing_news"



# ==============================
# statistics
# ==============================


year_counter =Counter ()

month_counter =Counter ()



total =0 



print ("Start counting time distribution...")



with open (
INPUT_FILE ,
"r",
encoding ="utf-8"
)as f :


    for line in f :


        try :

            news =json .loads (line )


        except :

            continue 



        date =news .get ("date","")


        if len (date )>=7 :


            year =date [:4 ]

            month =date [:7 ]


            year_counter [year ]+=1 

            month_counter [month ]+=1 


        total +=1 



print ("Total news volume:",total )



# ==============================
# annual save
# ==============================


year_df =pd .DataFrame (

{
"year":list (year_counter .keys ()),
"count":list (year_counter .values ())
}

)


year_df =year_df .sort_values (
"year"
)



year_csv =os .path .join (
OUTPUT_DIR ,
"AI_Computing_News_Year_Distribution.csv"
)


year_df .to_csv (
year_csv ,
index =False ,
encoding ="utf-8-sig"
)



# ==============================
# monthly save
# ==============================


month_df =pd .DataFrame (

{
"month":list (month_counter .keys ()),
"count":list (month_counter .values ())
}

)


month_df =month_df .sort_values (
"month"
)



month_csv =os .path .join (
OUTPUT_DIR ,
"AI_Computing_News_Month_Distribution.csv"
)


month_df .to_csv (
month_csv ,
index =False ,
encoding ="utf-8-sig"
)



# ==============================
# Plot monthly trends
# ==============================


plt .figure (
figsize =(14 ,5 )
)


plt .plot (

month_df ["month"],

month_df ["count"]

)


plt .xticks (
rotation =60 
)


plt .xlabel (
"Month"
)


plt .ylabel (
"News Count"
)


plt .title (
"AI Computing News Monthly Distribution"
)


plt .tight_layout ()



figure_file =os .path .join (

OUTPUT_DIR ,

"AI_Computing_News_Time_Distribution.png"

)


plt .savefig (
figure_file ,
dpi =300 
)



plt .close ()



print ("\n完成")

print ("Annual Documents:")
print (year_csv )

print ("Monthly documents:")
print (month_csv )

print ("Trend chart:")
print (figure_file )



print ("\n年度统计:")

print (year_df )
