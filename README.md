# Reshaping the Cloud Market: AI Compute Attention, Ex Ante Exposure, and Stock Return Divergence

> **Repository**: https://github.com/DAY-START/reshaping-the-cloud-market

This repository accompanies the paper above. It organizes the data-acquisition
and analysis scripts, the raw-data provenance notes, and the manuscript
figures/tables in a reproducible, upload-ready structure.

## Restrictions on use (read first)

This repository is published **for reference and transparency only**.
**No other party is permitted to use, copy, modify, redistribute, or run the
data, experiments, or code contained herein without the explicit prior written
consent of the author.**

- The **data, experiments, and code** are provided "as is" for inspection.
- Core datasets (CSMAR, THS iFinD) are licensed to the author under institutional
  agreements that prohibit redistribution and are **not** included.
- See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md) for the full legal terms.
  Any permitted use must credit the author and this repository.

## Paper structure (where each script maps)
| Section | Topic | Pipeline step |
|---|---|---|
| 1 Introduction | Media attention → ex-ante exposure → return divergence | — |
| 2 Literature & Hypotheses | Attention, infrastructure exposure, text measurement | — |
| 3 Data & Variables | News collection, GCS/UGCS, exposure | `01`–`04` |
| 4 Empirical Design | TWFE, nonlinearity, event windows | `05` |
| 5 Stability & Identification | Placebo, robustness | `05` |
| 6 Conclusion | Findings & limitations | — |

## Directory layout
```
reshaping-the-cloud-market/
├── README.md
├── LICENSE                  # All rights reserved; restricted-use terms
├── NOTICE.md                # Explicit restriction on data/experiments/code
├── scripts/
│   ├── 01_data_collection/    # crawl/download raw AI-compute news (uncleaned)
│   ├── 02_text_processing/    # v6_s01 preprocess, v6_s02 lexicon/TF-IDF, v6_s03 DA-MT Transformer
│   ├── 03_index_construction/ # v6_s04 GCS / UGCS index construction
│   ├── 04_panel_exposure/     # v6_s05 panel & ex-ante business exposure
│   ├── 05_empirical/          # v6_s06 regressions (TWFE, event study, H1–H5)
│   ├── 06_figures_tables/     # v6_s07 + fig_v8 figure/table generation
│   ├── 07_paper_build/        # v6_s08–s11 manuscript fill / docx build
│   └── 99_legacy_drafts/      # early C-drive drafts + v6 helper scripts (reference only)
├── data/
│   └── raw/                   # provenance notes + small raw-news sample (core data excluded)
│       └── sample/sample_raw_news.csv
├── results/
│   ├── figures/               # Figure 1–7, A1–A2 (png + svg, as shown in paper)
│   └── tables/                # Table 1–16 (png, as shown in paper)
└── docs/
```

## Recommended execution order
1. **`scripts/01_data_collection/`** — acquire raw AI-compute news (THS/iFinD API, OpenNewsArchive).
2. **`scripts/02_text_processing/`** — `v6_s01` clean → `v6_s02` lexicon/TF-IDF → `v6_s03` domain-adaptive multi-task Transformer scoring.
3. **`scripts/03_index_construction/`** — `v6_s04` build GCS / UGCS indices.
4. **`scripts/04_panel_exposure/`** — `v6_s05` build panel & ex-ante exposure.
5. **`scripts/05_empirical/`** — `v6_s06` two-way fixed effects, nonlinearity, event-study regressions.
6. **`scripts/06_figures_tables/`** — `v6_s07` (+ `fig_v8`) render paper figures and tables.
7. **`scripts/07_paper_build/`** — `v6_s08`–`v6_s11` populate the manuscript document.

> `scripts/99_legacy_drafts/` contains earlier exploratory drafts and helper
> scripts kept for transparency; the canonical pipeline is `v6_s01`–`v6_s11`.

## Data availability & compliance
- **Raw (uncleaned) news** is acquired by `01_data_collection` or downloaded from
  OpenNewsArchive (CC BY 4.0). A 100-row sample is provided under `data/raw/sample/`.
  Raw files are large and partly institution-licensed, so they are **not** committed here.
- **Core processed data** (stock returns/characteristics from CSMAR & iFinD, constructed
  panel variables, CSMAR investor sentiment) are distributed under institution licensing
  agreements that **prohibit redistribution**; they are therefore **excluded** from this repo.
  Replication requires obtaining these from the providers.
- See `data/raw/README.md` for details, and the paper's *Data Availability Statement*.

## Note on Chinese string literals (intentional, not untranslated)

All human-facing text in this repository is written in English: **every code
comment, docstring, `print()`/`logging` message, CLI help string, and f-string
literal has been translated to English.** Each script also carries a
`RESTRICTED USE` header.

A number of **Chinese string constants remain deliberately untranslated** because
they are *functional data*, not UI text — the pipeline matches, searches, and
labels **Chinese-language news**, so these values must stay in Chinese to
function. Translating them would break the data flow (e.g. a `KeyError` or a
search that matches nothing). These are:

| Category | Why it must stay Chinese | Example |
|---|---|---|
| **Search keyword lexicons** | Used as query terms against Chinese news corpora | `CORE_KEYWORDS`, `CONTEXT_KEYWORDS`, `AI_KW`, `AI_TERMS`, `COMPUTE_KW` |
| **Field-name aliases** | Heterogeneous sources use Chinese or English keys; both are tried | `get(rec, "source", "来源", …)` |
| **CSV / output column headers** | Category labels written to result files | `"人工智能"`, `"AI算力"`, `"不相关"` |
| **Company / institution aliases** | Chinese entity names used for matching | `英伟达`, `昇腾`, `寒武纪` |
| **THS industry-board code→name maps** | Board codes map to Chinese names | `CONCEPTS["885728"] = "人工智能"` |
| **Regex / substring patterns** | Match Chinese characters in text | `re.compile("\|".join(map(re.escape, KW)))` |
| **Windows file paths** | Real on-disk paths include Chinese dir/file names | `D:\study\date\ai_computing_news\…` |
| **SQL fragments** | Match Chinese content in source databases | `WHERE category = '人工智能'` |
| **Chinese dict keys inside f-strings** | Interpolated keys must equal the Chinese news fields | `row["新闻日期"]` |
| **`龥` code-point constant** | Upper bound of the CJK Unified Ideographs block | `'\u9fff'` |

Rule of thumb: if a Chinese string is **looked up, searched for, or written as
data**, it stays Chinese; if it is **shown to a human or explains code**, it is
English. This is by design and does not affect the restriction on use stated
above.

## Citation
If you use this repository, please cite the accompanying paper and reference this repository:

> Jiang, T., & Li, X. (2026). *Reshaping the Cloud Market: AI Compute Attention, Ex Ante Exposure, and Stock Return Divergence.* [Journal]. Code and sample data: https://github.com/DAY-START/reshaping-the-cloud-market
