# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Regenerate all 9 paper figures to publication quality per teacher Appendix D (Table D2 palette).
Outputs 600-dpi PNG + SVG into fig_v8/.  All text in English.  Colorblind-safe palette."""
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap
import scipy.cluster.hierarchy as sch

BASE = r"D:\study\test1\data_v2_experiment"
OUT  = os.path.dirname(os.path.abspath(__file__))

# ---- Appendix D Table D2 journal-level palette (colorblind-safe, Okabe-Ito derived) ----
GPU   = "#0072B2"   # GPU / positive exposure  (blue)
CPU   = "#D55E00"   # CPU / comparison         (vermillion)
SPRD  = "#7B2CBF"   # GPU-CPU spread           (purple)
CORAL = "#E76F51"   # high-attention state     (coral)
TEAL  = "#2A9D8F"   # normal/below-threshold   (teal)
GRAY  = "#BDBDBD"   # raw daily observations
BLACK = "#000000"   # moving average / main est
# Okabe-Ito 6-colour set for thematic composition
OKABE = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7", "#56B4E9"]

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "axes.linewidth": 0.8,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "legend.frameon": False,
    "figure.dpi": 600,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})
DPI = 600

def save(fig, name):
    png = os.path.join(OUT, name + ".png")
    svg = os.path.join(OUT, name + ".svg")
    fig.savefig(png, dpi=DPI)
    fig.savefig(svg, dpi=DPI)
    plt.close(fig)
    print("saved", name, os.path.getsize(png), "bytes")

# =====================================================================
# FIGURE 3 — Daily GCS with 30-day MA and major events
# =====================================================================
def fig3():
    df = pd.read_csv(os.path.join(BASE, "d04_index_gcs_ugcs", "gcs_daily.csv"))
    df = df.dropna(subset=["GCS"]).copy()
    df["d"] = pd.to_datetime(df["bucket"])
    df = df.sort_values("d")
    df["ma30"] = df["GCS"].rolling(30, min_periods=5).mean()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(df["d"], df["GCS"], color=GRAY, lw=0.6, label="Daily GCS", zorder=1)
    ax.plot(df["d"], df["ma30"], color=BLACK, lw=1.8, label="30-day moving average", zorder=2)
    ev = df[df["HighUGCS10"] == 1]
    for _, r in ev.iterrows():
        ax.axvline(r["d"], color="#999999", lw=0.5, alpha=0.35, zorder=0)
    # annotate a few notable extreme-event windows
    notes = ["ChatGPT\nNov-22", "A100 export\ncurbs Oct-22", "MIIT\n算力蓝图 23", "Sora\nFeb-24"]
    ax.set_title("Figure 3. Daily General Computing-concern Sentiment (GCS) with 30-Day Moving Average and Major Events", fontsize=10.5)
    ax.set_ylabel("GCS index")
    ax.legend(loc="upper right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "Figure3_daily_gcs_ma_events")

# =====================================================================
# FIGURE 4 — Monthly AI-compute news composition by theme (stacked area)
# =====================================================================
def fig4():
    df = pd.read_csv(os.path.join(BASE, "d04_index_gcs_ugcs", "gcs_topic_daily.csv"))
    df["d"] = pd.to_datetime(df["bucket"])
    df["month"] = df["d"].dt.to_period("M").astype(str)
    piv = df.pivot_table(index="month", columns="topic_name", values="n_news", aggfunc="sum").fillna(0)
    piv = piv.sort_index()
    order = ["Orders & Shipments", "Capacity & Capex", "Policy & Regulation",
             "Product & Technology", "Supply & Pricing", "Earnings & Market"]
    order = [c for c in order if c in piv.columns]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.stackplot(piv.index, [piv[c].values for c in order],
                 labels=order, colors=OKABE[:len(order)], alpha=0.9)
    ax.set_title("Figure 4. Monthly AI-Compute News Composition by Theme", fontsize=10.5)
    ax.set_ylabel("News count")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "Figure4_theme_composition")

# =====================================================================
# FIGURE 5 — Cumulative abnormal returns around extreme UGCS events
# =====================================================================
def fig5():
    e = pd.read_csv(os.path.join(BASE, "d06_regression_results", "event_study_car.csv"))
    e = e[e["thr"] == "top10"].sort_values("tau")
    x = e["tau"].values
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for y, se, col, lab in [
        (e["car_gpu"], e["carse_gpu"], GPU, "GPU portfolio"),
        (e["car_cpu"], e["carse_cpu"], CPU, "CPU portfolio"),
        (e["car_diff"], e["carse_diff"], SPRD, "GPU-CPU spread")]:
        ax.plot(x, y, color=col, lw=1.8, label=lab)
        ax.fill_between(x, y - 1.96 * se, y + 1.96 * se, color=col, alpha=0.12)
    ax.axhline(0, color="#888888", lw=0.7)
    ax.axvline(0, color="#888888", lw=0.7, ls="--")
    ax.set_title("Figure 5. Cumulative Abnormal Returns around Extreme UGCS Events (top-10%)", fontsize=10.5)
    ax.set_xlabel("Trading days relative to event (tau)")
    ax.set_ylabel("Cumulative abnormal return")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "Figure5_event_study_car")

# =====================================================================
# FIGURE 6 — Conditional GPU-CPU return spread across UGCS percentiles
# =====================================================================
def fig6():
    q = pd.read_csv(os.path.join(BASE, "d06_regression_results", "h2_quantile_slices.csv"))
    q = q.sort_values("q")
    xs = (q["q"] * 100).values
    def line(col, tcol, c, lab):
        coef = q[col].values
        se = np.abs(coef) / np.abs(q[tcol].values)
        return coef, se, c, lab
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for col, tcol, c, lab in [
        ("betaG", "tG", CORAL, "GPU exposure (beta_G)"),
        ("betaC", "tC", TEAL, "CPU exposure (beta_C)")]:
        coef, se, c, lab = line(col, tcol, c, lab)
        ax.plot(xs, coef, color=c, lw=1.8, marker="o", ms=5, label=lab)
        ax.fill_between(xs, coef - 1.96 * se, coef + 1.96 * se, color=c, alpha=0.14)
    ax.axhline(0, color="#888888", lw=0.7)
    ax.set_title("Figure 6. Conditional GPU-CPU Return Spread across UGCS Percentiles", fontsize=10.5)
    ax.set_xlabel("UGCS percentile of the daily distribution")
    ax.set_ylabel("Exposure coefficient on daily return")
    ax.legend(loc="lower left", fontsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "Figure6_quantile_spread")

# =====================================================================
# FIGURE 7 — Daily, weekly, monthly GPU-CPU responses (local projection)
# =====================================================================
def fig7():
    lp = pd.read_csv(os.path.join(BASE, "d06_regression_results", "h5_local_projection.csv"))
    freqs = ["daily", "weekly", "monthly"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, fr in zip(axes, freqs):
        d = lp[lp["freq"] == fr].sort_values("h")
        x = d["h"].values
        for y, se, c, lab in [
            (d["betaG"], d["seG"], GPU, "GPU"),
            (d["betaC"], d["seC"], CPU, "CPU"),
            (d["diff"], None, SPRD, "Spread")]:
            ax.plot(x, y, color=c, lw=1.6, label=lab)
            if se is not None:
                ax.fill_between(x, y - 1.96 * se, y + 1.96 * se, color=c, alpha=0.12)
        ax.axhline(0, color="#888888", lw=0.7)
        ax.set_title(fr.capitalize(), fontsize=10)
        ax.set_xlabel("Horizon h")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Local-projection coefficient")
    fig.suptitle("Figure 7. Daily, Weekly and Monthly GPU-CPU Return Responses", fontsize=10.5, y=1.02)
    axes[2].legend(loc="upper right", fontsize=8)
    save(fig, "Figure7_local_projection")

# =====================================================================
# FIGURE A1 — Topic correlation heatmap + dendrogram
# =====================================================================
def figA1():
    df = pd.read_csv(os.path.join(BASE, "d04_index_gcs_ugcs", "gcs_topic_daily.csv"))
    df["d"] = pd.to_datetime(df["bucket"])
    piv = df.pivot_table(index="d", columns="topic_name", values="n_news", aggfunc="sum").fillna(0)
    corr = piv.corr().values
    labels = list(piv.columns)
    order = ["Orders & Shipments", "Capacity & Capex", "Policy & Regulation",
             "Product & Technology", "Supply & Pricing", "Earnings & Market"]
    order = [c for c in order if c in labels]
    idx = [labels.index(c) for c in order]
    corr = corr[np.ix_(idx, idx)]
    labels = order
    fig = plt.figure(figsize=(7.2, 6.2))
    ax1 = fig.add_axes([0.30, 0.12, 0.55, 0.76])
    ax2 = fig.add_axes([0.06, 0.12, 0.18, 0.76])
    # dendrogram
    Z = sch.linkage(corr, method="average")
    sch.dendrogram(Z, labels=labels, ax=ax2, color_threshold=0, above_threshold_color="#7B2CBF")
    ax2.set_xticks([]); ax2.axis("off")
    cmap = LinearSegmentedColormap.from_list("purpleseq", ["#F2E6F5", "#7B2CBF"])
    im = ax1.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
    ax1.set_xticks(range(len(labels))); ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax1.set_yticks(range(len(labels))); ax1.set_yticklabels(labels, fontsize=8)
    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    ax1.set_title("Figure A1. Topic Correlation Heatmap and Hierarchical Clustering", fontsize=10)
    save(fig, "FigureA1_topic_corr")

# =====================================================================
# FIGURE A2 — DA-MT-FinTransformer confusion matrices (small multiples)
# =====================================================================
def figA2():
    cm = json.load(open(os.path.join(BASE, "d03_model_damt", "confusion_matrices.json")))
    full = cm["Full"]
    keys = [k for k in ["tone", "rel", "obj", "rlt", "top"] if k in full]
    n = len(keys)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(9, 3.0 * nrow))
    axes = np.atleast_1d(axes).ravel()
    cmap = LinearSegmentedColormap.from_list("purpleseq", ["#FFFFFF", "#7B2CBF"])
    for ax, k in zip(axes, keys):
        m = np.array(full[k], dtype=float)
        im = ax.imshow(m, cmap=cmap)
        ax.set_title(k, fontsize=10)
        ax.set_xticks(range(m.shape[1])); ax.set_yticks(range(m.shape[0]))
        ax.tick_params(labelsize=7)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=7,
                        color="white" if m[i, j] > m.max() * 0.55 else "black")
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Figure A2. DA-MT-FinTransformer Confusion Matrices (Full model)", fontsize=10.5, y=1.0)
    save(fig, "FigureA2_confusion")

# =====================================================================
# FIGURE 1 — Research framework (conceptual, self-contained)
# =====================================================================
def box(ax, x, y, w, h, text, fc, tc="white", fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
                                fc=fc, ec="#333333", lw=0.8, zorder=2))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", color=tc, fontsize=fs,
            zorder=3, wrap=True)

def arrow(ax, x1, y1, x2, y2, color="#333333"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                color=color, lw=1.4, zorder=1))

def fig1():
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(5, 9.6, "Figure 1. Research Framework: Attention Innovation x Pre-exposure -> Cross-sectional Divergence",
            ha="center", fontsize=10.5, fontweight="bold")
    # Left branch: text -> index
    box(ax, 0.3, 6.6, 2.6, 1.1, "AI-compute news\n(THS / iFinD / web)", "#E8E8E8", "#222222")
    box(ax, 0.3, 4.6, 2.6, 1.1, "DA-MT-FinTransformer\n(DA continued pretrain +\ndirectional attention, eq.4-15)",
        GPU, "white", 8.5)
    box(ax, 0.3, 2.4, 2.6, 1.1, "GCS & UGCS indices\n(freq-aggregated, eq.16-20)", "#E8E8E8", "#222222")
    arrow(ax, 1.6, 6.6, 1.6, 5.7)
    arrow(ax, 1.6, 4.6, 1.6, 3.5)
    # Right branch: market -> exposure
    box(ax, 7.1, 6.6, 2.6, 1.1, "Stock returns &\nfinancial statements", "#E8E8E8", "#222222")
    box(ax, 7.1, 4.6, 2.6, 1.1, "Pre-exposure G_i / C_i\n(business-income based, eq.21)", TEAL, "white", 8.5)
    arrow(ax, 8.4, 6.6, 8.4, 5.7)
    # middle: identification
    box(ax, 3.5, 3.4, 3.0, 1.4, "Two-way FE + Local Projection\ninteraction  UGCS x G_i / C_i\n(eq.22-24)", "#2B2B2B", "white", 8.5)
    arrow(ax, 2.9, 2.9, 3.6, 3.3)
    arrow(ax, 7.1, 5.1, 6.4, 4.1)
    # output
    box(ax, 3.5, 0.6, 3.0, 1.3, "Cross-sectional return divergence\nH1 relative reaction  H2 extreme\nH3 heterogeneity  H4 external\nH5 dynamic path", SPRD, "white", 8)
    arrow(ax, 5.0, 3.4, 5.0, 1.9)
    ax.text(1.6, 6.45, "Text measurement", ha="center", fontsize=8, color="#555555")
    ax.text(8.4, 6.45, "Market pricing", ha="center", fontsize=8, color="#555555")
    save(fig, "Figure1_framework")

# =====================================================================
# FIGURE 2 — Data processing & GCS-UGCS workflow (echoes eq numbers)
# =====================================================================
def fig2():
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 12); ax.axis("off")
    ax.text(5, 11.6, "Figure 2. Data Processing and GCS-UGCS Construction Workflow",
            ha="center", fontsize=10.5, fontweight="bold")
    steps = [
        (0.4, 10.4, "Raw news corpus\n(THS / iFinD / web)", "#E8E8E8", "#222"),
        (0.4, 8.7, "Lexicon + TF-IDF weak labels\nRelation/Object/Tone/Topic (eq.4)", "#E8E8E8", "#222"),
        (0.4, 7.0, "DA continued pretraining (DAPT)\n(eq.5-10)", GPU, "white"),
        (0.4, 5.3, "Per-article encoding +\nscore mapping (eq.11-18)", GPU, "white"),
        (0.4, 3.6, "Frequency aggregation\nDaily/Weekly/Monthly (eq.19-20)", "#E8E8E8", "#222"),
        (0.4, 1.9, "GCS & UGCS indices", "#E8E8E8", "#222"),
    ]
    for x, y, t, fc, tc in steps:
        box(ax, x, y, 4.2, 1.2, t, fc, tc, 8.5)
    for y in [9.6, 7.9, 6.2, 4.5, 3.1]:
        arrow(ax, 2.5, y+1.2, 2.5, y)
    # right column: market side
    rsteps = [
        (5.4, 8.7, "Stock returns &\nfinancial statements", "#E8E8E8", "#222"),
        (5.4, 6.7, "Pre-exposure G_i / C_i\nby business income (eq.21)", TEAL, "white"),
        (5.4, 4.4, "Panel: returns x exposure\n+ controls (eq.22)", "#E8E8E8", "#222"),
    ]
    for x, y, t, fc, tc in rsteps:
        box(ax, x, y, 4.2, 1.5, t, fc, tc, 8.5)
    arrow(ax, 7.5, 8.7, 7.5, 6.7)
    arrow(ax, 6.5, 6.7, 6.5, 5.9)
    arrow(ax, 4.6, 2.5, 5.4, 5.0)   # GCS/UGCS -> panel
    arrow(ax, 7.5, 6.0, 7.5, 5.2)   # exposure -> panel
    box(ax, 5.4, 1.8, 4.2, 1.6, "Estimation: Two-way FE (eq.22)\nNonlinear & extreme (eq.23)\nEvent / LP (eq.24)", "#2B2B2B", "white", 8.5)
    ax.text(2.5, 11.1, "A. Text-to-index", ha="center", fontsize=8.5, color="#555")
    ax.text(7.5, 10.6, "B. Market data", ha="center", fontsize=8.5, color="#555")
    save(fig, "Figure2_workflow")

if __name__ == "__main__":
    fig3(); fig4(); fig5(); fig6(); fig7(); figA1(); figA2(); fig1(); fig2()
    print("ALL FIGURES DONE")
