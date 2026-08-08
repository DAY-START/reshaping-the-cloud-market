# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import json
from pathlib import Path

source = Path(r"D:\study\date\news\data\AI_Computing_News_Complete.jsonl")
target = Path(
    r"D:\study\date\news\data"
    r"\AI_Computing_News_Complete_20210701_20260630.jsonl"
)

kept = outside = 0
with source.open("r", encoding="utf-8") as src, target.open(
    "w", encoding="utf-8"
) as dst:
    for line in src:
        record = json.loads(line)
        date_text = record.get("date", "")
        if "2021-07-01" <= date_text <= "2026-06-30":
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
        else:
            outside += 1

print(f"Complete records of the research period = {kept} Outside the time range, retained in the general archive = {outside}")
