# Response to Reviewers — *Reshaping the Cloud Market* (Sustainability, Major Revision)

**Decision received:** Major Revision
**Our stance:** We accept the core critique — the sustainability framing was
superficial and several conclusions overstated statistical significance. This
document (1) maps every reviewer point to a concrete action, (2) reports the new
analyses we ran in `experiments/`, and (3) states, where we do **not** modify, the
reason why.

---

## Master action map

| # | Reviewer point | Severity | Action | Status | Evidence |
|---|---|---|---|---|---|
| 1 | Sustainability视角表层化 | 🔴 | Reframe contribution at market-structure/resource-allocation level + add category-based resource-intensity heterogeneity | Partial (see 07/08) | `08/results_category_heterogeneity.csv`, `07/README.md` |
| 2 | H1方向与结果相反却含糊 | 🔴 | Honestly state H1 **rejected**; rebuild theory for mid-horizon negative GPU returns | Paper edit | §2.5, §4.2, §6.1 |
| 3 | 安慰剂 p≈0.30 却称显著 | 🔴 | Re-ran placebo at **1000** iterations; report p≈0.30 honestly; downgrade conclusions | Experiment done | `01/summary_placebo_1000.json` |
| 4 | 8种替代指标全不显著 | 🔴 | Explain why (measurement precision); state result is conditional on one model | Experiment done | `05/summary_alt_index.json` |
| 5 | CSMAR外部校验全不显著 | 🔴 | State H4 **unsupported**; delete "方向一致" wording | Paper edit | §4.5 |
| 6 | 上尾5%与上尾10%方向相反 | 🟠 | Report full [0,20] for both; discuss threshold sensitivity | Experiment done | `04/summary_event_tails.json` |
| 7 | 事前暴露 vs 后验分类 | 🟠 | Fixed-base exposure robustness (pre-ChatGPT classifier) | Experiment done | `06/summary_fixed_base.json` |
| 8 | 月度结果全不显著 | 🟠 | Emphasize monthly null; discuss attention-vs-revaluation | Paper edit | §5.1/§6.2 |
| 9 | "不解释可持续" vs "可持续贡献" | 🟠 | Bound the contribution explicitly; no longer equate returns with ESG performance | Paper edit | §1, §6 |
| 10 | 样本量小/统计效力 | 🟡 | Power analysis: observed effect ≈ −19% of MDES | Experiment done | `02/summary_power.json` |
| 11 | DA-MT验证不充分 (Kappa) | 🟡 | Data gap: annotation count/κ not in deposit → commit to report in revision + add ablation detail | Reason given | §3.5, §4.1 |
| 12 | 多重检验未校正 | 🟡 | BH + Bonferroni on H1–H5 family: **0/8 survive** | Experiment done | `03/summary_multiple_testing.json` |
| 13 | 反向因果/内生性 | 🟡 | Leader/ST/placebo already in paper; add IV/quasi-natural-exp caveat as limitation | Paper edit | §5.3 |
| 14 | 过于技术化(公式/算法) | 🟠 | Move 12 formulas + Algorithm 1 to Appendix; keep economic meaning in text | Paper edit | §3, App. |
| 15 | 缺独立 Discussion | 🟠 | Add standalone Discussion (lit comparison, meaning, limits, sustainability implication) | Paper edit | new §5.6/§6 |
| 16 | 占位符未完成 | 🟢 | Fill Author Contributions, COI, Acknowledgments (mentor status), DAS GitHub link | Paper edit | back matter |

---

## Detailed responses

### Major Issue 1 — Sustainability视角表层化 (partially addressed; data-limited)
We agree. Two honest moves:
- **Reframing (done in text):** the empirically supported sustainability contribution is
  at the *market-structure / resource-allocation* level — AI-compute attention
  re-prices the physical compute chain (GPU, fabs, cloud/data-center capacity) that
  underpins the energy- and water-intensive infrastructure of the digital/green
  transition. This is a legitimate Sustainability angle without overclaiming.
- **Heterogeneity test (done, `08/`):** with no firm-level carbon/water data, we use
  the four business categories as a transparent **coarse proxy** for resource
  intensity. Result: the GPU-CPU difference is **not monotonic** and **not significant**
  in either subsample (HIGH p=0.52, LOW p=0.47), so we do **not** claim a clean
  gradient. True firm-level emissions/water splits require environmental disclosures
  we do not hold (see `07/README.md`).
- **Why we do NOT add a firm-level sustainable-performance regression:** our licensed
  data contain only market/valuation/size/liquidity fields — **no TFP, R&D, capex,
  energy, or emissions**. Fabricating a proxy would be worse than stating the gap. We
  provide a runnable scaffold (`07/run_sustainability_perf.py`) and the exact data
  requirement. *Reason for not modifying this specific test: missing source data.*

### Major Issue 2 — H1 direction reversed (honest rewrite)
The data contradict H1: daily βG=+1.72 bp (n.s.), h=20 βG=−14.31 bp (n.s.), opposite
to the predicted positive sign. We will (a) state plainly that **H1 is rejected**,
(b) replace the "收益分化" hedge with "mid-horizon reversal inconsistent with H1",
(c) add a theory paragraph on why GPU-heavy firms may see *delayed* negative revaluation
(capex/energy cost overhang, supply-chain crowding-out). No masking of the sign.

### Major Issue 3 — Placebo p≈0.30 (done, `01/`)
We replicated the original 200-iteration placebo (seed 20260802) and recovered
**p=0.325**, confirming the reviewer's reading. We extended it to **1000 iterations**
(p=0.351; Monte-Carlo SE drops from ~0.033 to ~0.015). The conclusion is unchanged: the H1
difference is **not** distinguishable from random date shuffles. We downgrade all
H1/H3 wording to "suggestive only".

### Major Issue 4 — alternative text indices insignificant (done, `05/`)
All seven alternative text measures (raw news count, word-frequency/lexical GCS,
TF-IDF GCS, tone-free orientation, GPU-only attention, CPU-only attention,
original-media index) yield an insignificant
GPU-CPU difference (all diff_p>0.55). Interpretation: only the DA-MT-FinTransformer
**orientation+tone** extraction isolates genuine GPU-vs-CPU attention; the alternatives
are noisier measures, not independent confirmations. We state the result is **conditional
on a specific measurement construction** and qualify its economic interpretation.

> **Correction note:** the original manuscript text stated "eight" alternative indices and
> listed mainstream-/industry-media variants that were not separately estimated. We corrected
> the count to **seven** to match the actual robustness table (TableR7a, 7 rows), and updated
> the body text (§5.5 / Table 14 note) accordingly. We do not fabricate the two missing media
> splits.

### Major Issue 5 — CSMAR/H4 unsupported (honest rewrite)
We will state explicitly that **H4 is not supported**: BullishSentIndexA p=0.098 and
AvgComments p=0.120 are both insignificant; we delete "方向一致" phrasing and report
the results as null.

### Contradiction 6 — event-study tail sign flip (done, `04/`)
At [0,20], the GPU-CPU CAR difference is **−15.37 bp** for top-10% events but
**+14.64 bp** for top-5% events — opposite signs. We report both full windows and
discuss threshold sensitivity; we no longer selectively emphasize only the top-10% result.

### Contradiction 7 — ex-ante vs ex-post exposure (done, `06/`)
Fixed-base robustness using each firm's **first-available (pre-ChatGPT)** exposure as a
time-invariant classifier gives Wald p=0.230 — qualitatively similar to baseline, so the
classification is **not** purely a post-2022 hindsight artifact, but remains statistically
weak. Reported as a robustness check.

### Issue 8 — monthly null (emphasize)
We elevate the monthly-insignificant result and discuss what it implies for the
"short attention vs persistent revaluation" debate (daily/weekly weak signal vanishes
at monthly frequency → consistent with a transient attention effect, not fundamental
re-pricing).

### Issue 9 — bounding the sustainability claim (text)
We explicitly separate: *stock returns are not sustainable-performance*; the paper's
contribution is to the **resource-allocation / market-structure** understanding of the
AI-compute transition. Title/abstract/keywords are softened accordingly.

### Issue 10 — power (done, `02/`)
MDES at 80% power with 66 clusters ≈ 0.00050; observed |βG| ≈ 0.00009 ≈ **−19% of MDES**.
The study is under-powered to detect the hypothesized effect → honest qualifier.

### Issue 11 — model validation / Kappa (reason + commitment)
The labelled corpus size and inter-annotator Cohen's κ are **not retained in the
deposit** (data-lifecycle gap). We (a) commit to reporting both in the revision,
(b) add the existing 5-tier ablation detail to §3.5/§4.1, and (c) note the overfitting
risk openly. *Reason for not adding κ now: source annotation logs not in our possession;
will be regenerated and reported.*

### Issue 12 — multiple testing (done, `03/`)
BH + Bonferroni on the 8-test H1–H5 family: **0 survive at 5%**. This is the single
strongest honesty check and directly justifies downgrading every hypothesis claim.

### Issue 13 — reverse causality (caveat)
Leader/ST/placebo checks already exist (§5.4). We add an explicit limitation that
IV/quasi-natural-experiment identification is absent and frame results as reduced-form.

### Issue 14 — move formulas to appendix (text)
The 12 equations and Algorithm 1 move to a new **Appendix B**; the body keeps only the
economic intuition (common attention, ex-ante exposure, difference-in-differences logic).

### Issue 15 — standalone Discussion (text)
A new **Discussion** section is added (literature comparison, theoretical/practical
meaning, limitations, sustainability implication) — distinct from Results and Conclusion.

### Issue 16 — placeholders (text)
Author Contributions, Conflicts of Interest, Acknowledgments (clarifying Prof. Li
Xiaoming's role — co-author vs. mentor), and the Data Availability Zenodo dual-record DOI link are
completed.

---

## Experiments folder (`reshaping-the-cloud-market/experiments/`)
| Folder | What it does | Key result |
|---|---|---|
| `01_placebo_1000/` | Replicates + extends placebo to 1000 iters | p=0.351 (1000 iters), p=0.325 (200 iters) — not significant |
| `02_power_analysis/` | MDES at 80% power, 66 clusters | observed ≈ −19% of MDES |
| `03_multiple_testing/` | BH + Bonferroni on H1–H5 family | 0/8 survive |
| `04_event_study_tail/` | top5% vs top10% full windows | sign flip confirmed |
| `05_alt_index/` | seven alternative indices | all p>0.55; conditional on DA-MT model |
| `06_fixed_base_exposure/` | pre-ChatGPT fixed classifier | Wald p=0.230 |
| `07_sustainability_performance/` | scaffold + data-gap note | blocked (no ESG data) |
| `08_carbon_water_heterogeneity/` | category proxy for resource intensity | not monotonic, n.s. |

## Items we deliberately do NOT change (with reasons)
1. **Firm-level sustainable-performance regression** — no TFP/R&D/capex/energy data in
   licensed set; scaffolded, not fabricated (`07/README.md`).
2. **Figure numbering vs repo PNG** — pre-existing author constraint ("d不动"); cosmetic,
   does not affect the revision's scientific content.
3. **CSMAR numeric values (7,801,956 / 100,419)** — these are real and reproducible (verified
   against source); we only *restate them honestly* (H4 null), we do not alter the figures.
4. **Annotation Cohen's κ** — source logs unavailable; committed to report in revision.

**Bottom line:** we have executed every feasible revision and new analysis, honestly
downgraded the conclusions (multiple-testing + placebo + power all point the same way),
and given explicit, defensible reasons where data prevent a change the reviewer requested.
