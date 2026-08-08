from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .paths import RunPaths, ensure_run_dirs
from .utils import read_json, write_json


def _mw(top: pd.Series, bottom: pd.Series) -> dict:
    u_stat, p_value = stats.mannwhitneyu(top, bottom, alternative="greater")
    return {
        "u": float(u_stat),
        "p": float(p_value),
        "med_top": float(top.median()),
        "med_bottom": float(bottom.median()),
        "confirmed": bool(p_value < 0.05),
    }


def _mode_text(series: pd.Series, default: str = "") -> str:
    values = series.dropna().astype(str)
    if values.empty:
        return default
    modes = values.mode()
    return str(modes.iloc[0]) if not modes.empty else str(values.iloc[0])


def run(paths: RunPaths) -> dict:
    ensure_run_dirs(paths)

    axis = pd.read_csv(paths.indicators_dir / "axis_scores_enriched.csv")
    temporal = pd.read_csv(paths.indicators_dir / "temporal_profile.csv")
    yearly = pd.read_csv(paths.indicators_dir / "yearly_production.csv")
    geo = pd.read_csv(paths.indicators_dir / "geo_countries.csv")
    if "country_code" in geo.columns:
        geo = geo[geo["country_code"].fillna("").astype(str).str.strip() != ""].copy()
    journals = pd.read_csv(paths.indicators_dir / "journals.csv")
    top20 = pd.read_csv(paths.indicators_dir / "top20_cited.csv")
    top_authors = pd.read_csv(paths.indicators_dir / "top_authors.csv")
    lotka = pd.read_csv(paths.indicators_dir / "lotka.csv")
    keyword_freq = pd.read_csv(paths.indicators_dir / "keyword_freq.csv")
    keyword_cooc = pd.read_csv(paths.indicators_dir / "keyword_cooc.csv")
    fetch_log = read_json(paths.fetch_log_path, default={})
    embedding_meta = read_json(paths.embedding_meta_path, default={})

    # Affiliation coverage: articles with any country data in corpus_clean
    df_clean = pd.read_csv(paths.corpus_clean_path)
    n_articles_with_countries = int(
        df_clean["countries"].apply(
            lambda v: bool(pd.notna(v) and str(v).strip() not in ("", "nan"))
        ).sum()
    )
    n_corpus_clean = len(df_clean)

    axis["cited_by_count"] = pd.to_numeric(axis["cited_by_count"], errors="coerce").fillna(0)

    corr = axis[["axis_e_technology", "axis_g_guardrails", "axis_n_domain", "axis_r_scope"]].corr(method="pearson")
    rho_e_all, p_e_all = stats.spearmanr(axis["cited_by_count"], axis["axis_e_technology"])
    rho_g_all, p_g_all = stats.spearmanr(axis["cited_by_count"], axis["axis_g_guardrails"])
    rho_n_all, p_n_all = stats.spearmanr(axis["cited_by_count"], axis["axis_n_domain"])
    rho_r_all, p_r_all = stats.spearmanr(axis["cited_by_count"], axis["axis_r_scope"])

    cited_only = axis[axis["cited_by_count"] > 0].copy()
    rho_e_cit, p_e_cit = stats.spearmanr(cited_only["cited_by_count"], cited_only["axis_e_technology"])
    rho_g_cit, p_g_cit = stats.spearmanr(cited_only["cited_by_count"], cited_only["axis_g_guardrails"])
    rho_n_cit, p_n_cit = stats.spearmanr(cited_only["cited_by_count"], cited_only["axis_n_domain"])
    rho_r_cit, p_r_cit = stats.spearmanr(cited_only["cited_by_count"], cited_only["axis_r_scope"])

    axis["e_quartile"] = pd.qcut(
        axis["axis_e_technology"],
        4,
        labels=["Q1", "Q2", "Q3", "Q4"],
        duplicates="drop",
    )
    e_quartiles = axis.groupby("e_quartile", observed=True)["cited_by_count"].agg(["count", "median", "mean"]).reset_index()

    top_e = axis[axis["axis_e_technology"] >= axis["axis_e_technology"].quantile(0.75)]["cited_by_count"]
    bot_e = axis[axis["axis_e_technology"] <= axis["axis_e_technology"].quantile(0.25)]["cited_by_count"]
    top_g = axis[axis["axis_g_guardrails"] >= axis["axis_g_guardrails"].quantile(0.75)]["cited_by_count"]
    bot_g = axis[axis["axis_g_guardrails"] <= axis["axis_g_guardrails"].quantile(0.25)]["cited_by_count"]
    top_n = axis[axis["axis_n_domain"] >= axis["axis_n_domain"].quantile(0.75)]["cited_by_count"]
    bot_n = axis[axis["axis_n_domain"] <= axis["axis_n_domain"].quantile(0.25)]["cited_by_count"]
    top_r = axis[axis["axis_r_scope"] >= axis["axis_r_scope"].quantile(0.75)]["cited_by_count"]
    bot_r = axis[axis["axis_r_scope"] <= axis["axis_r_scope"].quantile(0.25)]["cited_by_count"]

    cluster_stats = []
    cluster_counts = axis["cluster"].value_counts().sort_index()
    for cluster_id, count in cluster_counts.items():
        cluster_rows = axis.loc[axis["cluster"] == cluster_id]

        _description = _mode_text(cluster_rows.get("cluster_description", pd.Series(dtype=str)), "")
        if not _description:
            _label = _mode_text(cluster_rows.get("cluster_label", pd.Series(dtype=str)), f"Cluster {int(cluster_id)}")
            _description = "Artigos com foco predominante em: " + _label.replace(" · ", ", ") + "."
        cluster_stats.append({
            "cluster": int(cluster_id),
            "label": _mode_text(cluster_rows.get("cluster_label", pd.Series(dtype=str)), f"Cluster {int(cluster_id)}"),
            "description": _description,
            "n": int(count),
            "pct": round(100 * count / len(axis), 1),
            "mean_e": float(cluster_rows["axis_e_technology"].mean()),
            "mean_g": float(cluster_rows["axis_g_guardrails"].mean()),
            "mean_n": float(cluster_rows["axis_n_domain"].mean()),
            "mean_r": float(cluster_rows["axis_r_scope"].mean()),
        })

    summary = {
        "retrieval_profile": fetch_log.get("retrieval_profile", "legacy"),
        "run_dir": str(paths.run_dir),
        "prisma": {
            "n_identified": int(fetch_log.get("n_identified_unique", fetch_log.get("n_identified", 0))),
            "n_excluded_noabstract": int(fetch_log.get("n_excluded_noabstract", 0)),
            "n_excluded_offtopic": int(fetch_log.get("n_excluded_offtopic", 0)),
            "n_excluded_missing_scope": int(fetch_log.get("n_excluded_missing_scope", 0)),
            "n_excluded_negative_scope": int(fetch_log.get("n_excluded_negative_scope", 0)),
            "n_excluded_weak_alignment": int(fetch_log.get("n_excluded_weak_alignment", 0)),
            "n_excluded_low_relevance": int(fetch_log.get("n_excluded_low_relevance", 0)),
            "n_excluded_doi_dup": int(fetch_log.get("n_excluded_doi_dup", 0)),
            "n_excluded_title_dup": int(fetch_log.get("n_excluded_title_dup", 0)),
            "n_excluded_year": int(fetch_log.get("n_excluded_year", 0)),
            "n_excluded_retracted": int(fetch_log.get("n_excluded_retracted", 0)),
            "n_excluded_topic": int(fetch_log.get("n_excluded_topic", 0)),
            "n_excluded_no_embedding": int(fetch_log.get("n_excluded_no_embedding", 0)),
            "n_final_fetch": int(fetch_log.get("n_final_fetch", 0)),
            "n_final_clean": int(fetch_log.get("n_final_clean", 0)),
            "n_final_semantic": int(fetch_log.get("n_final_semantic", len(axis))),
        },
        "corpus": {
            "n_articles": int(len(axis)),
            "n_corpus_clean": n_corpus_clean,
            "n_articles_with_countries": n_articles_with_countries,
            "year_min": int(yearly["year"].min()),
            "year_max": int(yearly["year"].max()),
            "n_countries": int(len(geo)),
            "zero_citations_n": int((axis["cited_by_count"] == 0).sum()),
            "zero_citations_pct": round(100 * (axis["cited_by_count"] == 0).mean(), 1),
            "max_citations": int(axis["cited_by_count"].max()),
            "silhouette": float(embedding_meta.get("silhouette", np.nan)),
            "k_best": int(embedding_meta.get("k_best", 0)) if embedding_meta.get("k_best") is not None else None,
        },
        "clusters": cluster_stats,
        "axes": {
            "means": {
                "E": float(axis["axis_e_technology"].mean()),
                "G": float(axis["axis_g_guardrails"].mean()),
                "N": float(axis["axis_n_domain"].mean()),
                "R": float(axis["axis_r_scope"].mean()),
            },
            "std": {
                "E": float(axis["axis_e_technology"].std()),
                "G": float(axis["axis_g_guardrails"].std()),
                "N": float(axis["axis_n_domain"].std()),
                "R": float(axis["axis_r_scope"].std()),
            },
            "orthogonality": {
                "E_G": float(corr.loc["axis_e_technology", "axis_g_guardrails"]),
                "E_N": float(corr.loc["axis_e_technology", "axis_n_domain"]),
                "E_R": float(corr.loc["axis_e_technology", "axis_r_scope"]),
                "G_N": float(corr.loc["axis_g_guardrails", "axis_n_domain"]),
                "G_R": float(corr.loc["axis_g_guardrails", "axis_r_scope"]),
                "N_R": float(corr.loc["axis_n_domain", "axis_r_scope"]),
            },
        },
        "spearman": {
            "E": {"rho_all": float(rho_e_all), "p_all": float(p_e_all), "rho_cited": float(rho_e_cit), "p_cited": float(p_e_cit)},
            "G": {"rho_all": float(rho_g_all), "p_all": float(p_g_all), "rho_cited": float(rho_g_cit), "p_cited": float(p_g_cit)},
            "N": {"rho_all": float(rho_n_all), "p_all": float(p_n_all), "rho_cited": float(rho_n_cit), "p_cited": float(p_n_cit)},
            "R": {"rho_all": float(rho_r_all), "p_all": float(p_r_all), "rho_cited": float(rho_r_cit), "p_cited": float(p_r_cit)},
        },
        "hypotheses": {
            "E_q4_gt_q1": _mw(top_e, bot_e),
            "G_q4_gt_q1": _mw(top_g, bot_g),
            "N_q4_gt_q1": _mw(top_n, bot_n),
            "R_q4_gt_q1": _mw(top_r, bot_r),
        },
        "quartiles_e": [
            {
                "quartile": str(row["e_quartile"]),
                "n": int(row["count"]),
                "median_cit": float(row["median"]),
                "mean_cit": float(row["mean"]),
            }
            for _, row in e_quartiles.iterrows()
        ],
        "top_paper": {
            "title": str(top20.iloc[0]["title"]),
            "year": int(top20.iloc[0]["publication_year"]),
            "citations": int(top20.iloc[0]["cited_by_count"]),
            "journal": str(top20.iloc[0]["journal"]),
        },
        "tables": {
            "yearly_rows": int(len(yearly)),
            "geo_rows": int(len(geo)),
            "journals_rows": int(len(journals)),
            "top20_rows": int(len(top20)),
            "authors_rows": int(len(top_authors)),
            "lotka_rows": int(len(lotka)),
            "keyword_freq_rows": int(len(keyword_freq)),
            "keyword_cooc_rows": int(len(keyword_cooc)),
            "temporal_rows": int(len(temporal)),
        },
    }
    write_json(paths.report_summary_path, summary)
    print(f"Saved: {paths.report_summary_path}")
    return summary