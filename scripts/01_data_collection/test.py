# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import os
import json
from collections import Counter

INPUT_DIR = r"D:\软件\python\项目\news_work\raw_news"

counter = Counter()

for root, dirs, files in os.walk(INPUT_DIR):
    for file in files:
        if not file.endswith(".jsonl"):
            continue

        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    news = json.loads(line)
                    d = news.get("date", "")
                    if len(d) >= 7:
                        counter[d[:7]] += 1
                except:
                    pass

for k in sorted(counter):
    if k.startswith("2023"):
        print(k, counter[k])
