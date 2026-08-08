# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

best = {}
with source.open(encoding="utf-8") as handle:
    for line in handle:
        item = json.loads(line)
        key = str(item.get("uuid") or item.get("url") or "")
        if key not in best or len(item.get("content", "")) > len(best[key].get("content", "")):
            best[key] = item

with target.open("w", encoding="utf-8") as handle:
    for item in sorted(best.values(), key=lambda x: (x.get("date", ""), x.get("uuid", ""))):
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"input={sum(1 for _ in source.open(encoding='utf-8'))}")
print(f"unique={len(best)}")
