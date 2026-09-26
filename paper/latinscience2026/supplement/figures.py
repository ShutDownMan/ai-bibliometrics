"""
Generate publication-ready figures for the Latin.Science 2026 manuscript.

Published Figure 1: Semantic-axis instrument (file prefix fig4).
Published Figure 2: Annual production and T/G distributions (prefix fig1).
Published Figure 3: T-G scatter with year-adjusted fit (prefix fig2).
The optional screening diagram is not used in the manuscript.

Usage:
    python figures.py          # writes the three published figure PDFs
    python figures.py --png    # also writes PNG at 300 dpi
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats

# ── CLI ───────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Latin.Science 2026 — figure generation")
parser.add_argument("--png", action="store_true", help="Also write PNG (300 dpi)")
parser.add_argument("--package", type=Path, help="Directory containing the final supplementary inputs")
parser.add_argument("--output-dir", type=Path, help="Directory for generated figures")
parser.add_argument("--screening-flow", action="store_true", help="Also render the unused screening diagram from the private ledger")
args = parser.parse_args()

# ── Paths ─────────────────────────────────────────────────────────────────────

HERE = Path(__file__).parent.resolve()
RUN_DIR = HERE.parent.parent.parent / "runs" / "latin_science_2026"
IND = RUN_DIR / "indicators"
PACKAGE = args.package or (HERE if (HERE / "S8_DERIVED_ANALYSIS_DATA.csv").exists() else HERE.parent / "supplement")
OUT_DIR = args.output_dir or HERE
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Load data ─────────────────────────────────────────────────────────────────

# The release table contains the frozen final scores for included records only.
df = pd.read_csv(PACKAGE / "S8_DERIVED_ANALYSIS_DATA.csv").rename(columns={
    "record_id": "id", "T_score": "axis_t_technology", "G_score": "axis_g_governance",
})
if len(df) != 711 or not df.id.is_unique:
    raise ValueError("The figure input must contain 711 unique included records")
df["publication_year"] = df["publication_year"].astype(int)

# Cohort split (matching the manuscript). 2026 is provisional context only.
cohort_map = {
    2020: "2020–2022\n(n = 20)", 2021: "2020–2022\n(n = 20)", 2022: "2020–2022\n(n = 20)",
    2023: "2023\n(n = 99)", 2024: "2024\n(n = 196)",
    2025: "2025\n(n = 314)", 2026: "2026*\n(n = 82)",
}
df["cohort"] = df["publication_year"].map(cohort_map)

# ── Visual constants ──────────────────────────────────────────────────────────

# A restrained colour palette suitable for a scholarly publication
COLOUR_PRE = "#4e79a7"   # muted blue, pre-2023
COLOUR_POST = "#e15759"  # muted red, post-2023
COLOUR_BARS = "#6a85b6"  # steel blue for the annual bar chart
COLOUR_LINE = "#333333"
COLOUR_GRID = "#e0e0e0"
COLOUR_TEXT = "#1a1a1a"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Libertinus Serif", "DejaVu Serif"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "text.color": COLOUR_TEXT,
        "axes.edgecolor": "#555555",
        "axes.labelcolor": COLOUR_TEXT,
    }
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1 — Annual production + T/G distributions by cohort
# ═══════════════════════════════════════════════════════════════════════════════

def fig1() -> None:
    yearly = df["publication_year"].value_counts().sort_index()
    labels = ["2020–22\n(n=20)", "2023\n(n=99)", "2024\n(n=196)", "2025\n(n=314)", "2026*\n(n=82)"]
    groups = [df[df["publication_year"].between(2020, 2022)], *[df[df["publication_year"] == y] for y in range(2023, 2027)]]
    fig, axes = plt.subplots(3, 1, figsize=(3.55, 5.7))
    ax = axes[0]
    ax.bar(yearly.index, yearly.values, color=COLOUR_BARS, edgecolor="white", zorder=3)
    for year, count in yearly.items(): ax.text(year, count + 7, str(count), ha="center", fontsize=8)
    ax.set_xticks(yearly.index); ax.set_ylabel("Records"); ax.set_title("(a) Annual production", fontweight="bold", loc="left")
    ax.set_ylim(0, yearly.max() * 1.15)
    ax.grid(axis="y", color=COLOUR_GRID, linewidth=.5); ax.set_axisbelow(True)
    for ax, column, title in ((axes[1], "axis_t_technology", "(b) Technological specificity (T)"), (axes[2], "axis_g_governance", "(c) Governance orientation (G)")):
        values = [group[column].to_numpy() for group in groups]
        ax.boxplot(values, tick_labels=labels, showfliers=False, medianprops={"color": "black", "linewidth": 1.6})
        rng = np.random.default_rng(20260808)
        for position, value in enumerate(values, 1): ax.scatter(rng.normal(position, .045, len(value)), value, s=4, alpha=.22, color=COLOUR_POST, linewidths=0)
        ax.set_title(title, fontweight="bold", loc="left"); ax.set_ylabel("Embedding-derived score")
        ax.grid(axis="y", color=COLOUR_GRID, linewidth=.5); ax.set_axisbelow(True)
    fig.text(.5, .005, "*2026 is partial and descriptive only; boxes show median and IQR.", ha="center", fontsize=7, color="#555555")
    fig.tight_layout(rect=[0, .025, 1, 1])
    fig.savefig(OUT_DIR / "fig1_temporal_production_and_distributions.pdf")
    if args.png:
        fig.savefig(OUT_DIR / "fig1_temporal_production_and_distributions.png", dpi=300)
    plt.close(fig)
    print("  Fig 1  ->  fig1_temporal_production_and_distributions.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2 — T vs G scatter with year-adjusted regression
# ═══════════════════════════════════════════════════════════════════════════════

def fig2() -> None:
    T = df["axis_t_technology"].values
    G = df["axis_g_governance"].values
    year = df["publication_year"].values.astype(float)

    pre_mask = year < 2023

    # Load authoritative statistical results to keep figure annotations
    # numerically identical to the manuscript text.
    import json
    stats_path = PACKAGE / "S11_PUBLICATION_RESULTS.json"
    with open(stats_path) as fh:
        stats_json = json.load(fh)
    bT_json = stats_json["principal"]["beta_t"]
    partial_r_json = stats_json["principal"]["partial_r"]
    r2_full_json = stats_json["principal"]["r_squared"]
    r2_year_json = stats_json["principal"]["r_squared_year_only"]
    f2_T_json = stats_json["principal"]["f_squared_t"]
    ci_lo, ci_hi = stats_json["principal"]["beta_t_ci_95"]

    # Fit: G ~ T + year  (matching the manuscript's model)
    X = np.column_stack([T, year])
    X = np.column_stack([np.ones_like(T), X])  # add intercept
    beta, residuals, rank, singular = np.linalg.lstsq(X, G, rcond=None)
    b0, bT, bY = beta

    # Partial regression line: G on T at mean year
    year_mean = year.mean()
    T_grid = np.linspace(T.min(), T.max(), 200)
    G_fit = b0 + bT * T_grid + bY * year_mean

    if not np.isclose(bT, bT_json, atol=1e-9, rtol=0):
        raise ValueError("The plotted regression differs from the final results")
    fig, ax = plt.subplots(figsize=(3.55, 3.8))

    # Scatter
    ax.scatter(T[pre_mask], G[pre_mask], c=COLOUR_PRE, s=15, alpha=0.70, edgecolors="none",
               label="2020–2022 (n = 20)", zorder=4, rasterized=True)
    ax.scatter(T[~pre_mask], G[~pre_mask], c=COLOUR_POST, s=6, alpha=0.38, edgecolors="none",
               label="2023–2026 (n = 691; 2026 partial)", zorder=3, rasterized=True)

    # Regression line
    ax.plot(T_grid, G_fit, color=COLOUR_LINE, lw=1.8, alpha=0.90, zorder=5,
            label=f"Year-adjusted OLS ($\\beta_T$ = {bT:.3f})")

    # Zero reference lines
    ax.axhline(0, color="#aaaaaa", lw=0.7, ls="-", alpha=0.55, zorder=1)
    ax.axvline(0, color="#aaaaaa", lw=0.7, ls="-", alpha=0.55, zorder=1)

    # Annotation box with model summary (values match statistical_results.json)
    textstr = (
        f"G ~ T + year\n"
        f"$\\beta_T$ = {bT_json:.3f}  (95% CI [{ci_lo:.3f}, {ci_hi:.3f}])\n"
        f"Partial $r$ = {partial_r_json:.3f}  ($p$ < 0.001)\n"
        f"$R^2$ = {r2_full_json:.3f}  (year alone: {r2_year_json:.4f})\n"
        f"$f^2$(T) = {f2_T_json:.3f}"
    )
    props = dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85, edgecolor="#cccccc", linewidth=0.8)
    ax.text(0.03, 0.97, textstr, transform=ax.transAxes, fontsize=6.8, verticalalignment="top",
            bbox=props, family="monospace")

    ax.set_xlabel("Technological specificity (T)")
    ax.set_ylabel("Governance orientation (G)")
    ax.set_title("Association between named-model specificity\nand governance orientation",
                 fontweight="bold", loc="left", fontsize=9)
    ax.legend(framealpha=0.85, fontsize=5.8, loc="lower right")
    ax.grid(color=COLOUR_GRID, linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig2_t_vs_g_scatter.pdf")
    if args.png:
        fig.savefig(OUT_DIR / "fig2_t_vs_g_scatter.png", dpi=300)
    plt.close(fig)
    print("  Fig 2  ->  fig2_t_vs_g_scatter.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3 — PRISMA-style scope-screening flow
# ═══════════════════════════════════════════════════════════════════════════════

def fig3() -> None:
    """Draw upstream processing and final scope-screening decision flow."""
    ledger = pd.read_csv(RUN_DIR / "screening_decisions.csv")
    counts = ledger["decision"].value_counts()
    included, excluded = int(counts["include"]), int(counts["exclude"])
    unresolved, screened = int(counts["needs_review"]), len(ledger)

    fig, axes = plt.subplots(2, 1, figsize=(7.0, 7.45),
                             gridspec_kw={"height_ratios": [1, 1]})

    def setup(ax):
        ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    def box(ax, x, y, w, h, text, *, face="#f7f7f7", edge="#555555", size=8.4):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=0.9))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
                linespacing=1.25, wrap=True)

    def arrow(ax, x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#555555", lw=1.0))

    # Stage A: the preserved broad-corpus processing history.
    ax = axes[0]; setup(ax)
    ax.text(.01, .98, "Stage A. Identification and initial processing of the broad corpus",
            ha="left", va="top", fontsize=10, fontweight="bold")
    box(ax, .04, .75, .40, .14, "Manual database exports\n(n = 6,752)", face="#e9f0f8")
    box(ax, .56, .75, .40, .14, "Automated retrieval\n(n = 1,648)", face="#e9f0f8")
    box(ax, .30, .52, .40, .14, "Unique records identified\n(n = 8,400)", face="#e9f0f8")
    box(ax, .30, .29, .40, .14, "Records after initial retrieval filters\n(n = 6,579)", face="#e9f0f8")
    box(ax, .30, .06, .40, .14, "Broad corpus with usable embeddings\n(n = 6,261)", face="#e9f0f8")
    box(ax, .73, .25, .24, .25,
        "Initial filters\nNo abstract: 1,241\nOff-topic title: 150\nWeak alignment: 228\nLow relevance: 202",
        face="#f9ecec", edge="#9b5555", size=7.0)
    box(ax, .73, .03, .24, .19,
        "Further cleaning\nOutside period: 31\nRetracted: 20\nOff-topic: 45\nNo usable embedding: 222",
        face="#f9ecec", edge="#9b5555", size=7.0)
    arrow(ax, .24, .75, .43, .66); arrow(ax, .76, .75, .57, .66)
    arrow(ax, .50, .52, .50, .43); arrow(ax, .50, .29, .50, .20)
    arrow(ax, .70, .59, .73, .42)
    arrow(ax, .70, .36, .73, .18)

    # Stage B: the final, article-specific screening ledger.
    ax = axes[1]; setup(ax)
    ax.text(.01, .98, "Stage B. Focused screening for this article",
            ha="left", va="top", fontsize=10, fontweight="bold")
    box(ax, .05, .72, .39, .15, f"Records assessed by title and abstract\n(n = {screened:,})", face="#e9f0f8")
    box(ax, .05, .42, .39, .15, f"Included in quantitative analysis\n(n = {included:,})", face="#e8f3e8", edge="#4f7d4f")
    box(ax, .56, .52, .39, .29,
        "Excluded (n = 5,542)\nClinical applications: 2,301\nNo scope signal: 1,813\n"
        "Off-topic title: 820\nOut-of-scope review: 235\nIndustrial: 178; pedagogy: 49; no-AI: 18\n"
        "Combined rule codes: 128", face="#f9ecec", edge="#9b5555", size=7.5)
    box(ax, .56, .24, .39, .15, f"Borderline records awaiting adjudication\n(n = {unresolved}; excluded from analysis)", face="#fff4dd", edge="#9a7a36")
    arrow(ax, .245, .72, .245, .57); arrow(ax, .44, .795, .56, .665)
    arrow(ax, .44, .74, .56, .315)
    ax.text(.50, .06, "Stage A records the archived broad-corpus pipeline; Stage B records the\nfinal article-specific ledger. The figure aids transparent reporting and is not a systematic-review claim.",
            ha="center", va="center", fontsize=7.1, color="#555555")
    fig.tight_layout(pad=.45)
    fig.savefig(OUT_DIR / "fig3_screening_flow.pdf")
    if args.png:
        fig.savefig(OUT_DIR / "fig3_screening_flow.png", dpi=300)
    plt.close(fig)
    print("  Fig 3  ->  fig3_screening_flow.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4 — Didactic semantic-axis instrument figure (3 panels, full-width)
# ═══════════════════════════════════════════════════════════════════════════════

def fig4() -> None:
    """Three-panel didactic figure explaining the prototype-based semantic axis.

    Panel (a): Prototypes in a schematic embedding plane with centroids and axis.
    Panel (b): Geometric construction — unit vector, midpoint, document projection.
    Panel (c): 1‑D score line with real corpus histogram and stability annotation.
    """
    # -- Synthetic prototype coordinates for pedagogical clarity --------------
    rng = np.random.default_rng(20260808)
    pole_left = rng.multivariate_normal([-2.0, 0.0], [[0.15, 0.05], [0.05, 0.20]], 5)
    pole_right = rng.multivariate_normal([2.0, 0.5], [[0.15, -0.04], [-0.04, 0.20]], 5)
    centroid_l = pole_left.mean(axis=0)
    centroid_r = pole_right.mean(axis=0)

    # Axis direction
    axis_vec = centroid_r - centroid_l
    axis_unit = axis_vec / np.linalg.norm(axis_vec)
    midpoint = (centroid_l + centroid_r) / 2

    # A sample document for projection illustration
    doc = np.array([0.6, -0.35])
    doc_centered = doc - midpoint
    proj_scalar = np.dot(doc_centered, axis_unit)
    proj_point = midpoint + proj_scalar * axis_unit

    # Real axis scores for the histogram
    T_vals = df["axis_t_technology"].values

    COLOUR_POLE_L = "#4e79a7"  # blue — generic AI
    COLOUR_POLE_R = "#e15759"  # red — named model
    COLOUR_DOC = "#555555"
    COLOUR_PROJ = "#b07d3c"   # gold-brown for projection highlight
    COLOUR_AXIS = "#333333"

    # ---- Layout: 2×2 grid, (c) spans full bottom row ------------------------
    plot_h = 2.45
    fig = plt.figure(figsize=(7.0, 2 * plot_h + 0.22))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.1], hspace=0.22,
                          width_ratios=[1.0, 1.0], wspace=0.22)

    XLIM = (-3.5, 3.5)
    YLIM = (-1.8, 2.0)

    # ---- Panel (a): Prototypes in embedding plane (top-left) -----------------
    ax_a = fig.add_subplot(gs[0, 0])
    # Faint doc cloud (behind everything)
    ax_a.scatter(T_vals[:250] * 1.8 + centroid_l[0] + 2.0,
                 rng.normal(-0.1, 0.25, 250), c=COLOUR_DOC, s=3, alpha=0.10, zorder=1)
    ax_a.scatter(T_vals[250:500] * 1.8 + centroid_l[0] + 2.0,
                 rng.normal(-0.2, 0.25, 250), c=COLOUR_DOC, s=3, alpha=0.10, zorder=1)
    # Prototypes
    ax_a.scatter(pole_left[:, 0], pole_left[:, 1], c=COLOUR_POLE_L, s=40, zorder=4,
                 edgecolors="white", linewidths=0.7)
    ax_a.scatter(pole_right[:, 0], pole_right[:, 1], c=COLOUR_POLE_R, s=40, zorder=4,
                 edgecolors="white", linewidths=0.7)
    # Centroids
    ax_a.scatter(*centroid_l, c=COLOUR_POLE_L, s=120, zorder=5, marker="D",
                 edgecolors="white", linewidths=1.0)
    ax_a.scatter(*centroid_r, c=COLOUR_POLE_R, s=120, zorder=5, marker="D",
                 edgecolors="white", linewidths=1.0)
    # Axis line with arrows
    ax_a.annotate("", xy=centroid_r, xytext=centroid_l,
                  arrowprops=dict(arrowstyle="<->", color=COLOUR_AXIS, lw=2.0,
                                  shrinkA=9, shrinkB=9))
    # Pole labels — pulled far from centroids into open space
    ax_a.text(centroid_l[0], centroid_l[1] - 1.05, "Generic\nAI / ML",
              ha="center", fontsize=8.2, color=COLOUR_POLE_L, fontweight="bold",
              linespacing=1.1, zorder=10)
    ax_a.text(centroid_r[0], centroid_r[1] + 0.75, "Named model\ncentral",
              ha="center", fontsize=8.2, color=COLOUR_POLE_R, fontweight="bold",
              linespacing=1.1, zorder=10)
    # Centroid call-out
    ax_a.text(-0.1, 1.5, "Centroid", ha="center", fontsize=7.5, color="#333333", zorder=10)
    ax_a.annotate("", xy=(-0.1, 1.42), xytext=(-0.1, 0.35),
                  arrowprops=dict(arrowstyle="->", color="#666666", lw=0.8))
    ax_a.text(0.03, 0.03, "5 prototypes per pole", transform=ax_a.transAxes,
              fontsize=7.0, color="#666666", style="italic")
    ax_a.set_title("(a) Prototypes in embedding space", fontweight="bold", loc="left",
                   fontsize=9.5)
    ax_a.set_xlabel("Embedding dim. 1 (schematic)", fontsize=7.8, color="#777777",
                    labelpad=1)
    ax_a.set_ylabel("Embedding dim. 2 (schematic)", fontsize=7.8, color="#777777",
                    labelpad=1)
    ax_a.tick_params(labelsize=6.5, colors="#aaaaaa")
    ax_a.set_aspect("equal")
    ax_a.set_xlim(*XLIM)
    ax_a.set_ylim(*YLIM)

    # ---- Panel (b): Geometric construction (top-right) -----------------------
    ax_b = fig.add_subplot(gs[0, 1])
    # Axis line
    ax_b.plot([centroid_l[0], centroid_r[0]], [centroid_l[1], centroid_r[1]],
              color=COLOUR_AXIS, lw=2.0, zorder=3)
    # Centroids with labels
    ax_b.scatter(*centroid_l, c=COLOUR_POLE_L, s=100, zorder=5, marker="D",
                 edgecolors="white", linewidths=0.8)
    ax_b.scatter(*centroid_r, c=COLOUR_POLE_R, s=100, zorder=5, marker="D",
                 edgecolors="white", linewidths=0.8)
    ax_b.text(centroid_l[0] - 0.35, centroid_l[1] - 0.50, r"$\mathbf{c}_L$",
              fontsize=9.5, color=COLOUR_POLE_L, fontweight="bold", zorder=10)
    ax_b.text(centroid_r[0] + 0.10, centroid_r[1] + 0.22, r"$\mathbf{c}_R$",
              fontsize=9.5, color=COLOUR_POLE_R, fontweight="bold", zorder=10)
    # Midpoint
    ax_b.scatter(*midpoint, c="#333333", s=55, zorder=5, marker="s",
                 edgecolors="white", linewidths=0.7)
    ax_b.text(midpoint[0] - 0.10, midpoint[1] + 0.22, r"$\mathbf{m}$",
              fontsize=9.5, color="#333333", zorder=10)
    # Unit vector annotation — placed in open space
    ax_b.annotate(
        r"$\mathbf{\hat{u}} = \frac{\mathbf{c}_R - \mathbf{c}_L}"
        r"{\|\mathbf{c}_R - \mathbf{c}_L\|}$",
        xy=(midpoint[0] + 0.4, midpoint[1] - 0.30),
        xytext=(midpoint[0] - 0.6, midpoint[1] - 1.2),
        fontsize=7.6, color="#333333",
        arrowprops=dict(arrowstyle="->", color="#666666", lw=0.8))
    # Document point
    ax_b.scatter(*doc, c=COLOUR_DOC, s=65, zorder=5, edgecolors="white",
                 linewidths=0.6)
    ax_b.text(doc[0] + 0.18, doc[1] + 0.08, r"$\mathbf{v}_{\mathrm{doc}}$",
              fontsize=9, color=COLOUR_DOC, zorder=10)
    # Dashed projection line
    ax_b.plot([doc[0], proj_point[0]], [doc[1], proj_point[1]],
              ls="--", color=COLOUR_PROJ, lw=1.4, zorder=4)
    ax_b.scatter(*proj_point, c=COLOUR_PROJ, s=55, zorder=5, marker="o",
                 edgecolors="white", linewidths=0.6)
    ax_b.text(proj_point[0] - 0.35, proj_point[1] + 0.28, r"projection",
              fontsize=8, color=COLOUR_PROJ, zorder=10, fontweight="bold")
    # Formula box
    ax_b.text(0.5, 0.94,
              r"$s = (\mathbf{v}_{\mathrm{doc}} - \mathbf{m}) \cdot \mathbf{\hat{u}}$",
              transform=ax_b.transAxes, fontsize=8.5, color="#333333", ha="center",
              bbox=dict(boxstyle="round,pad=0.3", facecolor="#f7f7f7",
                        edgecolor="#cccccc", linewidth=0.7))
    ax_b.set_title("(b) Axis construction", fontweight="bold", loc="left",
                   fontsize=9.5)
    ax_b.set_xlabel("Embedding dim. 1 (schematic)", fontsize=7.8, color="#777777",
                    labelpad=1)
    ax_b.tick_params(labelsize=6.5, colors="#aaaaaa")
    ax_b.set_aspect("equal")
    ax_b.set_xlim(*XLIM)
    ax_b.set_ylim(*YLIM)

    # ---- Panel (c): 1-D score line (bottom row, full width) ------------------
    ax_c = fig.add_subplot(gs[1, :])
    bins = np.linspace(T_vals.min(), T_vals.max(), 55)
    counts, edges = np.histogram(T_vals, bins=bins)
    counts_norm = counts / counts.max() * 0.65
    bin_centers = (edges[:-1] + edges[1:]) / 2
    ax_c.bar(bin_centers, counts_norm, width=np.diff(edges)[0],
             color=COLOUR_BARS, alpha=0.45, edgecolor="none", zorder=2)
    ax_c.axhline(0, color=COLOUR_AXIS, lw=2.2, zorder=3)
    ax_c.axvline(0, color=COLOUR_AXIS, lw=0.9, ls=":", alpha=0.5, zorder=3)
    ax_c.text(0, 0.74, "0", ha="center", fontsize=9, fontweight="bold",
              color="#333333")
    # Pole labels
    pad = 0.03
    ax_c.text(T_vals.min() - pad, 0.04, "Generic AI / ML\n(negative scores)",
              ha="center", fontsize=7.8, color=COLOUR_POLE_L, fontweight="bold",
              linespacing=1.1)
    ax_c.text(T_vals.max() + pad, 0.04,
              "Named model\ncentral\n(positive scores)",
              ha="center", fontsize=7.8, color=COLOUR_POLE_R, fontweight="bold",
              linespacing=1.1)
    # Arrows at ends
    for x_end in (T_vals.min(), T_vals.max()):
        dx = 0.025 if x_end > 0 else -0.025
        ax_c.annotate("", xy=(x_end - 2 * dx, 0), xytext=(x_end + dx, 0),
                      arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2))
    # Read the frozen final diagnostics without a hard-coded fallback.
    import json
    with open(PACKAGE / "S13_FROZEN_AXIS_DIAGNOSTICS.json") as fh:
        loo_t_min = json.load(fh)["loo_T"]["min"]
    loo_label = rf"Leave-one-out stability: min $\rho = {loo_t_min:.3f}$"
    ax_c.text(0.97, 0.91, loo_label,
              transform=ax_c.transAxes, fontsize=7.2, ha="right", color="#555555",
              bbox=dict(boxstyle="round,pad=0.2", facecolor="#f9f9f9",
                        edgecolor="#dddddd", linewidth=0.6))
    # Prototype tick marks
    proto_positions = np.linspace(T_vals.min() * 0.45, T_vals.max() * 0.45, 5)
    for pp in proto_positions:
        ax_c.plot(pp, 0, marker="|", color="#333333", markersize=9,
                  markeredgewidth=0.9)
    ax_c.text(proto_positions[2], -0.20, "5 prototype pairs", ha="center",
              fontsize=7.2, color="#777777", style="italic")
    ax_c.set_title("(c) 1-D score distribution ($N$ = 711)", fontweight="bold",
                   loc="left", fontsize=9.5)
    ax_c.set_xlabel("Technological specificity (T)", fontsize=8.5)
    ax_c.set_ylabel("Rel. frequency", fontsize=8.5)
    ax_c.tick_params(labelsize=7)
    ax_c.set_xlim(T_vals.min() - 0.12, T_vals.max() + 0.12)
    ax_c.set_ylim(-0.30, 1.02)
    ax_c.grid(axis="y", color=COLOUR_GRID, linewidth=0.4, zorder=0)
    ax_c.set_axisbelow(True)

    # ---- Save ---------------------------------------------------------------
    out = OUT_DIR / "fig4_semantic_axis_instrument.pdf"
    fig.savefig(out)
    if args.png:
        fig.savefig(OUT_DIR / "fig4_semantic_axis_instrument.png", dpi=300)
    plt.close(fig)
    print("  Fig 4  ->  fig4_semantic_axis_instrument.pdf")


def main() -> None:
    print(f"Data: {len(df)} included records")
    print(f"Years: {df['publication_year'].min()}–{df['publication_year'].max()}")
    print(f"Cohort: {df['cohort'].value_counts().to_dict()}")
    print()
    fig1()
    fig2()
    if args.screening_flow:
        fig3()
    fig4()
    print(f"\nDone -- figures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
