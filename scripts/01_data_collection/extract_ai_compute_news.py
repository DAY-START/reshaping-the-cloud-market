# -*- coding:utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================


"""Large-scale news library AI computing power news filtering program

Input:
D:/software/python/project/news_work/raw_news

Output:
D:/study/date/ai_computing_news

Function:
Filter from industry-wide news:
After 2021-07-01
AI computing power related news"""


import os 
import json 
from datetime import datetime 
from collections import Counter 



# ==================================================
# path
# ==================================================


INPUT_DIR =r"D:\软件\python\项目\news_work\raw_news"


OUTPUT_DIR =r"D:\study\date\ai_computing_news"



OUTPUT_FILE =os .path .join (
OUTPUT_DIR ,
"AI_Computing_News_Raw_after_20210701.jsonl"
)


REPORT_FILE =os .path .join (
OUTPUT_DIR ,
"AI_Computing_Filter_Report.txt"
)



# ==================================================
# time
# ==================================================


START_DATE =datetime (
2021 ,
7 ,
1 
)



# ==================================================
# core keywords
# ==================================================


KEYWORDS =[


# Computing power

"算力",
"AI算力",
"智能算力",
"计算力",

"算力中心",
"智算中心",
"智能计算中心",

"算力网络",
"东数西算",

"高性能计算",
"超级计算",
"超算",
"HPC",



# cloud

"云算力",
"云计算",
"云服务",
"云平台",

"数据中心",
"IDC",



# GPU

"GPU",
"英伟达",
"NVIDIA",

"A100",
"H100",
"H200",
"B100",
"B200",
"GH200",

"GPU服务器",
"GPU云",
"GPU租赁",

"AI服务器",
"智能服务器",



# AI chip

"AI芯片",
"AI加速卡",
"计算卡",

"国产GPU",
"国产CPU",

"芯片",
"半导体",



# large model

"大模型",
"生成式人工智能",
"AIGC",

"ChatGPT",
"GPT",

"模型训练",
"模型推理",

"深度学习",
"机器学习"



]



# ==================================================
# Date parsing
# ==================================================


def parse_date (value ):

    if not value :

        return None 


    try :

        return datetime .strptime (
        value [:10 ],
        "%Y-%m-%d"
        )


    except :

        return None 




        # ==================================================
        # news judgment
        # ==================================================


def match_keywords (text ):


    hits =[]


    text =text .lower ()



    for k in KEYWORDS :


        if k .lower ()in text :

            hits .append (k )



    return hits 



    # ==================================================
    # main program
    # ==================================================


def main ():


    os .makedirs (
    OUTPUT_DIR ,
    exist_ok =True 
    )



    total =0 

    date_pass =0 

    selected =0 

    error =0 


    keyword_counter =Counter ()



    print ("Start scanning news library...")
    print (INPUT_DIR )



    with open (
    OUTPUT_FILE ,
    "w",
    encoding ="utf-8"
    )as fout :



    # Traverse all files


        for root ,dirs ,files in os .walk (INPUT_DIR ):


            for file in files :


                if not file .endswith (".jsonl"):

                    continue 



                filepath =os .path .join (
                root ,
                file 
                )



                print (
                "\n正在处理:",
                filepath 
                )



                with open (
                filepath ,
                "r",
                encoding ="utf-8"
                )as fin :



                    for line in fin :


                        total +=1 



                        try :

                            news =json .loads (line )


                        except :


                            error +=1 

                            continue 



                            # date


                        date =parse_date (
                        news .get ("date")
                        )



                        if not date :

                            continue 



                        if date <START_DATE :

                            continue 



                        date_pass +=1 



                        # text

                        content =news .get (
                        "content",
                        ""
                        )



                        if not content :

                            continue 



                        hits =match_keywords (
                        content 
                        )



                        if not hits :

                            continue 



                        selected +=1 



                        for h in hits :

                            keyword_counter [h ]+=1 



                            # Add tag

                        news ["_dataset"]="AI_Computing_News_Raw"

                        news ["_filter_date"]="2021-07-01_after"

                        news ["_keyword_hits"]=hits 



                        fout .write (

                        json .dumps (
                        news ,
                        ensure_ascii =False 
                        )

                        +"\n"

                        )



                        # Refresh regularly

                        if selected %5000 ==0 :

                            fout .flush ()



                            # schedule

                        if total %100000 ==0 :


                            print (
                            "scanning:",
                            total ,
                            "|Time matches:",
                            date_pass ,
                            "|AI computing power:",
                            selected 
                            )



                            # =============================
                            # Output report
                            # =============================


    with open (
    REPORT_FILE ,
    "w",
    encoding ="utf-8"
    )as f :


        f .write (
        "AI算力新闻筛选报告\n"
        )

        f .write (
        "="*60 +"\n"
        )


        f .write (
        f"Number of news scanned: {total } \n"
        )


        f .write (
        f"News after 2021:{date_pass }\n"
        )


        f .write (
        f"AI computing power news:{selected }\n"
        )


        f .write (
        f"Parsing failed: {error } \n \n"
        )



        f .write (
        "关键词频次:\n"
        )


        for k ,v in keyword_counter .most_common ():

            f .write (
            f"{k }: {v }\n"
            )



    print ("\n==============================")

    print ("Finish")

    print (
    "General news:",
    total 
    )

    print (
    "After 2021:",
    date_pass 
    )

    print (
    "AI computing power:",
    selected 
    )

    print (
    "Output:",
    OUTPUT_FILE 
    )



if __name__ =="__main__":

    main ()
