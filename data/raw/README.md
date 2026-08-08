# Raw Data — Provenance and Access

This directory documents the **raw (initial, uncleaned) dataset** used in the
paper and provides a minimal structural sample.

> **Restriction**: The data and scripts here are provided for reference only.
> No third party may use, copy, redistribute, or run them without the author's
> prior written consent. See `LICENSE` and `NOTICE.md` at the repository root.

## Sources of the raw (uncleaned) data
- **AI-compute news corpus** — produced by the collection scripts in
  `scripts/01_data_collection/`, drawn from:
  - THS (iFinD) news API crawling;
  - the public corpus **OpenNewsArchive**
    (https://opendatalab.com/OpenDataLab/OpenNewsArchive, released under the
    Creative Commons Attribution 4.0 International License, CC BY 4.0).
- The raw news is in an *uncleaned* state (pre-deduplication records, full
  article text, original fields) — i.e., the initial dataset described in
  Chapter 3 of the paper.

## Why the raw data is not distributed in this repository
- A single raw news file can reach hundreds of MB (e.g., the THS supplementary
  crawl is ~177 MB), which is unsuitable for direct Git tracking;
- Some sources (THS / iFinD) are bound by institutional licensing agreements
  that discourage public redistribution of the raw crawl.
- Therefore this repository provides **only the acquisition method plus a
  structural sample**; obtain the raw data by re-running the collection scripts
  or by accessing OpenNewsArchive directly.

## Sample
- `sample/sample_raw_news.csv` — the first 100 rows taken from the THS raw
  crawl, illustrating the original field structure (not the full dataset).
  Note: the news text in this sample retains its original Chinese content, as
  it is data rather than documentation.

## Full raw corpus (kept locally, not in this repository)
- The complete uncleaned AI-compute news corpus is **~305,000 records (~1.78 GB)**
  and is **retained locally by the author** (a local copy at
  `D:\AI_news_dataset_300k\`, with its own `README.md` describing schema and
  restrictions). It is **not committed here** because (a) it exceeds Git file-size
  limits and (b) the THS (iFinD) portion is bound by institutional licensing that
  discourages public redistribution.
- To obtain the full corpus, re-run the collection scripts in
  `scripts/01_data_collection/`, or access the CC BY 4.0 portion via OpenNewsArchive.
- Only the 100-row structural sample above is distributed in this repository.

## Core processed data (excluded by license)
The following **processed core data** are **not included** in this repository
because their institutional licenses (CSMAR / iFinD) prohibit redistribution.
Replication requires the researcher to obtain them from the providers:
- Stock daily/weekly/monthly returns and corporate-governance characteristics
  (`stock_data_v1_initial`, `ifind_v1_initial`);
- Constructed panel variables and exposure measures
  (`data_v2_experiment/d05_panel_dataset`, files `panel_*`, `exposure_*`);
- CSMAR investor sentiment (`investor_sentiment_data_v1_initial`).

> The paper's *Data Availability Statement* gives the formal English wording and
> points to this GitHub repository.
