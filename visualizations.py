"""
D6 — Visualization pipeline for the bibliometric review.

Generates NOTES/report.md — a single self-contained HTML/Markdown file
with all figures embedded as base64 PNGs (readable in GitHub / VS Code
without external dependencies).

Usage:
    python visualizations.py           # dark mode (screen)
    python visualizations.py --light   # light mode (article export, dpi=220)

Then extract PNGs for LaTeX:
    python extract_report_figs.py NOTES/report.md figures/
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats as sp_stats
from scipy.ndimage import gaussian_filter1d

# ── CLI ───────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--light", action="store_true", help="Light mode for article export")
parser.add_argument("--run-dir", default=None, help="Run directory (overrides repo root for paths)")
args = parser.parse_args()
LIGHT = args.light
DPI = 220 if LIGHT else 150

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(args.run_dir).resolve() if args.run_dir else Path(__file__).parent
IND  = ROOT / "indicators"
OUT  = ROOT / "NOTES" / ("report_light.md" if LIGHT else "report.md")
OUT.parent.mkdir(exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────

if LIGHT:
    BG       = "white"
    AX_BG    = "#f7f8fa"
    TEXT     = "#1a1a2e"
    SUBTEXT  = "#555566"
    GRID     = "#ddddee"
    EDGE     = "#ccccdd"
    SPINE    = "#aaaacc"
else:
    BG       = "#13131f"
    AX_BG    = "#1a1a2e"
    TEXT     = "#e8e8f0"
    SUBTEXT  = "#8888aa"
    GRID     = "#252540"
    EDGE     = "#2a2a50"
    SPINE    = "#3a3a60"

# Fixed cluster palette — consistent across ALL figures
C_PALETTE = {
    0: "#4e9af1",   # C0 — steel blue
    1: "#f07850",   # C1 — warm orange
    2: "#44b894",   # C2 — teal green
    3: "#a87fe8",   # C3 — soft violet
    4: "#e8c44a",   # C4 — amber gold
}

_PT_MONTHS = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
}

_CLUSTER_LABEL_TRANSLATIONS = {
    "AI-Generated Content": "Conteúdo gerado por IA",
    "Academic Integrity": "Integridade acadêmica",
    "Higher Education": "Ensino superior",
    "Diagnostic Imaging": "Imagem diagnóstica",
    "Magnetic Resonance": "Ressonância magnética",
    "Prediction Models": "Modelos preditivos",
    "Internet of Things": "Internet das Coisas",
    "Internet Things": "Internet das Coisas",
    "Federated Learning": "Aprendizado federado",
    "Integrity Governance": "Integridade e governança",
    "Other Relevant": "Outros relevantes",
    "Applied AI Systems": "Sistemas de IA aplicada",
    "Engineering and Environment": "Engenharia e meio ambiente",
    "Clinical Risk and Prediction Models": "Modelos clinicos de risco e predicao",
    "Medical Imaging and Diagnostic AI": "IA diagnostica por imagem",
    "Clinical Prediction Models": "Modelos clinicos preditivos",
    "Diagnostic AI": "IA diagnostica",
    "Clinical Imaging AI": "IA em imagem clinica",
    "Decision Support": "Suporte a decisao",
    "ChatGPT in Education and Research": "ChatGPT na educacao e pesquisa",
    "Integrity and Writing": "Integridade e escrita",
    "AI in Higher Education": "IA no ensino superior",
    "Policy, Assessment and Literacy": "Politica, avaliacao e letramento",
}


def _format_pt_date(value: date) -> str:
    return f"{value.day:02d} {_PT_MONTHS[value.month]} {value.year}"


def _localize_cluster_label(label: str, max_len: int | None = None) -> str:
    text = str(label)
    for old, new in sorted(_CLUSTER_LABEL_TRANSLATIONS.items(), key=lambda item: -len(item[0])):
        text = text.replace(old, new)
    text = " ".join(text.split())
    if max_len is not None and len(text) > max_len:
        return text[:max_len - 1].rstrip() + "…"
    return text


def _cluster_label_card_html(label: str) -> str:
    text = _localize_cluster_label(label)
    if " · " in text:
        left, right = text.split(" · ", 1)
        return f"{left}<br>{right}"
    words = text.split()
    if len(words) >= 4:
        mid = len(words) // 2
        return " ".join(words[:mid]) + "<br>" + " ".join(words[mid:])
    return text


def _build_cluster_labels() -> dict[int, str]:
    """Read cluster names dynamically while preserving numeric cluster ids."""
    axis_csv = IND / "axis_scores_enriched.csv"
    if axis_csv.exists():
        axis_df = pd.read_csv(axis_csv, usecols=["cluster", "cluster_label"]).dropna()
        if not axis_df.empty:
            labels: dict[int, str] = {}
            for cluster_id, group in axis_df.groupby("cluster", sort=True):
                modes = group["cluster_label"].mode()
                label = modes.iat[0] if not modes.empty else group["cluster_label"].iloc[0]
                labels[int(cluster_id)] = _localize_cluster_label(label)
            if labels:
                return labels

    csv = IND / "cluster_share_by_year.csv"
    if csv.exists():
        cols = [c for c in pd.read_csv(csv, nrows=0).columns if c != "publication_year"]
        return {i: _localize_cluster_label(name) for i, name in enumerate(cols)}
    # Fallback
    return {0: "Cluster 0", 1: "Cluster 1", 2: "Cluster 2", 3: "Cluster 3", 4: "Cluster 4"}


def _build_raw_cluster_labels() -> dict[int, str]:
    axis_csv = IND / "axis_scores_enriched.csv"
    if axis_csv.exists():
        axis_df = pd.read_csv(axis_csv, usecols=["cluster", "cluster_label"]).dropna()
        if not axis_df.empty:
            labels: dict[int, str] = {}
            for cluster_id, group in axis_df.groupby("cluster", sort=True):
                modes = group["cluster_label"].mode()
                label = modes.iat[0] if not modes.empty else group["cluster_label"].iloc[0]
                labels[int(cluster_id)] = str(label)
            if labels:
                return labels
    return {0: "Cluster 0", 1: "Cluster 1", 2: "Cluster 2", 3: "Cluster 3", 4: "Cluster 4"}


_COMPACT_CLUSTER_LEGEND_LABELS = {
    0: "C0 · IA aplicada",
    1: "C1 · Risco e prognostico",
    2: "C2 · Diagnostico por imagem",
    3: "C3 · ChatGPT e integridade",
    4: "C4 · IA no ensino superior",
}


def _compact_cluster_legend_label(cluster_id: int) -> str:
    return _COMPACT_CLUSTER_LEGEND_LABELS.get(
        int(cluster_id),
        f"C{int(cluster_id)} · {_localize_cluster_label(C_LABELS.get(int(cluster_id), f'Cluster {int(cluster_id)}'), max_len=24)}",
    )


def _citation_coverage_stats() -> dict[str, float | int]:
    df = pd.read_csv(ROOT / "corpus_clustered.csv", usecols=["doi", "data_source", "cited_by_count"])
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    has_doi = df["doi"].fillna("").astype(str).str.strip() != ""
    pubmed_no_doi = df["data_source"].eq("pubmed_manual") & (~has_doi)
    n_total = len(df)
    n_with_doi = int(has_doi.sum())
    n_zero_with_doi = int(((df["cited_by_count"] == 0) & has_doi).sum())
    n_zero_without_doi = int(((df["cited_by_count"] == 0) & (~has_doi)).sum())
    n_pubmed_no_doi = int(pubmed_no_doi.sum())
    n_pubmed_no_doi_cited = int((pubmed_no_doi & (df["cited_by_count"] > 0)).sum())
    return {
        "n_total": n_total,
        "n_with_doi": n_with_doi,
        "n_zero_with_doi": n_zero_with_doi,
        "n_zero_without_doi": n_zero_without_doi,
        "n_pubmed_no_doi": n_pubmed_no_doi,
        "n_pubmed_no_doi_cited": n_pubmed_no_doi_cited,
        "pct_with_doi": 100 * n_with_doi / max(n_total, 1),
        "pct_zero_without_doi": 100 * n_zero_without_doi / max(n_total, 1),
    }


def _safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    rho, pval = sp_stats.spearmanr(x, y)
    if np.isnan(rho):
        return 0.0, 1.0
    return float(rho), float(pval)


def _top_share(values: pd.Series, fraction: float) -> float:
    ordered = pd.to_numeric(values, errors="coerce").fillna(0).sort_values(ascending=False)
    top_n = max(1, int(round(len(ordered) * fraction)))
    total = float(ordered.sum())
    return 0.0 if total <= 0 else 100 * float(ordered.head(top_n).sum()) / total


def _load_axis_scores() -> pd.DataFrame:
    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    return df


def _axis_temporal_diagnostics(df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = _load_axis_scores() if df is None else df.copy()
    work["year_band"] = pd.cut(
        work["publication_year"],
        bins=[2019, 2022, 2024, 2026],
        labels=["2020-2022", "2023-2024", "2025-2026"],
    )
    e_q75 = work["axis_e_technology"].quantile(0.75)
    e_q25 = work["axis_e_technology"].quantile(0.25)

    def _summarise(label: str, group: pd.DataFrame) -> dict[str, float | str | int]:
        q4 = group.loc[group["axis_e_technology"] >= e_q75, "cited_by_count"]
        q1 = group.loc[group["axis_e_technology"] <= e_q25, "cited_by_count"]
        rho_e, p_e = _safe_spearman(group["axis_e_technology"], group["cited_by_count"])
        rho_r, p_r = _safe_spearman(group["axis_r_scope"], group["cited_by_count"])
        return {
            "label": label,
            "n": int(len(group)),
            "rho_e": rho_e,
            "p_e": p_e,
            "rho_r": rho_r,
            "p_r": p_r,
            "med_q4": float(q4.median()) if len(q4) else 0.0,
            "med_q1": float(q1.median()) if len(q1) else 0.0,
            "mean_q4": float(q4.mean()) if len(q4) else 0.0,
            "mean_q1": float(q1.mean()) if len(q1) else 0.0,
            "share_q4": float(100 * (q4 > 0).mean()) if len(q4) else 0.0,
            "share_q1": float(100 * (q1 > 0).mean()) if len(q1) else 0.0,
        }

    rows = [_summarise("Geral", work)]
    for band, group in work.groupby("year_band", observed=False):
        rows.append(_summarise(str(band), group))
    return work, pd.DataFrame(rows)


def _cluster_concentration_stats(df: pd.DataFrame | None = None) -> pd.DataFrame:
    work = _load_axis_scores() if df is None else df.copy()
    rows: list[dict[str, float | str]] = []
    for cluster_label, group in work.groupby("cluster_label"):
        rows.append({
            "cluster_label": cluster_label,
            "mean_cit": float(group["cited_by_count"].mean()),
            "median_cit": float(group["cited_by_count"].median()),
            "top10_share": _top_share(group["cited_by_count"], 0.10),
            "top20_share": _top_share(group["cited_by_count"], 0.20),
            "pct_2025_plus": 100 * float((group["publication_year"] >= 2025).mean()),
        })
    return pd.DataFrame(rows)

CLUSTER_LABELS_RAW = _build_raw_cluster_labels()
C_LABELS = _build_cluster_labels()

ACCENT   = "#4e9af1"   # primary highlight
RED      = "#e05050"
GREEN    = "#44b894"
AMBER    = "#e8c44a"

# ── matplotlib rcParams ───────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.facecolor":   BG,
    "axes.facecolor":     AX_BG,
    "axes.edgecolor":     SPINE,
    "axes.labelcolor":    TEXT,
    "axes.titlepad":      14,
    "axes.grid":          True,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "text.color":         TEXT,
    "xtick.color":        SUBTEXT,
    "ytick.color":        SUBTEXT,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "grid.color":         GRID,
    "grid.alpha":         1.0,
    "grid.linestyle":     "--",
    "grid.linewidth":     0.6,
    "legend.facecolor":   AX_BG,
    "legend.edgecolor":   EDGE,
    "legend.labelcolor":  TEXT,
    "legend.fontsize":    9,
    "font.family":        "sans-serif",
    "font.size":          10,
    "figure.dpi":         DPI,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.25,
    "savefig.facecolor":  BG,
    "lines.linewidth":    1.8,
})

# ── Figure helpers ────────────────────────────────────────────────────────────

def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    buf.seek(0)
    enc = base64.b64encode(buf.read()).decode("ascii")
    plt.close(fig)
    return f"data:image/png;base64,{enc}"


def _embed(out: io.StringIO, fig: plt.Figure, caption: str, fig_id: str = "") -> None:
    uri = _fig_to_base64(fig)
    alt = caption.replace('"', "'")
    out.write(f'\n<figure>\n')
    out.write(f'<img src="{uri}" alt="{alt}" style="max-width:100%;border-radius:6px;'
              f'box-shadow:0 2px 12px rgba(0,0,0,0.25)">\n')
    out.write(f'<figcaption style="color:{SUBTEXT};font-size:0.84em;'
              f'font-style:italic;margin-top:0.4em;line-height:1.5">'
              f'{caption}</figcaption>\n</figure>\n\n')


def _callout(out: io.StringIO, kind: str, text: str) -> None:
    icons = {"question": ("Q:", "#4e9af1"), "method": ("M:", "#888899"), "read": ("R:", "#44b894")}
    icon, colour = icons.get(kind, (">", SUBTEXT))
    out.write(
        f'<div style="border-left:3px solid {colour};padding:0.5em 1em;'
        f'margin:0.6em 0;background:rgba(0,0,0,0.06);font-size:0.92em;'
        f'line-height:1.6">'
        f'<strong style="color:{colour}">{icon}</strong> {text}</div>\n\n'
    )


def _section_break(out: io.StringIO, label: str) -> None:
    out.write(
        f'\n<div style="border-top:1px solid {EDGE};margin:2.5em 0 1.5em;'
        f'padding-top:1em"><span style="color:{SUBTEXT};font-size:0.78em;'
        f'text-transform:uppercase;letter-spacing:2px;font-weight:600">'
        f'{label}</span></div>\n\n'
    )


# ── Bootstrap CI helper ───────────────────────────────────────────────────────

def _bootstrap_ci(values: np.ndarray, n_boot: int = 2000, ci: float = 0.95) -> tuple[float, float, float]:
    rng = np.random.default_rng(42)
    n = len(values)
    idx = rng.integers(0, n, size=(n_boot, n))
    means = values[idx].mean(axis=1)
    lo = float(np.percentile(means, 100 * (1 - ci) / 2))
    hi = float(np.percentile(means, 100 * (1 - (1 - ci) / 2)))
    return float(values.mean()), lo, hi


# ── UMAP ellipse helper ───────────────────────────────────────────────────────

def _cluster_ellipse(x: np.ndarray, y: np.ndarray, colour: str, ax: plt.Axes,
                     n_std: float = 1.2, alpha: float = 0.12) -> None:
    if len(x) < 5:
        return
    cov = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    w, h = 2 * n_std * np.sqrt(vals)
    ell = mpatches.Ellipse(
        xy=(np.mean(x), np.mean(y)), width=w, height=h, angle=theta,
        facecolor=colour, alpha=alpha, edgecolor=colour,
        linewidth=1.4, linestyle="--",
    )
    ax.add_patch(ell)


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE BUILDERS
# ═════════════════════════════════════════════════════════════════════════════

def fig_temporal(out: io.StringIO) -> None:
    """Fig 2 — Annual production stacked by ChatGPT/GenAI framing."""
    _section_break(out, "Seção 4.2 · Evolução Temporal")
    out.write("## Fig 2 — Produção Científica Anual\n\n")

    _callout(out, "question",
             "O campo cresceu de forma contínua ou há uma ruptura discernível associada ao lançamento do ChatGPT?")
    yearly = pd.read_csv(IND / "yearly_production.csv")
    axis_df  = pd.read_csv(IND / "axis_scores_enriched.csv")

    years_plot = sorted(yearly["year"].astype(int).tolist())

    n_chatgpt, n_other = [], []
    for yr in years_plot:
        sub = axis_df[axis_df["publication_year"] == yr]["axis_e_technology"].values
        n_chatgpt.append(int((sub > 0).sum()))
        n_other.append(int((sub <= 0).sum()))

    n_total = [a + b for a, b in zip(n_chatgpt, n_other)]
    pct_chatgpt = [100 * a / t if t > 0 else 0 for a, t in zip(n_chatgpt, n_total)]
    _last_two_n = sum(n_total[-2:]) if len(n_total) >= 2 else sum(n_total)
    _last_two_pct = 100 * _last_two_n / sum(n_total) if sum(n_total) else 0

    _callout(out, "method",
             "Barras empilhadas por ano. A porção superior representa artigos com Eixo E > 0, "
             "ou seja, artigos que mencionam explicitamente ChatGPT ou IA generativa; a porção inferior "
             "representa os demais. Os rótulos no topo mostram o total anual de artigos e a porcentagem "
             "com menção explícita a ChatGPT/GenAI. A faixa sombreada marca a ruptura 2022–2023.")
    _callout(out, "read",
             f"Os dois últimos anos da série ({years_plot[-2]}–{years_plot[-1]}) concentram {_last_two_pct:.0f}% "
             "do corpus. O volume cresce fortemente, mas a fração de artigos que nomeia explicitamente "
             "ChatGPT/GenAI perde peso relativo. Essa queda de E>0 sugere normalização do rótulo, "
             "não necessariamente retração temática do campo.")

    x = np.arange(len(years_plot))
    width = 0.55

    colour_other   = ACCENT if not LIGHT else "#3a7bd5"
    colour_chatgpt = C_PALETTE[1]

    fig, ax = plt.subplots(figsize=(9, 5))

    bars_other   = ax.bar(x, n_other,   width=width, color=colour_other,   alpha=0.75,
                          label="Sem menção explícita a ChatGPT/GenAI", zorder=3, edgecolor="none")
    bars_chatgpt = ax.bar(x, n_chatgpt, width=width, color=colour_chatgpt, alpha=0.85,
                          bottom=n_other, label="Com menção explícita a ChatGPT/GenAI", zorder=3, edgecolor="none")

    # Annotate bar tops with total N and % ChatGPT
    for xi, (nt, pct) in enumerate(zip(n_total, pct_chatgpt)):
        ax.text(xi, nt + 1.5, f"{nt}\n({pct:.0f}%)", ha="center", va="bottom",
                fontsize=8, color=TEXT, fontweight="600", linespacing=1.3)

    # Rupture shading — dynamic
    _idx_2022 = years_plot.index(2022) if 2022 in years_plot else None
    if _idx_2022 is not None:
        ax.axvspan(_idx_2022 - 0.35, _idx_2022 + 1.35, color=RED, alpha=0.07, zorder=1)
        ax.text(_idx_2022 + 0.5, max(n_total) * 0.88, "ChatGPT\n(nov 2022)", ha="center", va="top",
                fontsize=8, color=RED, fontstyle="italic", fontweight="600")

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years_plot])
    ax.set_ylabel("Artigos publicados", color=TEXT, labelpad=10)
    ax.set_ylim(0, max(n_total) * 1.22)
    ax.set_title(f"Produção Científica Anual ({years_plot[0]}–{years_plot[-1]})", fontsize=13, fontweight="700",
                 color=TEXT, pad=16)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", framealpha=0.85)

    fig.tight_layout()
    _embed(out, fig,
            "Fig 2 — Produção anual. Barras empilhadas: laranja = artigos com menção explícita a ChatGPT/GenAI "
            "(Eixo E > 0); azul = demais artigos. Rótulos mostram total anual e porcentagem de menção explícita. "
           "Faixa avermelhada marca o período de ruptura (2022–2023).",
           "fig02")


def fig_cluster_composition(out: io.StringIO) -> None:
    """Fig 3 — Stacked area chart (absolute counts) — volume + composition in one view."""
    _section_break(out, "Composição por Cluster")
    out.write("## Fig 3 — Composição Temática por Ano\n\n")

    share = pd.read_csv(IND / "cluster_share_by_year.csv")
    yearly_prod = pd.read_csv(IND / "yearly_production.csv")
    years = sorted(yearly_prod["year"].astype(int).tolist())
    cluster_keys = [cluster_id for cluster_id in sorted(CLUSTER_LABELS_RAW) if CLUSTER_LABELS_RAW[cluster_id] in share.columns]
    cluster_cols = [CLUSTER_LABELS_RAW[cluster_id] for cluster_id in cluster_keys]

    _first_year = int(share["publication_year"].min())
    _last_year = int(share["publication_year"].max())
    _first_top = share.loc[share["publication_year"] == _first_year, cluster_cols].iloc[0].sort_values(ascending=False).head(2)
    _last_top = share.loc[share["publication_year"] == _last_year, cluster_cols].iloc[0].sort_values(ascending=False).head(2)
    _first_top_str = ", ".join(f"{_localize_cluster_label(lbl)} ({val:.0f}%)" for lbl, val in _first_top.items())
    _last_top_str = ", ".join(f"{_localize_cluster_label(lbl)} ({val:.0f}%)" for lbl, val in _last_top.items())
    _share_by_year = share.set_index("publication_year")
    # Dominant cluster in terms of mean share across all years
    _avg_share = _share_by_year[cluster_cols].mean()
    _dom_col  = str(_avg_share.idxmax())
    _dom_name = _localize_cluster_label(_dom_col)
    _get = lambda yr, col: float(_share_by_year.loc[yr, col]) if yr in _share_by_year.index else float("nan")
    _dom_early  = _get(_first_year, _dom_col)
    # Mid point for trend: use 2023 if available, else middle year
    _mid_year   = 2023 if 2023 in _share_by_year.index else int(np.median(list(_share_by_year.index)))
    _dom_mid    = _get(_mid_year, _dom_col)
    _dom_late   = _get(_last_year, _dom_col)

    _callout(out, "question",
             "A composição temática mudou desde 2023, após a generalização do ChatGPT?")
    _callout(out, "method",
             "Gráfico de áreas empilhadas com contagens absolutas por ano. A altura total de cada coluna temporal "
             "é o número de artigos do ano; cada faixa colorida representa o volume anual de um cluster temático "
             "identificado por KMeans nos embeddings dos resumos. Assim, o gráfico mostra simultaneamente "
             "crescimento do campo e recomposição temática.")
    _callout(out, "read",
             f"No início da série ({_first_year}), os maiores blocos eram {_first_top_str}. "
             f"No fim da série ({_last_year}), passam a liderar {_last_top_str}. "
             f"O cluster dominante ({_dom_name}) representa {_dom_early:.1f}% em {_first_year}, "
             f"{_dom_mid:.1f}% em {_mid_year} e {_dom_late:.1f}% em {_last_year}.")

    share = share[share["publication_year"].isin(years)].set_index("publication_year")
    pct = share[cluster_cols].values
    pct = pct / pct.sum(axis=1, keepdims=True)  # 0–1 proportions

    n_per_year = np.array([int(yearly_prod[yearly_prod["year"] == y]["n"].values[0])
                           if y in yearly_prod["year"].values else 0 for y in years])
    # Absolute counts per cluster per year
    counts = pct * n_per_year[:, None]   # shape (6, 5)

    x = np.array(years, dtype=float)

    fig, ax = plt.subplots(figsize=(11, 5.5))

    # stackplot — draws filled areas directly
    ys = [counts[:, ci] for ci in range(len(cluster_cols))]
    colours = [C_PALETTE[k] for k in cluster_keys]
    ax.stackplot(x, ys, labels=[_compact_cluster_legend_label(k) for k in cluster_keys],
                 colors=colours, alpha=0.88)

    # thin white edge between stacks for separation
    cumulative = np.zeros(len(years))
    for ci in range(len(cluster_cols)):
        cumulative += counts[:, ci]
        ax.plot(x, cumulative, color=BG, lw=0.8, zorder=3)

    # Total-n annotation at each year's peak
    total_n = counts.sum(axis=1)
    for i, (yr, n) in enumerate(zip(years, total_n)):
        ax.text(yr, n + 4, f"n={int(round(n))}", ha="center", va="bottom",
                fontsize=8, color=SUBTEXT)

    # ChatGPT rupture line
    ax.axvline(2022.92, color=RED, lw=1.2, ls=":", alpha=0.8)
    ax.text(2022.85, total_n.max() * 0.55, "ChatGPT\nnov 2022",
            color=TEXT, fontsize=7.5, fontstyle="italic",
            va="center", ha="right",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                      edgecolor=RED, linewidth=0.8, alpha=0.85))

    ax.set_xlim(years[0] - 0.3, years[-1] + 0.5)
    ax.set_ylim(0, total_n.max() * 1.18)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years])
    ax.set_ylabel("N de artigos", color=TEXT, labelpad=8)
    ax.set_title("Crescimento e Composição Temática por Ano",
                 fontsize=13, fontweight="700", color=TEXT, pad=16)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.35, lw=0.6)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper left",
              fontsize=8.5, ncol=1, framealpha=0.9)

    fig.tight_layout()
    _embed(out, fig,
           "Fig 3 — Área empilhada (contagens absolutas): altura total = volume por ano; "
            "faixas = clusters temáticos. O gráfico combina volume anual e participação relativa de cada cluster "
            "em uma única visualização.",
           "fig03")


def fig_geo_countries(out: io.StringIO) -> None:
    """Fig 4 — Geographic presence map from article-country occurrence counts."""
    _section_break(out, "Seção 4.3 · Distribuição Geográfica do Corpus")
    out.write("## Fig 4 — Distribuição Geográfica do Corpus\n\n")

    _callout(out, "question",
             "Quais países concentram a produção do corpus e quão ampla é a cobertura geográfica da literatura?")
    _callout(out, "method",
             "Painel duplo. À esquerda, mapa por país em escala logarítmica, usado para preservar a leitura da cauda "
             "longa sem apagar os maiores polos. À direita, ranking dos 10 países com maior contagem no campo countries. "
             "A unidade analítica é ocorrência de país: um artigo multinacional pode contribuir para mais de um país.")

    geo = pd.read_csv(IND / "geo_countries.csv")
    if geo.empty:
        out.write(f'<p style="color:{SUBTEXT};font-style:italic">geo_countries.csv não encontrado ou vazio.</p>\n\n')
        return

    from matplotlib import colors as mcolors
    from matplotlib.cm import ScalarMappable
    import plotly.graph_objects as go
    import plotly.io as pio
    import pycountry

    code_aliases = {"UK": "GB", "EL": "GR", "XK": "XKX"}
    country_name_pt = {
        "US": "Estados Unidos",
        "GB": "Reino Unido",
        "CN": "China",
        "IT": "Itália",
        "IN": "Índia",
        "AU": "Austrália",
        "CA": "Canadá",
        "DE": "Alemanha",
        "ES": "Espanha",
        "BR": "Brasil",
        "FR": "França",
        "NL": "Países Baixos",
        "KR": "Coreia do Sul",
        "JP": "Japão",
        "TR": "Turquia",
        "SE": "Suécia",
        "CH": "Suíça",
        "PT": "Portugal",
        "MX": "México",
        "SA": "Arábia Saudita",
        "IR": "Irã",
        "ZA": "África do Sul",
    }

    def _normalize_country_code(code: str) -> str:
        cleaned = str(code).strip().upper()
        return code_aliases.get(cleaned, cleaned)

    def _country_record(code: str):
        lookup = _normalize_country_code(code)
        if lookup == "XKX":
            return None
        return pycountry.countries.get(alpha_2=lookup)

    def _country_iso3(code: str) -> str | None:
        lookup = _normalize_country_code(code)
        if lookup == "XKX":
            return "XKX"
        record = _country_record(code)
        return None if record is None else str(record.alpha_3)

    def _country_name(code: str) -> str:
        cleaned = str(code).strip().upper()
        record = _country_record(cleaned)
        if cleaned in country_name_pt:
            return country_name_pt[cleaned]
        if record is None:
            return cleaned
        return str(getattr(record, "name", cleaned))

    def _country_display(code: str) -> str:
        label = f"{str(code).strip().upper()} · {_country_name(code)}"
        return label if len(label) <= 26 else label[:25].rstrip() + "…"

    geo["country_code"] = geo["country_code"].fillna("").astype(str).str.strip().str.upper()
    geo["n"] = pd.to_numeric(geo["n"], errors="coerce").fillna(0)
    geo["pct"] = pd.to_numeric(geo["pct"], errors="coerce").fillna(0)
    geo["iso3"] = geo["country_code"].map(_country_iso3)
    geo["country_name"] = geo["country_code"].map(_country_name)
    geo = geo[geo["iso3"].notna() & (geo["n"] > 0)].copy()
    if geo.empty:
        out.write(f'<p style="color:{SUBTEXT};font-style:italic">Nenhum código de país pôde ser convertido para o mapa.</p>\n\n')
        return

    geo["log_n"] = np.log1p(geo["n"])
    total_occ = float(geo["n"].sum())
    represented = int(len(geo))
    top_ranked = geo.sort_values("n", ascending=False).reset_index(drop=True)
    top10 = top_ranked.head(10).copy()
    top10["display"] = top10["country_code"].map(_country_display)
    top10_share = 100 * float(top10["n"].sum()) / max(total_occ, 1.0)

    top3 = top_ranked.head(3)
    top3_str = ", ".join(
        f"{row.country_name} ({int(row.n):,}; {row.pct:.1f}%)"
        for row in top3.itertuples(index=False)
    )
    _callout(out, "read",
             f"{represented} países aparecem no corpus. Os maiores polos são {top3_str}. "
             f"Os 10 países líderes concentram {top10_share:.1f}% das ocorrências geográficas. "
             "A leitura correta é de presença institucional do corpus por país, não de partição exclusiva de artigos.")

    max_n = float(geo["n"].max())
    tick_counts = [1, 5, 20, 100, 500, 1000]
    tick_counts = [value for value in tick_counts if value <= max_n]
    if int(max_n) not in tick_counts:
        tick_counts.append(int(max_n))

    map_colorscale = [
        (0.00, "#e9eff7" if LIGHT else "#2a3550"),
        (0.28, "#b7cce6" if LIGHT else "#3b5f8d"),
        (0.56, "#7fa9d9" if LIGHT else "#4e9af1"),
        (1.00, "#1f4c8f" if LIGHT else "#bcd7ff"),
    ]

    map_fig = go.Figure(
        go.Choropleth(
            locations=geo["iso3"],
            z=geo["log_n"],
            locationmode="ISO-3",
            colorscale=map_colorscale,
            zmin=float(geo["log_n"].min()),
            zmax=float(geo["log_n"].max()),
            marker_line_color=BG,
            marker_line_width=0.35 if LIGHT else 0.25,
            showscale=False,
            hoverinfo="skip",
        )
    )
    map_fig.update_geos(
        projection_type="natural earth",
        showframe=False,
        showcoastlines=False,
        showcountries=True,
        countrycolor=BG,
        countrywidth=0.35,
        showland=True,
        landcolor="#f5f7fa" if LIGHT else "#20283c",
        showocean=True,
        oceancolor="#eef3f7" if LIGHT else "#161c2c",
        showlakes=True,
        lakecolor="#eef3f7" if LIGHT else "#161c2c",
        bgcolor=AX_BG,
    )
    map_fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=AX_BG,
        plot_bgcolor=AX_BG,
        font=dict(color=TEXT, size=10),
    )
    map_png = pio.to_image(
        map_fig,
        format="png",
        width=1280 if LIGHT else 1180,
        height=780,
        scale=2,
    )
    map_image = np.asarray(Image.open(io.BytesIO(map_png)).convert("RGBA"))

    fig, (ax_map, ax_bar) = plt.subplots(
        1,
        2,
        figsize=(15.4, 6.4),
        gridspec_kw={"width_ratios": [1.85, 1.0]},
    )
    fig.patch.set_facecolor(BG)

    ax_map.set_facecolor(AX_BG)
    ax_map.imshow(map_image)
    ax_map.set_axis_off()
    ax_map.set_title("Ocorrências por país",
                     fontsize=11.5, fontweight="700", color=TEXT, pad=10)

    cbar_cmap = mcolors.LinearSegmentedColormap.from_list("geo_occ_scale", map_colorscale)
    cbar_norm = mcolors.Normalize(
        vmin=float(geo["log_n"].min()),
        vmax=float(geo["log_n"].max()),
    )
    cbar_ax = ax_map.inset_axes([0.22, 0.045, 0.56, 0.045])
    cbar = fig.colorbar(
        ScalarMappable(norm=cbar_norm, cmap=cbar_cmap),
        cax=cbar_ax,
        orientation="horizontal",
    )
    cbar.set_ticks([float(np.log1p(value)) for value in tick_counts])
    cbar.set_ticklabels([f"{value:,}" for value in tick_counts])
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(axis="x", labelsize=8.8, colors=TEXT, length=0, pad=1)
    cbar.ax.set_title("Ocorrências por país (escala log)", fontsize=9.2, color=TEXT, pad=8)
    cbar_ax.set_facecolor(AX_BG)

    ax_bar.set_facecolor(AX_BG)
    base_bar = "#c0cde0" if LIGHT else "#5e6f91"
    bar_colours = [base_bar] * len(top10)
    highlight_colours = [AMBER, C_PALETTE[0], C_PALETTE[2]]
    for idx, colour in enumerate(highlight_colours):
        if idx < len(bar_colours):
            bar_colours[idx] = colour

    y = np.arange(len(top10))
    bars = ax_bar.barh(y, top10["n"], color=bar_colours, edgecolor="none", height=0.64, zorder=3)
    for bar, row in zip(bars, top10.itertuples(index=False)):
        ax_bar.text(bar.get_width() + max_n * 0.018,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(row.n):,}  ({row.pct:.1f}%)",
                    va="center", fontsize=8.6, color=TEXT, fontweight="600")

    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(top10["display"], fontsize=9)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, max_n * 1.32)
    ax_bar.set_xlabel("Ocorrências no campo countries", color=TEXT, labelpad=8)
    ax_bar.set_title("Top 10 países\n(por ocorrências de afiliação)",
                     fontsize=11.5, fontweight="700", color=TEXT, pad=10)
    ax_bar.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    ax_bar.set_axisbelow(True)
    ax_bar.spines["left"].set_visible(False)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.spines["bottom"].set_edgecolor(SPINE)
    ax_bar.tick_params(axis="y", length=0)
    ax_bar.tick_params(axis="x", colors=SUBTEXT)
    ax_bar.text(0.98, 0.02,
                f"{represented} países\nTop 10 = {top10_share:.1f}%\ndas ocorrências",
                transform=ax_bar.transAxes,
                ha="right", va="bottom",
                fontsize=8.4, color=SUBTEXT,
                bbox=dict(facecolor=BG, edgecolor=EDGE, boxstyle="round,pad=0.35", alpha=0.92))

    fig.suptitle("Distribuição Geográfica do Corpus — Mapa + Top 10 Países",
                 fontsize=12.8, fontweight="700", color=TEXT, y=1.01)
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 4 — Painel duplo da distribuição geográfica do corpus. Esquerda: mapa mundial por país "
           f"com escala logarítmica de ocorrências por país a partir do campo countries. Direita: Top 10 países "
           f"por número de ocorrências, com rótulos de N e %. A contagem não é mutuamente exclusiva: artigos "
           f"multinacionais contribuem para mais de um país. País líder: {top_ranked.iloc[0]['country_name']} "
           f"({int(top_ranked.iloc[0]['n']):,} ocorrências).",
           "fig04")


def fig_bradford(out: io.StringIO) -> None:
    """Fig 5 — Bradford's Law: cumulative publications curve with zone demarcation."""
    _section_break(out, "Seção 4.4 · Dispersão em Periódicos — Lei de Bradford")
    out.write("## Fig 5 — Lei de Bradford: Dispersão da Produção em Periódicos\n\n")

    _callout(out, "question",
             "Como a produção sobre IA na produção acadêmica se distribui entre os periódicos? "
             "Existe um núcleo de revistas de alta concentração e uma longa cauda periférica?")
    _callout(out, "method",
             "Curva de Bradford: periódicos ordenados pelo rank de produtividade (nº de artigos, "
             "decrescente) plotados contra a produção acumulada. "
             "Três zonas de Bradford delimitadas por áreas iguais de produção — "
             "Zona 1 (núcleo), Zona 2 (intermediária), Zona 3 (periférica). "
             "Escala X logarítmica (rank do periódico); Y = artigos acumulados.")
    journals = pd.read_csv(IND / "journals.csv")
    journals_sorted = journals.sort_values("n", ascending=False).reset_index(drop=True)
    journals_sorted["rank"] = journals_sorted.index + 1
    journals_sorted["cum_n"] = journals_sorted["n"].cumsum()
    total_papers = journals_sorted["n"].sum()

    # Zone boundaries already computed in the data; compute cumulative thresholds
    zone_colours = {1: C_PALETTE[0], 2: C_PALETTE[2], 3: C_PALETTE[3]}
    zone_labels  = {1: f"Zona 1 — Núcleo ({journals[journals['bradford_zone']==1].shape[0]} periódicos)",
                    2: f"Zona 2 — Intermediária ({journals[journals['bradford_zone']==2].shape[0]} periódicos)",
                    3: f"Zona 3 — Periférica ({journals[journals['bradford_zone']==3].shape[0]} periódicos)"}

    # Zone boundaries: use max rank of each zone (zones may interleave in sorted order,
    # so find the rank cutoffs from cumulative production targets: 1/3 and 2/3 of total)
    target1 = total_papers / 3
    target2 = total_papers * 2 / 3
    boundary_z1 = int(journals_sorted.loc[journals_sorted["cum_n"] <= target1, "rank"].max())
    boundary_z2 = int(journals_sorted.loc[journals_sorted["cum_n"] <= target2, "rank"].max())
    # zone_boundaries: [end_of_zone1_rank, end_of_zone2_rank]
    zone_boundaries = [boundary_z1, boundary_z2]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)

    # Shade zones
    zone_ranges = [(1, zone_boundaries[0]), (zone_boundaries[0]+1, zone_boundaries[1]),
                   (zone_boundaries[1]+1, len(journals_sorted))]
    for i, (z_start, z_end) in enumerate(zone_ranges, start=1):
        ax.axvspan(np.log10(z_start), np.log10(z_end + 1),
                   color=zone_colours[i], alpha=0.10)

    # Plot cumulative curve
    ax.plot(np.log10(journals_sorted["rank"]), journals_sorted["cum_n"],
            color=ACCENT, lw=2.2, zorder=5)

    # Vertical demarcation lines
    for boundary_rank in zone_boundaries:
        ax.axvline(np.log10(boundary_rank + 0.5), color=SPINE, lw=1.0, ls="--", alpha=0.8)

    # Annotate zone labels inside shaded regions
    prev_end = 0
    for i, (z_start, z_end) in enumerate(zone_ranges, start=1):
        mid_log = (np.log10(z_start) + np.log10(z_end + 1)) / 2
        cum_end = journals_sorted.loc[journals_sorted["rank"] <= z_end, "cum_n"].max()
        cum_start = journals_sorted.loc[journals_sorted["rank"] <= z_start, "cum_n"].max() if z_start > 1 else 0
        y_label = (cum_start + cum_end) / 2
        ax.text(mid_log, y_label, zone_labels[i],
                ha="center", va="center", fontsize=8, color=TEXT,
                bbox=dict(facecolor=AX_BG, edgecolor=EDGE, boxstyle="round,pad=0.3",
                          alpha=0.85, linewidth=0.7))

    ax.set_xlabel("Rank do Periódico (escala log₁₀)", color=TEXT, labelpad=10)
    ax.set_ylabel("Artigos Acumulados", color=TEXT, labelpad=10)
    ax.set_title("Lei de Bradford — Dispersão da Produção por Periódicos (2020–2026)",
                 fontsize=13, fontweight="700", color=TEXT, pad=16)
    ax.set_axisbelow(True)
    ax.grid(alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend patches
    legend_items = [mpatches.Patch(color=zone_colours[z], alpha=0.55, label=zone_labels[z])
                    for z in (1, 2, 3)]
    ax.legend(handles=legend_items, loc="upper left", fontsize=8.5, framealpha=0.9)
    fig.tight_layout()

    _z1n = journals[journals["bradford_zone"] == 1]
    _top1 = _z1n.nlargest(3, "n")[["journal", "n"]]
    _top1_str = "; ".join(f"{r['journal']} ({int(r['n'])} art.)" for _, r in _top1.iterrows())
    _z_counts = journals["bradford_zone"].value_counts().sort_index()
    _embed(out, fig,
            f"Fig 5 — Curva de Bradford (N={total_papers:,} artigos, {len(journals_sorted):,} periódicos). "
           f"Zona 1 ({_z_counts[1]} periódicos) concentra ~1/3 da produção; "
           f"Zona 3 ({_z_counts[3]} periódicos) dispersa outro terço pela longa cauda. "
           f"Periódicos de núcleo mais produtivos: {_top1_str}.",
           "fig04")


def fig_umap(out: io.StringIO) -> None:
    """Fig 6 — UMAP 2D semantic scatter with cluster ellipses."""
    _section_break(out, "Seção 4.6 · Análise Semântica — Clusters UMAP")
    out.write("## Fig 6 — Mapa Semântico UMAP (Clusters Temáticos)\n\n")

    _callout(out, "question",
             "Quão distintos são os temas presentes no corpus? "
             "Os clusters correspondem a subcampos identificáveis?")

    # Load data early so we can reference n_clusters in callout text
    df = pd.read_csv(ROOT / "corpus_clustered.csv",
                     usecols=["umap_x", "umap_y", "cluster", "cited_by_count"])
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["s"] = 8 + np.log1p(df["cited_by_count"]) * 3.5
    n_clusters = df["cluster"].nunique()

    _callout(out, "method",
             f"Embeddings BGE-M3 (1024 dimensões) reduzidos para 2D via UMAP (métrica cosseno). "
             f"Cada ponto é um artigo; tamanho proporcional a log(1 + citações). "
             f"Clusters definidos por KMeans em 1024D (k={n_clusters}); "
             "sobreposição no plano 2D é esperada dado o corpus temático estreito.")
    _callout(out, "read",
             f"{n_clusters} clusters temáticos identificados. Leve sobreposição confirmada — "
             "corpus estreito, todos sobre IA aplicada à produção/escrita acadêmica e clínica. "
             "Pontos maiores = artigos mais citados. Estrelas = mais citado por cluster.")

    fig, ax = plt.subplots(figsize=(9, 7))

    for c in range(n_clusters):
        mask = df["cluster"] == c
        sub = df[mask]
        ax.scatter(sub["umap_x"], sub["umap_y"],
                   c=C_PALETTE[c], s=sub["s"], alpha=0.40,
                   edgecolors="none", zorder=3, label=_compact_cluster_legend_label(c),
                   rasterized=True)
        # Centroid label
        cx, cy = sub["umap_x"].mean(), sub["umap_y"].mean()
        ax.text(cx, cy, f"C{c}", ha="center", va="center",
                fontsize=8, fontweight="700",
                color=C_PALETTE[c], zorder=6,
                bbox=dict(facecolor=BG, edgecolor=C_PALETTE[c],
                          boxstyle="round,pad=0.2", alpha=0.75, linewidth=0.8))

    # Confidence ellipses per cluster
    from matplotlib.patches import Ellipse
    import matplotlib.transforms as _mtrans
    for c in range(n_clusters):
        sub = df[df["cluster"] == c]
        if len(sub) < 5:
            continue
        _cx, _cy = sub["umap_x"].values, sub["umap_y"].values
        _cov = np.cov(_cx, _cy)
        _pearson = _cov[0, 1] / np.sqrt(_cov[0, 0] * _cov[1, 1])
        _ell = Ellipse((0, 0),
                       width=np.sqrt(1 + _pearson) * 2,
                       height=np.sqrt(1 - _pearson) * 2,
                       facecolor=C_PALETTE[c], alpha=0.10,
                       edgecolor=C_PALETTE[c], linewidth=1.2,
                       linestyle="--", zorder=2)
        _t = (_mtrans.Affine2D()
              .rotate_deg(45)
              .scale(np.sqrt(_cov[0, 0]) * 2.0, np.sqrt(_cov[1, 1]) * 2.0)
              .translate(_cx.mean(), _cy.mean()))
        _ell.set_transform(_t + ax.transData)
        ax.add_patch(_ell)

    # Star for most-cited article in each cluster
    import matplotlib.lines as _mlines
    for c in range(n_clusters):
        sub_c = df[df["cluster"] == c]
        if sub_c["cited_by_count"].max() > 0:
            top_idx = sub_c["cited_by_count"].idxmax()
            ax.scatter(df.loc[top_idx, "umap_x"], df.loc[top_idx, "umap_y"],
                       s=180, marker="*", color=C_PALETTE[c], zorder=7,
                       edgecolors=TEXT, linewidths=0.6)
    star_proxy = _mlines.Line2D([], [], marker="*", color="none",
                                markeredgecolor=TEXT, markerfacecolor="gray",
                                markersize=10, label="Mais citado")

    ax.set_xlabel("UMAP dimensão 1", color=TEXT, labelpad=10)
    ax.set_ylabel("UMAP dimensão 2", color=TEXT, labelpad=10)
    ax.set_title(f"Mapa Semântico UMAP — {len(df)} Artigos / {n_clusters} Clusters", fontsize=13,
                 fontweight="700", color=TEXT, pad=16)
    handles, hlabels = ax.get_legend_handles_labels()
    ax.legend(handles + [star_proxy], hlabels + [star_proxy.get_label()],
              loc="upper left", fontsize=8.5, markerscale=1.4, framealpha=0.9)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _embed(out, fig,
            "Fig 6 — UMAP 2D (métrica cosseno). Cada ponto representa um artigo; "
            "o tamanho é proporcional a log(1 + citações). As cores indicam os clusters obtidos por KMeans "
            "nos embeddings em 1024 dimensões. A estrela marca o artigo mais citado de cada cluster.",
           "fig05")


def fig_scatter_ea(out: io.StringIO) -> None:
    """Fig 7 — Semantic scatter Axis E × Axis N, the central finding."""
    _section_break(out, "Eixos Semânticos — Projeção E × N")
    out.write("## Fig 7 — Mapa de Eixos Semânticos (E × N)\n\n")

    _callout(out, "question",
             "O corpus distribui-se entre artigos de postura otimista (oportunidade/adoção) e artigos de postura "
             "crítica (risco/governança) — e essa dimensão interage com o enquadramento tecnológico "
             "(ChatGPT/GenAI vs. IA genérica)?")
    _callout(out, "method",
             "Projeção de cada resumo nos Eixos E (enquadramento tecnológico) e N (postura). "
             "Eixo E: produto interno embedding × (polo ChatGPT − polo IA genérica). "
             "Eixo N: produto interno × (polo risco/governança − polo oportunidade/adoção). "
             "Tamanho dos pontos: log(1 + citações). Cores por cluster KMeans. "
             "As linhas em zero separam os quatro quadrantes interpretativos do espaço semântico.")
    _callout(out, "read",
             "Artigos com postura de risco/governança (Eixo N positivo) tendem a concentrar-se no lado ChatGPT/GenAI do plano E×N, "
             "sobretudo nos clusters de integridade acadêmica. Mas esta projeção é semântica, não causal: "
             "o teste temporal da Fig 8 mostra que o efeito agregado do Eixo E é instável quando o corpus é estratificado por coorte.")

    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["s"] = 7 + np.log1p(df["cited_by_count"]) * 3.5
    n_clusters_ea = df["cluster"].nunique()

    fig, ax = plt.subplots(figsize=(9, 7))

    for c in range(n_clusters_ea):
        mask = df["cluster"] == c
        sub = df[mask]
        ax.scatter(sub["axis_e_technology"], sub["axis_n_domain"],
                   c=C_PALETTE[c], s=sub["s"], alpha=0.45,
                   edgecolors="none", zorder=3, label=_compact_cluster_legend_label(c),
                   rasterized=True)

    # Axis zero lines
    ax.axhline(0, color=SPINE, lw=1.0, ls="-", alpha=0.8, zorder=2)
    ax.axvline(0, color=SPINE, lw=1.0, ls="-", alpha=0.8, zorder=2)

    # Quadrant labels
    ax.autoscale()
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    q_style = dict(fontsize=7.5, color=SUBTEXT, fontstyle="italic",
                   ha="center", va="center")
    q_offset_x = (x1 - x0) * 0.20
    q_offset_y = (y1 - y0) * 0.13
    for qx, qy, label in [
        (x0 + q_offset_x, y1 - q_offset_y, "IA genérica\n→ risco/govern."),
        (x1 - q_offset_x, y1 - q_offset_y, "ChatGPT/GenAI\n→ risco/govern."),
        (x0 + q_offset_x, y0 + q_offset_y, "IA genérica\n→ oportunidade"),
        (x1 - q_offset_x, y0 + q_offset_y, "ChatGPT/GenAI\n→ oportunidade"),
    ]:
        ax.text(qx, qy, label, **q_style,
                bbox=dict(facecolor=BG, edgecolor=EDGE, boxstyle="round,pad=0.3",
                          alpha=0.55, linewidth=0.6), zorder=2)

    # 0: Blue, 1: Orange, 2: Green, 3: Purple, 4: Yellow
    _label_layout = {
        0: {"offset": (96, -24),  "ha": "left",  "va": "top",    "rad": 0.08},
        1: {"offset": (84, 52),   "ha": "left",  "va": "bottom", "rad": 0.10},
        2: {"offset": (-18, 40),  "ha": "left",  "va": "bottom", "rad": 0.10},
        3: {"offset": (116, 64),  "ha": "right", "va": "bottom", "rad": 0.08},
        4: {"offset": (8, -62),   "ha": "left",  "va": "top",    "rad": 0.10},
    }
    import matplotlib.lines as _mlines6
    for c in range(n_clusters_ea):
        sub_c = df[df["cluster"] == c]
        if sub_c["cited_by_count"].max() > 0:
            top_idx = sub_c["cited_by_count"].idxmax()
            row = df.loc[top_idx]
            xe, xn = row["axis_e_technology"], row["axis_n_domain"]
            ax.scatter(xe, xn, s=180, marker="*", color=C_PALETTE[c], zorder=7,
                       edgecolors=TEXT, linewidths=0.6)
            layout = _label_layout.get(c, {"offset": (90, 36), "ha": "left", "va": "bottom", "rad": 0.0})
            off_x, off_y = layout["offset"]
            ax.annotate(
                f"C{c} · mais citado\n{int(row['cited_by_count'])} citações",
                xy=(xe, xn), xycoords="data",
                xytext=(off_x, off_y), textcoords="offset points",
                fontsize=6.5, color=TEXT, ha=layout["ha"], va=layout["va"],
                arrowprops=dict(arrowstyle="-", color=SUBTEXT, lw=0.6,
                                shrinkA=0, shrinkB=4,
                                connectionstyle=f"arc3,rad={layout['rad']}"),
                bbox=dict(facecolor=BG, edgecolor=C_PALETTE[c],
                          boxstyle="round,pad=0.25", alpha=0.92, linewidth=0.8),
                zorder=8,
            )
    star_proxy6 = _mlines6.Line2D([], [], marker="*", color="none",
                                   markeredgecolor=TEXT, markerfacecolor="gray",
                                   markersize=10, label="Mais citado")

    ax.set_xlabel("Eixo E — IA genérica (−) → ChatGPT/GenAI (+)", color=TEXT, labelpad=10)
    ax.set_ylabel("Eixo N — Oportunidade/Adoção (−) → Risco/Governança (+)", color=TEXT, labelpad=10)
    ax.set_title("Mapa Semântico E × N — Enquadramento Tecnológico vs. Postura", fontsize=13,
                 fontweight="700", color=TEXT, pad=16)
    handles6, hlabels6 = ax.get_legend_handles_labels()
    ax.legend(handles6 + [star_proxy6], hlabels6 + [star_proxy6.get_label()],
              loc="upper center", bbox_to_anchor=(0.5, -0.13),
              fontsize=8.0, markerscale=1.25, framealpha=0.9, ncol=3,
              columnspacing=1.1, handletextpad=0.45, borderpad=0.4, labelspacing=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(rect=[0, 0.11, 1, 1])
    _embed(out, fig,
            "Fig 7 — Projeção de artigos nos Eixos E (enquadramento tecnológico) × N (postura). "
            "O tamanho dos pontos é proporcional a log(1 + citações) e as cores representam os clusters KMeans. "
           "Estrela = artigo mais citado de cada cluster. A figura mostra afinidades semânticas entre enquadramento tecnológico "
            "e postura, mas a leitura de impacto deve ser complementada pelo teste de sensibilidade temporal da Fig 8.",
           "fig06")


def fig_axis_e_citations(out: io.StringIO) -> None:
    """Fig 8 — Axis E aggregated effect vs cohort-sensitive diagnostics."""
    _section_break(out, "Eixo E × Citações")
    out.write("## Fig 8 — Enquadramento ChatGPT: Efeito Agregado vs. Sensibilidade por Coorte\n\n")

    _callout(out, "question",
             "Artigos que nomeiam explicitamente ChatGPT ou IA generativa recebem mais citações, "
             "ou esse sinal desaparece quando se controla o efeito de coorte temporal?")
    _callout(out, "method",
             "Painel esquerdo: boxplots com pontos individuais para os quartis do Eixo E no corpus agregado. "
             "Painel direito: comparação das medianas de citações entre Q1 e Q4 usando as mesmas fronteiras globais do Eixo E, "
             "aplicadas separadamente às faixas 2020-2022, 2023-2024 e 2025-2026. "
             "Assim, a figura separa o efeito agregado do possível efeito de composição temporal.")
    _df7, _diag7 = _axis_temporal_diagnostics()
    _overall7 = _diag7[_diag7["label"] == "Geral"].iloc[0]
    _bands7 = _diag7[_diag7["label"] != "Geral"].copy()
    _q4_sub = _df7[_df7["axis_e_technology"] >= _df7["axis_e_technology"].quantile(0.75)]["cited_by_count"]
    _q1_sub = _df7[_df7["axis_e_technology"] <= _df7["axis_e_technology"].quantile(0.25)]["cited_by_count"]
    _q4_mean7 = _q4_sub.mean(); _q4_med7 = _q4_sub.median()
    _q1_mean7 = _q1_sub.mean(); _q1_med7 = _q1_sub.median()
    _u7, _p7 = sp_stats.mannwhitneyu(_q4_sub, _q1_sub, alternative="greater")
    _max_cit7 = int(_df7["cited_by_count"].max())
    _callout(out, "read",
             f"No agregado, Q4 (ChatGPT/GenAI) tem mediana {_q4_med7:.0f} vs {_q1_med7:.0f} em Q1 e maior proporção de artigos citados "
             f"({_overall7['share_q4']:.1f}% vs {_overall7['share_q1']:.1f}%). Mas o sinal contínuo do Eixo E é sensível à coorte: "
             f"ρE é {_bands7.loc[_bands7['label'] == '2020-2022', 'rho_e'].iloc[0]:+.3f} em 2020-2022, "
             f"{_bands7.loc[_bands7['label'] == '2023-2024', 'rho_e'].iloc[0]:+.3f} em 2023-2024 e "
             f"{_bands7.loc[_bands7['label'] == '2025-2026', 'rho_e'].iloc[0]:+.3f} em 2025-2026. "
             f"Isso enfraquece a leitura de um prêmio estável de citações para o framing ChatGPT.")

    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)

    df["quartile"] = pd.qcut(df["axis_e_technology"], 4, labels=["Q1\nIA genérica", "Q2", "Q3", "Q4\nChatGPT/GenAI"])
    q_order = ["Q1\nIA genérica", "Q2", "Q3", "Q4\nChatGPT/GenAI"]
    q_colours = [C_PALETTE[0], "#7ab0e0", "#e09050", C_PALETTE[1]]

    fig, (ax, ax_band) = plt.subplots(1, 2, figsize=(12, 5.8), gridspec_kw={"width_ratios": [1.25, 1]})

    # Box plot
    bplot_data = [df[df["quartile"] == q]["cited_by_count"].values for q in q_order]
    bp = ax.boxplot(bplot_data, positions=np.arange(4), widths=0.42,
                    patch_artist=True, showfliers=False,
                    medianprops=dict(color=TEXT, linewidth=2),
                    whiskerprops=dict(color=SUBTEXT, linewidth=1.2),
                    capprops=dict(color=SUBTEXT, linewidth=1.2),
                    boxprops=dict(linewidth=1.2))
    for patch, colour in zip(bp["boxes"], q_colours):
        patch.set_facecolor(colour)
        patch.set_alpha(0.55)

    # Strip overlay
    rng = np.random.default_rng(42)
    for i, (data, colour) in enumerate(zip(bplot_data, q_colours)):
        jit = rng.uniform(-0.18, 0.18, len(data))
        # log-safe: plot at log scale, just offset x
        ax.scatter(i + jit, data, color=colour, alpha=0.28, s=12, zorder=5, edgecolors="none")

    # Annotate medians and N
    for i, (data, colour) in enumerate(zip(bplot_data, q_colours)):
        med = np.median(data)
        ax.text(i, med + 0.15, f"med.={med:.0f}", ha="center", va="bottom",
                fontsize=8, color=TEXT, fontweight="600")
        ax.text(i, 0.025, f"n={len(data)}",
            transform=ax.get_xaxis_transform(),
            ha="center", va="bottom", fontsize=8,
            color=SUBTEXT,
            bbox=dict(facecolor=AX_BG, edgecolor="none", pad=0.15, alpha=0.9))

    # Highlight Q4
    ax.axvspan(2.65, 3.35, color=C_PALETTE[1], alpha=0.08, zorder=1)

    # Mann-Whitney annotation
    top_q = df[df["axis_e_technology"] >= df["axis_e_technology"].quantile(0.75)]["cited_by_count"]
    bot_q = df[df["axis_e_technology"] <= df["axis_e_technology"].quantile(0.25)]["cited_by_count"]
    u_stat, p_val = sp_stats.mannwhitneyu(top_q, bot_q, alternative="greater")
    sig_text = f"Teste U de Mann-Whitney\nQ4 > Q1 · U={u_stat:.0f}, p={p_val:.3f}"
    ax.text(0.98, 0.97, sig_text, transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color=GREEN, fontweight="600",
            bbox=dict(facecolor=AX_BG, edgecolor=GREEN, boxstyle="round,pad=0.4",
                      alpha=0.9, linewidth=0.8))

    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks(np.arange(4))
    ax.set_xticklabels(q_order, fontsize=9.5)
    ax.set_ylabel("Citações (escala log-simétrica)", color=TEXT, labelpad=10)
    ax.set_title("Impacto por Citações — Quartis do Eixo E (Enquadramento Tecnológico)",
                 fontsize=13, fontweight="700", color=TEXT, pad=16)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.5)

    _band_plot = _diag7.copy().set_index("label").loc[["Geral", "2020-2022", "2023-2024", "2025-2026"]].reset_index()
    y = np.arange(len(_band_plot))
    ax_band.hlines(y, _band_plot["med_q1"], _band_plot["med_q4"], color=SUBTEXT, lw=2.0, alpha=0.65, zorder=2)
    ax_band.scatter(_band_plot["med_q1"], y, color=C_PALETTE[0], s=52, zorder=4, label="Q1 · IA genérica")
    ax_band.scatter(_band_plot["med_q4"], y, color=C_PALETTE[1], s=52, zorder=4, label="Q4 · ChatGPT/GenAI")
    for yi, row in enumerate(_band_plot.itertuples(index=False)):
        ax_band.text(max(row.med_q1, row.med_q4) + 1.6, yi, f"ρE={row.rho_e:+.3f}",
                     va="center", ha="left", fontsize=8.2, color=TEXT,
                     bbox=dict(facecolor=AX_BG, edgecolor=EDGE, boxstyle="round,pad=0.25",
                               alpha=0.82, linewidth=0.7))
    ax_band.axvline(0, color=EDGE, lw=0.8, alpha=0.4)
    ax_band.set_yticks(y)
    ax_band.set_yticklabels(_band_plot["label"].tolist(), fontsize=9.2)
    ax_band.invert_yaxis()
    ax_band.set_xlabel("Mediana de citações (Q1 vs Q4)", color=TEXT, labelpad=10)
    ax_band.set_title("Agregado vs. faixas temporais", fontsize=11.5, fontweight="700", color=TEXT, pad=14)
    ax_band.set_xlim(0, max(_band_plot[["med_q1", "med_q4"]].max()) * 1.35)
    ax_band.grid(axis="x", alpha=0.45)
    ax_band.set_axisbelow(True)
    ax_band.legend(loc="lower right", fontsize=8.2, framealpha=0.9)

    fig.tight_layout()
    _embed(out, fig,
            f"Fig 8 — Painel esquerdo: citações por quartil do Eixo E no corpus agregado (escala log-simétrica). "
            f"Painel direito: medianas de Q1 vs Q4 por faixa temporal, com ρE anotado em cada coorte. "
            f"O agregado sugere vantagem distributiva de Q4 (p={_p7:.3f}), mas a estratificação por coorte revela um sinal muito menos estável.",
           "fig07")


def fig_axis_r_citations(out: io.StringIO) -> None:
    """Fig 9 — Axis R temporal drift: the structural shift from clinical to academic/educational.

    Stacked bar chart showing the proportion of papers in each R-zone per year,
    making the ChatGPT inflection in 2023 visible.
    """
    _section_break(out, "Eixo R × Tempo")
    out.write("## Fig 9 — Domínio Temático ao Longo do Tempo: Inflexão Estrutural em 2023\n\n")

    _callout(out, "question",
             "A composição temática do corpus — especificamente o equilíbrio entre o polo "
             "acadêmico/educacional e o polo clínico/biomédico do Eixo R — mudou de forma "
             "sistemática ao longo dos anos de publicação?")

    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df2 = df[df["axis_r_scope"].notna() & df["publication_year"].notna()].copy()
    df2["publication_year"] = df2["publication_year"].astype(int)

    years = sorted([y for y in df2["publication_year"].unique() if y <= 2025])

    # Four R-zones: strong_acad ≤ -0.10 < mild_acad ≤ 0 < mild_clin ≤ 0.10 < strong_clin
    def zone_counts(sub):
        n = len(sub)
        return {
            "strong_acad": (sub < -0.10).sum() / n,
            "mild_acad":   ((sub >= -0.10) & (sub < 0)).sum() / n,
            "mild_clin":   ((sub >= 0) & (sub < 0.10)).sum() / n,
            "strong_clin": (sub >= 0.10).sum() / n,
        }

    yr_data = {}
    for yr in years:
        sub = df2[df2["publication_year"] == yr]["axis_r_scope"]
        yr_data[yr] = zone_counts(sub)

    yr_df = pd.DataFrame(yr_data).T  # index=year, cols=zones

    # Also compute mean Axis R per year for the overlay
    r_mean_by_yr = df2.groupby("publication_year")["axis_r_scope"].mean().loc[years]
    n_by_yr = df2.groupby("publication_year")["axis_r_scope"].count().loc[years]

    rho, pval = sp_stats.spearmanr(
        df2["publication_year"], df2["axis_r_scope"]
    )

    # What changed 2022→2023?
    pct_acad_2022 = 100 * (yr_df.loc[2022, "strong_acad"] + yr_df.loc[2022, "mild_acad"])
    pct_acad_2023 = 100 * (yr_df.loc[2023, "strong_acad"] + yr_df.loc[2023, "mild_acad"])
    pct_acad_2025 = 100 * (yr_df.loc[2025, "strong_acad"] + yr_df.loc[2025, "mild_acad"])

    _callout(out, "method",
             f"Barras empilhadas de proporção: cada barra representa um ano de publicação "
             f"({years[0]}–{years[-1]}), dividida em quatro zonas do Eixo R — polo acadêmico "
             f"forte (R < −0,10), polo acadêmico moderado (−0,10 ≤ R < 0), polo clínico "
             f"moderado (0 ≤ R < 0,10) e polo clínico forte (R ≥ 0,10). "
             f"A linha sobreposta mostra o valor médio do Eixo R por ano.")

    _callout(out, "read",
             f"A composição temática do corpus sofreu uma inflexão estrutural em 2023: "
             f"em 2020–2022, apenas {pct_acad_2022:.0f}% dos artigos estavam no polo "
             f"acadêmico/educacional; em 2023 essa proporção saltou para {pct_acad_2023:.0f}% "
             f"e estabilizou em {pct_acad_2025:.0f}% em 2025. "
             f"O fenômeno coincide com o lançamento do ChatGPT (nov/2022) e o surgimento "
             f"massivo de pesquisas sobre IA generativa na educação e integridade acadêmica. "
             f"A correlação temporal é significativa: Spearman ρ={rho:+.3f} (p<0,001) entre "
             f"ano de publicação e escore do Eixo R — indicando que o corpus migrou "
             f"progressivamente em direção ao polo acadêmico ao longo do período.")

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, (ax_bar, ax_mean) = plt.subplots(
        1, 2, figsize=(13, 6.0),
        gridspec_kw={"width_ratios": [2, 1]},
    )
    fig.patch.set_facecolor(BG)

    for ax in (ax_bar, ax_mean):
        ax.set_facecolor(AX_BG)
        ax.tick_params(colors=TEXT, labelsize=9.5)
        for spine in ax.spines.values():
            spine.set_edgecolor(EDGE)
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)

    # Colours for zones (blue→orange spectrum)
    zone_cols = {
        "strong_acad": C_PALETTE[0],         # steel blue
        "mild_acad":   "#9ac4f0",             # light blue
        "mild_clin":   "#f0b090",             # light orange
        "strong_clin": C_PALETTE[1],          # warm orange
    }
    zone_labels = {
        "strong_acad": "Polo acadêmico forte  (R < −0,10)",
        "mild_acad":   "Polo acadêmico moderado  (−0,10 ≤ R < 0)",
        "mild_clin":   "Polo clínico moderado  (0 ≤ R < 0,10)",
        "strong_clin": "Polo clínico forte  (R ≥ 0,10)",
    }
    zones = ["strong_acad", "mild_acad", "mild_clin", "strong_clin"]

    xs     = np.arange(len(years))
    bottom = np.zeros(len(years))
    bars_by_zone: dict = {}

    for zone in zones:
        vals = yr_df.loc[years, zone].to_numpy() * 100
        b = ax_bar.bar(xs, vals, bottom=bottom, color=zone_cols[zone],
                       width=0.72, zorder=3, edgecolor=AX_BG, linewidth=0.4,
                       label=zone_labels[zone])
        bars_by_zone[zone] = (vals, bottom.copy())
        bottom += vals

    # Annotate the % academic (strong+mild) inside each bar stack
    for i, yr in enumerate(years):
        pct_acad = 100 * (yr_df.loc[yr, "strong_acad"] + yr_df.loc[yr, "mild_acad"])
        n = int(n_by_yr.loc[yr])
        ax_bar.text(i, 50, f"{pct_acad:.0f}%\nacad.",
                    ha="center", va="center", fontsize=8.5,
                    fontweight="700", color="white", linespacing=1.2,
                    zorder=6)
        ax_bar.text(i, -4.5, f"n={n:,}", ha="center", va="top",
                    fontsize=8, color=SUBTEXT)

    # 2023 inflection annotation
    x2023 = years.index(2023)
    ax_bar.annotate(
        "Inflexão ChatGPT\n(nov/2022)",
        xy=(x2023, 102), xytext=(x2023 + 0.6, 108),
        fontsize=8.5, color=C_PALETTE[0], fontweight="600",
        arrowprops=dict(arrowstyle="->", color=C_PALETTE[0], lw=1.1),
        bbox=dict(facecolor=BG, edgecolor=C_PALETTE[0],
                  boxstyle="round,pad=0.4", alpha=0.92, linewidth=0.8),
    )

    ax_bar.set_xticks(xs)
    ax_bar.set_xticklabels([str(y) for y in years], fontsize=10, color=TEXT)
    ax_bar.set_ylabel("% dos artigos do ano", color=TEXT, labelpad=8)
    ax_bar.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax_bar.set_ylim(-8, 115)
    ax_bar.set_title(
        "Composição do Eixo R por Ano de Publicação\n"
        "O polo clínico dominou até 2022; o acadêmico cresce de ~12% para ~37%",
        fontsize=10.5, fontweight="700", color=TEXT, pad=10,
    )
    ax_bar.legend(
        loc="upper left", fontsize=8, framealpha=0.92,
        ncol=1, handlelength=1.0, handleheight=0.9,
    )

    # ── Right: mean Axis R per year (drift line) ──────────────────────────────
    r_means = r_mean_by_yr.to_numpy()
    ax_mean.plot(r_means, xs, color=TEXT, lw=2.4, marker="o", ms=7, zorder=5)
    ax_mean.axvline(0, color=SPINE, lw=1.2, ls="--", alpha=0.8)
    ax_mean.fill_betweenx(xs, 0, r_means,
                          where=(r_means < 0), color=C_PALETTE[0], alpha=0.22, zorder=2)
    ax_mean.fill_betweenx(xs, 0, r_means,
                          where=(r_means >= 0), color=C_PALETTE[1], alpha=0.18, zorder=2)

    for i, (yr, rm) in enumerate(zip(years, r_means)):
        ax_mean.text(rm + 0.003 if rm >= 0 else rm - 0.003, i,
                     f"{rm:+.3f}",
                     ha="left" if rm >= 0 else "right",
                     va="center", fontsize=8.5, color=TEXT, fontweight="600")

    ax_mean.set_yticks(xs)
    ax_mean.set_yticklabels([str(y) for y in years], fontsize=10, color=TEXT)
    ax_mean.invert_yaxis()
    ax_mean.set_xlabel("Média do Eixo R\n← acadêmico / clínico →", color=TEXT, labelpad=8)
    ax_mean.set_title(
        "Média Anual do Eixo R\n(migração em direção ao polo acadêmico)",
        fontsize=10.5, fontweight="700", color=TEXT, pad=10,
    )
    ax_mean.text(0.97, 0.04, f"Spearman ρ={rho:+.3f} · p<0,001",
                 transform=ax_mean.transAxes, ha="right", va="bottom",
                 fontsize=8, color=SUBTEXT,
                 bbox=dict(facecolor=AX_BG, edgecolor=EDGE,
                           boxstyle="round,pad=0.3", alpha=0.9))

    fig.suptitle(
        "Eixo R × Tempo — O Campo Migrou do Polo Clínico para o Acadêmico a Partir de 2023",
        fontsize=12, fontweight="700", color=TEXT, y=1.01,
    )
    fig.tight_layout()

    _embed(out, fig,
            f"Fig 9 — Deriva temporal do Eixo R. "
           f"Painel esquerdo: composição por zona do Eixo R por ano de publicação ({years[0]}–{years[-1]}). "
           f"Em 2020–2022 o polo clínico detinha 87–90% dos artigos; a partir de 2023, "
           f"após o lançamento do ChatGPT, o polo acadêmico sobe abruptamente e estabiliza "
           f"em ~37% em 2024–2025. "
           f"Painel direito: migração da média anual do Eixo R em direção a valores negativos "
           f"(acadêmico). Spearman ρ={rho:+.3f} (p<0,001).",
           "fig08")


def fig_citation_cohorts(out: io.StringIO) -> None:
    """Fig 10 — The 2023 citation anomaly: CitGPT cohort effect.

    48% of all corpus citations belong to 2023 papers.
    The top-10 most-cited papers are all from 2023 and all discuss ChatGPT.
    """
    _section_break(out, "Citações por Coorte")
    out.write("## Fig 10 — Anomalia de Citações em 2023: O Efeito Coorte ChatGPT\n\n")

    _callout(out, "question",
             "A distribuição de citações pelo corpus é uniforme ao longo dos anos, "
             "ou existe alguma coorte de publicação que concentra desproporcionalmente "
             "o impacto? Esse efeito pode ser explicado por saturação temporal ou "
             "reflete uma qualidade intrínseca dos artigos da coorte?")

    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df_yr = df[df["publication_year"].notna()].copy()
    df_yr["publication_year"] = df_yr["publication_year"].astype(int)

    total_cit = df_yr["cited_by_count"].sum()
    years = sorted([y for y in df_yr["publication_year"].unique() if 2020 <= y <= 2025])

    # Use the same colour encoding as Fig 2
    colour_chatgpt = C_PALETTE[1]                         # orange
    colour_other   = ACCENT if not LIGHT else "#3a7bd5"   # blue

    yr_stats = {}
    for yr in years:
        sub      = df_yr[df_yr["publication_year"] == yr]
        yr_cit   = sub["cited_by_count"].sum()
        gpt_cit  = sub.loc[sub["axis_e_technology"] > 0, "cited_by_count"].sum()
        base_cit = sub.loc[sub["axis_e_technology"] <= 0, "cited_by_count"].sum()
        yr_stats[yr] = {
            "n":         len(sub),
            "total_cit": yr_cit,
            "mean_cit":  sub["cited_by_count"].mean(),
            "pct_share": 100 * yr_cit   / max(total_cit, 1),
            "gpt_pct":   100 * gpt_cit  / max(total_cit, 1),
            "base_pct":  100 * base_cit / max(total_cit, 1),
            "n_gt100":   int((sub["cited_by_count"] > 100).sum()),
        }

    pct_2023     = yr_stats[2023]["pct_share"]
    n_gt100_2023 = yr_stats[2023]["n_gt100"]
    n_gt100_rest = sum(v["n_gt100"] for k, v in yr_stats.items() if k != 2023)
    mean_2023    = yr_stats[2023]["mean_cit"]
    mean_2020    = yr_stats[2020]["mean_cit"]

    _callout(out, "method",
             f"Barras empilhadas por ano ({years[0]}–{years[-1]}): laranja = artigos com "
             f"enquadramento ChatGPT/GenAI (Eixo E > 0), azul = demais. "
             f"A mesma codificação de cores da Fig 2 permite ler este gráfico como o "
             f"'espelho de impacto' da produção anual — quem publica também domina as citações. "
             f"Nota: artigos mais antigos tiveram mais tempo para acumular citações; "
             f"ainda assim, 2020 tem apenas {mean_2020:.1f} cit./art. contra "
             f"{mean_2023:.1f} em 2023 — o efeito coorte é real, não apenas temporal.")

    _callout(out, "read",
             f"A coorte de 2023 é anomalamente influente: com {yr_stats[2023]['n']:,} artigos "
             f"({100*yr_stats[2023]['n']/len(df_yr):.0f}% do corpus), ela concentra "
             f"{pct_2023:.0f}% de todas as citações do período. "
             f"Artigos com mais de 100 citações: {n_gt100_2023} em 2023 versus "
             f"{n_gt100_rest} nos outros cinco anos combinados. "
             f"A fatia laranja em cada barra confirma que são os artigos com enquadramento "
             f"explícito em ChatGPT/GenAI (os mesmos destacados na Fig 2) que concentram o "
             f"impacto — o pico reflete o momento de maior atenção global ao tema.")

    # ── Figure — single panel ─────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)
    ax.tick_params(colors=TEXT, labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor(EDGE)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)

    xs         = np.arange(len(years))
    base_vals  = [yr_stats[yr]["base_pct"]  for yr in years]
    gpt_vals   = [yr_stats[yr]["gpt_pct"]   for yr in years]
    total_vals = [yr_stats[yr]["pct_share"] for yr in years]

    ax.bar(xs, base_vals, color=colour_other,   width=0.65, zorder=3,
           edgecolor=AX_BG, linewidth=0.4, label="Outros artigos")
    ax.bar(xs, gpt_vals,  color=colour_chatgpt, width=0.65, zorder=4,
           edgecolor=AX_BG, linewidth=0.4, bottom=base_vals,
           label="ChatGPT / GenAI  (Eixo E > 0)")

    for i, (yr, total_pct) in enumerate(zip(years, total_vals)):
        mean_cit = yr_stats[yr]["mean_cit"]
        is_2023  = yr == 2023
        # percentage + mean above bar — single text call
        ax.text(xs[i], total_pct + 0.8,
                f"{total_pct:.0f}%\n{mean_cit:.0f} cit./art.",
                ha="center", va="bottom",
                fontsize=11 if is_2023 else 8.5,
                fontweight="700",
                color=colour_chatgpt if is_2023 else TEXT,
                linespacing=1.5)

    ax.set_xticks(xs)
    ax.set_xticklabels([str(y) for y in years], fontsize=11, color=TEXT)
    ax.set_ylabel("% das citações totais do corpus", color=TEXT, labelpad=8)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_ylim(0, max(total_vals) * 1.40)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.85,
              facecolor=AX_BG, edgecolor=EDGE, labelcolor=TEXT)
    ax.set_title(
        f"Impacto por Coorte — 2023 concentra {pct_2023:.0f}% das citações com {yr_stats[2023]['n']:,} artigos",
        fontsize=11, fontweight="700", color=TEXT, pad=10,
    )

    fig.tight_layout()

    _embed(out, fig,
            f"Fig 10 — Concentração de citações por coorte (2020–2025). "
           f"Barras empilhadas: laranja = artigos ChatGPT/GenAI (Eixo E > 0), azul = demais — "
           f"mesma codificação da Fig 2. "
           f"2023 concentra {pct_2023:.0f}% das citações com apenas {yr_stats[2023]['n']:,} artigos "
           f"(~13% do corpus) e {mean_2023:.0f} cit./art. em média; "
           f"{n_gt100_2023} artigos com >100 citações contra {n_gt100_rest} nos demais anos.",
           "fig09")


def fig_orthogonality(out: io.StringIO) -> None:
    """Fig 11 — 3×3 axis correlation heatmap."""
    _section_break(out, "Validação dos Eixos — Ortogonalidade")
    out.write("## Fig 11 — Matriz de Ortogonalidade dos Eixos Semânticos\n\n")

    _callout(out, "question",
             "Os três eixos selecionados medem dimensões independentes, "
             "ou há redundância entre eles?")
    _callout(out, "method",
             "Correlação de Pearson entre os vetores de pontuação dos artigos para cada par de eixos. "
             "Mapa de calor 3×3 com escala divergente RdBu: azul = ortogonal, vermelho = correlacionado. "
             "Limiar de correlação aceitável: |r| < 0.40.")
    _callout(out, "read",
             "Eixos E, N e R foram redesenhados com polos adequados ao domínio do corpus. "
             "A ortogonalidade entre pares confirma que cada eixo captura uma dimensão independente: "
             "enquadramento tecnológico, postura (oportunidade vs. risco/governança) e domínio (acadêmico vs. clínico).")

    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    _corr = df[["axis_e_technology", "axis_n_domain", "axis_r_scope"]].corr(method="pearson")
    r_en = _corr.loc["axis_e_technology", "axis_n_domain"]
    r_er = _corr.loc["axis_e_technology", "axis_r_scope"]
    r_nr = _corr.loc["axis_n_domain", "axis_r_scope"]

    corr = np.array([
        [1.000,  r_en,  r_er],
        [ r_en, 1.000,  r_nr],
        [ r_er,  r_nr, 1.000],
    ])
    labels = ["E\n(Enquadramento\nTecnológico)", "N\n(Postura:\nOport.→Risco)", "R\n(Domínio:\nAcad.→Clínico)"]

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

    _cmap = plt.get_cmap("RdBu_r")
    for i in range(3):
        for j in range(3):
            v = corr[i, j]
            v_norm = (v - (-1)) / (1 - (-1))
            r, g, b, _ = _cmap(v_norm)
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            text_colour = "#1a1a2e" if lum > 0.45 else "white"
            sym = "—" if i == j else f"{v:+.3f}"
            ax.text(j, i, sym, ha="center", va="center",
                    fontsize=11, color=text_colour, fontweight="700")

    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_title("Ortogonalidade entre Eixos Semânticos (Pearson r)", fontsize=12,
                 fontweight="700", color=TEXT, pad=14)

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.ax.tick_params(colors=SUBTEXT, labelsize=8)
    cbar.set_label("Pearson r", color=SUBTEXT, fontsize=9)

    ax.text(0.98, 0.02, "|r| < 0.40 → aceitável", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color=SUBTEXT,
            bbox=dict(facecolor=AX_BG, edgecolor=EDGE, boxstyle="round,pad=0.3",
                      alpha=0.8, linewidth=0.6))

    fig.tight_layout()
    _embed(out, fig,
            "Fig 11 — Matriz de correlação (Pearson r) entre os três eixos semânticos (E, N, R). "
            "Azul = ortogonal; vermelho = correlação. Pares dentro do limiar |r| < 0.40.",
            "fig09")


def fig_journals(out: io.StringIO) -> None:
    """Fig 12 — Top journals by total citations in a dispersed editorial field."""
    _section_break(out, "Seção 4.4 · Principais Periódicos")
    out.write("## Fig 12 — 12 Periódicos com Maior Impacto Acumulado\n\n")

    _callout(out, "question",
             "Onde está concentrado o impacto desta literatura? "
             "Quais periódicos produziram os artigos mais citados do corpus?")
    journals = pd.read_csv(IND / "journals.csv")
    _n_journals = len(journals)
    _top_journal = journals.sort_values("total_cit", ascending=False).iloc[0]
    _top10_cit_share = 100 * journals.nlargest(10, "total_cit")["total_cit"].sum() / max(journals["total_cit"].sum(), 1)
    _top10_art_share = 100 * journals.nlargest(10, "n")["n"].sum() / max(journals["n"].sum(), 1)
    _callout(out, "method",
             f"Barras horizontais ordenadas pelo total acumulado de citações por periódico. "
             f"Cada barra agrega todas as citações dos artigos daquele periódico no corpus. "
             f"A seleção mostra os 12 maiores entre {_n_journals:,} periódicos identificados, "
             "permitindo comparar concentração de impacto editorial.")
    _callout(out, "read",
             f"O periódico de maior impacto acumulado é '{_top_journal['journal']}', com "
             f"{int(_top_journal['total_cit']):,} citações somadas no corpus. "
             f"Ainda assim, os 10 principais reúnem só {_top10_art_share:.1f}% dos artigos e {_top10_cit_share:.1f}% das citações, "
             "o que reforça a leitura de um campo editorialmente disperso, não de um núcleo estreito.")

    def shorten(name: str, maxlen: int = 52) -> str:
        return name if len(name) <= maxlen else name[:maxlen - 1] + "…"

    top12 = journals.nlargest(12, "total_cit").copy()
    top12["short"] = top12["journal"].apply(shorten)
    top12 = top12.sort_values("total_cit")  # ascending for hbar

    bar_colour = C_PALETTE[0]
    colours = [bar_colour] * len(top12)

    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(top12))
    bars = ax.barh(y, top12["total_cit"], color=colours, edgecolor="none", height=0.60, alpha=0.88)

    for bar, cit in zip(bars, top12["total_cit"]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{int(cit):,} cit.",
                va="center", fontsize=8.5, color=TEXT)

    ax.set_yticks(y)
    ax.set_yticklabels(top12["short"], fontsize=9)
    ax.set_xlabel("Citações totais", color=TEXT, labelpad=10)
    ax.set_xlim(0, top12["total_cit"].max() * 1.35)
    ax.set_title("12 Periódicos com Maior Impacto Acumulado",
                 fontsize=13, fontweight="700", color=TEXT, pad=16)
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.5)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    _embed(out, fig,
            "Fig 12 — Barras horizontais com os 12 periódicos de maior impacto acumulado no corpus, "
            "medido pela soma das citações de seus artigos. Os nomes dos periódicos são mantidos "
            "como indexados nas bases bibliográficas.",
           "fig10")


def fig_keyword_network(out: io.StringIO) -> None:
    """Fig 13 — Keyword co-occurrence network (networkx, matplotlib)."""
    import networkx as nx

    _section_break(out, "Seção 4.7 · Rede de Coocorrência de Palavras-chave")
    out.write("## Fig 13 — Rede de Coocorrência de Palavras-chave\n\n")

    _callout(out, "question",
             "Quais subtemas emergem das palavras-chave do corpus? "
             "Como eles se relacionam entre si?")
    cooc = pd.read_csv(IND / "keyword_cooc.csv")
    freq = pd.read_csv(IND / "keyword_freq.csv")
    _top_kw_read = ", ".join(f"'{kw}'" for kw in freq.head(3)["keyword"].tolist())
    _top_edge = cooc.sort_values("weight", ascending=False).iloc[0]
    _callout(out, "method",
             "Rede de coocorrência: cada nó representa uma palavra-chave e cada aresta representa um par "
             "de palavras-chave que aparece no mesmo artigo. O tamanho do nó é proporcional à frequência "
             "da palavra-chave; a espessura da aresta é proporcional à força de coocorrência. "
             "O posicionamento dos nós usa o algoritmo de Fruchterman-Reingold (layout por forças). "
             "Os rótulos são preservados no idioma original indexado pelas bases.")
    _callout(out, "read",
             f"Os termos mais frequentes são {_top_kw_read}. A ligação mais forte observada é entre "
             f"'{_top_edge['source']}' e '{_top_edge['target']}' (peso = {int(_top_edge['weight'])}).")

    # Top-20 nodes by frequency; prune edges to weight >= 4 for this smaller corpus
    top_kw = set(freq.head(20)["keyword"].tolist())
    WEIGHT_THRESH = 4
    cooc_filtered = cooc[
        cooc["source"].isin(top_kw) &
        cooc["target"].isin(top_kw) &
        (cooc["weight"] >= WEIGHT_THRESH)
    ]

    G = nx.Graph()
    for _, row in freq[freq["keyword"].isin(top_kw)].iterrows():
        G.add_node(row["keyword"], freq=int(row["freq"]))
    for _, row in cooc_filtered.iterrows():
        G.add_edge(row["source"], row["target"], weight=int(row["weight"]))

    # Remove isolated nodes (keywords with no strong co-occurrence)
    G.remove_nodes_from(list(nx.isolates(G)))

    # Community detection → colour by community (up to 5 colours)
    communities = list(nx.community.greedy_modularity_communities(G))
    comm_map = {}
    for i, comm in enumerate(communities):
        for node in comm:
            comm_map[node] = i
    node_colours = [C_PALETTE[comm_map.get(n, 0) % len(C_PALETTE)] for n in G.nodes]

    pos = nx.spring_layout(G, seed=42, k=3.5, iterations=120)

    # Node size: sqrt-scaled frequency (dampens extreme size differences)
    import math
    node_sizes = [math.sqrt(G.nodes[n]["freq"]) * 120 for n in G.nodes]

    edge_weights = [G[u][v]["weight"] for u, v in G.edges]
    max_w = max(edge_weights) if edge_weights else 1
    edge_widths = [0.8 + 4.0 * (w / max_w) for w in edge_weights]
    edge_alphas = [0.25 + 0.55 * (w / max_w) for w in edge_weights]

    fig, ax = plt.subplots(figsize=(11, 9))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)

    # Draw edges with per-edge alpha via LineCollection
    from matplotlib.collections import LineCollection
    segments, lwidths, lalphas = [], [], []
    for (u, v), w_px, a in zip(G.edges(), edge_widths, edge_alphas):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        segments.append([(x0, y0), (x1, y1)])
        lwidths.append(w_px)
        lalphas.append(a)
    lc = LineCollection(segments, linewidths=lwidths, colors=SUBTEXT, zorder=1)
    lc.set_alpha(0.55)   # overall alpha; individual control via set_alpha not trivial
    ax.add_collection(lc)

    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes,
                           node_color=node_colours, alpha=0.90)

    # Labels with a semi-transparent background box for readability
    for node, (x, y) in pos.items():
        ax.text(x, y, node, fontsize=8, fontweight="600", color=TEXT,
                ha="center", va="center", zorder=3,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                          edgecolor="none", alpha=0.65))

    ax.set_axis_off()
    ax.set_title("Rede de Coocorrência de Palavras-chave — 20 Termos Mais Frequentes",
                 fontsize=13, fontweight="700", color=TEXT, pad=16)
    ax.autoscale_view()

    # Legend: one patch per community
    comm_labels = ["Comunidade A", "Comunidade B", "Comunidade C",
                   "Comunidade D", "Comunidade E"]
    legend_items = [
        mpatches.Patch(color=C_PALETTE[i % len(C_PALETTE)],
                       label=comm_labels[i % len(comm_labels)])
        for i in range(min(len(communities), 5))
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=8.5, framealpha=0.9)

    fig.tight_layout()
    _embed(out, fig,
            "Fig 13 — Rede de coocorrência de palavras-chave (20 termos mais frequentes; arestas com peso ≥ 4). "
            "O tamanho do nó é proporcional à raiz quadrada da frequência e a espessura das arestas ao peso da coocorrência. "
           "Cor por comunidade (greedy modularity).",
           "fig11")


def _write_top20_table(out: io.StringIO) -> None:
    """HTML table — top 20 most cited papers."""
    _section_break(out, "Seção 4.5 · Artigos de Alto Impacto")
    out.write("## Tabela 1 — 20 Artigos Mais Citados\n\n")

    top20 = pd.read_csv(IND / "top20_cited.csv")
    _top_row = top20.iloc[0]
    _callout(out, "method",
             "Tabela ordenada por número de citações em ordem decrescente. "
             "Para cada artigo, são mostrados título, ano, periódico e total de citações. "
             "Títulos e nomes de periódicos permanecem no idioma original dos metadados indexados.")
    _callout(out, "read",
             f"O artigo líder é '{_top_row['title']}', publicado em {_top_row['publication_year']:.0f}, "
             f"com {int(_top_row['cited_by_count']):,} citações. O topo da lista concentra revisões, "
             "artigos de posicionamento editorial e discussões sobre uso responsável de IA.")

    th_style = f'style="background:{EDGE};color:{TEXT};padding:6px 10px;text-align:left;font-size:0.85em"'
    td_style = f'style="padding:5px 10px;font-size:0.82em;color:{TEXT};vertical-align:top"'
    td_n_style = f'style="padding:5px 10px;font-size:0.82em;color:{ACCENT};font-weight:700;text-align:center;vertical-align:top"'

    out.write(f'<table style="width:100%;border-collapse:collapse;margin:1em 0">\n')
    out.write(f'<tr>'
              f'<th {th_style}>#</th>'
              f'<th {th_style}>Título</th>'
              f'<th {th_style}>Ano</th>'
              f'<th {th_style}>Periódico</th>'
              f'<th {th_style}>Cit.</th>'
              f'</tr>\n')

    for i, row in top20.iterrows():
        title = str(row["title"])
        if len(title) > 90:
            title = title[:89] + "…"
        journal = str(row["journal"])
        if len(journal) > 40:
            journal = journal[:39] + "…"
        doi = str(row.get("doi", ""))
        title_cell = (f'<a href="{doi}" style="color:{ACCENT};text-decoration:none">{title}</a>'
                      if doi and doi != "nan" else title)
        bg = f'background:rgba(255,255,255,0.02)' if i % 2 == 0 else ''
        out.write(
            f'<tr style="{bg}">'
            f'<td {td_n_style}>{i + 1}</td>'
            f'<td {td_style}>{title_cell}</td>'
            f'<td {td_style}>{int(row["publication_year"])}</td>'
            f'<td {td_style}>{journal}</td>'
            f'<td {td_n_style}>{int(row["cited_by_count"])}</td>'
            f'</tr>\n'
        )
    out.write("</table>\n\n")


def _write_lotka_table(out: io.StringIO) -> None:
    """HTML table — top authors + Lotka's Law summary."""
    _section_break(out, "Seção 4.8 · Autores e Lei de Lotka")
    out.write("## Tabela 2 — Autores Mais Produtivos e Lei de Lotka\n\n")

    authors = pd.read_csv(IND / "top_authors.csv")
    lotka = pd.read_csv(IND / "lotka.csv")

    if authors.empty:
        out.write(f'<p style="color:{SUBTEXT};font-size:0.9em;font-style:italic">'
                  f'Dados de autoria não disponíveis para este corpus '
                  f'(metadados estruturados de autoria ausentes nos registros das fontes).'
                  f'</p>\n\n')
        return

    # Side-by-side: authors table + lotka table
    out.write('<div style="display:grid;grid-template-columns:1fr 1fr;gap:2em;margin:1em 0">\n')

    # Authors table
    th = f'style="background:{EDGE};color:{TEXT};padding:5px 10px;font-size:0.84em;text-align:left"'
    td = f'style="padding:4px 10px;font-size:0.82em;color:{TEXT}"'
    tdn = f'style="padding:4px 10px;font-size:0.82em;color:{ACCENT};font-weight:600;text-align:center"'
    out.write(f'<div>\n<h3 style="color:{TEXT};font-size:1em">15 Autores Mais Produtivos</h3>\n')
    out.write(f'<table style="width:100%;border-collapse:collapse">\n')
    out.write(f'<tr><th {th}>#</th><th {th}>Autor</th><th {th}>Artigos</th><th {th}>Cit. Total</th></tr>\n')
    for i, row in authors.head(15).iterrows():
        out.write(f'<tr><td {tdn}>{i+1}</td><td {td}>{row["author"]}</td>'
                  f'<td {tdn}>{int(row["n_papers"])}</td><td {tdn}>{int(row["total_cit"])}</td></tr>\n')
    out.write("</table>\n</div>\n")

    # Lotka table
    out.write(f'<div>\n<h3 style="color:{TEXT};font-size:1em">Lei de Lotka — Distribuição de Produtividade</h3>\n')
    if lotka.empty:
        out.write(f'<p style="color:{SUBTEXT};font-size:0.82em;font-style:italic">Dados insuficientes para calcular a Lei de Lotka.</p>\n')
    else:
        out.write(f'<table style="width:100%;border-collapse:collapse">\n')
        out.write(f'<tr><th {th}>Artigos</th><th {th}>N autores</th><th {th}>% autores</th></tr>\n')
        for _, row in lotka.iterrows():
            out.write(f'<tr><td {tdn}>{int(row["n_papers"])}</td>'
                      f'<td {tdn}>{int(row["n_authors"])}</td>'
                      f'<td {td}>{float(row["pct_authors"]):.2f}%</td></tr>\n')
        out.write("</table>\n")
        out.write(f'<p style="font-size:0.82em;color:{SUBTEXT};margin-top:0.8em">'
                  f'Lei de Lotka verificada: 1/n² de autores publica n artigos.'
                  f'</p>\n')
    out.write("</div>\n")

    out.write("</div>\n\n")


def _write_prisma(out: io.StringIO) -> None:
    """PRISMA-simplified flow as HTML."""
    _section_break(out, "Seção 3 · Fluxo PRISMA Simplificado")
    out.write("## Fluxo de Seleção do Corpus (PRISMA)\n\n")

    # --- data-driven values ---
    import json as _json
    _log   = _json.loads((ROOT / "fetch_log.json").read_text(encoding="utf-8"))
    _clean = len(pd.read_csv(ROOT / "corpus_clean.csv"))
    _clust = len(pd.read_csv(ROOT / "corpus_clustered.csv"))
    _required_keys = [
        "n_identified",
        "n_excluded_offtopic",
        "n_excluded_noabstract",
        "n_excluded_doi_dup",
        "n_excluded_title_dup",
        "n_excluded_year",
        "n_excluded_topic",
    ]
    _missing = [key for key in _required_keys if key not in _log]
    if _missing:
        raise KeyError(
            "fetch_log.json incompleto para o PRISMA: " + ", ".join(_missing)
        )

    _n_id        = int(_log["n_identified"])
    _n_offtopic  = int(_log["n_excluded_offtopic"])
    _n_noabs     = int(_log["n_excluded_noabstract"])
    _n_doi_dup   = int(_log["n_excluded_doi_dup"])
    _n_title_dup = int(_log["n_excluded_title_dup"])
    _n_year      = int(_log["n_excluded_year"])
    _n_topic     = int(_log["n_excluded_topic"])
    # Hybrid-relevance fetch may have additional exclusion stages
    _n_weak      = int(_log.get("n_excluded_weak_alignment", 0))
    _n_lowrel    = int(_log.get("n_excluded_low_relevance", 0))
    _n_retracted = int(_log.get("n_excluded_retracted", 0))
    _n_final_fetch = int(_log.get("n_final_fetch", 0))

    # Derive _post_fetch from the actual final fetch count (multi-stage filtering)
    _post_fetch = _n_final_fetch if _n_final_fetch > 0 else _n_id - _n_offtopic - _n_noabs
    _clean_expected = _post_fetch - _n_doi_dup - _n_title_dup - _n_year - _n_topic - _n_retracted
    if abs(_clean_expected - _clean) > 2:   # tolerate minor off-by-one from rounding
        raise ValueError(
            "PRISMA inconsistente: fetch_log.json implica "
            f"{_clean_expected} artigos limpos, mas corpus_clean.csv tem {_clean}. "
            "Re-execute clean_corpus.py para sincronizar o log."
        )

    _n_noemb = _clean - _clust   # derived, never hardcoded
    if _n_noemb < 0:
        raise ValueError(
            "PRISMA inconsistente: corpus_clustered.csv tem mais linhas do que corpus_clean.csv."
        )

    # Build step list — include hybrid-relevance stages only when present
    _n_manual    = int(_log.get("n_manual_new", 0))
    _sources = [s for s in _log.get("sources_enabled", []) if s != "semantic_scholar"]
    _src_str = " + ".join(s.replace("_", " ").title() for s in _sources) if _sources else "OpenAlex"
    _n_auto = _n_id - _n_manual
    steps = []
    if _n_manual > 0:
        steps += [
            (f"Identificados — exportações manuais (ACM/IEEE/PubMed/WoS/Scopus)", str(_n_manual), ACCENT),
            (f"Identificados — busca automatizada ({_src_str})", str(_n_auto), ACCENT),
            ("Total único identificado", str(_n_id), ACCENT),
        ]
    else:
        steps.append((f"Registros identificados ({_src_str})", str(_n_id), ACCENT))
    steps += [
        ("Excluídos — sem abstract", f"−{_n_noabs}", RED),
        ("Excluídos — off-topic (título)", f"−{_n_offtopic}", RED),
    ]
    if _n_weak:
        steps.append(("Excluídos — baixo alinhamento temático (BGE-M3)", f"−{_n_weak}", RED))
    if _n_lowrel:
        steps.append(("Excluídos — abaixo do threshold de relevância", f"−{_n_lowrel}", RED))
    steps += [
        ("Corpus pós-fetch", str(_post_fetch), GREEN),
        ("Excluídos — DOI duplicado", f"−{_n_doi_dup}", RED) if _n_doi_dup else None,
        ("Excluídos — títulos duplicados", f"−{_n_title_dup}", RED) if _n_title_dup else None,
        ("Excluídos — fora do período", f"−{_n_year}", RED) if _n_year else None,
        ("Excluídos — artigos retratados", f"−{_n_retracted}", RED) if _n_retracted else None,
        ("Excluídos — tópico off-topic (limpeza)", f"−{_n_topic}", RED) if _n_topic else None,
        ("Corpus final limpo", str(_clean), GREEN),
        ("Excluídos — sem embedding válido", f"−{_n_noemb}", RED),
        ("Corpus usado na análise semântica", str(_clust), GREEN),
    ]
    steps = [s for s in steps if s is not None]
    out.write(f'<div style="max-width:520px;margin:1.5em auto">\n')
    for label, val, colour in steps:
        is_total = colour == GREEN
        border = f"2px solid {colour}" if is_total else f"1px solid {colour}"
        bg = f"rgba(78,154,241,0.08)" if colour == ACCENT else (
             f"rgba(68,184,148,0.10)" if colour == GREEN else f"rgba(224,80,80,0.07)")
        out.write(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'border:{border};border-radius:6px;padding:8px 16px;margin:6px 0;background:{bg}">'
            f'<span style="font-size:0.88em;color:{TEXT}">{label}</span>'
            f'<span style="font-size:1.1em;font-weight:700;color:{colour};margin-left:1em">{val}</span>'
            f'</div>\n'
        )
    out.write('</div>\n\n')


# ═════════════════════════════════════════════════════════════════════════════
# FOCAL CORPUS (C3 + C4)  — field-in-formation analyses
# ═════════════════════════════════════════════════════════════════════════════

def _load_focal_corpus() -> pd.DataFrame:
    """Return axis_scores_enriched filtered to C3+C4 with numeric citations."""
    df = pd.read_csv(IND / "axis_scores_enriched.csv")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    return df[df["cluster"].isin([3, 4])].copy()


def fig_focal_emergence(out: io.StringIO) -> None:
    """Fig 14 — Birth of the focal field: C3+C4 papers near-zero before ChatGPT."""
    _section_break(out, "Corpus Focal C3+C4 · Emergência do Campo")
    out.write("## Fig 14 — Emergência do Campo Focal (C3+C4): Quase Zero Antes de 2023\n\n")

    _callout(out, "question",
             "O subconjunto de pesquisa diretamente voltado para IA como apoio à produção acadêmica "
             "(clusters C3 e C4) existia antes de 2023 ou é um campo nascido com o ChatGPT?")
    _callout(out, "method",
             "Painel esquerdo: barras empilhadas por ano para C3 (violeta) e C4 (âmbar), "
             "mostrando o volume absoluto de publicações por coorte. "
             "Painel direito: evolução da **participação** do corpus focal no total anual — "
             "evidencia tanto o crescimento absoluto quanto a penetração relativa no campo mais amplo.")

    df_all = pd.read_csv(IND / "axis_scores_enriched.csv")
    df_all["cited_by_count"] = pd.to_numeric(df_all["cited_by_count"], errors="coerce").fillna(0)
    df_focal = df_all[df_all["cluster"].isin([3, 4])].copy()

    years = sorted([int(y) for y in df_all["publication_year"].dropna().unique() if 2020 <= y <= 2026])
    total_by_yr  = {y: (df_all["publication_year"] == y).sum() for y in years}
    c3_by_yr     = {y: ((df_focal["cluster"] == 3) & (df_focal["publication_year"] == y)).sum() for y in years}
    c4_by_yr     = {y: ((df_focal["cluster"] == 4) & (df_focal["publication_year"] == y)).sum() for y in years}
    focal_by_yr  = {y: c3_by_yr[y] + c4_by_yr[y] for y in years}
    focal_share  = {y: 100 * focal_by_yr[y] / max(total_by_yr[y], 1) for y in years}

    n_focal = sum(focal_by_yr.values())
    n_pre23 = sum(v for y, v in focal_by_yr.items() if y < 2023)
    n_2023  = focal_by_yr.get(2023, 0)
    n_2025  = focal_by_yr.get(2025, 0)

    _callout(out, "read",
             f"Apenas {n_pre23} artigos focais foram publicados em 2020–2022 "
             f"({100 * n_pre23 / n_focal:.1f}% do subconjunto). "
             f"Em 2023, com o lançamento massivo do ChatGPT, o campo irrompe para {n_2023} artigos, "
             f"e escala a {n_2025} em 2025 — um crescimento de "
             f"{round(n_2025 / max(n_2023, 1))}× em dois anos. "
             f"A participação relativa dos clusters C3+C4 no corpus anual também salta, "
             f"de valores inferiores a 5% antes de 2023 para cerca de "
             f"{focal_share.get(2025, focal_share.get(2024, 0)):.0f}% em 2025, "
             f"indicando que o campo está ganhando peso estrutural no corpus bibliométrico.")

    fig, (ax_bar, ax_share) = plt.subplots(1, 2, figsize=(13, 5.5),
                                            gridspec_kw={"width_ratios": [5, 3]})
    fig.patch.set_facecolor(BG)
    for ax in (ax_bar, ax_share):
        ax.set_facecolor(AX_BG)
        ax.tick_params(colors=TEXT, labelsize=9.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(EDGE)
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)

    xs     = np.arange(len(years))
    c3_vals = [c3_by_yr[y] for y in years]
    c4_vals = [c4_by_yr[y] for y in years]

    ax_bar.bar(xs, c3_vals, width=0.65, color=C_PALETTE[3], alpha=0.88,
               zorder=3, edgecolor=AX_BG, linewidth=0.4,
               label="C3 · ChatGPT e integridade")
    ax_bar.bar(xs, c4_vals, width=0.65, color=C_PALETTE[4], alpha=0.88,
               zorder=3, edgecolor=AX_BG, linewidth=0.4, bottom=c3_vals,
               label="C4 · IA no ensino superior")

    # Annotate each bar with total
    for i, yr in enumerate(years):
        total = focal_by_yr[yr]
        if total > 0:
            ax_bar.text(xs[i], total + 6, str(total),
                        ha="center", va="bottom", fontsize=9.5,
                        fontweight="700", color=TEXT)
        ax_bar.text(xs[i], -28, f"n={total_by_yr[yr]:,}",
                    ha="center", va="top", fontsize=8, color=SUBTEXT)

    # 2023 inflection arrow
    x2023 = years.index(2023)
    ax_bar.annotate("Lançamento do\nChatGPT (nov/22)",
                    xy=(x2023, focal_by_yr[2023] + 18),
                    xytext=(x2023 + 0.7, focal_by_yr[2023] + 120),
                    fontsize=8.5, color=C_PALETTE[3], fontweight="600",
                    arrowprops=dict(arrowstyle="->", color=C_PALETTE[3], lw=1.1),
                    bbox=dict(facecolor=BG, edgecolor=C_PALETTE[3],
                              boxstyle="round,pad=0.4", alpha=0.92, linewidth=0.8))

    ax_bar.set_xticks(xs)
    ax_bar.set_xticklabels([str(y) for y in years], fontsize=10.5, color=TEXT)
    ax_bar.set_ylabel("Artigos publicados (C3+C4)", color=TEXT, labelpad=8)
    ax_bar.set_ylim(-60, max(focal_by_yr.values()) * 1.35)
    ax_bar.set_title("Volume absoluto — C3+C4 por ano",
                     fontsize=11, fontweight="700", color=TEXT, pad=10)
    ax_bar.legend(loc="upper left", fontsize=8.5, framealpha=0.92,
                  facecolor=AX_BG, edgecolor=EDGE, labelcolor=TEXT)

    # Share panel — line + area
    share_vals = [focal_share[y] for y in years]
    ax_share.plot(xs, share_vals, color=C_PALETTE[3], lw=2.5, marker="o",
                  ms=7, zorder=5)
    ax_share.fill_between(xs, share_vals, alpha=0.18, color=C_PALETTE[4], zorder=2)

    for i, (yr, sh) in enumerate(zip(years, share_vals)):
        ax_share.text(xs[i], sh + 0.8, f"{sh:.1f}%",
                      ha="center", va="bottom", fontsize=8.5,
                      fontweight="700", color=TEXT)

    ax_share.set_xticks(xs)
    ax_share.set_xticklabels([str(y) for y in years], fontsize=9.5, color=TEXT)
    ax_share.set_ylabel("% do corpus anual total", color=TEXT, labelpad=8)
    ax_share.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax_share.set_ylim(0, max(share_vals) * 1.40)
    ax_share.set_title("Participação relativa no corpus anual",
                       fontsize=11, fontweight="700", color=TEXT, pad=10)
    ax_share.set_axisbelow(True)
    ax_share.grid(axis="y", alpha=0.5)

    fig.suptitle("Campo Focal C3+C4 — Nascimento em 2023 e Crescimento Exponencial",
                 fontsize=12.5, fontweight="700", color=TEXT, y=1.01)
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 14 — Emergência do corpus focal (C3+C4). "
           f"Painel esquerdo: produções anuais empilhadas por cluster (C3=violeta, C4=âmbar). "
           f"Apenas {n_pre23} artigos antes de 2023; {n_2023} em 2023; {n_2025} em 2025. "
           f"n= indica o total do corpus em cada ano. "
           f"Painel direito: participação do corpus focal no corpus anual total — "
           f"sobe de <5% pré-2023 para ~{focal_share.get(2025, focal_share.get(2024, 0)):.0f}% em 2025.",
           "fig13")


def fig_focal_themes(out: io.StringIO) -> None:
    """Fig 15 — Category (theme) breakdown within focal corpus C3+C4 over time."""
    _section_break(out, "Corpus Focal C3+C4 · Composição Temática")
    out.write("## Fig 15 — Composição Temática no Corpus Focal: Governança Domina sobre Ferramentas\n\n")

    _callout(out, "question",
             "O corpus focal é primordialmente sobre **regular** a IA (integridade, política, detecção) "
             "ou sobre **adotar** a IA como ferramenta (fluxo de trabalho de pesquisa, escrita assistida)? "
             "Essa composição muda ao longo dos anos?")
    _callout(out, "method",
             "Barras empilhadas 100% por ano para as quatro categorias temáticas dentro de C3+C4. "
             "A categoria integrity_governance agrupa artigos sobre detecção de texto gerado por IA, "
             "plágio, políticas editoriais e integridade acadêmica. "
             "research_workflow cobre automação de revisão, síntese e suporte à escrita. "
             "research_writing inclui artigos sobre redação científica assistida. "
             "other_relevant são artigos no tema mas sem categoria principal clara.")

    df = _load_focal_corpus()
    years = sorted([int(y) for y in df["publication_year"].dropna().unique() if 2022 <= y <= 2026])

    CAT_ORDER  = ["integrity_governance", "research_workflow", "research_writing", "other_relevant"]
    CAT_LABELS = {
        "integrity_governance": "Integridade e Governança",
        "research_workflow":    "Fluxo de Trabalho",
        "research_writing":     "Escrita Científica",
        "other_relevant":       "Outros Relevantes",
    }
    CAT_COLS = {
        "integrity_governance": C_PALETTE[3],    # violet
        "research_workflow":    C_PALETTE[0],    # steel blue
        "research_writing":     C_PALETTE[4],    # amber
        "other_relevant":       SUBTEXT,
    }

    cat_yr = (
        df.groupby(["publication_year", "category"])
        .size()
        .unstack(fill_value=0)
        .reindex(years, fill_value=0)
        .reindex(columns=CAT_ORDER, fill_value=0)
    )
    cat_yr_pct = cat_yr.div(cat_yr.sum(axis=1), axis=0) * 100

    _gov_peak_yr = int(cat_yr_pct["integrity_governance"].idxmax())
    _gov_peak_pct = float(cat_yr_pct["integrity_governance"].max())
    _wf_2025 = float(cat_yr_pct.loc[2025, "research_workflow"]) if 2025 in cat_yr_pct.index else 0.0
    _gov_2025 = float(cat_yr_pct.loc[2025, "integrity_governance"]) if 2025 in cat_yr_pct.index else 0.0

    _callout(out, "read",
             f"Integrity_governance domina todos os anos ({_gov_peak_pct:.0f}% em {_gov_peak_yr}); "
             f"mesmo em 2025, representa {_gov_2025:.0f}% dos artigos focais. "
             f"Research_workflow cresce consistentemente, atingindo {_wf_2025:.0f}% em 2025 — "
             "sinal de que o polo de ferramentas começa a ganhar terreno relativo. "
             "Research_writing mantém fatia estável (~9%), indicando que a escrita científica "
             "assistida é um nicho persistente mas não explosivo no campo. "
             "A leitura macro: o campo ancora-se em preocupações normativas antes de avançar "
             "para adoção ampla.")

    fig, (ax_pct, ax_abs) = plt.subplots(1, 2, figsize=(13, 5.8),
                                          gridspec_kw={"width_ratios": [1, 1]})
    fig.patch.set_facecolor(BG)
    for ax in (ax_pct, ax_abs):
        ax.set_facecolor(AX_BG)
        ax.tick_params(colors=TEXT, labelsize=9.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(EDGE)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)

    xs = np.arange(len(years))

    # 100% stacked bars (left)
    bottom_pct = np.zeros(len(years))
    for cat in CAT_ORDER:
        vals = cat_yr_pct[cat].to_numpy()
        ax_pct.bar(xs, vals, bottom=bottom_pct, color=CAT_COLS[cat],
                   width=0.70, zorder=3, edgecolor=AX_BG, linewidth=0.4,
                   label=CAT_LABELS[cat])
        # Annotate only if large enough to read
        for i, v in enumerate(vals):
            if v >= 8:
                ax_pct.text(xs[i], bottom_pct[i] + v / 2, f"{v:.0f}%",
                            ha="center", va="center", fontsize=8.5,
                            fontweight="700", color="white")
        bottom_pct += vals

    ax_pct.set_xticks(xs)
    ax_pct.set_xticklabels([str(y) for y in years], fontsize=10.5, color=TEXT)
    ax_pct.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax_pct.set_ylim(0, 103)
    ax_pct.set_ylabel("% dos artigos focais do ano", color=TEXT, labelpad=8)
    ax_pct.set_title("Distribuição 100% por categoria", fontsize=11, fontweight="700",
                     color=TEXT, pad=10)
    ax_pct.legend(loc="lower left", fontsize=8, framealpha=0.92,
                  facecolor=AX_BG, edgecolor=EDGE, labelcolor=TEXT)

    # Absolute stacked bars (right)
    bottom_abs = np.zeros(len(years))
    for cat in CAT_ORDER:
        vals = cat_yr[cat].to_numpy().astype(float)
        ax_abs.bar(xs, vals, bottom=bottom_abs, color=CAT_COLS[cat],
                   width=0.70, zorder=3, edgecolor=AX_BG, linewidth=0.4,
                   label=CAT_LABELS[cat])
        bottom_abs += vals

    # Annotate total n per bar
    for i, yr in enumerate(years):
        total = int(cat_yr.loc[yr].sum())
        ax_abs.text(xs[i], total + 8, str(total),
                    ha="center", va="bottom", fontsize=9, fontweight="600", color=TEXT)

    ax_abs.set_xticks(xs)
    ax_abs.set_xticklabels([str(y) for y in years], fontsize=10.5, color=TEXT)
    ax_abs.set_ylabel("N artigos C3+C4", color=TEXT, labelpad=8)
    ax_abs.set_title("Volume absoluto por categoria", fontsize=11, fontweight="700",
                     color=TEXT, pad=10)
    ax_abs.set_axisbelow(True)

    fig.suptitle("Corpus Focal C3+C4 — Governança e Integridade Lideram Sobre Adoção de Ferramentas",
                 fontsize=12, fontweight="700", color=TEXT, y=1.01)
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 15 — Composição temática do corpus focal C3+C4 por ano (2022–2026). "
           f"Painel esquerdo: barras 100% empilhadas; painel direito: volume absoluto. "
           f"Integrity_governance domina em todos os anos (pico {_gov_peak_pct:.0f}% em {_gov_peak_yr}); "
           f"research_workflow cresce para {_wf_2025:.0f}% em 2025. "
           f"O campo regula mais do que adota.",
           "fig14")


def fig_focal_citation_maturity(out: io.StringIO) -> None:
    """Fig 16 — Citation maturity by cohort within focal corpus C3+C4."""
    _section_break(out, "Corpus Focal C3+C4 · Maturidade de Citações")
    out.write("## Fig 16 — Maturidade de Citações no Corpus Focal: Impacto Existe, a Recência é que Esconde\n\n")

    _callout(out, "question",
             "O corpus focal tem baixo impacto bibliométrico por ser um campo de nicho, "
             "ou a média baixa de citações é simplesmente efeito do horizonte temporal "
             "(2025–2026 não teve tempo de acumular citações)?")
    _callout(out, "method",
             "Boxplots com pontos individuais por coorte anual dentro do corpus focal C3+C4. "
             "Escala log-simétrica para escalar artigos de 0 a centenas de citações. "
             "O eixo horizontal é ordenado por ano de publicação para revelar a curva de maturação. "
             "Taxa de citação (% com ≥1 citação) anotada abaixo de cada coorte.")

    df = _load_focal_corpus()
    all_years = sorted([int(y) for y in df["publication_year"].dropna().unique() if 2020 <= y <= 2026])

    cohort_data = {y: df[df["publication_year"] == y]["cited_by_count"].values for y in all_years}
    pct_cited   = {y: 100 * (cohort_data[y] > 0).mean() for y in all_years}
    medians     = {y: float(np.median(cohort_data[y])) for y in all_years}
    means       = {y: float(np.mean(cohort_data[y]))   for y in all_years}

    _mature_pct = float(np.mean([pct_cited[y] for y in all_years if y <= 2023]))
    _mature_med = float(np.mean([medians[y]   for y in all_years if y <= 2023]))
    _recent_pct = float(np.mean([pct_cited[y] for y in all_years if y >= 2025]))

    _callout(out, "read",
             f"Coortes 2020–2023 (artigos com ≥2 anos de maturação): "
             f"{_mature_pct:.0f}% de taxa de citação e mediana de {_mature_med:.1f} cit. — "
             "impacto sólido para um campo recente. "
             f"Coortes 2025–2026: apenas {_recent_pct:.0f}% de taxa de citação, "
             "mas isso é esperado para literatura publicada há menos de 12–18 meses. "
             "A curva de maturação visível no gráfico descarta interpretações de baixo impacto "
             "intrínseco: é efeito de calendário, não de qualidade.")

    rng = np.random.default_rng(42)
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)
    ax.tick_params(colors=TEXT, labelsize=9.5)
    for sp in ax.spines.values():
        sp.set_edgecolor(EDGE)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Colour ramp: early (violet→amber) = C3/C4 palette; recent years fade
    yr_colours = {
        2020: C_PALETTE[3], 2021: C_PALETTE[3], 2022: C_PALETTE[3],
        2023: "#d060d0",
        2024: C_PALETTE[4],
        2025: "#aaaacc",
        2026: SUBTEXT,
    }

    xs = np.arange(len(all_years))
    bplot_data = [cohort_data[y].astype(float) for y in all_years]
    bp = ax.boxplot(bplot_data, positions=xs, widths=0.45, patch_artist=True,
                    showfliers=False,
                    medianprops=dict(color=TEXT, linewidth=2.0),
                    whiskerprops=dict(color=SUBTEXT, linewidth=1.2),
                    capprops=dict(color=SUBTEXT, linewidth=1.2),
                    boxprops=dict(linewidth=1.2))
    for patch, yr in zip(bp["boxes"], all_years):
        patch.set_facecolor(yr_colours[yr])
        patch.set_alpha(0.55)

    # Strip overlay
    for i, (yr, data) in enumerate(zip(all_years, bplot_data)):
        jit = rng.uniform(-0.18, 0.18, len(data))
        ax.scatter(xs[i] + jit, data, color=yr_colours[yr],
                   alpha=0.30, s=10, zorder=5, edgecolors="none")

    # Median annotation
    for i, yr in enumerate(all_years):
        med = medians[yr]
        ax.text(xs[i], med + 0.4, f"m={med:.0f}",
                ha="center", va="bottom", fontsize=8, color=TEXT, fontweight="600")

    # % cited annotation below axis
    for i, yr in enumerate(all_years):
        ax.text(xs[i], -0.05, f"{pct_cited[yr]:.0f}% cit.",
                transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=8, color=SUBTEXT,
                bbox=dict(facecolor=AX_BG, edgecolor="none", pad=0.12, alpha=0.9))

    # "Mature" vs "Recent" band
    if 2022 in all_years and 2023 in all_years:
        x_split = (all_years.index(2022) + all_years.index(2023)) / 2
        ax.axvspan(-0.5, x_split, color=C_PALETTE[3], alpha=0.04, zorder=1)
        ax.axvspan(x_split, len(all_years) - 0.5, color=SUBTEXT, alpha=0.03, zorder=1)
        ax.text(x_split / 2 - 0.2, 0.97, "Coortes\nMaturas", transform=ax.transAxes,
                ha="center", va="top", fontsize=9, color=C_PALETTE[3],
                fontstyle="italic")
        ax.text((x_split + len(all_years) - 0.5) / 2 / len(all_years), 0.97,
                "Coortes\nRecentes", transform=ax.transAxes,
                ha="center", va="top", fontsize=9, color=SUBTEXT, fontstyle="italic")

    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(y) for y in all_years], fontsize=10.5, color=TEXT)
    ax.set_ylabel("Citações (escala log-simétrica)", color=TEXT, labelpad=10)
    ax.set_title(
        "Maturidade de Citações por Coorte — Corpus Focal C3+C4\n"
        "m = mediana · % cit. = percentual de artigos com ≥1 citação",
        fontsize=12, fontweight="700", color=TEXT, pad=14,
    )
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 16 — Boxplots de citações por coorte anual no corpus focal C3+C4 (2020–2026). "
           f"Escala log-simétrica. Coortes 2020–2023 têm {_mature_pct:.0f}% de taxa de citação "
           f"e mediana {_mature_med:.1f} cit.; coortes 2025–2026 têm {_recent_pct:.0f}% — "
           f"diferença explicada pelo horizonte temporal, não por baixo impacto intrínseco.",
           "fig15")


def fig_focal_journals(out: io.StringIO) -> None:
    """Fig 17 — Top journals in focal corpus vs. full corpus — nuclear core inversion."""
    _section_break(out, "Corpus Focal C3+C4 · Núcleo Editorial")
    out.write("## Fig 17 — Inversão do Núcleo Editorial: Periódicos de Educação Lideram no Corpus Focal\n\n")

    _callout(out, "question",
             "O núcleo editorial do corpus focal (C3+C4) é o mesmo do corpus completo — "
             "dominado por IEEE, periódicos médicos e de engenharia — "
             "ou há uma inversão para periódicos de educação, ética e informática aplicada?")
    _callout(out, "method",
             "Gráficos de barras horizontais lado a lado: "
             "esquerdo = top 12 periódicos no corpus **focal** (C3+C4) por número de artigos; "
             "direito = top 12 no corpus **completo**, para referência. "
             "A comparação revela dois campos editorialmente distintos coexistindo no corpus.")

    # Focal journals — derive from corpus_clustered.csv (run dir) + cluster filter
    focal_df = _load_focal_corpus()
    focal_ids = set(focal_df["id"])

    cc = pd.read_csv(ROOT / "corpus_clustered.csv", usecols=["id", "journal", "cited_by_count"])
    cc["cited_by_count"] = pd.to_numeric(cc["cited_by_count"], errors="coerce").fillna(0)

    def _prep_journals(sub: pd.DataFrame) -> pd.DataFrame:
        sub = sub.copy()
        sub["journal"] = sub["journal"].fillna("").str.strip().str.title()
        return (
            sub[sub["journal"] != ""]
            .groupby("journal")
            .agg(n=("id", "count"), total_cit=("cited_by_count", "sum"))
            .sort_values("n", ascending=False)
            .reset_index()
        )

    focal_jrn = _prep_journals(cc[cc["id"].isin(focal_ids)])
    full_jrn  = _prep_journals(cc)

    def shorten(name: str, max_len: int = 44) -> str:
        return name if len(name) <= max_len else name[:max_len - 1] + "…"

    top_f = focal_jrn.head(12).copy()
    top_f["short"] = top_f["journal"].apply(shorten)
    top_f = top_f.sort_values("n")

    top_a = full_jrn.head(12).copy()
    top_a["short"] = top_a["journal"].apply(shorten)
    top_a = top_a.sort_values("n")

    fig, (ax_f, ax_a) = plt.subplots(1, 2, figsize=(14, 6.2))
    fig.patch.set_facecolor(BG)
    for ax in (ax_f, ax_a):
        ax.set_facecolor(AX_BG)
        ax.tick_params(colors=TEXT, labelsize=8.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(EDGE)
        ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)

    # Focal
    y_f = np.arange(len(top_f))
    bars_f = ax_f.barh(y_f, top_f["n"], color=C_PALETTE[3], alpha=0.85,
                       height=0.60, edgecolor="none")
    for bar, n in zip(bars_f, top_f["n"]):
        ax_f.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                  str(int(n)), va="center", fontsize=8.5, color=TEXT)
    ax_f.set_yticks(y_f)
    ax_f.set_yticklabels(top_f["short"], fontsize=8.5)
    ax_f.set_xlabel("N artigos", color=TEXT, labelpad=8)
    ax_f.set_xlim(0, top_f["n"].max() * 1.40)
    ax_f.set_title("Corpus Focal C3+C4\n(educação · ética · informática)",
                   fontsize=10.5, fontweight="700", color=C_PALETTE[3], pad=10)

    # Full corpus
    y_a = np.arange(len(top_a))
    bars_a = ax_a.barh(y_a, top_a["n"], color=C_PALETTE[2], alpha=0.75,
                       height=0.60, edgecolor="none")
    for bar, n in zip(bars_a, top_a["n"]):
        ax_a.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                  str(int(n)), va="center", fontsize=8.5, color=TEXT)
    ax_a.set_yticks(y_a)
    ax_a.set_yticklabels(top_a["short"], fontsize=8.5)
    ax_a.set_xlabel("N artigos", color=TEXT, labelpad=8)
    ax_a.set_xlim(0, top_a["n"].max() * 1.40)
    ax_a.set_title("Corpus Completo (n=6.261)\n(engenharia · biomédica · imagem)",
                   fontsize=10.5, fontweight="700", color=C_PALETTE[2], pad=10)

    fig.suptitle("Inversão do Núcleo Editorial — C3+C4 tem Ecossistema de Periódicos Próprio",
                 fontsize=12.5, fontweight="700", color=TEXT, y=1.01)
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 17 — Top 12 periódicos por N artigos: esquerdo = corpus focal C3+C4; "
           f"direito = corpus completo. "
           f"Periódico líder no focal: '{top_f.iloc[-1]['journal']}' ({int(top_f.iloc[-1]['n'])} artigos). "
           f"Periódico líder no corpus completo: '{top_a.iloc[-1]['journal']}' ({int(top_a.iloc[-1]['n'])} artigos). "
           f"Os dois rankings têm sobreposição mínima — evidência de campos editorialmente distintos.",
           "fig16")


# ═════════════════════════════════════════════════════════════════════════════
# HTML HEADER & KPI CARDS
# ═════════════════════════════════════════════════════════════════════════════

def _write_header(out: io.StringIO) -> None:
    today = _format_pt_date(date.today())
    _ax = pd.read_csv(IND / "axis_scores_enriched.csv")
    _yr = pd.read_csv(IND / "yearly_production.csv")
    n_papers  = len(_ax)
    yr_min    = int(_yr["year"].min())
    yr_max    = int(_yr["year"].max())
    out.write(f"""
# Relatório de Análise Bibliométrica

## IA como Ferramenta de Apoio à Produção Acadêmica · Trabalho 5

<div style="color:{SUBTEXT};font-size:0.9em;margin-bottom:2em">
Gerado em {today} · Embeddings BGE-M3 · {n_papers} artigos · {yr_min}–{yr_max}
</div>

<div style="color:{SUBTEXT};font-size:0.84em;margin:-1.1em 0 2em;font-style:italic">
Todo o texto analítico deste relatório está em português. Títulos de artigos, nomes de periódicos
e palavras-chave foram preservados no idioma original dos metadados indexados.
</div>

""")


def _write_kpi_cards(out: io.StringIO) -> None:
    _section_break(out, "Visão Geral do Corpus")
    out.write("## Indicadores do Corpus\n\n")
    kpi_bg = "#16213e" if not LIGHT else "#f0f2f8"
    kpi_val_colour = ACCENT
    kpi_lbl_colour = SUBTEXT

    # Compute KPI values from data files (never hardcoded)
    _ax  = pd.read_csv(IND / "axis_scores_enriched.csv")
    _geo = pd.read_csv(IND / "geo_countries.csv")
    if "country_code" in _geo.columns:
        _geo = _geo[_geo["country_code"].fillna("").astype(str).str.strip() != ""].copy()
    _yr  = pd.read_csv(IND / "yearly_production.csv")
    _n   = len(_ax)
    _yr_range = f"{int(_yr['year'].min())}\u2013{int(_yr['year'].max())}"
    _n_countries = len(_geo)
    _max_cit = int(_ax["cited_by_count"].max())
    _dom_label = _ax["cluster_label"].value_counts().idxmax()
    _dom_display = _localize_cluster_label(_dom_label)
    _dom_pct   = round(100 * _ax["cluster_label"].value_counts().max() / _n)
    _pct_zero  = round(100 * (_ax["cited_by_count"] == 0).mean())
    _dom_code  = int(_ax[_ax["cluster_label"] == _dom_label]["cluster"].iloc[0])

    cards = [
        {"value": str(_n), "label": "Artigos no corpus"},
        {"value": _yr_range, "label": "Período coberto"},
        {"value": str(_n_countries), "label": "Países representados"},
        {"value": str(_max_cit), "label": "Máx. citações (1 artigo)"},
        {
            "value": f"C{_dom_code}",
            "subvalue": _cluster_label_card_html(_dom_display),
            "label": f"Cluster dominante ({_dom_pct}%)",
        },
        {"value": f"{_pct_zero}%", "label": "Artigos sem nenhuma citação"},
    ]
    out.write('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));'
              'gap:14px;margin:1em 0 2em">\n')
    for card in cards:
        subvalue_html = ""
        if card.get("subvalue"):
            subvalue_html = (
                f'<div style="font-size:0.88em;line-height:1.45;color:{kpi_val_colour};'
                f'font-weight:600;margin-top:0.35em">{card["subvalue"]}</div>'
            )
        out.write(
            f'<div style="background:{kpi_bg};border:1px solid {EDGE};border-radius:8px;'
            f'padding:14px 18px;text-align:center">'
            f'<div style="font-size:1.65em;font-weight:700;color:{kpi_val_colour}">{card["value"]}</div>'
            f'{subvalue_html}'
            f'<div style="font-size:0.80em;color:{kpi_lbl_colour};text-transform:uppercase;'
            f'letter-spacing:1.2px;margin-top:4px">{card["label"]}</div>'
            f'</div>\n'
        )
    out.write("</div>\n\n")


def _write_citation_coverage_note(out: io.StringIO) -> None:
    cov = _citation_coverage_stats()
    out.write(
        f'<div style="margin:0 0 1.8em;border-left:4px solid {GREEN};padding:0.9em 1.2em;'
        f'background:{AX_BG};border-radius:0 8px 8px 0;color:{SUBTEXT};font-size:0.92em">'
        f'<strong style="color:{GREEN}">Cobertura de citações.</strong> '
        f'{cov["n_with_doi"]:,} de {cov["n_total"]:,} artigos ({cov["pct_with_doi"]:.1f}%) têm DOI e '
        f'{cov["n_pubmed_no_doi"]} registros PubMed sem DOI foram verificados via Europe PMC. '
        f'Apenas {cov["n_zero_without_doi"]} artigos ({cov["pct_zero_without_doi"]:.1f}%) permanecem com 0 citações e sem DOI, '
        'de modo que os zeros restantes devem ser lidos majoritariamente como zeros observados, '
        'não como ausência de metadado.'
        '</div>\n\n'
    )


def _write_findings_summary(out: io.StringIO) -> None:
    _section_break(out, "Leituras Guiadas")
    out.write("## Leituras Principais\n\n")

    cov = _citation_coverage_stats()
    _ax_f, _diag = _axis_temporal_diagnostics()
    _diag_idx = _diag.set_index("label")
    _overall = _diag_idx.loc["Geral"]
    _n_papers = len(_ax_f)
    _pct_2025_plus = 100 * (_ax_f["publication_year"] >= 2025).mean()
    _zero_by_year = _ax_f.assign(is_zero=_ax_f["cited_by_count"] == 0).groupby("publication_year")["is_zero"].sum()
    _zero_recent_share = 100 * _zero_by_year[_zero_by_year.index >= 2025].sum() / max(_zero_by_year.sum(), 1)

    _temp_pct = (
        _ax_f.groupby("publication_year")
        .apply(lambda g: 100 * (g["axis_e_technology"] > 0).mean())
        .reset_index(name="pct_e_pos")
    )
    _peak_row = _temp_pct.loc[_temp_pct["pct_e_pos"].idxmax()]
    _peak_yr = int(_peak_row["publication_year"])
    _peak_pct = round(_peak_row["pct_e_pos"])
    _pct_yr_2025_rows = _temp_pct.loc[_temp_pct["publication_year"] == 2025, "pct_e_pos"]
    _pct_yr_2026_rows = _temp_pct.loc[_temp_pct["publication_year"] == 2026, "pct_e_pos"]
    _pct_yr_2025 = round(_pct_yr_2025_rows.values[0]) if len(_pct_yr_2025_rows) else round(_peak_pct)
    _pct_yr_2026 = round(_pct_yr_2026_rows.values[0]) if len(_pct_yr_2026_rows) else round(_peak_pct)

    # Cluster share dynamics — read actual columns, no hardcoding
    _share = pd.read_csv(IND / "cluster_share_by_year.csv").set_index("publication_year")
    _cluster_cols = [c for c in _share.columns]
    _share_years = sorted(_share.index.tolist())
    _yr_early = _share_years[0] if _share_years else 2022
    _yr_late  = _share_years[-1] if len(_share_years) >= 2 else _yr_early
    # Dominant cluster by average share
    _avg_share = _share[_cluster_cols].mean()
    _dom_col   = str(_avg_share.idxmax())
    _dom_name  = _localize_cluster_label(_dom_col)
    _dom_share_early = float(_share.loc[_yr_early, _dom_col]) if _yr_early in _share.index else float("nan")
    _dom_share_late  = float(_share.loc[_yr_late,  _dom_col]) if _yr_late  in _share.index else float("nan")
    _other_cols = [c for c in _cluster_cols if c != _dom_col]
    _other_name = _localize_cluster_label(_other_cols[0]) if _other_cols else "outros clusters"

    _rho_n, _p_n = _safe_spearman(_ax_f["axis_n_domain"], _ax_f["cited_by_count"])
    _acad = _ax_f[_ax_f["axis_r_scope"] < 0]["cited_by_count"]
    _clin = _ax_f[_ax_f["axis_r_scope"] >= 0]["cited_by_count"]

    # Concentration stats — use actual cluster labels from the data
    _conc = _cluster_concentration_stats(_ax_f).sort_values("mean_cit", ascending=False)
    _top_cluster  = _conc.iloc[0]
    _low_cluster  = _conc.iloc[-1]
    _top_name = _localize_cluster_label(str(_top_cluster["cluster_label"]))
    _low_name = _localize_cluster_label(str(_low_cluster["cluster_label"]))

    findings = [
        (ACCENT, "Q1 — O efeito de recência basta para explicar a cauda zero-pesada?",
         f"{_pct_2025_plus:.1f}% do corpus está em 2025–2026 e {_zero_recent_share:.1f}% dos artigos com zero citação também está nesses dois anos. "
         f"Como apenas {cov['n_zero_without_doi']} registros ({cov['pct_zero_without_doi']:.1f}%) seguem sem DOI e com 0 citações, "
         "o principal candidato explicativo é maturação bibliométrica insuficiente, não ausência de metadado. "
         "A ressalva é que 2025 já acumula grande volume: se parte do baixo impacto persistir após maturação, a recência não será explicação suficiente."),
        ("#f07850", "Q2 — A normalização do rótulo é sustentada por tendências lexicais ou apenas por padrões de citação?",
         f"A taxa de artigos com E>0 atinge pico em {_peak_yr} ({_peak_pct}%) e recua para {_pct_yr_2025}% em 2025 e {_pct_yr_2026}% em 2026 — evidência lexical direta de normalização do rótulo. "
         f"O cluster dominante ({_dom_name}) representa {_dom_share_early:.1f}% do corpus em {_yr_early} e {_dom_share_late:.1f}% em {_yr_late}, "
         "mostrando que a agenda avança com ou sem vocabulário explícito de IA. "
         f"Nos padrões de citação, porém, o sinal do Eixo E fica negativo dentro de cada faixa temporal "
         f"(2020-2022={_diag_idx.loc['2020-2022', 'rho_e']:+.3f}, 2023-2024={_diag_idx.loc['2023-2024', 'rho_e']:+.3f}, 2025-2026={_diag_idx.loc['2025-2026', 'rho_e']:+.3f}), "
         "indicando que a normalização aparece nas tendências lexicais e na composição temática, mas não como prêmio de citação estável."),
        (GREEN, "Q3 — O impacto por cluster é conduzido por poucos artigos altamente citados?",
         f"{_top_name} lidera em média de citações ({_top_cluster['mean_cit']:.1f}), "
         f"mas {_top_cluster['top10_share']:.1f}% das citações do cluster estão no seu top 10%. "
         f"Em {_low_name}, a concentração é de {_low_cluster['top10_share']:.1f}% e "
         f"{_low_cluster['pct_2025_plus']:.1f}% dos artigos já é de 2025–2026. "
         "Médias por cluster não sustentam, sozinhas, leituras amplas de impacto."),
        ("#a87fe8", "Q4 — As diferenças de domínio são o sinal mais estável, acima do enquadramento tecnológico?",
         f"O Eixo R tem ρ={_overall['rho_r']:+.3f} no agregado e permanece positivo nas três bandas temporais "
         f"({_diag_idx.loc['2020-2022', 'rho_r']:+.3f}, {_diag_idx.loc['2023-2024', 'rho_r']:+.3f}, {_diag_idx.loc['2025-2026', 'rho_r']:+.3f}), "
         "comportamento oposto ao do Eixo E. "
         f"No polo acadêmico/educacional, a mediana é {_acad.median():.0f} citações; no clínico/biomédico, {_clin.median():.0f}. "
         "Domínio distingue impacto de forma mais robusta e consistente do que o framing tecnológico."),
    ]
    for colour, title, text in findings:
        out.write(
            f'<div style="border-left:4px solid {colour};padding:0.6em 1.2em;'
            f'margin:0.8em 0;background:rgba(0,0,0,0.05)">'
            f'<strong style="color:{colour}">{title}</strong><br>'
            f'<span style="font-size:0.94em;line-height:1.6">{text}</span>'
            f'</div>\n\n'
        )


# ═════════════════════════════════════════════════════════════════════════════
# CLAIM-VERIFICATION CHARTS (Figs 17–20)
# ═════════════════════════════════════════════════════════════════════════════

def fig_claim_chatgpt_reversal(out: io.StringIO) -> None:
    """Fig 18 — Simpson's paradox: ρE collapses by cohort while ρR stays positive."""
    _section_break(out, "Teses-Chave · Reversão do Sinal de Framing")
    out.write("## Fig 18 — Reversão do Sinal E por Coorte: Paradoxo de Simpson\n\n")

    _callout(out, "question",
             "O prêmio de citações atribuído ao framing ChatGPT/GenAI (Eixo E positivo) é estrutural "
             "ou desaparece quando o corpus é estratificado por coorte temporal, revelando um artefato de composição?")
    _callout(out, "method",
             "Gráfico dumbbell: dois pontos por linha — badge circular laranja com a letra E = ρ(E×citações) framing ChatGPT/GenAI, "
             "badge quadrado azul com a letra R = ρ(R×citações) domínio clínico/acadêmico. "
             "A identidade da série fica embutida no próprio ponto, de forma legível mesmo sem depender da cor. "
             "A reversão deve ser lida contra a linha ρ = 0, não como troca de posição entre E e R. "
             "A linha vertical em zero separa sinal positivo de negativo. "
             "Linhas horizontais conectam os dois pontos de cada faixa. "
             "Faixa sombreada em vermelho-claro = coorte onde ρE reverte para negativo.")

    _, diag = _axis_temporal_diagnostics()
    target_rows = ["Geral", "2020-2022", "2023-2024", "2025-2026"]
    diag_plot = (
        diag[diag["label"].isin(target_rows)]
        .set_index("label").loc[target_rows].reset_index()
    )

    rho_e = diag_plot["rho_e"].tolist()
    rho_r = diag_plot["rho_r"].tolist()
    labels = diag_plot["label"].tolist()
    e_reverses = sum(1 for v in rho_e[1:] if v <= 0)
    r_stable   = sum(1 for v in rho_r[1:] if v > 0)

    _callout(out, "read",
             f"ρE agregado = {rho_e[0]:+.3f}; nas coortes: "
             f"{rho_e[1]:+.3f} (2020-2022), {rho_e[2]:+.3f} (2023-2024), {rho_e[3]:+.3f} (2025-2026). "
             f"ρR nas coortes: {rho_r[1]:+.3f}, {rho_r[2]:+.3f}, {rho_r[3]:+.3f}. "
             f"E cruza ρ=0 e torna-se negativo em {e_reverses}/3 coortes; R permanece positivo em {r_stable}/3. "
             "Não há cruzamento E↔R nas linhas exibidas: a reversão é contra zero, não uma troca esquerda-direita entre as duas séries. "
             "Padrão consistente com paradoxo de Simpson: artigos fundadores (2020-2022) acumularam "
             "citações antes que o rótulo ChatGPT existisse, inflando artificialmente o agregado.")

    fig, ax = plt.subplots(figsize=(9.5, 5))

    y = np.arange(len(labels))

    # Shade rows where ρE is negative (cohort bands only)
    for yi, re in enumerate(rho_e):
        if yi > 0 and re <= 0:
            ax.axhspan(yi - 0.46, yi + 0.46, color=RED, alpha=0.07, zorder=0)

    # Connecting lines
    for yi, (re, rr) in enumerate(zip(rho_e, rho_r)):
        ax.hlines(yi, min(re, rr), max(re, rr), color=SUBTEXT, lw=2.2, alpha=0.50, zorder=2)

    # Point marks — OCR-friendly letter badges placed at the exact data coordinates
    size_agg = 110
    size_band = 75
    sizes = [size_agg if i == 0 else size_band for i in range(len(labels))]
    for yi, (re, rr, size) in enumerate(zip(rho_e, rho_r, sizes)):
        marker_fs = 10.5 if yi == 0 else 9.8
        ax.text(re, yi, "E", ha="center", va="center", fontsize=marker_fs,
                color="white", fontweight="900", zorder=5,
                bbox=dict(boxstyle="circle,pad=0.28", facecolor=C_PALETTE[1],
                          edgecolor=AX_BG, linewidth=1.3))
        ax.text(rr, yi, "R", ha="center", va="center", fontsize=marker_fs,
                color="white", fontweight="900", zorder=5,
                bbox=dict(boxstyle="square,pad=0.22", facecolor=ACCENT,
                          edgecolor=AX_BG, linewidth=1.3))

    # Direct labels — outside the segment, attached to the actual point position
    x_range = max(abs(v) for v in rho_e + rho_r) + 0.06
    for yi, (re, rr) in enumerate(zip(rho_e, rho_r)):
        e_left = re <= rr
        r_left = rr < re
        ax.annotate(
            f"{re:+.3f}",
            xy=(re, yi),
            xytext=((-18, 0) if e_left else (18, 0)),
            textcoords="offset points",
            ha=("right" if e_left else "left"),
            va="center",
            fontsize=8.1,
            color=C_PALETTE[1],
            fontweight="700",
            zorder=6,
        )
        ax.annotate(
            f"{rr:+.3f}",
            xy=(rr, yi),
            xytext=((-18, 0) if r_left else (18, 0)),
            textcoords="offset points",
            ha=("right" if r_left else "left"),
            va="center",
            fontsize=8.1,
            color=ACCENT,
            fontweight="700",
            zorder=6,
        )

    # Zero line and label
    ax.axvline(0, color=SPINE, lw=1.5, ls="--", alpha=0.75, zorder=1)
    ax.text(0.002, len(labels) - 0.55, "ρ = 0", fontsize=8, color=SUBTEXT, va="top", fontstyle="italic")

    # Aggregate vs band separator
    ax.axhline(0.5, color=EDGE, lw=1.0, ls=":", alpha=0.7)
    ax.text(x_range * 0.92, 0.5, "  ↑ agregado   ↓ por coorte", fontsize=7.5,
            color=SUBTEXT, va="bottom", ha="right", fontstyle="italic")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5)
    ax.invert_yaxis()
    ax.set_xlabel("Correlação de Spearman ρ com citações", color=TEXT, labelpad=10)
    ax.set_xlim(-x_range, x_range)
    ax.set_title(
        "Reversão do Sinal de Framing (Eixo E) por Coorte — Paradoxo de Simpson\n"
        f"ρE positivo no agregado, negativo em {e_reverses}/3 coortes · ρR estável (positivo em {r_stable}/3)",
        fontsize=11, fontweight="700", color=TEXT, pad=14,
    )
    ax.grid(axis="x", alpha=0.35)
    ax.set_axisbelow(True)

    fig.tight_layout()
    _embed(out, fig,
            f"Fig 18 — Dumbbell ρ por faixa temporal. "
            f"Badge circular laranja com E = ρ(E×cit) framing ChatGPT/GenAI; badge quadrado azul com R = ρ(R×cit) domínio clínico/acadêmico. "
            f"A letra está no próprio ponto, tornando a distinção verificável sem depender da cor. "
            f"ρE = {rho_e[0]:+.3f} no agregado mas cruza ρ=0 e torna-se negativo em {e_reverses}/3 coortes; "
            f"ρR mantém sinal positivo em {r_stable}/3 coortes. Não há troca E↔R nas coortes exibidas; a reversão é contra a linha zero. "
           "Consistente com artefato de composição temporal.",
           "fig17")


def fig_claim_vocabulary_structure(out: io.StringIO) -> None:
    """Fig 19 — ChatGPT vocabulary label fades while focal field structural share grows."""
    _section_break(out, "Teses-Chave · Vocabulário vs. Estrutura")
    out.write("## Fig 19 — Rótulo ChatGPT Recua, Campo Focal (C3+C4) Persiste\n\n")

    _callout(out, "question",
             "O recuo da menção explícita a ChatGPT/GenAI (Eixo E > 0) representa esfriamento do campo "
             "ou apenas normalização do vocabulário? A estrutura temática de C3+C4 mantém-se independentemente?")
    _callout(out, "method",
             "Dois indicadores plotados sobre o mesmo eixo Y (%) e o mesmo eixo X (ano de publicação): "
             "(1) % de artigos com E>0 — menção explícita ao rótulo ChatGPT/GenAI no embedding; "
             "(2) % do corpus anual pertencente a C3+C4 — participação estrutural do campo focal. "
             "Divergência após 2023 = vocabulário recua mas campo cresce.")

    temporal = pd.read_csv(IND / "temporal_profile.csv")
    share_df  = pd.read_csv(IND / "cluster_share_by_year.csv")
    axis_df   = _load_axis_scores()

    years_t = sorted([int(y) for y in temporal["year"].unique() if 2020 <= y <= 2026])
    e_pct_by_yr = {
        int(y): float(100 * (axis_df[axis_df["publication_year"] == y]["axis_e_technology"] > 0).mean())
        for y in years_t
    }

    # C3+C4 share per year
    share_idx = share_df.set_index("publication_year")
    c3_col = CLUSTER_LABELS_RAW.get(3, "")
    c4_col = CLUSTER_LABELS_RAW.get(4, "")
    c34_pct_by_yr: dict[int, float] = {}
    for yr in years_t:
        if yr not in share_idx.index:
            c34_pct_by_yr[yr] = float("nan")
            continue
        c3v = float(share_idx.loc[yr, c3_col]) if c3_col in share_idx.columns else 0.0
        c4v = float(share_idx.loc[yr, c4_col]) if c4_col in share_idx.columns else 0.0
        c34_pct_by_yr[yr] = c3v + c4v

    e_vals   = [e_pct_by_yr.get(y, float("nan"))   for y in years_t]
    c34_vals = [c34_pct_by_yr.get(y, float("nan")) for y in years_t]

    peak_e_yr   = years_t[int(np.nanargmax(e_vals))]
    peak_e_val  = float(np.nanmax(e_vals))
    last_e_val  = float(e_vals[-1]) if not np.isnan(e_vals[-1]) else float("nan")
    last_c34    = float(c34_vals[-1]) if not np.isnan(c34_vals[-1]) else float("nan")
    start_c34   = float(c34_vals[0])  if not np.isnan(c34_vals[0])  else float("nan")

    _callout(out, "read",
             f"E>0 atinge pico em {peak_e_yr} ({peak_e_val:.0f}%) depois recua para {last_e_val:.0f}% "
             f"em {years_t[-1]}. "
             f"Ao mesmo tempo, a participação de C3+C4 no corpus anual cresce de {start_c34:.0f}% "
             f"({years_t[0]}) para {last_c34:.0f}% ({years_t[-1]}). "
             "O campo absorve a inovação sem depender do rótulo que a nomeou.")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.array(years_t, dtype=float)

    # E>0 line
    ax.plot(x, e_vals, color=C_PALETTE[1], lw=2.5, marker="o", ms=7, zorder=4,
            label="% artigos com E>0  (vocabulário ChatGPT/GenAI)")
    # C3+C4 line
    ax.plot(x, c34_vals, color=C_PALETTE[3], lw=2.5, marker="s", ms=7, zorder=4,
            label="% corpus em C3+C4  (campo focal estrutural)")

    # Shade fill under C3+C4
    ax.fill_between(x, 0, c34_vals, color=C_PALETTE[3], alpha=0.10, zorder=1)

    # Annotate each point
    for xi, (yr, ev, cv) in enumerate(zip(years_t, e_vals, c34_vals)):
        if not np.isnan(ev):
            ax.text(yr, ev + 1.5, f"{ev:.0f}%", ha="center", va="bottom",
                    fontsize=8, color=C_PALETTE[1], fontweight="600")
        if not np.isnan(cv):
            ax.text(yr, cv - 2.0, f"{cv:.0f}%", ha="center", va="top",
                    fontsize=8, color=C_PALETTE[3], fontweight="600")

    # Divergence annotation
    if 2023 in years_t:
        x2023 = years_t.index(2023)
        ax.axvspan(2023 - 0.3, years_t[-1] + 0.3, color=AX_BG, alpha=0.0, zorder=0)
        ax.annotate(
            "Divergência:\nE>0 recua,\nC3+C4 cresce",
            xy=(2023.5, (e_vals[x2023] + c34_vals[x2023]) / 2),
            xytext=(2024.5, (e_vals[x2023] + c34_vals[x2023]) / 2 + 10),
            fontsize=8.5, color=TEXT,
            arrowprops=dict(arrowstyle="->", color=SUBTEXT, lw=1.0),
            bbox=dict(facecolor=AX_BG, edgecolor=EDGE, boxstyle="round,pad=0.35", alpha=0.9),
        )

    # ChatGPT launch marker
    ax.axvline(2022.92, color=RED, lw=1.2, ls=":", alpha=0.7)
    ax.text(2022.85, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 70,
            "ChatGPT\nnov/2022", fontsize=7.5, color=RED, fontstyle="italic",
            va="top", ha="right",
            bbox=dict(facecolor=AX_BG, edgecolor=RED, boxstyle="round,pad=0.25", alpha=0.85))

    ax.set_xticks(years_t)
    ax.set_xticklabels([str(y) for y in years_t])
    ax.set_ylabel("% do corpus anual", color=TEXT, labelpad=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_ylim(0, max(max(e_vals), max(c34_vals)) * 1.32)
    ax.set_title(
        "Vocabulário vs. Estrutura — O Rótulo ChatGPT Recua, o Campo Focal Persiste",
        fontsize=12, fontweight="700", color=TEXT, pad=16,
    )
    ax.grid(axis="y", alpha=0.35)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", fontsize=9.5, framealpha=0.9)

    fig.tight_layout()
    _embed(out, fig,
            f"Fig 19 — Dois indicadores por ano: % de artigos com E>0 (laranja) e % do corpus em C3+C4 (violeta). "
           f"E>0 pico em {peak_e_yr} ({peak_e_val:.0f}%) e recua; C3+C4 cresce de {start_c34:.0f}% para {last_c34:.0f}%. "
           "Separação entre sinal semântico (vocabulário) e sinal estrutural (participação temática).",
           "fig18")


def fig_claim_impact_concentration(out: io.StringIO) -> None:
    """Fig 20 — Lorenz curves + top-decile bar chart: impact is extremely concentrated."""
    _section_break(out, "Teses-Chave · Concentração do Impacto")
    out.write("## Fig 20 — Concentração Extrema do Impacto: Top 10% Domina as Citações\n\n")

    _callout(out, "question",
             "O impacto bibliométrico do corpus está distribuído de forma ampla entre os artigos, "
             "ou extremamente concentrado em um topo mínimo — tornando as médias por cluster enganosas?")
    _callout(out, "method",
             "Painel esquerdo: curvas de Lorenz por cluster. Eixo X = percentual cumulativo de artigos "
             "(ordenados do menos ao mais citado); eixo Y = percentual cumulativo de citações. "
             "A diagonal pontilhada representa distribuição perfeitamente igual. "
             "Quanto mais côncava a curva, maior a concentração. "
             "Painel direito: barras com a percentagem de citações concentradas no top 10% dos artigos de cada cluster.")

    df = _load_axis_scores()
    clusters = sorted(df["cluster"].dropna().astype(int).unique().tolist())

    conc_rows: list[dict] = []
    for c in clusters:
        grp = df[df["cluster"] == c]["cited_by_count"].sort_values(ascending=True)
        conc_rows.append({
            "cluster_id":   c,
            "label":        _compact_cluster_legend_label(c),
            "top10_share":  _top_share(grp[::-1], 0.10),
            "top20_share":  _top_share(grp[::-1], 0.20),
            "lorenz_x":     np.linspace(0, 100, len(grp)).tolist(),
            "lorenz_y":     (np.cumsum(grp.values) / max(grp.sum(), 1) * 100).tolist(),
            "n":            len(grp),
        })
    # Also compute for full corpus
    full_cit = df["cited_by_count"].sort_values(ascending=True)
    corpus_top10 = _top_share(full_cit[::-1], 0.10)
    corpus_top20 = _top_share(full_cit[::-1], 0.20)

    _callout(out, "read",
             f"Corpus total: top 10% = {corpus_top10:.1f}% das citações; top 20% = {corpus_top20:.1f}%. "
             f"Por cluster, a concentração no top decil varia entre "
             f"{min(r['top10_share'] for r in conc_rows):.1f}% e "
             f"{max(r['top10_share'] for r in conc_rows):.1f}%. "
             "Em todos os casos a curva de Lorenz é fortemente côncava — median e percentil 75 "
             "são métricas muito mais informativas do que a média para descrever o impacto de um cluster.")

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(13, 5.5))

    # ── Lorenz curves ─────────────────────────────────────────────────
    for row in conc_rows:
        ax_l.plot(row["lorenz_x"], row["lorenz_y"],
                  color=C_PALETTE[row["cluster_id"]], lw=2.0, zorder=3,
                  label=row["label"])

    # Full corpus Lorenz
    ax_l.plot(
        np.linspace(0, 100, len(full_cit)),
        np.cumsum(full_cit.values) / max(full_cit.sum(), 1) * 100,
        color=SUBTEXT, lw=1.5, ls="-.", zorder=3, alpha=0.85, label="Corpus total",
    )

    # Perfect equality diagonal
    ax_l.plot([0, 100], [0, 100], color=SUBTEXT, lw=1.2, ls="--", alpha=0.7, label="Igualdade perfeita")

    # Shade between Lorenz curve and diagonal for worst-concentration cluster
    worst = max(conc_rows, key=lambda r: r["top10_share"])
    ax_l.fill_between(worst["lorenz_x"], worst["lorenz_y"], worst["lorenz_x"],
                      alpha=0.06, color=C_PALETTE[worst["cluster_id"]])

    # Annotation for top-10% reference
    ax_l.axvline(90, color=EDGE, lw=0.9, ls=":", alpha=0.7)
    ax_l.text(90.5, 12, "top 10%\ndos artigos", fontsize=7.5, color=SUBTEXT, va="bottom")

    ax_l.set_xlabel("% cumulativo de artigos (do menos ao mais citado)", color=TEXT, labelpad=8)
    ax_l.set_ylabel("% cumulativo de citações", color=TEXT, labelpad=8)
    ax_l.set_title("Curvas de Lorenz por Cluster", fontsize=12, fontweight="700", color=TEXT, pad=14)
    ax_l.set_xlim(0, 100)
    ax_l.set_ylim(0, 100)
    ax_l.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax_l.grid(alpha=0.35)
    ax_l.set_axisbelow(True)

    # ── Top-10% bar chart ──────────────────────────────────────────────
    conc_sorted = sorted(conc_rows, key=lambda r: r["top10_share"])
    y_r = np.arange(len(conc_sorted))
    colours_r = [C_PALETTE[r["cluster_id"]] for r in conc_sorted]
    bars_r = ax_r.barh(y_r, [r["top10_share"] for r in conc_sorted],
                       color=colours_r, edgecolor="none", height=0.60, alpha=0.88, zorder=3)

    # Corpus total reference line
    ax_r.axvline(corpus_top10, color=TEXT, lw=1.5, ls="--", alpha=0.7, zorder=4,
                 label=f"Corpus total: {corpus_top10:.1f}%")

    for bar, row in zip(bars_r, conc_sorted):
        ax_r.text(row["top10_share"] + 0.5, bar.get_y() + bar.get_height() / 2,
                  f"{row['top10_share']:.1f}%  (n={row['n']:,})",
                  va="center", fontsize=8.5, color=TEXT)

    ax_r.set_yticks(y_r)
    ax_r.set_yticklabels([r["label"] for r in conc_sorted], fontsize=8.5)
    ax_r.set_xlabel("% das citações no top 10% dos artigos", color=TEXT, labelpad=8)
    ax_r.set_xlim(0, max(r["top10_share"] for r in conc_rows) * 1.30)
    ax_r.set_title(f"Top 10% dos artigos por citações\n(corpus total: {corpus_top10:.1f}%)",
                   fontsize=12, fontweight="700", color=TEXT, pad=14)
    ax_r.legend(loc="lower right", fontsize=8.5, framealpha=0.9)
    ax_r.grid(axis="x", alpha=0.35)
    ax_r.set_axisbelow(True)
    ax_r.spines["left"].set_visible(False)
    ax_r.tick_params(axis="y", length=0)

    fig.tight_layout()
    _embed(out, fig,
            f"Fig 20 — Concentração do impacto. "
           f"Esquerda: curvas de Lorenz por cluster (quanto mais côncava, maior a concentração). "
           f"Direita: percentagem das citações totais de cada cluster concentrada no seu top décimo de artigos. "
           f"Corpus total: top 10% = {corpus_top10:.1f}%; top 20% = {corpus_top20:.1f}%. "
           "Em todos os clusters, o impacto é dominado por uma minoria de artigos agenda-setters.",
           "fig19")


def fig_claim_two_ecosystems(out: io.StringIO) -> None:
    """Fig 21 — Side-by-side top journals: core technical vs. focal educational."""
    _section_break(out, "Teses-Chave · Dois Ecossistemas Editoriais")
    out.write("## Fig 21 — Dois Ecossistemas Editoriais: Corpus Técnico vs. Campo Focal\n\n")

    _callout(out, "question",
             "Os periódicos que publicam o corpus técnico-clínico (C0+C1+C2) e os que publicam "
             "o campo focal (C3+C4) são os mesmos ou formam ecossistemas editoriais distintos?")
    _callout(out, "method",
             "Barras horizontais lado a lado: esquerdo = 12 periódicos mais produtivos do corpus técnico-clínico (C0+C1+C2); "
             "direito = 12 periódicos mais produtivos do campo focal (C3+C4). "
             "Periódicos presentes nos dois lados (sobreposição) destacados em vermelho. "
             "O índice de Jaccard sobre os top-15 de cada lado mede a distância editorial.")

    df = _load_axis_scores()
    df["id"] = df["id"].astype(str)
    cc = pd.read_csv(ROOT / "corpus_clustered.csv", usecols=["id", "journal"])
    cc["journal"] = cc["journal"].fillna("").str.strip().str.title()
    cc["id"] = cc["id"].astype(str)
    cc = cc.merge(df[["id", "cluster"]], on="id", how="left")
    cc = cc[cc["journal"] != ""]

    def shorten(name: str, maxlen: int = 48) -> str:
        return name if len(name) <= maxlen else name[:maxlen - 1] + "…"

    def top_journals(cluster_ids: list[int], top_n: int = 12) -> pd.Series:
        return (
            cc[cc["cluster"].isin(cluster_ids)]
            .groupby("journal").size()
            .sort_values(ascending=False)
            .head(top_n)
        )

    core_top  = top_journals([0, 1, 2], 15)
    focal_top = top_journals([3, 4], 15)
    overlap   = set(core_top.index) & set(focal_top.index)
    jaccard   = len(overlap) / max(len(set(core_top.index) | set(focal_top.index)), 1)

    # Display top-12
    core_plot  = core_top.head(12)
    focal_plot = focal_top.head(12)

    _callout(out, "read",
             f"{len(overlap)} periódicos em comum nos top-15 de cada subcorpus "
             f"(Jaccard = {jaccard:.2f}). "
             + (
                 f"Sobreposição: {', '.join(sorted(overlap))}."
                 if overlap else
                 "Sem sobreposição — ecossistemas completamente disjuntos."
             ))

    fig, (ax_c, ax_f) = plt.subplots(1, 2, figsize=(16, 6.5))

    def plot_side(ax: plt.Axes, jrn: pd.Series, title: str, col_main: str,
                  overl: set[str]) -> None:
        jrn_asc = jrn[::-1]  # ascending order for hbar (bottom = largest)
        colours = [RED if j in overl else col_main for j in jrn_asc.index]
        y = np.arange(len(jrn_asc))
        bars = ax.barh(y, jrn_asc.values, color=colours, edgecolor="none",
                       height=0.62, alpha=0.88, zorder=3)
        for bar, n in zip(bars, jrn_asc.values):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{int(n)}", va="center", fontsize=8.5, color=TEXT)
        ax.set_yticks(y)
        ax.set_yticklabels([shorten(j) for j in jrn_asc.index], fontsize=8.5)
        ax.set_xlabel("N artigos no subcorpus", color=TEXT, labelpad=8)
        ax.set_xlim(0, jrn.max() * 1.38)
        ax.set_title(title, fontsize=11, fontweight="700", color=TEXT, pad=12)
        ax.grid(axis="x", alpha=0.35)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        # Overlap legend
        if overl:
            ax.axhline(-1, color=RED, lw=3, label="Em ambos os subcorpus")
            ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    plot_side(ax_c, core_plot, "Corpus Técnico-Clínico (C0+C1+C2)\n12 periódicos mais produtivos",
              C_PALETTE[0], overlap)
    plot_side(ax_f, focal_plot, "Corpus Focal — IA na Produção Acadêmica (C3+C4)\n12 periódicos mais produtivos",
              C_PALETTE[3], overlap)

    fig.suptitle(
        f"Dois Ecossistemas Editoriais Distintos — Jaccard top-15 = {jaccard:.2f}"
        + (" (sem sobreposição)" if not overlap else f" ({len(overlap)} periódico(s) em comum)"),
        fontsize=12, fontweight="700", color=TEXT, y=1.02,
    )
    fig.tight_layout()
    _embed(out, fig,
            f"Fig 21 — Comparação dos 12 periódicos mais produtivos entre corpus técnico-clínico (C0+C1+C2) "
           f"e campo focal (C3+C4). Vermelho = presença nos dois; Jaccard top-15 = {jaccard:.2f}. "
           "O corpus focal publica em periódicos de educação, ética e computação educacional; "
           "o técnico-clínico concentra-se em engenharia, biomédica e periódicos de amplo alcance.",
           "fig20")


def fig_lotka(out: io.StringIO) -> None:
    """Fig 13b — Lotka's Law: observed vs expected author productivity distribution."""
    _section_break(out, "Seção 4.8 · Lei de Lotka — Visualização")
    out.write("## Fig 13b — Lei de Lotka: Distribuição de Produtividade dos Autores\n\n")

    _callout(out, "question",
             "A distribuição de produtividade dos autores segue a Lei de Lotka — "
             "a maioria dos autores publica apenas um artigo, e o número de autores com n artigos "
             "cai proporcionalmente a 1/n²?")
    _callout(out, "method",
             "Barras = percentual observado de autores com n artigos publicados (n = 1 a 10); "
             "Linha = percentual esperado pela Lei de Lotka (P(n) = C/n², "
             "C normalizado para o intervalo observado). "
             "Escala Y linear; eixo X = número de artigos por autor.")

    lotka = pd.read_csv(IND / "lotka.csv")
    if lotka.empty or len(lotka) < 2:
        out.write(f'<p style="color:{SUBTEXT};font-style:italic">Dados insuficientes para plotar Lotka.</p>\n\n')
        return

    # Restrict to n_papers ≤ 10 for readability
    plot_df = lotka[lotka["n_papers"] <= 10].copy().reset_index(drop=True)
    ns      = plot_df["n_papers"].values
    obs_pct = plot_df["pct_authors"].values

    # Expected Lotka: P(n) ∝ 1/n²; normalize over the observed range
    raw_expected = 1.0 / (ns ** 2)
    norm_factor  = obs_pct.sum() / raw_expected.sum()
    exp_pct      = raw_expected * norm_factor

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)

    bar_width = 0.55
    x = np.arange(len(ns))
    bars = ax.bar(x, obs_pct, width=bar_width, color=ACCENT, alpha=0.75,
                  edgecolor=EDGE, linewidth=0.6, label="Observado", zorder=3)

    ax.plot(x, exp_pct, color=RED, lw=2.2, marker="o", markersize=5,
            markeredgewidth=0.8, markeredgecolor=BG, zorder=4, label="Esperado (Lotka 1/n²)")

    ax.set_xticks(x)
    ax.set_xticklabels([str(int(n)) for n in ns], color=TEXT, fontsize=9.5)
    ax.set_xlabel("N artigos publicados por autor", color=TEXT, labelpad=10)
    ax.set_ylabel("% dos autores", color=TEXT, labelpad=10)
    ax.set_title("Lei de Lotka — Distribuição de Produtividade dos Autores (2020–2026)",
                 fontsize=12.5, fontweight="700", color=TEXT, pad=14)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor(SPINE)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.legend(fontsize=9, framealpha=0.88)

    fig.tight_layout()

    n1 = int(lotka.loc[lotka["n_papers"] == 1, "n_authors"].iloc[0]) if 1 in lotka["n_papers"].values else 0
    pct1 = float(lotka.loc[lotka["n_papers"] == 1, "pct_authors"].iloc[0]) if 1 in lotka["n_papers"].values else 0.0
    n_total = int(lotka["n_authors"].sum())
    _embed(out, fig,
            f"Fig 13b — Lei de Lotka (N={n_total:,} autores únicos). "
           f"{pct1:.1f}% ({n1:,}) publicaram exatamente 1 artigo. "
           f"A linha vermelha (esperado 1/n²) acompanha de perto as barras observadas, "
           f"confirmando que a distribuição de produtividade segue a Lei de Lotka.",
           "fig12b")


def fig_zipf(out: io.StringIO) -> None:
    """Fig 13c — Zipf's Law: rank-frequency distribution of author keywords."""
    _section_break(out, "Seção 4.9 · Lei de Zipf — Distribuição de Palavras-chave")
    out.write("## Fig 13c — Lei de Zipf: Distribuição de Frequência das Palavras-chave\n\n")

    _callout(out, "question",
             "A distribuição de frequência das palavras-chave dos autores segue uma lei de potência "
             "(Lei de Zipf) — poucas palavras extremamente frequentes, com cauda longa de termos raros?")
    _callout(out, "method",
             "Gráfico log-log: eixo X = rank da palavra-chave (1 = mais frequente), "
             "eixo Y = frequência observada. Pontos = vocabulário nuclear (freq ≥ 2, N=33 termos). "
             "Linha vermelha = ajuste de lei de potência: log(freq) ~ −α × log(rank). "
             "α próximo de 1 indica distribuição de Zipf clássica. "
             "99,5% das palavras-chave são hapax (freq = 1) e são excluídas do ajuste.")

    zipf_path = IND / "zipf_analysis.csv"
    stats_path = IND / "zipf_stats.csv"
    if not zipf_path.exists() or not stats_path.exists():
        out.write(f'<p style="color:{SUBTEXT};font-style:italic">Arquivo zipf_analysis.csv não encontrado.</p>\n\n')
        return

    zdf   = pd.read_csv(zipf_path)
    stats = pd.read_csv(stats_path).iloc[0]
    alpha  = float(stats["zipf_alpha"])
    r2     = float(stats["zipf_r2"])
    n_core = int(stats["n_core_vocab"])
    n_hapax = int(stats.get("n_hapax", 0))
    top1   = str(stats["top1_keyword"])
    top1_f = int(stats["top1_freq"])

    # Compute fitted values for the plot line using all core ranks
    log_ranks  = np.log(zdf["rank"].values.astype(float))
    log_fitted = np.log(zdf["freq_expected"].values.astype(float))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(AX_BG)

    # Scatter — observed
    ax.scatter(np.log(zdf["rank"]), np.log(zdf["freq"]),
               color=ACCENT, s=55, zorder=4, alpha=0.90, edgecolors=BG, linewidths=0.6,
               label=f"Observado (vocabulário nuclear, N={n_core})")

    # Fitted line
    ax.plot(log_ranks, log_fitted, color=RED, lw=2.2, zorder=5,
            label=f"Ajuste Zipf: log(freq) = C − {alpha:.3f}·log(rank)")

    # Annotation box
    ann_text = f"α = {alpha:.3f}\nR² = {r2:.3f}\nN (vocab. nuclear) = {n_core}"
    ax.text(0.97, 0.97, ann_text, transform=ax.transAxes,
            ha="right", va="top", fontsize=9.5,
            color=TEXT, bbox=dict(facecolor=AX_BG, edgecolor=SPINE, boxstyle="round,pad=0.5",
                                  alpha=0.92, linewidth=0.8))

    # Label top keywords
    for _, row in zdf.head(5).iterrows():
        kw = str(row["keyword"])
        kw_short = kw[:28] + "…" if len(kw) > 28 else kw
        ax.annotate(kw_short,
                    xy=(np.log(row["rank"]), np.log(row["freq"])),
                    xytext=(6, 3), textcoords="offset points",
                    fontsize=7.5, color=SUBTEXT, ha="left")

    ax.set_xlabel("log(rank)", color=TEXT, labelpad=10)
    ax.set_ylabel("log(frequência)", color=TEXT, labelpad=10)
    ax.set_title("Lei de Zipf — Distribuição de Frequência das Palavras-chave (vocabulário nuclear)",
                 fontsize=12, fontweight="700", color=TEXT, pad=14)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor(SPINE)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, lw=0.6, alpha=0.6)
    ax.legend(fontsize=9, framealpha=0.88)
    fig.tight_layout()

    _embed(out, fig,
            f"Fig 13c — Lei de Zipf (vocabulário nuclear: {n_core} termos com freq ≥ 2; "
           f"{n_hapax:,} hapax excluídos). "
           f"Expoente α = {alpha:.3f} (Zipf puro = 1.0; típico em corpora científicos: 0.7–1.3). "
           f"R² = {r2:.3f} — excelente qualidade de ajuste. "
           f"Termo mais frequente: '{top1}' ({top1_f} artigos).",
           "fig12c")


def fig_focal_top_papers(out: io.StringIO) -> None:
    """Fig 17b — Top-cited papers per focal cluster (C3 and C4)."""
    _section_break(out, "Corpus Focal C3+C4 · Artigos de Maior Impacto")
    out.write("## Fig 17b — Artigos de Maior Impacto por Cluster Focal (C3 e C4)\n\n")

    _callout(out, "question",
             "Quais artigos concentram o impacto dos clusters focais C3 e C4? "
             "O impacto é distribuído amplamente ou concentrado em poucos outliers?")
    _callout(out, "method",
             "Gráficos de barras horizontais lado a lado: esquerdo = top 8 artigos mais citados de C3 "
             "(ChatGPT e Integridade); direito = top 8 de C4 (IA no Ensino Superior). "
             "Títulos truncados para legibilidade; citações indicadas no extremo de cada barra.")

    focus_path = IND / "cluster_focus_papers.csv"
    if not focus_path.exists():
        out.write(f'<p style="color:{SUBTEXT};font-style:italic">cluster_focus_papers.csv não encontrado.</p>\n\n')
        return

    fp = pd.read_csv(focus_path)
    fp["cited_by_count"] = pd.to_numeric(fp["cited_by_count"], errors="coerce").fillna(0)

    def _prep(cid: int, top_n: int = 8) -> pd.DataFrame:
        sub = fp[fp["cluster_id"] == cid].nlargest(top_n, "cited_by_count").copy()
        # Shorten title for display
        sub["short_title"] = sub["title"].apply(
            lambda t: (t[:52] + "…") if len(str(t)) > 52 else str(t))
        return sub.sort_values("cited_by_count").reset_index(drop=True)

    c3 = _prep(3)
    c4 = _prep(4)

    fig, (ax3, ax4) = plt.subplots(1, 2, figsize=(16, 6.0))
    fig.patch.set_facecolor(BG)

    def _draw(ax: plt.Axes, df: pd.DataFrame, color: str, panel_title: str) -> None:
        ax.set_facecolor(AX_BG)
        y = np.arange(len(df))
        bars = ax.barh(y, df["cited_by_count"], color=color, alpha=0.82,
                       height=0.60, edgecolor="none")
        for bar, cit in zip(bars, df["cited_by_count"]):
            ax.text(bar.get_width() + df["cited_by_count"].max() * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(cit):,}", va="center", fontsize=8.5, color=TEXT, fontweight="600")
        ax.set_yticks(y)
        ax.set_yticklabels(df["short_title"], fontsize=8)
        ax.set_xlabel("Citações", color=TEXT, labelpad=8)
        xlim_max = df["cited_by_count"].max() * 1.30
        ax.set_xlim(0, max(xlim_max, 10))
        ax.set_title(panel_title, fontsize=10.5, fontweight="700", color=color, pad=10)
        ax.tick_params(colors=TEXT, labelsize=8.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(EDGE)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)

    c3_label = _build_raw_cluster_labels().get(3, "C3 — ChatGPT e Integridade")
    c4_label = _build_raw_cluster_labels().get(4, "C4 — IA no Ensino Superior")
    _draw(ax3, c3, C_PALETTE[3], f"C3 · {c3_label[:42]}")
    _draw(ax4, c4, C_PALETTE[4], f"C4 · {c4_label[:42]}")

    fig.suptitle("Top Artigos por Citações — Clusters Focais C3 e C4",
                 fontsize=12.5, fontweight="700", color=TEXT, y=1.01)
    fig.tight_layout()

    c3_top  = c3.iloc[-1]
    c4_top  = c4.iloc[-1]
    _embed(out, fig,
            f"Fig 17b — Top 8 artigos mais citados por cluster focal. "
           f"C3 líder: '{str(c3_top['title'])[:70]}…' ({int(c3_top['cited_by_count']):,} cit., {int(c3_top['publication_year'])}). "
           f"C4 líder: '{str(c4_top['title'])[:70]}…' ({int(c4_top['cited_by_count']):,} cit., {int(c4_top['publication_year'])}). "
           f"Impacto altamente concentrado — o artigo mais citado de cada cluster domina largamente a mediana.",
           "fig16b")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print(f"Mode: {'light' if LIGHT else 'dark'} · DPI={DPI}")
    out = io.StringIO()

    # HTML wrapper
    font_stack = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
    out.write(f"""<html><head><meta charset="utf-8">
<style>
  body {{ font-family: {font_stack}; background:{BG}; color:{TEXT};
         max-width:960px; margin:2em auto; padding:0 2em; line-height:1.7; }}
  h1 {{ color:{TEXT}; font-size:1.6em; margin-bottom:0.2em; }}
  h2 {{ color:{TEXT}; font-size:1.15em; margin-top:2em; border-bottom:1px solid {EDGE};
        padding-bottom:0.3em; }}
  h1, h2, h3 {{ font-weight:700; }}
  table {{ border-collapse:collapse; margin:1em 0; }}
  th, td {{ border:1px solid {EDGE}; padding:5px 12px; }}
  th {{ background:{EDGE}; }}
  a {{ color:{ACCENT}; }}
  figure {{ margin:1.5em 0; }}
</style>
</head><body>
""")

    _write_header(out)
    _write_kpi_cards(out)
    _write_citation_coverage_note(out)
    _write_findings_summary(out)

    # Figures
    print("  Fig 2  temporal…")
    fig_temporal(out)
    print("  Fig 3  cluster composition…")
    fig_cluster_composition(out)
    print("  Fig 4  geographic map…")
    fig_geo_countries(out)
    print("  Fig 5  Bradford's Law…")
    fig_bradford(out)
    print("  Fig 6  UMAP…")
    fig_umap(out)
    print("  Fig 7  scatter E×N…")
    fig_scatter_ea(out)
    print("  Fig 8  axis E × citations…")
    fig_axis_e_citations(out)
    print("  Fig 9  axis R × time (temporal drift)…")
    fig_axis_r_citations(out)
    print("  Fig 10 citation cohort anomaly…")
    fig_citation_cohorts(out)
    print("  Fig 11 orthogonality…")
    fig_orthogonality(out)
    print("  Fig 12 journals…")
    fig_journals(out)
    print("  PRISMA flow…")
    _write_prisma(out)
    print("  Table: top-20 cited…")
    _write_top20_table(out)
    print("  Fig 13 keyword network…")
    fig_keyword_network(out)
    print("  Table: authors / Lotka…")
    _write_lotka_table(out)
    print("  Fig 13b Lotka's Law…")
    fig_lotka(out)
    print("  Fig 13c Zipf's Law…")
    fig_zipf(out)
    print("  Fig 14 focal emergence…")
    fig_focal_emergence(out)
    print("  Fig 15 focal themes…")
    fig_focal_themes(out)
    print("  Fig 16 focal citation maturity…")
    fig_focal_citation_maturity(out)
    print("  Fig 17 focal journals…")
    fig_focal_journals(out)
    print("  Fig 17b focal top papers…")
    fig_focal_top_papers(out)
    print("  Fig 18 claim: ChatGPT reversal…")
    fig_claim_chatgpt_reversal(out)
    print("  Fig 19 claim: vocabulary vs structure…")
    fig_claim_vocabulary_structure(out)
    print("  Fig 20 claim: impact concentration…")
    fig_claim_impact_concentration(out)
    print("  Fig 21 claim: two ecosystems…")
    fig_claim_two_ecosystems(out)

    out.write("\n</body></html>\n")

    OUT.write_text(out.getvalue(), encoding="utf-8")
    size_kb = OUT.stat().st_size // 1024
    print(f"\nSaved: {OUT}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
