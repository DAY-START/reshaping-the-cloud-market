# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import os 
import pandas as pd 

source_folder =r"D:\study\date\同花顺新闻"
output_folder =r"D:\study\date\news"
output_file =os .path .join (output_folder ,"同花顺爬虫汇总.csv")

os .makedirs (output_folder ,exist_ok =True )
data_list =[]

# Traverse the directory, increase fault tolerance, only read normal xls files, and automatically skip damaged files
for filename in os .listdir (source_folder ):
# Splice full path
    full_path =os .path .join (source_folder ,filename )
    # Only process files, exclude folders
    if not os .path .isfile (full_path ):
        continue 
        # Match xls suffix
    if filename .lower ().endswith (".xls"):
        try :
            df =pd .read_excel (full_path ,engine ="xlrd")
            data_list .append (df )
            print (f"Read: {filename }")
        except Exception as e :
            print (f"File reading failed and skipped {filename }, error: {str (e )}")

            # Merge, remove duplicates
all_data =pd .concat (data_list ,ignore_index =True )
all_data =all_data .drop_duplicates (subset =["原文链接"],keep ="first")

# Export CSV
all_data .to_csv (output_file ,index =False ,encoding ="utf-8-sig")

print (f"\nAll execution completed")
print (f"Total number of valid news: {len (all_data )}")
print (f"Output path: {output_file }")
