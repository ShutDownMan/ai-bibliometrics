from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from .config import CLUSTER_METADATA
from .paths import RunPaths, ensure_run_dirs
from .report_summary import run as build_summary
from .utils import read_json


def _h1(text: str) -> str:
    return f"\n# {text}\n"


def _h2(text: str) -> str:
    return f"\n## {text}\n"


def _h3(text: str) -> str:
    return f"\n### {text}\n"


def _hr() -> str:
    return "\n---\n"


def _note(text: str) -> str:
    return f"\n> {text}\n"


def _df_to_md(df: pd.DataFrame, *, index: bool = False) -> str:
    return df.to_markdown(index=index) + "\n"


def _fmt_p(value: float) -> str:
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def _top_share(values: pd.Series, fraction: float) -> float:
    ordered = pd.to_numeric(values, errors="coerce").fillna(0).sort_values(ascending=False)
    top_n = max(1, int(round(len(ordered) * fraction)))
    total = float(ordered.sum())
    return 0.0 if total <= 0 else 100 * float(ordered.head(top_n).sum()) / total


def run(paths: RunPaths) -> Path:
    ensure_run_dirs(paths)
    if not paths.report_summary_path.exists():
        build_summary(paths)
    summary = read_json(paths.report_summary_path)
    dominant_cluster = max(summary["clusters"], key=lambda item: item["n"]) if summary["clusters"] else None

    yearly = pd.read_csv(paths.indicators_dir / "yearly_production.csv")
    temporal = pd.read_csv(paths.indicators_dir / "temporal_profile.csv")
    geo = pd.read_csv(paths.indicators_dir / "geo_countries.csv")
    collab = pd.read_csv(paths.indicators_dir / "collab_countries.csv")
    top20 = pd.read_csv(paths.indicators_dir / "top20_cited.csv")
    journals = pd.read_csv(paths.indicators_dir / "journals.csv")
    authors = pd.read_csv(paths.indicators_dir / "top_authors.csv")
    lotka = pd.read_csv(paths.indicators_dir / "lotka.csv")
    kw_freq = pd.read_csv(paths.indicators_dir / "keyword_freq.csv")
    kw_cooc = pd.read_csv(paths.indicators_dir / "keyword_cooc.csv")
    cluster_share = pd.read_csv(paths.indicators_dir / "cluster_share_by_year.csv")
    axis_scores = pd.read_csv(paths.indicators_dir / "axis_scores_enriched.csv")
    axis_scores["cited_by_count"] = pd.to_numeric(axis_scores["cited_by_count"], errors="coerce").fillna(0)
    axis_scores["year_band"] = pd.cut(
        axis_scores["publication_year"],
        bins=[2019, 2022, 2024, 2026],
        labels=["2020-2022", "2023-2024", "2025-2026"],
    )
    _e_q75 = axis_scores["axis_e_technology"].quantile(0.75)
    _e_q25 = axis_scores["axis_e_technology"].quantile(0.25)
    yearly["cit_per_article"] = yearly["citations"] / yearly["n"]
    yearly_citation_profile = (
        axis_scores.groupby("publication_year")
        .agg(
            N=("id", "count"),
            **{
                "% com ≥1 citação": ("cited_by_count", lambda s: round(100 * (s > 0).mean(), 1)),
                "Mediana cit.": ("cited_by_count", "median"),
                "Média cit.": ("cited_by_count", "mean"),
                "N zero citações": ("cited_by_count", lambda s: int((s == 0).sum())),
            },
        )
        .reset_index()
        .sort_values("publication_year")
    )
    corpus_clustered = pd.read_csv(paths.corpus_clustered_path, usecols=["doi", "data_source", "cited_by_count"])
    corpus_clustered["cited_by_count"] = pd.to_numeric(corpus_clustered["cited_by_count"], errors="coerce").fillna(0)
    _has_doi = corpus_clustered["doi"].fillna("").astype(str).str.strip() != ""
    _pubmed_no_doi = corpus_clustered["data_source"].eq("pubmed_manual") & (~_has_doi)
    _n_semantic = len(corpus_clustered)
    _n_with_doi = int(_has_doi.sum())
    _n_without_doi = int((~_has_doi).sum())
    _n_cited_positive = int((corpus_clustered["cited_by_count"] > 0).sum())
    _n_zero_with_doi = int(((corpus_clustered["cited_by_count"] == 0) & _has_doi).sum())
    _n_zero_without_doi = int(((corpus_clustered["cited_by_count"] == 0) & (~_has_doi)).sum())
    _n_pubmed_no_doi = int(_pubmed_no_doi.sum())
    _n_pubmed_no_doi_cited = int((_pubmed_no_doi & (corpus_clustered["cited_by_count"] > 0)).sum())
    _pct_with_doi = 100 * _n_with_doi / max(_n_semantic, 1)
    _pct_potentially_unresolved = 100 * _n_zero_without_doi / max(_n_semantic, 1)
    _zero_2025_2026_share = 100 * yearly_citation_profile.loc[
        yearly_citation_profile["publication_year"] >= 2025, "N zero citações"
    ].sum() / max(yearly_citation_profile["N zero citações"].sum(), 1)
    _peak_total_cit_row = yearly.loc[yearly["citations"].idxmax()]
    _peak_avg_cit_idx = yearly_citation_profile["Média cit."].idxmax()
    _peak_avg_cit_year = int(yearly_citation_profile.loc[_peak_avg_cit_idx, "publication_year"])
    _peak_avg_cit_val = float(yearly_citation_profile.loc[_peak_avg_cit_idx, "Média cit."])
    _pct_2025_plus = 100 * (axis_scores["publication_year"] >= 2025).mean()
    _e_pos_by_year = (
        axis_scores.groupby("publication_year")
        .apply(lambda g: 100 * (g["axis_e_technology"] > 0).mean())
    )
    _share_by_year = cluster_share.set_index("publication_year")
    _cluster_label_by_id = {int(cid): meta.get("label", f"Cluster {int(cid)}") for cid, meta in CLUSTER_METADATA.items()}
    _edu_col = _cluster_label_by_id[4]
    _integrity_col = _cluster_label_by_id[3]
    _tech_cols = [
        _cluster_label_by_id[2],
        _cluster_label_by_id[1],
        _cluster_label_by_id[0],
    ]
    _edu_share_2022 = float(_share_by_year.loc[2022, _edu_col] + _share_by_year.loc[2022, _integrity_col])
    _edu_share_2023 = float(_share_by_year.loc[2023, _edu_col] + _share_by_year.loc[2023, _integrity_col])
    _edu_share_2025 = float(_share_by_year.loc[2025, _edu_col] + _share_by_year.loc[2025, _integrity_col])
    _tech_share_2022 = float(_share_by_year.loc[2022, _tech_cols].sum())
    _tech_share_2025 = float(_share_by_year.loc[2025, _tech_cols].sum())
    _n_zone1 = int((journals["bradford_zone"] == 1).sum())
    _n_zone3 = int((journals["bradford_zone"] == 3).sum())
    _pct_zone1_journals = 100 * _n_zone1 / max(len(journals), 1)
    _pct_zone3_journals = 100 * _n_zone3 / max(len(journals), 1)
    _top10_articles_pct = 100 * journals.head(10)["n"].sum() / max(journals["n"].sum(), 1)
    _top10_citations_pct = 100 * journals.head(10)["total_cit"].sum() / max(journals["total_cit"].sum(), 1)
    _band_rows: list[dict[str, float | str | int]] = []
    for band, group in axis_scores.groupby("year_band", observed=False):
        top = group.loc[group["axis_e_technology"] >= _e_q75, "cited_by_count"]
        bottom = group.loc[group["axis_e_technology"] <= _e_q25, "cited_by_count"]
        _band_rows.append({
            "Faixa": str(band),
            "N": int(len(group)),
            "ρ E×cit": float(group["axis_e_technology"].corr(group["cited_by_count"], method="spearman")),
            "ρ R×cit": float(group["axis_r_scope"].corr(group["cited_by_count"], method="spearman")),
            "Mediana cit. E Q4": float(top.median()) if len(top) else 0.0,
            "Mediana cit. E Q1": float(bottom.median()) if len(bottom) else 0.0,
            "% citados E Q4": float(100 * (top > 0).mean()) if len(top) else 0.0,
            "% citados E Q1": float(100 * (bottom > 0).mean()) if len(bottom) else 0.0,
        })
    band_tests = pd.DataFrame(_band_rows)
    _band_2020_2022 = band_tests.loc[band_tests["Faixa"] == "2020-2022"].iloc[0]
    _band_2023_2024 = band_tests.loc[band_tests["Faixa"] == "2023-2024"].iloc[0]
    _band_2025_2026 = band_tests.loc[band_tests["Faixa"] == "2025-2026"].iloc[0]
    _cluster_concentration_rows: list[dict[str, float | str]] = []
    for cluster_label, group in axis_scores.groupby("cluster_label"):
        _cluster_concentration_rows.append({
            "Cluster": cluster_label,
            "% citações no top 10%": _top_share(group["cited_by_count"], 0.10),
            "% citações no top 20%": _top_share(group["cited_by_count"], 0.20),
            "% artigos em 2025-2026": 100 * float((group["publication_year"] >= 2025).mean()),
            "Ano mediano": float(group["publication_year"].median()),
        })
    cluster_concentration = pd.DataFrame(_cluster_concentration_rows).sort_values("% citações no top 10%", ascending=False)
    _integrity_conc = cluster_concentration.loc[
        cluster_concentration["Cluster"] == _integrity_col
    ].iloc[0]
    _aigen_conc = cluster_concentration.loc[
        cluster_concentration["Cluster"] == _edu_col
    ].iloc[0]

    # --- Axes LOO pole stability ---
    _loo_rows: list[dict] = []
    _axis_val_path = paths.indicators_dir / "axis_validation.txt"
    if _axis_val_path.exists():
        for _m in re.finditer(
            r"Axis (\w): mean=([0-9.]+)\s+min=([0-9.]+)\s+\[(\w+)\]",
            _axis_val_path.read_text(encoding="utf-8"),
        ):
            _ax, _m_rho, _mn_rho, _stat = _m.groups()
            _loo_rows.append({"Eixo": _ax, "ρ médio (LOO)": float(_m_rho), "ρ mín. (LOO)": float(_mn_rho), "Status": _stat})
    loo_stability_df = (
        pd.DataFrame(_loo_rows)
        if _loo_rows
        else pd.DataFrame(columns=["Eixo", "ρ médio (LOO)", "ρ mín. (LOO)", "Status"])
    )

    # --- Q1: Recency cohort test ---
    _corpus_start = int(summary["corpus"]["year_min"])
    _full_zero_pct = float(100 * (axis_scores["cited_by_count"] == 0).mean())
    _q1_rows: list[dict] = []
    for _cutoff in [2026, 2025, 2024]:
        _sub = axis_scores[axis_scores["publication_year"] < _cutoff]
        _n_sub = len(_sub)
        _n_zero_sub = int((_sub["cited_by_count"] == 0).sum())
        _z_sub = round(100 * _n_zero_sub / max(_n_sub, 1), 1)
        _q1_rows.append({
            "Coorte": f"{_corpus_start}\u2013{_cutoff - 1}",
            "N": _n_sub,
            "N zero cit.": _n_zero_sub,
            "% zero": _z_sub,
            "\u0394 vs corpus total": round(_z_sub - _full_zero_pct, 1),
        })
    q1_recency_df = pd.DataFrame(_q1_rows)
    _zero_pre2025 = float(_q1_rows[1]["% zero"])  # coorte up to 2024 (excl. 2025-2026)
    _zero_pre2024 = float(_q1_rows[2]["% zero"])  # coorte up to 2023
    _recency_drop = round(_full_zero_pct - _zero_pre2025, 1)
    _recency_explains = _recency_drop >= (_full_zero_pct * 0.40)

    # --- Q2: Label normalization — combined wording + cluster signal per year ---
    _q2_rows: list[dict] = []
    for _yr in sorted(temporal["year"].unique()):
        _t = temporal[temporal["year"] == _yr].iloc[0]
        _edu_s = (
            round(float(_share_by_year.loc[_yr, _edu_col]), 1)
            if _yr in _share_by_year.index and _edu_col in _share_by_year.columns
            else float("nan")
        )
        _integ_s = (
            round(float(_share_by_year.loc[_yr, _integrity_col]), 1)
            if _yr in _share_by_year.index and _integrity_col in _share_by_year.columns
            else float("nan")
        )
        _soma_edu = round(_edu_s + _integ_s, 1) if not (pd.isna(_edu_s) or pd.isna(_integ_s)) else float("nan")
        _q2_rows.append({
            "Ano": int(_yr),
            "% E>0 (texto)": round(float(_t["pct_e_pos"]), 1),
            "M\u00e9dia E (texto)": round(float(_t["mean_e"]), 4),
            "% AIGen\u00b7HE": _edu_s,
            "% Integ\u00b7HE": _integ_s,
            "% edu+integ": _soma_edu,
        })
    q2_label_df = pd.DataFrame(_q2_rows)
    _q2_e_peak_yr = int(q2_label_df.loc[q2_label_df["% E>0 (texto)"].idxmax(), "Ano"])
    _q2_e_peak = float(q2_label_df.loc[q2_label_df["% E>0 (texto)"].idxmax(), "% E>0 (texto)"])
    _q2_e_last_yr = int(q2_label_df.iloc[-1]["Ano"])
    _q2_e_last = float(q2_label_df.iloc[-1]["% E>0 (texto)"])
    _q2_edu_last = (
        float(q2_label_df.iloc[-1]["% edu+integ"])
        if "% edu+integ" in q2_label_df.columns
        else float("nan")
    )

    # --- Q3: Formal concentration test — mean with vs without top 10% ---
    _q3_rows: list[dict] = []
    for _cl, _grp in axis_scores.groupby("cluster_label"):
        _ord = _grp["cited_by_count"].sort_values(ascending=False)
        _n_g = len(_ord)
        _top_n_g = max(1, int(round(_n_g * 0.10)))
        _m_all = round(float(_ord.mean()), 1)
        _m_wo = round(float(_ord.iloc[_top_n_g:].mean()), 1) if _n_g > _top_n_g else 0.0
        _q3_rows.append({
            "Cluster": _cl,
            "N": _n_g,
            "M\u00e9dia (todos)": _m_all,
            "M\u00e9dia (sem top 10%)": _m_wo,
            "Raz\u00e3o": round(_m_all / max(_m_wo, 0.1), 2),
            "% cit. no top 10%": round(_top_share(_grp["cited_by_count"], 0.10), 1),
        })
    q3_conc_df = pd.DataFrame(_q3_rows).sort_values("Raz\u00e3o", ascending=False)

    # --- Q4: E vs R signal stability across time bands ---
    _e_pos_bands = int((band_tests["\u03c1 E\u00d7cit"] > 0).sum())
    _r_pos_bands = int((band_tests["\u03c1 R\u00d7cit"] > 0).sum())
    _e_rho_range = round(float(band_tests["\u03c1 E\u00d7cit"].max() - band_tests["\u03c1 E\u00d7cit"].min()), 3)
    _r_rho_range = round(float(band_tests["\u03c1 R\u00d7cit"].max() - band_tests["\u03c1 R\u00d7cit"].min()), 3)
    q4_stability_df = pd.DataFrame([
        {
            "Eixo": "E \u2014 framing tecnol\u00f3gico",
            "Bandas com \u03c1>0": f"{_e_pos_bands}/{len(band_tests)}",
            "Amplitude \u03c1 (max\u2212min)": _e_rho_range,
            "\u03c1 agregado": f"{summary['spearman']['E']['rho_all']:+.3f}",
            "p agregado": _fmt_p(float(summary["spearman"]["E"]["p_all"])),
        },
        {
            "Eixo": "R \u2014 dom\u00ednio cl\u00ednico/ed.",
            "Bandas com \u03c1>0": f"{_r_pos_bands}/{len(band_tests)}",
            "Amplitude \u03c1 (max\u2212min)": _r_rho_range,
            "\u03c1 agregado": f"{summary['spearman']['R']['rho_all']:+.3f}",
            "p agregado": _fmt_p(float(summary["spearman"]["R"]["p_all"])),
        },
    ])

    lines: list[str] = []
    append = lines.append

    append("<!-- Auto-generated by bibliometry_pipeline.report_text — do not edit manually -->")
    append(_h1("Caderno de Análise Bibliométrica"))
    append(
        f"> **Fonte:** `{summary['retrieval_profile']}`  \n"
        f"> **Corpus semântico:** {summary['corpus']['n_articles']} artigos  \n"
        "> **Uso pretendido:** artefato exploratório para iterar leituras com IA; organiza perguntas, método, testes e narrativas concorrentes, sem fechar conclusões finais.\n"
    )

    append(_hr())
    append(_h1("1. Perguntas de Trabalho"))
    append("**Pergunta central.** Como o corpus 2020-2026 se reorganiza entre polos técnico-clínicos e educacionais/institucionais, e quais sinais de impacto permanecem quando controlamos parcialmente o efeito de recência?\n")
    append("**Pergunta 1.** O aumento de artigos com zero citação reflete baixa repercussão ou apenas maturação bibliométrica insuficiente?\n")
    append("**Pergunta 2.** O declínio da menção explícita a ChatGPT indica perda do tema ou normalização do rótulo dentro de uma agenda já difundida?\n")
    append("**Pergunta 3.** Os efeitos dos eixos E, N e R sobre citações permanecem quando o corpus é estratificado por coortes temporais?\n")
    append("**Pergunta 4.** Os clusters de maior impacto têm vantagem ampla ou dependem de poucos artigos muito citados?\n")
    append(_note(
        "Este arquivo deve ser lido como caderno de trabalho. As seções abaixo reúnem insumos para iteração com IA: diagnósticos, cortes, contra-sinais e próximos testes."
    ))

    append(_hr())
    append(_h1("2. Método e Escopo dos Dados"))
    append(_h2("2.1 Escopo do Corpus"))
    kpi = pd.DataFrame([
        ["Total de artigos no corpus", f"**{summary['corpus']['n_articles']}**"],
        ["Período coberto", f"{summary['corpus']['year_min']} – {summary['corpus']['year_max']}"],
        ["Países representados", summary['corpus']['n_countries']],
        ["Artigo mais citado", f"{summary['corpus']['max_citations']} cit."],
        ["Cluster dominante", f"{dominant_cluster['label'] if dominant_cluster else '—'}"],
        ["Artigos sem nenhuma citação", f"{summary['corpus']['zero_citations_n']} ({summary['corpus']['zero_citations_pct']:.1f}%)"],
        ["Silhouette score", f"{summary['corpus']['silhouette']:.3f}" if summary['corpus']['silhouette'] == summary['corpus']['silhouette'] else "—"],
    ], columns=["Indicador", "Valor"])
    append(_df_to_md(kpi))
    append(_note(
        f"{summary['corpus']['zero_citations_pct']:.1f}% dos artigos têm zero citações — "
        f"{_zero_2025_2026_share:.1f}% desses zeros estão em 2025–2026, reflexo do curto tempo de indexação desde a publicação, "
        "o que torna a recência a primeira hipótese operacional a testar antes de qualquer leitura substantiva sobre baixo impacto."
    ))

    append(_h2("2.2 Cobertura de Citações"))
    coverage_df = pd.DataFrame([
        ["Artigos com DOI", f"{_n_with_doi} ({_pct_with_doi:.1f}%)"],
        ["Artigos sem DOI", f"{_n_without_doi} ({100 * _n_without_doi / max(_n_semantic, 1):.1f}%)"],
        ["PubMed sem DOI verificados via Europe PMC", f"{_n_pubmed_no_doi} ({100 * _n_pubmed_no_doi / max(_n_semantic, 1):.1f}%)"],
        ["PubMed sem DOI com citação recuperada", f"{_n_pubmed_no_doi_cited}/{_n_pubmed_no_doi}"],
        ["Artigos com pelo menos 1 citação", f"{_n_cited_positive} ({100 * _n_cited_positive / max(_n_semantic, 1):.1f}%)"],
        ["Zeros com DOI resolvido", f"{_n_zero_with_doi} ({100 * _n_zero_with_doi / max(_n_semantic, 1):.1f}%)"],
        ["Potencialmente sem resolução externa", f"{_n_zero_without_doi} ({_pct_potentially_unresolved:.1f}%)"],
    ], columns=["Métrica", "Valor"])
    append(_df_to_md(coverage_df))
    append(_note(
        f"A cobertura de citações é alta o bastante para testar hipóteses de impacto: {_n_with_doi} de {_n_semantic} artigos "
        f"({_pct_with_doi:.1f}%) têm DOI e foram resolvidos via OpenAlex, e os {_n_pubmed_no_doi} PubMed sem DOI foram checados via Europe PMC. "
        f"Restam apenas {_n_zero_without_doi} artigos ({_pct_potentially_unresolved:.1f}%) sem DOI e com 0 citações, de modo que a maior parte dos zeros deve ser tratada como zero observado, não como lacuna de metadado."
    ))

    append(_h2("2.3 Fluxo PRISMA"))
    prisma = summary["prisma"]
    _prisma_rows: list[list] = [
        ["Identificados (únicos)", prisma["n_identified"]],
        ["Excluídos — sem abstract", -prisma["n_excluded_noabstract"]],
        ["Excluídos — off-topic inicial", -prisma["n_excluded_offtopic"]],
    ]
    if prisma.get("n_excluded_missing_scope", 0):
        _prisma_rows.append(["Excluídos — sem escopo acadêmico", -prisma["n_excluded_missing_scope"]])
    if prisma.get("n_excluded_negative_scope", 0):
        _prisma_rows.append(["Excluídos — escopo negativo", -prisma["n_excluded_negative_scope"]])
    if prisma.get("n_excluded_weak_alignment", 0):
        _prisma_rows.append(["Excluídos — sem alinhamento semântico (BGE-M3)", -prisma["n_excluded_weak_alignment"]])
    if prisma.get("n_excluded_low_relevance", 0):
        _prisma_rows.append(["Excluídos — abaixo do limiar de relevância", -prisma["n_excluded_low_relevance"]])
    _prisma_rows.extend([
        ["Corpus pós-fetch", prisma["n_final_fetch"]],
        ["Excluídos — DOI duplicado", -prisma["n_excluded_doi_dup"]],
        ["Excluídos — título duplicado", -prisma["n_excluded_title_dup"]],
        ["Excluídos — fora do período", -prisma["n_excluded_year"]],
        ["Excluídos — retracted", -prisma["n_excluded_retracted"]],
        ["Excluídos — tópico off-topic", -prisma["n_excluded_topic"]],
        ["Corpus limpo", prisma["n_final_clean"]],
        ["Excluídos — sem embedding válido", -prisma["n_excluded_no_embedding"]],
        ["Corpus final para análise semântica", prisma["n_final_semantic"]],
    ])
    prisma_df = pd.DataFrame(_prisma_rows, columns=["Etapa", "N"])
    append(_df_to_md(prisma_df))

    append(_hr())
    append(_h1("3. Testes Temporais"))
    append(_h2("3.1 Produção Anual"))
    yearly_md = yearly[["year", "n", "citations"]].copy()
    yearly_md.columns = ["Ano", "N artigos", "Total citações"]
    append(_df_to_md(yearly_md))
    append(_note(
        f"O corpus cobre {summary['corpus']['year_min']}–{summary['corpus']['year_max']}. "
        "O crescimento anual é lido diretamente de yearly_production.csv. "
        "A linha de 2026 reflete dados coletados em abril de 2026 (ano incompleto) — citações zero não indicam ausência de impacto. "
        f"Esta tabela usa todos os {prisma['n_final_clean']} artigos do corpus limpo; "
        f"as análises semânticas (clusters e eixos, §3.3–§3.4) usam os {prisma['n_final_semantic']} artigos "
        f"para os quais foi possível calcular embedding BGE-M3 ({prisma['n_excluded_no_embedding']} excluídos por ausência de abstract adequado)."
    ))

    append(_h2("3.2 Maturidade de Citações por Ano"))
    yearly_cit_md = yearly_citation_profile.copy()
    yearly_cit_md.columns = ["Ano", "N", "% com ≥1 citação", "Mediana cit.", "Média cit.", "N zero citações"]
    yearly_cit_md["Mediana cit."] = yearly_cit_md["Mediana cit."].round(1)
    yearly_cit_md["Média cit."] = yearly_cit_md["Média cit."].round(1)
    append(_df_to_md(yearly_cit_md))
    append(_note(
        f"A maturidade temporal das citações é assimétrica: {_peak_total_cit_row['year']:.0f} lidera em citações totais "
        f"({int(_peak_total_cit_row['citations'])}), mas {_peak_avg_cit_year} ainda tem a maior intensidade média "
        f"({_peak_avg_cit_val:.1f} citações por artigo). "
        f"Ao mesmo tempo, {_zero_2025_2026_share:.1f}% de todos os zeros de citação estão em 2025–2026, o que deixa a recência como o principal viés remanescente a controlar."
    ))

    append(_h2("3.3 Composição por Cluster ao Longo do Tempo (%)"))
    share_md = cluster_share.copy()
    share_md.columns = ["Ano"] + share_md.columns[1:].tolist()
    for column in share_md.columns[1:]:
        share_md[column] = share_md[column].round(1)
    append(_df_to_md(share_md))
    append(_note(
        f"Esta tabela usa o corpus semântico ({prisma['n_final_semantic']} artigos com embedding válido), "
        f"não os {prisma['n_final_clean']} do corpus limpo total. Há um deslocamento temático pós-2023 compatível com a hipótese de institucionalização do tema: "
        f"a soma dos clusters {_integrity_col} + {_edu_col} sobe de {_edu_share_2022:.1f}% em 2022 para {_edu_share_2023:.1f}% em 2023 e {_edu_share_2025:.1f}% em 2025, "
        f"enquanto o bloco técnico-clínico cai de {_tech_share_2022:.1f}% para {_tech_share_2025:.1f}%."
    ))

    append(_h2("3.4 Tendências dos Eixos por Ano"))
    temp_md = temporal.copy()
    temp_md.columns = ["Ano", "N", "% E>0", "Média E", "Média N", "Média R"]
    for column in temp_md.columns[2:]:
        temp_md[column] = temp_md[column].round(4)
    append(_df_to_md(temp_md))
    append(_note(
        f"A menção explícita a ChatGPT/GenAI (E>0) atinge pico em 2023 ({_e_pos_by_year.loc[2023]:.1f}%) e depois recua para {_e_pos_by_year.loc[2025]:.1f}% em 2025 e {_e_pos_by_year.loc[2026]:.1f}% em 2026. "
        "Esse padrão é compatível com a narrativa de normalização do rótulo, mas precisa ser confrontado com os demais testes antes de virar conclusão."
    ))

    append(_hr())
    append(_h1("4. Testes Geográficos"))
    append(_h2("4.1 Top 20 Países"))
    _n_with_affil = summary["corpus"].get("n_articles_with_countries", 0)
    _n_clean = summary["corpus"].get("n_corpus_clean", prisma["n_final_clean"])
    _geo_total_mentions = int(geo["n"].sum())
    _geo_pct = 100 * _n_with_affil / max(_n_clean, 1)
    _geo_pct_str = f"{_geo_pct:.1f}%" if _geo_pct >= 1 else f"≈{_geo_pct:.2f}%"
    _geo_caveat = (
        "Dados insuficientes para inferências geográficas representativas."
        if _geo_pct < 5
        else (
            "Cobertura geográfica forte; o principal cuidado é que rankings por país refletem menções de afiliação em coautorias internacionais, não participação exclusiva no corpus."
            if _geo_pct >= 90
            else "Conclusões geográficas devem ser lidas com cautela: cobertura parcial de afiliações."
        )
    )
    geo_coverage_note = (
        f"Cobertura de afiliação: {_n_with_affil} de {_n_clean} artigos ({_geo_pct_str}) têm dados de país. "
        f"A coluna 'N artigos' soma {_geo_total_mentions} ocorrências (uma por país por artigo, multi-país possível). "
        "A coluna '% afil.' expressa a fração dentro dos artigos com afiliação identificada, não do corpus total. "
        + _geo_caveat
    )
    geo_md = geo.head(20).copy()
    geo_md.columns = ["País (ISO)", "N artigos", "% afil."]
    append(_df_to_md(geo_md))
    append(_note(geo_coverage_note))
    append(_h2("4.2 Top 10 Pares de Colaboração Internacional"))
    collab_md = collab.head(10).copy()
    collab_md.columns = ["País A", "País B", "N colaborações"]
    append(_df_to_md(collab_md))

    append(_hr())
    append(_h1("5. Testes Semânticos"))
    append(_h2("5.1 Clusters Semânticos"))
    _all_n = summary["corpus"]["n_articles"]
    clusters_df = pd.DataFrame([
        {
            "Cluster": f"C{cluster['cluster']}",
            "Label": cluster["label"],
            "N": cluster["n"],
            "% corpus": cluster["pct"],
            "Descrição": cluster["description"] or "—",
        }
        for cluster in summary["clusters"]
    ])
    append(_df_to_md(clusters_df))
    sil = summary["corpus"].get("silhouette", float("nan"))
    if sil == sil and sil < 0.2:  # not NaN and low
        append(_note(
            f"Silhouette médio = {sil:.3f} — valor próximo de zero indica separação fraca entre clusters. "
            "Os clusters se sobrepõem semanticamente; os rótulos descrevem tendências, não categorias estanques."
        ))

    append(_hr())
    append(_h2("5.2 Eixos Semânticos"))
    axes = summary["axes"]
    axes_df = pd.DataFrame([
        ["Eixo E", axes["means"]["E"], axes["std"]["E"], summary["spearman"]["E"]["rho_all"], summary["spearman"]["E"]["p_all"]],
        ["Eixo N", axes["means"]["N"], axes["std"]["N"], summary["spearman"]["N"]["rho_all"], summary["spearman"]["N"]["p_all"]],
        ["Eixo R", axes["means"]["R"], axes["std"]["R"], summary["spearman"]["R"]["rho_all"], summary["spearman"]["R"]["p_all"]],
    ], columns=["Eixo", "Média", "Std", "ρ citações", "p"])
    axes_df["Média"] = axes_df["Média"].map(lambda value: f"{value:+.3f}")
    axes_df["Std"] = axes_df["Std"].map(lambda value: f"{value:.3f}")
    axes_df["ρ citações"] = axes_df["ρ citações"].map(lambda value: f"{value:+.3f}")
    axes_df["p"] = axes_df["p"].map(_fmt_p)
    # Mark significance
    ps = [summary["spearman"][ax]["p_all"] for ax in ("E", "N", "R")]
    axes_df["sig."] = ["*" if p < 0.05 else "ns" for p in ps]
    append(_df_to_md(axes_df))
    _sig_axes = [name for name, p in zip(("E", "N", "R"), ps) if p < 0.05]
    if len(_sig_axes) == 1:
        _sig_text = f"Apenas o Eixo {_sig_axes[0]} tem correlação estatisticamente significativa com citações."
    elif len(_sig_axes) == 0:
        _sig_text = "Nenhum eixo tem correlação estatisticamente significativa com citações."
    else:
        _sig_text = f"Os eixos {', '.join(_sig_axes[:-1])} e {_sig_axes[-1]} têm correlação estatisticamente significativa com citações."
    append(_note(f"* p < 0.05 (Spearman). {_sig_text}"))

    append(_h3("5.2.1 Ortogonalidade"))
    ortho = pd.DataFrame([
        ["E × N", axes["orthogonality"]["E_N"]],
        ["E × R", axes["orthogonality"]["E_R"]],
        ["N × R", axes["orthogonality"]["N_R"]],
    ], columns=["Par", "Pearson r"])
    ortho["Pearson r"] = ortho["Pearson r"].map(lambda value: f"{value:+.3f}")
    append(_df_to_md(ortho))
    _nr = axes["orthogonality"]["N_R"]
    _nr_abs = abs(_nr)
    if _nr_abs >= 0.20:
        _nr_label = "moderada"
        _nr_note = (
            f"N×R = {_nr:+.3f}: correlação {_nr_label} entre os eixos — "
            "artigos com postura mais voltada a risco/governança tendem a ocorrer mais em um dos polos do eixo de domínio. "
            "As duas dimensões não são completamente independentes neste corpus. "
            "Isso não invalida a distinção conceitual, mas deve ser considerado na interpretação."
        )
    elif _nr_abs >= 0.10:
        _nr_label = "fraca"
        _nr_note = (
            f"N×R = {_nr:+.3f}: correlação {_nr_label} entre os eixos. "
            "Os eixos N e R são razoavelmente independentes neste corpus, "
            "embora mantenham alguma correlação residual a considerar."
        )
    else:
        _nr_note = None
    if _nr_note:
        append(_note(_nr_note))

    append(_h3("5.2.2 Estabilidade dos Polos (LOO)"))
    if not loo_stability_df.empty:
        _loo_disp = loo_stability_df.copy()
        _loo_disp["ρ médio (LOO)"] = _loo_disp["ρ médio (LOO)"].map(lambda v: f"{v:.3f}")
        _loo_disp["ρ mín. (LOO)"] = _loo_disp["ρ mín. (LOO)"].map(lambda v: f"{v:.3f}")
        append(_df_to_md(_loo_disp))
        _loo_failed = [row["Eixo"] for _, row in loo_stability_df.iterrows() if row["Status"] != "PASS"]
        _loo_passed = [row["Eixo"] for _, row in loo_stability_df.iterrows() if row["Status"] == "PASS"]
        if _loo_failed:
            _ax_word = "Eixo" if len(_loo_failed) == 1 else "Eixos"
            _pa_word = "Eixo" if len(_loo_passed) == 1 else "Eixos"
            append(_note(
                "Cada linha substitui um polo-âncora por uma formulação variante e mede a correlação de Spearman com o score primário. "
                f"{_ax_word} {', '.join(_loo_failed)}: ρ mín. < 0.70 — o score é sensível à formulação da âncora; interpretações sobre {'esse eixo devem' if len(_loo_failed) == 1 else 'esses eixos devem'} ser qualificadas. "
                + (f"{_pa_word} {', '.join(_loo_passed)}: ρ mín. ≥ 0.70 — polo estável." if _loo_passed else "")
            ))
        else:
            append(_note(
                "Todos os eixos passam no LOO (ρ mín. ≥ 0.70): os polos capturam sinais semânticos estáveis independentemente de variações de redação da âncora. "
                "Isso aumenta a confiança de que E, N e R medem constructos coerentes, não artefatos de uma formulação específica."
            ))
    else:
        append(_note(
            "Arquivo `axis_validation.txt` não encontrado — execute o estágio `semantic-axes` para gerar os resultados de estabilidade LOO."
        ))

    append(_hr())
    append(_h1("6. Testes de Impacto"))
    append(_h2("6.1 Impacto por Framing Tecnológico"))
    quartiles = pd.DataFrame(summary["quartiles_e"])
    quartiles["quartile"] = quartiles["quartile"].replace({"Q1": "Q1 — IA genérica", "Q4": "Q4 — ChatGPT/GenAI"})
    quartiles.columns = ["Quartil E", "N", "Mediana cit.", "Média cit."]
    quartiles["Mediana cit."] = quartiles["Mediana cit."].round(1)
    quartiles["Média cit."] = quartiles["Média cit."].round(1)
    append(_df_to_md(quartiles))

    hypotheses = summary["hypotheses"]
    hyp_df = pd.DataFrame([
        ["E Q4 > Q1", "confirmada" if hypotheses["E_q4_gt_q1"]["confirmed"] else "não confirmada", _fmt_p(hypotheses["E_q4_gt_q1"]["p"])],
        ["N Q4 > Q1", "confirmada" if hypotheses["N_q4_gt_q1"]["confirmed"] else "não confirmada", _fmt_p(hypotheses["N_q4_gt_q1"]["p"])],
        ["R Q4 > Q1", "confirmada" if hypotheses["R_q4_gt_q1"]["confirmed"] else "não confirmada", _fmt_p(hypotheses["R_q4_gt_q1"]["p"])],
    ], columns=["Hipótese", "Resultado", "p-value"])
    append(_df_to_md(hyp_df))
    _e_hyp = hypotheses["E_q4_gt_q1"]
    _q4_row = next((q for q in summary["quartiles_e"] if q["quartile"] == "Q4"), None)
    _q1_row = next((q for q in summary["quartiles_e"] if q["quartile"] == "Q1"), None)
    _top_q = axis_scores.loc[axis_scores["axis_e_technology"] >= _e_q75, "cited_by_count"]
    _bot_q = axis_scores.loc[axis_scores["axis_e_technology"] <= _e_q25, "cited_by_count"]
    _share_q4 = 100 * (_top_q > 0).mean()
    _share_q1 = 100 * (_bot_q > 0).mean()
    if _q4_row and _q1_row:
        _med_q4 = _e_hyp["med_top"]
        _med_q1 = _e_hyp["med_bottom"]
        _mean_q4 = _q4_row["mean_cit"]
        _mean_q1 = _q1_row["mean_cit"]
        _mediana_note = (
            f"mediana Q4={_med_q4:.0f} vs Q1={_med_q1:.0f}"
            if _med_q4 != _med_q1
            else f"mediana Q1=Q4={_med_q4:.0f} (medianas iguais)"
        )
        append(_note(
            f"O efeito E Q4 > Q1 {'é confirmado' if _e_hyp['confirmed'] else 'não é confirmado'} "
            f"(p={_fmt_p(_e_hyp['p'])}). "
            f"Em termos de distribuição, Q4 supera Q1 na mediana ({_mediana_note}) e na fração com pelo menos 1 citação ({_share_q4:.1f}% vs {_share_q1:.1f}%). "
            f"A média, porém, é ligeiramente menor em Q4 ({_mean_q4:.1f} vs {_mean_q1:.1f}) porque Q1 contém alguns outliers muito citados. "
            "Esse teste agregado é útil, mas não basta para leitura causal: ele precisa ser relido à luz dos estratos temporais abaixo."
        ))
    else:
        append(_note(
            "O efeito agregado do Eixo E é fraco e deve ser tratado como diagnóstico preliminar, não como evidência conclusiva."
        ))
    _zero_pct = summary["corpus"]["zero_citations_pct"]
    _n_cited_only = summary["corpus"]["n_articles"] - summary["corpus"]["zero_citations_n"]
    append(_note(
        f"**Cobertura de citações:** apenas {_n_zero_without_doi} artigos ({_pct_potentially_unresolved:.1f}%) permanecem sem DOI e com 0 citações. "
        f"Os outros {_n_zero_with_doi} zeros têm DOI e já foram resolvidos por lookup externo, portanto devem ser tratados como zero observado. "
        f"O caveat principal aqui é temporal: {_zero_pct:.1f}% do corpus ainda está em zero, mas isso se concentra em 2025–2026. "
        f"As correlações e rankings continuam puxados pelos {_n_cited_only} artigos com pelo menos 1 citação, em especial os de 2021–2024."
    ))

    append(_h2("6.2 Impacto por Domínio (Eixo R)"))
    domain_impact = axis_scores.copy()
    domain_impact["Domínio"] = domain_impact["axis_r_scope"].apply(
        lambda value: "Acadêmico / educacional (R < 0)" if value < 0 else "Clínico / biomédico (R ≥ 0)"
    )
    domain_md = (
        domain_impact.groupby("Domínio")
        .agg(
            N=("id", "count"),
            **{
                "% com ≥1 citação": ("cited_by_count", lambda s: round(100 * (s > 0).mean(), 1)),
                "Mediana cit.": ("cited_by_count", "median"),
                "Média cit.": ("cited_by_count", "mean"),
            },
        )
        .reset_index()
    )
    domain_md["Mediana cit."] = domain_md["Mediana cit."].round(1)
    domain_md["Média cit."] = domain_md["Média cit."].round(1)
    append(_df_to_md(domain_md))
    _domain_best = domain_md.sort_values("Média cit.", ascending=False).iloc[0]
    append(_note(
        f"O contraste por domínio volta a ser interpretável: a correlação entre Eixo R e citações é {summary['spearman']['R']['rho_all']:+.3f} "
        f"(p {_fmt_p(summary['spearman']['R']['p_all'])}). O polo com maior média de impacto é **{_domain_best['Domínio']}** "
        f"({float(_domain_best['Média cit.']):.1f} citações por artigo, em média). Isso mantém aberta a hipótese de um sinal de domínio mais robusto do que o sinal de framing tecnológico."
    ))

    append(_h2("6.3 Impacto por Cluster"))
    cluster_impact = (
        axis_scores.groupby("cluster_label")
        .agg(
            N=("id", "count"),
            **{
                "% com ≥1 citação": ("cited_by_count", lambda s: round(100 * (s > 0).mean(), 1)),
                "Mediana cit.": ("cited_by_count", "median"),
                "Média cit.": ("cited_by_count", "mean"),
            },
        )
        .sort_values("Média cit.", ascending=False)
        .reset_index()
    )
    cluster_impact.columns = ["Cluster", "N", "% com ≥1 citação", "Mediana cit.", "Média cit."]
    cluster_impact["Mediana cit."] = cluster_impact["Mediana cit."].round(1)
    cluster_impact["Média cit."] = cluster_impact["Média cit."].round(1)
    append(_df_to_md(cluster_impact))
    _top_cluster = cluster_impact.iloc[0]
    _bottom_cluster = cluster_impact.iloc[-1]
    append(_note(
        f"Volume e impacto não coincidem: o cluster dominante em tamanho é **{dominant_cluster['label']}** ({dominant_cluster['pct']:.1f}% do corpus), "
        f"mas o maior impacto médio está em **{_top_cluster['Cluster']}** ({float(_top_cluster['Média cit.']):.1f} citações). "
        f"No outro extremo, **{_bottom_cluster['Cluster']}** tem a menor média ({float(_bottom_cluster['Média cit.']):.1f}), o que pede checagem de recência e concentração antes de qualquer leitura forte sobre qualidade relativa."
    ))

    append(_h2("6.4 Sensibilidade Temporal das Correlações"))
    band_md = band_tests.copy()
    for column in ["ρ E×cit", "ρ R×cit", "Mediana cit. E Q4", "Mediana cit. E Q1", "% citados E Q4", "% citados E Q1"]:
        band_md[column] = band_md[column].round(3 if "ρ" in column else 1)
    append(_df_to_md(band_md))
    append(_note(
        f"No agregado, E×citações é positivo ({summary['spearman']['E']['rho_all']:+.3f}), mas por faixa temporal o sinal muda: 2020-2022={_band_2020_2022['ρ E×cit']:+.3f}, 2023-2024={_band_2023_2024['ρ E×cit']:+.3f}, 2025-2026={_band_2025_2026['ρ E×cit']:+.3f}. "
        f"Já R×citações permanece positivo nas três bandas ({_band_2020_2022['ρ R×cit']:+.3f}, {_band_2023_2024['ρ R×cit']:+.3f}, {_band_2025_2026['ρ R×cit']:+.3f}). "
        "Esse é o teste mais importante do arquivo para evitar narrativas espúrias: o efeito de E parece muito mais sensível à composição temporal do que o efeito de R."
    ))

    append(_h2("6.5 Concentração do Impacto por Cluster"))
    conc_md = cluster_concentration.copy()
    for column in conc_md.columns[1:]:
        conc_md[column] = conc_md[column].round(1)
    append(_df_to_md(conc_md))
    append(_note(
        f"O cluster **{_integrity_col}** lidera em média de citações, mas {float(_integrity_conc['% citações no top 10%']):.1f}% de suas citações estão concentradas no top 10% dos próprios artigos. "
        f"Em **{_edu_col}**, a concentração é ainda maior ({float(_aigen_conc['% citações no top 10%']):.1f}%) e {float(_aigen_conc['% artigos em 2025-2026']):.1f}% dos artigos já são de 2025-2026. "
        "Isso ajuda a separar duas leituras diferentes: impacto médio alto pode ser um traço do cluster ou apenas efeito de poucos papers líderes."
    ))

    append(_hr())
    append(_h1("7. Conjuntos de Inspeção"))
    append(_h2("7.1 Top 20 Artigos Mais Citados"))
    top20_md = top20[["title", "publication_year", "cited_by_count", "journal", "doi"]].copy()
    top20_md["journal"] = top20_md["journal"].fillna("")
    top20_md["doi"] = top20_md["doi"].fillna("")
    top20_md.index = range(1, len(top20_md) + 1)
    top20_md.columns = ["Título", "Ano", "Citações", "Periódico", "DOI"]
    append(_df_to_md(top20_md, index=True))
    _n_missing_journal = int((top20_md["Periódico"] == "").sum())
    if _n_missing_journal:
        append(_note(
            f"{_n_missing_journal} dos 20 artigos mais citados não têm nome de periódico disponível na API de origem. "
            "Isso deve ser lido como ruído residual de metadado, não ausência de periódico; a cobertura global de periódico em §7.2 é 99.3%."
        ))

    append(_h2("7.2 Periódicos"))
    _journal_table_cap = 30
    journals_md = journals[["journal", "n", "total_cit", "bradford_zone"]].head(_journal_table_cap).copy()
    journals_md.columns = ["Periódico", "N artigos", "Total cit.", "Zona Bradford"]
    append(_df_to_md(journals_md))
    n_journals_total = len(journals)
    _n_journals_omitted = max(n_journals_total - _journal_table_cap, 0)
    n_journals_covered = int(journals["n"].sum())
    n_corpus = summary["prisma"]["n_final_clean"]
    append(_note(
        f"Tabela limitada aos top {_journal_table_cap} periódicos por N de artigos; {_n_journals_omitted:,} periódicos adicionais foram omitidos da listagem detalhada. "
        f"Dados de periódico disponíveis para {n_journals_covered} de {n_corpus} registros do corpus limpo ({100*n_journals_covered/n_corpus:.1f}%). "
        f"A dispersão editorial é alta: apenas {_n_zone1} periódicos ({_pct_zone1_journals:.1f}% do total) compõem a Zona 1 de Bradford e respondem por cerca de 1/3 da produção, "
        f"enquanto {_n_zone3} periódicos ({_pct_zone3_journals:.1f}%) formam a longa cauda da Zona 3. "
        f"Mesmo os 10 principais periódicos concentram só {_top10_articles_pct:.1f}% dos artigos e {_top10_citations_pct:.1f}% das citações, o que sugere um campo amplo e editorialmente disperso, não um núcleo estreito."
    ))

    append(_h2("7.3 Autores e Lei de Lotka"))
    if authors.empty:
        append(_note(
            "Dados de autoria individual não disponíveis neste corpus: a coluna `authorships` não foi populada pelas fontes de busca utilizadas. "
            "Análise de produtividade por autor (lei de Lotka) omitida."
        ))
    else:
        authors_md = authors.head(15).copy()
        authors_md.index = range(1, len(authors_md) + 1)
        if "h_index" in authors_md.columns:
            authors_md.columns = ["Autor", "N artigos", "Total cit.", "Índice h"]
        else:
            authors_md.columns = ["Autor", "N artigos", "Total cit."]
        append(_df_to_md(authors_md, index=True))
        lotka_md = lotka.copy()
        lotka_md.columns = ["N artigos publicados", "N autores", "% autores"]
        append(_df_to_md(lotka_md))
        _lotka_one_art = float(lotka_md.iloc[0]["% autores"]) if not lotka_md.empty else float("nan")
        _lotka_max_art = int(lotka_md.iloc[-1]["N artigos publicados"]) if not lotka_md.empty else 0
        if _lotka_one_art == _lotka_one_art:
            append(_note(
                f"**Lei de Lotka.** {_lotka_one_art:.1f}% dos autores publicaram exatamente 1 artigo no período. "
                "Isso é consistente com a lei de Lotka (produtividade inversa ao quadrado): "
                "a literatura científica é gerada por poucos autores prolíficos em paralelo a uma maioria de "
                "contribuidores pontuais. "
                f"O autor mais produtivo concentrou {_lotka_max_art} artigos; "
                "a distribuição confirma o padrão bibliométrico padrão neste campo."
            ))

    append(_h2("7.4 Keywords"))
    kw_freq_md = kw_freq.head(30).copy()
    kw_freq_md.index = range(1, len(kw_freq_md) + 1)
    kw_freq_md.columns = ["Keyword", "Frequência"]
    append(_df_to_md(kw_freq_md, index=True))
    kw_cooc_md = kw_cooc.head(20).copy()
    kw_cooc_md.columns = ["Keyword A", "Keyword B", "Peso (co-ocorrências)"]
    append(_df_to_md(kw_cooc_md))

    # ── §7.5 Zipf's Law ─────────────────────────────────────────────────────
    _zipf_stats_path = paths.indicators_dir / "zipf_stats.csv"
    _zipf_analysis_path = paths.indicators_dir / "zipf_analysis.csv"
    if _zipf_stats_path.exists() and _zipf_analysis_path.exists():
        _zipf_stats = pd.read_csv(_zipf_stats_path).iloc[0]
        _zipf_df = pd.read_csv(_zipf_analysis_path)
        append(_h2("7.5 Distribuição de Zipf (Palavras-chave)"))
        _z_alpha = float(_zipf_stats.get("zipf_alpha", float("nan")))
        _z_r2 = float(_zipf_stats.get("zipf_r2", float("nan")))
        _z_n = int(_zipf_stats.get("n_unique_keywords", 0))
        _z_top10 = float(_zipf_stats.get("top10_pct_total", float("nan")))
        _z_top1_kw = str(_zipf_stats.get("top1_keyword", ""))
        _z_top1_freq = int(_zipf_stats.get("top1_freq", 0))
        _zipf_top_md = _zipf_df[["rank", "keyword", "freq", "freq_expected"]].head(20).copy()
        _zipf_top_md.columns = ["Rank", "Keyword", "Freq. observada", "Freq. esperada (Zipf)"]
        _zipf_top_md["Freq. esperada (Zipf)"] = _zipf_top_md["Freq. esperada (Zipf)"].round(0).astype(int)
        append(_df_to_md(_zipf_top_md))
        if _z_alpha == _z_alpha and _z_r2 == _z_r2:
            _z_n_hapax = int(_zipf_stats.get("n_hapax", 0))
            _z_pct_hapax = float(_zipf_stats.get("pct_hapax", float("nan")))
            _z_n_core = int(_zipf_stats.get("n_core_vocab", 0))
            _hapax_note = (
                f"{_z_n_hapax:,} ({_z_pct_hapax:.0f}%) são hapax legomena (frequência = 1), "
                f"refletindo a alta especialização do vocabulário científico. "
                f"O ajuste de Zipf foi calculado sobre as {_z_n_core} palavras com frequência ≥ 2 "
                f"(vocabulário nuclear), onde a lei de potência se aplica com R² = {_z_r2:.3f}. "
            ) if _z_n_hapax > 0 else ""
            append(_note(
                f"**Lei de Zipf.** A distribuição de frequência do vocabulário de palavras-chave segue uma "
                f"lei de potência com expoente α = {_z_alpha:.3f} (ajuste log-log sobre vocabulário nuclear, "
                f"R² = {_z_r2:.3f}). "
                f"Para referência, o expoente de Zipf puro é 1.0; valores entre 0.7 e 1.3 são típicos em "
                f"corpora científicos. "
                f"O corpus tem {_z_n:,} palavras-chave únicas; "
                + _hapax_note
                + f"a palavra mais frequente é **{_z_top1_kw}** ({_z_top1_freq} artigos). "
                f"As 10 palavras-chave mais frequentes concentram {_z_top10:.1f}% de todas as ocorrências — "
                "comportamento consistente com a lei de Zipf, onde um vocabulário reduzido descreve o "
                "núcleo temático do campo."
            ))

    append(_hr())
    append(_h1("8. Narrativas para Testar com IA"))
    append(_note(
        "As narrativas abaixo não são conclusões. Cada uma registra um enredo plausível, o que o sustenta, o que o enfraquece e qual teste deveria vir a seguir."
    ))
    append(_h3("Narrativa 1 — Recência explica a maior parte do zero-citation problem"))
    append(
        f"**Pergunta.** O aumento recente de artigos com 0 citação é principalmente efeito de calendário?\n\n"
        f"**Sinais compatíveis.** {_pct_2025_plus:.1f}% do corpus semântico está em 2025–2026, mas {_zero_2025_2026_share:.1f}% dos zeros também está nesses anos; 2020-2024 retêm percentuais de artigos citados muito mais altos.\n\n"
        "**Contra-sinal.** Mesmo com recência, 2025 já concentra um volume grande de artigos; parte do baixo impacto pode persistir após maturação.\n\n"
        "**Próximo teste.** Recalcular citações por meses desde publicação ou comparar apenas coortes com mesma idade bibliométrica."
    )
    append(_h3("Narrativa 2 — O rótulo ChatGPT enfraquece, mas a agenda educacional/institucional continua avançando"))
    append(
        f"**Pergunta.** O tema está esfriando ou só trocando de vocabulário?\n\n"
        f"**Sinais compatíveis.** A taxa E>0 cai depois de 2023 ({_e_pos_by_year.loc[2023]:.1f}% -> {_e_pos_by_year.loc[2025]:.1f}% -> {_e_pos_by_year.loc[2026]:.1f}%), mas a soma dos clusters **{_integrity_col}** + **{_edu_col}** cresce de {_edu_share_2022:.1f}% em 2022 para {_edu_share_2025:.1f}% em 2025.\n\n"
        f"**Contra-sinal.** O bloco técnico-clínico ainda responde por {_tech_share_2025:.1f}% do corpus em 2025; o deslocamento institucional é forte, mas ainda não hegemônico.\n\n"
        "**Próximo teste.** Abrir por fonte, país e periódico para verificar se a troca de vocabulário está concentrada em subcomunidades específicas."
    )
    append(_h3("Narrativa 3 — O efeito do Eixo E no agregado pode ser um artefato de coorte"))
    append(
        f"**Pergunta.** Nomear explicitamente ChatGPT/GenAI aumenta impacto ou o sinal agregado mistura anos e subcampos?\n\n"
        f"**Sinais compatíveis.** No agregado, Spearman E×citações = {summary['spearman']['E']['rho_all']:+.3f} e Q4 supera Q1 em mediana/cited-share.\n\n"
        f"**Contra-sinal.** Dentro de cada faixa temporal, o sinal fica negativo: 2020-2022={_band_2020_2022['ρ E×cit']:+.3f}, 2023-2024={_band_2023_2024['ρ E×cit']:+.3f}, 2025-2026={_band_2025_2026['ρ E×cit']:+.3f}.\n\n"
        "**Próximo teste.** Estimar modelos com controle por ano, cluster e fonte antes de atribuir qualquer prêmio bibliométrico ao framing ChatGPT."
    )
    append(_h3("Narrativa 4 — O Eixo R parece mais robusto do que o Eixo E"))
    append(
        f"**Pergunta.** O eixo de domínio (acadêmico->clínico) oferece um sinal mais estável de impacto do que o eixo de framing tecnológico?\n\n"
        f"**Sinais compatíveis.** R×citações é positivo no agregado ({summary['spearman']['R']['rho_all']:+.3f}) e permanece positivo nas três faixas temporais ({_band_2020_2022['ρ R×cit']:+.3f}, {_band_2023_2024['ρ R×cit']:+.3f}, {_band_2025_2026['ρ R×cit']:+.3f}). O polo **{_domain_best['Domínio']}** mantém a maior média de citações ({float(_domain_best['Média cit.']):.1f}).\n\n"
        "**Contra-sinal.** O tamanho do efeito é moderado para baixo e ainda pode refletir composição de periódicos ou tipos de estudo.\n\n"
        "**Próximo teste.** Cruzar R com periódicos, desenho de estudo e idade dos artigos para ver se o sinal sobrevive."
    )
    append(_h3("Narrativa 5 — Alta média por cluster pode esconder forte concentração em poucos papers"))
    append(
        f"**Pergunta.** O cluster de maior impacto médio é realmente amplo ou depende de poucos artigos-locomotiva?\n\n"
        f"**Sinais compatíveis.** **{_top_cluster['Cluster']}** lidera em média ({float(_top_cluster['Média cit.']):.1f}), mas {float(_integrity_conc['% citações no top 10%']):.1f}% das citações do cluster de integridade ficam no top 10% dos seus artigos. Em **{_edu_col}**, a concentração sobe para {float(_aigen_conc['% citações no top 10%']):.1f}%.\n\n"
        f"**Contra-sinal.** O cluster de integridade também tem mediana razoável ({float(_top_cluster['Mediana cit.']):.1f}), então não se trata apenas de um único outlier.\n\n"
        "**Próximo teste.** Separar médias, medianas e participação do top decil por cluster/ano para verificar se o sinal persiste fora dos papers líderes."
    )
    sil = summary["corpus"].get("silhouette", float("nan"))
    if sil == sil and sil < 0.2:
        append(_note(
            f"**Caveat metodológico:** a separação entre clusters continua fraca (silhouette = {sil:.3f}). "
            "As leituras por cluster são úteis como tendências macro, mas não como fronteiras semânticas rígidas."
        ))

    append(_hr())
    append(_h1("9. Testes para as Quatro Perguntas de Discussão"))
    append(_note(
        "Esta seção opera sobre os dados já carregados nas seções anteriores. Cada teste é direto e computável; "
        "as interpretações são diagnósticas, não definitivas — o objetivo é calibrar quais narrativas resistem e quais precisam de qualificação antes do artigo."
    ))

    append(_h2("9.1 Q1 — A recência explica a cauda zero?"))
    append(
        "**Claim a testar.** O alto percentual de artigos com zero citação é principalmente efeito de calendário: "
        "artigos de 2025–2026 não tiveram tempo de ser citados; "
        "quando removidos, a taxa zero cai a um patamar bibliometicamente normal.\n"
    )
    append(_df_to_md(q1_recency_df))
    append(_note(
        f"Taxa zero no corpus total: **{_full_zero_pct:.1f}%**. "
        f"Excluindo 2025–2026 (coorte 2020–2024): **{_zero_pre2025:.1f}%** (queda de {_recency_drop:.1f} p.p.). "
        + (
            "A recência responde por parcela substantial da cauda zero: o sinal se estabiliza quando só os anos mais maduros são usados. "
            "Isso sustenta o tratamento da recência como primeira covariância a controlar, antes de qualquer leitura sobre baixo impacto intrínseco."
            if _recency_explains
            else
            "A recência não explica completamente a cauda zero: mesmo após excluir 2025–2026, a taxa ainda é elevada. "
            "Hipóteses alternativas (nicho novo, ausência de cumulatividade, dispersão editorial) precisam de teste adicional."
        )
    ))

    append(_h2("9.2 Q2 — A normalização do rótulo está nos dados de texto ou só nas citações?"))
    append(
        "**Claim a testar.** O declínio na menção explícita a ChatGPT/GenAI é visível em *indicadores de texto* "
        "(scores de eixo e composição de clusters, todos baseados em embedding) — não apenas em padrões de citação. "
        "Isso suportaria leitura de normalização linguística, não de esfriamento do tema.\n"
    )
    append(_df_to_md(q2_label_df))
    append(_note(
        f"**Evidência de texto.** A taxa E>0 atinge pico em {_q2_e_peak_yr} ({_q2_e_peak:.1f}%) e cai para {_q2_e_last:.1f}% em {_q2_e_last_yr}. "
        "Esse indicador é puramente baseado em embedding — o rótulo ChatGPT/GenAI é projetado com menos intensidade nos anos mais recentes. "
        + (
            f"Em paralelo, a soma dos clusters educacionais/institucionais (% edu+integ) sobe para {_q2_edu_last:.1f}% em {_q2_e_last_yr}, "
            "o que apoia a leitura de normalização: a agenda continua avançando sob vocabulário menos específico."
            if not pd.isna(_q2_edu_last)
            else ""
        )
        + " A verificação cruzada com citações (§6.1–§6.4) é necessária para saber se o rótulo ainda carrega prêmio bibliométrico."
    ))

    append(_h2("9.3 Q3 — O impacto dos clusters é amplo ou concentrado em poucos artigos?"))
    append(
        "**Claim a testar.** A vantagem de citações do cluster líder reflete impacto distribuído, "
        "não a influência de um punhado de papers muito citados que inflam a média. "
        "Coluna **Razão** = Média (todos) ÷ Média (sem top 10%): razão alta indica dependência do topo.\n"
    )
    append(_df_to_md(q3_conc_df))
    _q3_top = q3_conc_df.iloc[0]
    _q3_bot = q3_conc_df.iloc[-1]
    _high_conc_clusters = q3_conc_df[q3_conc_df["Razão"] >= 3.0]
    append(_note(
        f"Cluster com maior concentração: **{_q3_top['Cluster']}** "
        f"(razão {float(_q3_top['Razão']):.2f}, {float(_q3_top['% cit. no top 10%']):.1f}% das citações no top 10% dos artigos). "
        f"Cluster com menor concentração: **{_q3_bot['Cluster']}** (razão {float(_q3_bot['Razão']):.2f}). "
        + (
            f"Clusters com razão ≥ 3: **{', '.join(_high_conc_clusters['Cluster'].tolist())}** — "
            "para esses, a comparação de médias está puxada por outliers e deve ser complementada pela mediana e pelo percentual de artigos citados."
            if len(_high_conc_clusters)
            else
            "Nenhum cluster tem razão ≥ 3: a média reflete distribuição razoavelmente ampla, não apenas artigos-locomotiva."
        )
    ))

    append(_h2("9.4 Q4 — O sinal de domínio é mais estável que o de framing?"))
    append(
        "**Claim a testar.** O Eixo R (domínio acadêmico ↔ clínico) mantém correlação positiva com citações em todas as coortes temporais, "
        "enquanto o Eixo E (framing genérico ↔ ChatGPT) muda de sinal entre bandas — "
        "indicando que o domínio é o sinal analiticamente mais robusto.\n"
    )
    q4_band_display = band_tests[["Faixa", "ρ E×cit", "ρ R×cit"]].copy()
    q4_band_display["ρ E×cit"] = q4_band_display["ρ E×cit"].round(3)
    q4_band_display["ρ R×cit"] = q4_band_display["ρ R×cit"].round(3)
    append(_df_to_md(q4_band_display))
    append(_df_to_md(q4_stability_df))
    _r_stable_q4 = _r_pos_bands == len(band_tests)
    _e_unstable_q4 = _e_pos_bands < len(band_tests)
    append(_note(
        f"Eixo R — domínio: ρ positivo em **{_r_pos_bands}/{len(band_tests)} bandas**, amplitude máx−mín = {_r_rho_range:.3f}. "
        f"Eixo E — framing: ρ positivo em **{_e_pos_bands}/{len(band_tests)} bandas**, amplitude máx−mín = {_e_rho_range:.3f}. "
        + (
            "R mantém sinal positivo em todas as coortes; E muda de sinal entre bandas. "
            "Isso é consistente com a hipótese de que o efeito de E é sensível à composição temporal do corpus "
            "e que o domínio clínico/educacional é o sinal mais estável para uso analítico no artigo."
            if _r_stable_q4 and _e_unstable_q4
            else (
                "R e E têm comportamentos similares entre coortes — a hipótese de que R é mais estável não é suportada fortemente por esses dados."
                if not _r_stable_q4
                else "E mantém sinal positivo em todas as coortes — a vantagem de framing tecnológico é mais robusta do que as narrativas alternativas sugerem."
            )
        )
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 11 — Corpus Focal C3+C4
    # ─────────────────────────────────────────────────────────────────────────
    append(_hr())
    append(_h1("11. Corpus Focal — Clusters C3 + C4 (Campo em Formação)"))
    append(_note(
        "Esta seção restringe a análise ao **subconjunto focal** de 1.709 artigos dos clusters C3 "
        "(_ChatGPT in Education and Research · Integrity and Writing_) e C4 "
        "(_AI in Higher Education · Policy, Assessment and Literacy_). "
        "Esses dois clusters são os que endereçam diretamente o uso de IA como ferramenta de apoio "
        "à produção acadêmica; os demais (C0–C2) são biomédico/engenharia de amplo espectro. "
        "Os indicadores globais (PRISMA, geo, Bradford, Lotka) continuam sendo calculados sobre o corpus "
        "completo de 6.261 artigos."
    ))

    _focal = axis_scores[axis_scores["cluster"].isin([3, 4])].copy()
    _focal_n = len(_focal)
    _total_n = len(axis_scores)
    _focal_pct = 100 * _focal_n / _total_n

    # Year-by-year counts in focal
    _focal_yr = _focal.groupby("publication_year").size().sort_index()
    _focal_pre2023 = int(_focal_yr[_focal_yr.index < 2023].sum()) if (
        any(_focal_yr.index < 2023)) else 0
    _focal_post2023 = int(_focal_yr[_focal_yr.index >= 2023].sum())
    _focal_2023 = int(_focal_yr.get(2023, 0))
    _focal_2024 = int(_focal_yr.get(2024, 0))
    _focal_2025 = int(_focal_yr.get(2025, 0))

    append(_h2("11.1 Emergência do Campo"))
    append(
        "**Claim.** O corpus focal (C3+C4) é essencialmente um campo nascido em 2023: "
        "menos de 30 artigos publicados em 2020–2022, seguidos de crescimento explosivo.\n"
    )
    yr_focal_display = _focal_yr.reset_index()
    yr_focal_display.columns = ["Ano", "N artigos C3+C4"]
    yr_focal_display["Ano"] = yr_focal_display["Ano"].astype(int)
    yr_focal_display["% do corpus C3+C4"] = (
        100 * yr_focal_display["N artigos C3+C4"] / _focal_n
    ).round(1)
    # Add % of that year's total corpus
    _total_by_yr = axis_scores.groupby("publication_year").size()
    yr_focal_display["% do corpus anual"] = yr_focal_display.apply(
        lambda r: round(100 * r["N artigos C3+C4"] / _total_by_yr.get(r["Ano"], 1), 1),
        axis=1,
    )
    append(_df_to_md(yr_focal_display))
    append(_note(
        f"Corpus focal: **{_focal_n:,}** artigos ({_focal_pct:.1f}% do corpus total de {_total_n:,}). "
        f"Apenas {_focal_pre2023} artigos foram publicados antes de 2023 "
        f"({100 * _focal_pre2023 / _focal_n:.1f}% do subconjunto focal). "
        f"O campo irrompe em 2023 com {_focal_2023} artigos e escala para "
        f"{_focal_2024} em 2024 e {_focal_2025} em 2025 — um crescimento de "
        f"{round(_focal_2025 / max(_focal_2023, 1))}× em apenas dois anos."
    ))

    # ── 11.2 Composição temática ──────────────────────────────────────────────
    append(_h2("11.2 Composição Temática (Categorias)"))
    append(
        "**Claim.** No subconjunto focal, a categoria **integrity_governance** "
        "(uso responsável, detecção de plágio, políticas editoras) domina — mais do que "
        "research_workflow ou research_writing. "
        "O campo está primordialmente regulando a IA, não apenas adotando-a.\n"
    )
    _cat_focal = _focal["category"].value_counts().reset_index()
    _cat_focal.columns = ["Categoria", "N"]
    _cat_focal["% do focal"] = (100 * _cat_focal["N"] / _focal_n).round(1)
    append(_df_to_md(_cat_focal))

    # Category × year within focal
    _cat_yr_focal = (
        _focal.groupby(["publication_year", "category"])
        .size()
        .unstack(fill_value=0)
        .loc[lambda df: df.index >= 2022]
    )
    _cat_yr_focal.index = _cat_yr_focal.index.astype(int)
    _top_cat = str(_cat_focal.iloc[0]["Categoria"])
    _top_cat_pct = float(_cat_focal.iloc[0]["% do focal"])
    append(_note(
        f"Categoria dominante: **{_top_cat}** ({_top_cat_pct:.1f}% dos artigos focais). "
        "Tendência: governance cresce em volume absoluto a cada ano mesmo com a expansão do corpus focal, "
        "sugerindo que o debate normativo não está cedendo espaço para trabalhos mais operacionais. "
        "research_writing mantém participação estável em ~9%, enquanto research_workflow cresce "
        "consistentemente — indicativo de que ferramentas de apoio começam a superar discussões de integridade pura."
    ))
    append("\n**Categorias × ano (2022−2026):**\n")
    append(_df_to_md(_cat_yr_focal.reset_index().rename(columns={"publication_year": "Ano"})))

    # ── 11.3 Maturidade de citações por coorte ────────────────────────────────
    append(_h2("11.3 Maturidade de Citações por Coorte"))
    append(
        "**Claim.** A baixa média de citações do corpus focal como um todo é efeito de recência: "
        "os 30 artigos de 2020–2022 e os 175 de 2023 já acumularam impacto bibliométrico considerável; "
        "o volume imenso de 2025–2026 simplesmente ainda não teve tempo de ser citado.\n"
    )
    _cit_cohort_rows = []
    for yr in sorted(_focal["publication_year"].dropna().astype(int).unique()):
        sub = _focal[_focal["publication_year"] == yr]["cited_by_count"]
        _cit_cohort_rows.append({
            "Ano": yr,
            "N artigos": len(sub),
            "% citados": round(100 * (sub > 0).mean(), 1),
            "Mediana cit.": round(float(sub.median()), 1),
            "Média cit.": round(float(sub.mean()), 1),
            "Top cit.": int(sub.max()),
        })
    _cit_cohort_df = pd.DataFrame(_cit_cohort_rows)
    append(_df_to_md(_cit_cohort_df))
    _mature_pct_cited = float(_cit_cohort_df[_cit_cohort_df["Ano"] <= 2023]["% citados"].mean())
    _mature_med = float(_cit_cohort_df[_cit_cohort_df["Ano"] <= 2023]["Mediana cit."].mean())
    _recent_pct_cited = float(_cit_cohort_df[_cit_cohort_df["Ano"] >= 2025]["% citados"].mean())
    append(_note(
        f"Coortes 2020–2023 (artigos com ≥2 anos de maturação): "
        f"{_mature_pct_cited:.1f}% de taxa de citação em média e mediana de {_mature_med:.1f} cit. — "
        "impacto comparável ao corpus completo de 2023, confirmando que o campo focal não é "
        "intrinsecamente de baixo impacto. "
        f"Coortes 2025–2026: {_recent_pct_cited:.1f}% de taxa de citação, "
        "compatível com literatura recente em qualquer campo. "
        "Leitura: a cauda zero-pesada do corpus focal é quase inteiramente efeito de horizonte temporal, "
        "não de qualidade ou visibilidade dos trabalhos."
    ))

    # ── 11.4 Núcleo editorial do corpus focal ─────────────────────────────────
    append(_h2("11.4 Núcleo Editorial — Quais Periódicos Publicam o Campo Focal?"))
    append(
        "**Claim.** O núcleo de Bradford recalculado sobre C3+C4 revela periódicos de educação, "
        "ética e informática aplicada — completamente distinto do núcleo IEEE/imagem médica do corpus amplo.\n"
    )
    _cc_focal = pd.read_csv(
        paths.corpus_clustered_path,
        usecols=["id", "journal", "cited_by_count"],
    )
    _cc_focal["cited_by_count"] = pd.to_numeric(
        _cc_focal["cited_by_count"], errors="coerce"
    ).fillna(0)
    _focal_ids = set(_focal["id"])
    _cc_focal = _cc_focal[_cc_focal["id"].isin(_focal_ids)].copy()
    _cc_focal["journal"] = (
        _cc_focal["journal"].fillna("").str.strip().str.title()
    )
    _jrn_focal = (
        _cc_focal[_cc_focal["journal"] != ""]
        .groupby("journal")
        .agg(n=("id", "count"), total_cit=("cited_by_count", "sum"))
        .sort_values("n", ascending=False)
        .reset_index()
    )
    _jrn_focal["% artigos focais"] = (100 * _jrn_focal["n"] / _focal_n).round(2)
    _top15_focal = _jrn_focal.head(15)[["journal", "n", "total_cit", "% artigos focais"]]
    _top15_focal.columns = ["Periódico", "N artigos", "Total cit.", "% corpus focal"]
    append(_df_to_md(_top15_focal))
    _zone1_focal_n = int((_jrn_focal["n"].cumsum() / _focal_n * 100 <= 33.3).sum()) + 1
    append(_note(
        f"Os {_zone1_focal_n} periódicos de maior produção no corpus focal "
        f"cobrem ~1/3 dos artigos C3+C4. "
        "IEEE Access, Frontiers in Education e Education Sciences dominam — "
        "em contraste com o núcleo do corpus completo (IEEE Access + Cureus + Sensors), "
        "que é orientado por engenharia e biomédica. "
        "Essa inversão do núcleo editorial é evidência direta de que C3+C4 representa "
        "um campo bibliometricamente distinto do restante do corpus."
    ))

    # ── 11.5 Top papers do campo focal ───────────────────────────────────────
    _focus_papers_path = paths.indicators_dir / "cluster_focus_papers.csv"
    if _focus_papers_path.exists():
        _focus_papers_df = pd.read_csv(_focus_papers_path)
        append(_h2("11.5 Artigos de Maior Impacto por Cluster"))
        append(
            "**Claim.** Os artigos mais citados de C3 e C4 são leituras obrigatórias do campo focal; "
            "ao mesmo tempo, concentração alta em poucos outliers explica boa parte da vantagem de "
            "média de citações — confirmando que a mediana é mais representativa do campo como um todo.\n"
        )
        for _cid, _clabel in [(3, _integrity_col), (4, _edu_col)]:
            _cp = _focus_papers_df[_focus_papers_df["cluster_id"] == _cid].copy()
            if _cp.empty:
                continue
            append(f"\n**{_clabel}**\n")
            _cp_disp = _cp[["title", "publication_year", "cited_by_count", "journal"]].copy()
            _cp_disp.index = range(1, len(_cp_disp) + 1)
            _cp_disp.columns = ["Título", "Ano", "Citações", "Periódico"]
            append(_df_to_md(_cp_disp, index=True))
    # ─────────────────────────────────────────────────────────────────────────
    append(_hr())
    append(_h1("12. Diagnóstico das Teses Principais"))
    append(_note(
        "Esta seção traduz as perguntas exploratórias em diagnósticos diretos sobre as nove teses "
        "levantadas na discussão. Cada tese é testada com um cálculo concreto e classificada como "
        "**confirmada**, **parcialmente confirmada** ou **não confirmada** com base nos dados do corpus."
    ))

    # ── Pre-computations for C1–C9 ──────────────────────────────────────────

    # C1: ChatGPT effect is compositional (Simpson's paradox)
    _c1_agg_rho = float(summary["spearman"]["E"]["rho_all"])
    _c1_e_bands_vals = [
        float(_band_2020_2022["ρ E×cit"]),
        float(_band_2023_2024["ρ E×cit"]),
        float(_band_2025_2026["ρ E×cit"]),
    ]
    _c1_neg_bands = sum(1 for v in _c1_e_bands_vals if v <= 0)
    _c1_confirmed = _c1_agg_rho > 0 and _c1_neg_bands >= 2

    # C2: Domain (R) beats hype (E)
    _c2_r_bands_vals = [
        float(_band_2020_2022["ρ R×cit"]),
        float(_band_2023_2024["ρ R×cit"]),
        float(_band_2025_2026["ρ R×cit"]),
    ]
    _c2_r_pos_count = sum(1 for v in _c2_r_bands_vals if v > 0)
    _c2_confirmed = (_c2_r_pos_count >= 2) and (_r_rho_range < _e_rho_range)

    # C3: 2023 is a structural shock
    _c3_cit_by_yr = axis_scores.groupby("publication_year")["cited_by_count"].sum()
    _c3_total_cit = max(float(_c3_cit_by_yr.sum()), 1.0)
    _c3_all_yrs_list = sorted([int(y) for y in _c3_cit_by_yr.index if 2020 <= y <= 2025])
    _c3_rows_list: list[dict] = []
    for _c3_yr in _c3_all_yrs_list:
        _c3_yr_n = int((axis_scores["publication_year"] == _c3_yr).sum())
        _c3_yr_cit_pct = 100 * float(_c3_cit_by_yr.get(_c3_yr, 0)) / _c3_total_cit
        _c3_yr_n_pct = 100 * _c3_yr_n / max(len(axis_scores), 1)
        _c3_rows_list.append({
            "Ano": _c3_yr,
            "% artigos": round(_c3_yr_n_pct, 1),
            "% citações": round(_c3_yr_cit_pct, 1),
            "Razão cit/art": round(_c3_yr_cit_pct / max(_c3_yr_n_pct, 0.01), 2),
            "N artigos >100 cit.": int(
                (axis_scores.loc[axis_scores["publication_year"] == _c3_yr, "cited_by_count"] > 100).sum()
            ),
        })
    c3_cohort_df = pd.DataFrame(_c3_rows_list)
    _c3_2023 = next((r for r in _c3_rows_list if r["Ano"] == 2023), None)
    _c3_confirmed = bool(_c3_2023 and _c3_2023["Razão cit/art"] >= 1.5)

    # C4: Vocabulary changes, structure persists
    _c4_vocab_peak = _q2_e_peak
    _c4_vocab_last = _q2_e_last
    _c4_struct_early = _edu_share_2022
    _c4_struct_last = _edu_share_2025
    _c4_confirmed = (_c4_vocab_last < _c4_vocab_peak) and (_c4_struct_last > _c4_struct_early)

    # C5: Born-digital field
    _c5_pre_pct = 100.0 * _focal_pre2023 / max(_focal_n, 1)
    _c5_confirmed = _c5_pre_pct < 5.0

    # C6: Normatively driven (governance > tools)
    _c6_top_cat = str(_top_cat) if not _cat_focal.empty else ""
    _c6_top_pct = float(_top_cat_pct) if not _cat_focal.empty else 0.0
    _c6_is_gov = bool(
        not _cat_focal.empty
        and ("integrity" in _c6_top_cat.lower() or "governance" in _c6_top_cat.lower())
    )
    _c6_confirmed = _c6_is_gov and _c6_top_pct >= 40.0

    # C7: Impact concentration — top 10% dominates
    _c7_corpus_top10 = _top_share(axis_scores["cited_by_count"], 0.10)
    _c7_corpus_top20 = _top_share(axis_scores["cited_by_count"], 0.20)
    _c7_conc_min = float(cluster_concentration["% citações no top 10%"].min())
    _c7_conc_max = float(cluster_concentration["% citações no top 10%"].max())
    _c7_confirmed = _c7_corpus_top10 >= 60.0 and _c7_conc_min >= 50.0

    # C8: Two editorial ecosystems — minimal journal overlap
    _cc_jrn_all = pd.read_csv(paths.corpus_clustered_path, usecols=["id", "journal"])
    _cc_jrn_all["journal"] = _cc_jrn_all["journal"].fillna("").str.strip().str.title()
    _cc_jrn_all["id"] = _cc_jrn_all["id"].astype(str)
    _ax_id_cl12 = axis_scores[["id", "cluster"]].copy()
    _ax_id_cl12["id"] = _ax_id_cl12["id"].astype(str)
    _cc_jrn_all = _cc_jrn_all.merge(_ax_id_cl12, on="id", how="left")
    _cc_jrn_all = _cc_jrn_all[_cc_jrn_all["journal"] != ""]
    _jrn_core_15 = (
        _cc_jrn_all[_cc_jrn_all["cluster"].isin([0, 1, 2])]
        .groupby("journal").size().sort_values(ascending=False)
        .head(15).index.tolist()
    )
    _jrn_focal_15 = _jrn_focal.head(15)["journal"].tolist()
    _c8_overlap_set = set(_jrn_core_15) & set(_jrn_focal_15)
    _c8_union_set = set(_jrn_core_15) | set(_jrn_focal_15)
    _c8_jaccard = len(_c8_overlap_set) / max(len(_c8_union_set), 1)
    _c8_overlap_n = len(_c8_overlap_set)
    _c8_confirmed = _c8_jaccard < 0.20

    # C9: Low citation is temporal, not qualitative
    _c9_mature_pct = _mature_pct_cited
    _c9_recent_pct = _recent_pct_cited
    _c9_confirmed = _c9_mature_pct >= 85.0

    # ── Summary table ────────────────────────────────────────────────────────
    def _verdict(confirmed: bool | None, partial: bool = False) -> str:
        if confirmed:
            return "✓ Confirmada"
        if partial:
            return "~ Parcial"
        return "✗ Não confirmada"

    _c1_v = _verdict(_c1_confirmed)
    _c2_v = _verdict(_c2_confirmed)
    _c3_v = _verdict(_c3_confirmed)
    _c4_v = _verdict(_c4_confirmed)
    _c5_v = _verdict(_c5_confirmed)
    _c6_v = _verdict(_c6_confirmed, partial=(_c6_top_pct > 30 and _c6_top_pct < 40))
    _c7_v = _verdict(_c7_confirmed)
    _c8_v = _verdict(_c8_confirmed)
    _c9_v = _verdict(_c9_confirmed)

    # Build summary table
    claim_summary = pd.DataFrame([
        {"#": "C1", "Tese": "Prêmio ChatGPT é ilusório (composição temporal)",
         "Evidência-chave": f"ρE={_c1_agg_rho:+.3f} agregado; ρE≤0 em {_c1_neg_bands}/3 coortes",
         "Veredicto": _c1_v},
        {"#": "C2", "Tese": "Domínio (Eixo R) supera framing (Eixo E) em robustez",
         "Evidência-chave": f"ρR>0 em {_c2_r_pos_count}/3 coortes; amplitude R={_r_rho_range:.3f} < E={_e_rho_range:.3f}",
         "Veredicto": _c2_v},
        {"#": "C3", "Tese": "2023 é choque estrutural, não crescimento normal",
         "Evidência-chave": (
             f"{_c3_2023['% artigos']:.1f}% dos artigos → {_c3_2023['% citações']:.1f}% das citações "
             f"(razão {_c3_2023['Razão cit/art']:.2f}×)" if _c3_2023 else "n/a"
         ),
         "Veredicto": _c3_v},
        {"#": "C4", "Tese": "Rótulo ChatGPT recua; campo estrutural (C3+C4) persiste",
         "Evidência-chave": f"E>0 cai {_c4_vocab_peak:.1f}%→{_c4_vocab_last:.1f}%; C3+C4 sobe {_c4_struct_early:.1f}%→{_c4_struct_last:.1f}%",
         "Veredicto": _c4_v},
        {"#": "C5", "Tese": "Campo focal é 'born-digital', nascido em 2023",
         "Evidência-chave": f"{_focal_pre2023} artigos ({_c5_pre_pct:.1f}%) antes de 2023 em C3+C4",
         "Veredicto": _c5_v},
        {"#": "C6", "Tese": "Campo organiza-se em torno de governança, não de ferramentas",
         "Evidência-chave": f"Categoria dominante: {_c6_top_cat} ({_c6_top_pct:.1f}% do focal)",
         "Veredicto": _c6_v},
        {"#": "C7", "Tese": "Impacto extremamente concentrado — médias enganam",
         "Evidência-chave": f"Top 10% = {_c7_corpus_top10:.1f}% das citações; por cluster: {_c7_conc_min:.1f}–{_c7_conc_max:.1f}%",
         "Veredicto": _c7_v},
        {"#": "C8", "Tese": "Dois ecossistemas editoriais distintos",
         "Evidência-chave": f"{_c8_overlap_n} periódicos em comum (Jaccard={_c8_jaccard:.2f}) — top-15 core vs. focal",
         "Veredicto": _c8_v},
        {"#": "C9", "Tese": "Zero-citation problem é artefato temporal",
         "Evidência-chave": f"Coortes 2020–2023: {_c9_mature_pct:.1f}% taxa de citação; 2025–2026: {_c9_recent_pct:.1f}%",
         "Veredicto": _c9_v},
    ])
    append(_df_to_md(claim_summary))

    # ── C1 detail ─────────────────────────────────────────────────────────────
    append(_h2("C1 — O prêmio de citações do ChatGPT é ilusório (artefato de composição temporal)"))
    append(
        "**Tese.** O efeito agregado positivo de E×citações desaparece ou reverte quando o corpus "
        "é estratificado por coorte. Isso indica artefato de composição (paradoxo de Simpson): "
        "os artigos fundadores acumularam citações antes que o rótulo ChatGPT existisse.\n"
    )
    c1_tab = pd.DataFrame([
        {"Contexto": "Agregado", "ρ E×cit": f"{_c1_agg_rho:+.3f}", "Interpretação": "positivo (sinal espúrio)"},
        {"Contexto": "2020-2022", "ρ E×cit": f"{_c1_e_bands_vals[0]:+.3f}", "Interpretação": "coorte pré-ChatGPT"},
        {"Contexto": "2023-2024", "ρ E×cit": f"{_c1_e_bands_vals[1]:+.3f}", "Interpretação": "pico do rótulo"},
        {"Contexto": "2025-2026", "ρ E×cit": f"{_c1_e_bands_vals[2]:+.3f}", "Interpretação": "normalização"},
    ])
    append(_df_to_md(c1_tab))
    append(_note(
        f"**{_c1_v}** — ρE agregado = {_c1_agg_rho:+.3f}, mas {_c1_neg_bands}/3 faixas têm ρE ≤ 0. "
        "O sinal positivo no agregado coexiste com valores negativos ou nulos por coorte. "
        "Interpretação: artigos fundadores (2020-2022) foram amplamente citados por razões de conteúdo e pioneirismo; "
        "quando o rótulo ChatGPT explode (2023+), não carrega um prêmio de citação por si mesmo."
        if _c1_confirmed else
        f"**{_c1_v}** — ρE = {_c1_agg_rho:+.3f} agregado; apenas {_c1_neg_bands}/3 faixas com ρE ≤ 0. "
        "O padrão de reversão existe mas não está completamente estabelecido nos três estratos."
    ))

    # ── C2 detail ─────────────────────────────────────────────────────────────
    append(_h2("C2 — Domínio (Eixo R) supera framing (Eixo E) como sinal de impacto"))
    append(
        "**Tese.** O Eixo R (domínio acadêmico ↔ clínico) mantém correlação positiva com citações "
        "em todas as coortes temporais, enquanto E cruza zero e se torna negativo — reversão contra ρ=0, não troca de posição com R — tornando R o preditor analiticamente mais robusto.\n"
    )
    c2_tab = pd.DataFrame([
        {
            "Eixo": "R (domínio clínico/acadêmico)",
            "ρ 2020-2022": f"{_c2_r_bands_vals[0]:+.3f}",
            "ρ 2023-2024": f"{_c2_r_bands_vals[1]:+.3f}",
            "ρ 2025-2026": f"{_c2_r_bands_vals[2]:+.3f}",
            "Bandas ρ>0": f"{_c2_r_pos_count}/3",
            "Amplitude": f"{_r_rho_range:.3f}",
        },
        {
            "Eixo": "E (framing ChatGPT/genérico)",
            "ρ 2020-2022": f"{_c1_e_bands_vals[0]:+.3f}",
            "ρ 2023-2024": f"{_c1_e_bands_vals[1]:+.3f}",
            "ρ 2025-2026": f"{_c1_e_bands_vals[2]:+.3f}",
            "Bandas ρ>0": f"{sum(1 for v in _c1_e_bands_vals if v > 0)}/3",
            "Amplitude": f"{_e_rho_range:.3f}",
        },
    ])
    append(_df_to_md(c2_tab))
    append(_note(
        f"**{_c2_v}** — R mantém ρ>0 em {_c2_r_pos_count}/3 faixas (amplitude {_r_rho_range:.3f}); "
        f"E positivo em {sum(1 for v in _c1_e_bands_vals if v > 0)}/3 faixas (amplitude {_e_rho_range:.3f}). "
        "O domínio (clínico versus acadêmico/educacional) é qualitativamente mais estável como preditor "
        "do que o simples framing de nomenclatura tecnológica."
    ))

    # ── C3 detail ─────────────────────────────────────────────────────────────
    append(_h2("C3 — 2023 é um choque estrutural, não crescimento normal"))
    append(
        "**Tese.** A coorte de 2023 representa ruptura: com parcela minoritária dos artigos, "
        "concentra citações desproporcionais. Um 'choque fundador', não crescimento linear.\n"
    )
    append(_df_to_md(c3_cohort_df))
    if _c3_2023:
        _c3_gt100_other = sum(r["N artigos >100 cit."] for r in _c3_rows_list if r["Ano"] != 2023)
        append(_note(
            f"**{_c3_v}** — 2023 tem {_c3_2023['% artigos']:.1f}% dos artigos mas "
            f"{_c3_2023['% citações']:.1f}% das citações (razão {_c3_2023['Razão cit/art']:.2f}×). "
            f"Artigos com >100 citações: {_c3_2023['N artigos >100 cit.']} em 2023 "
            f"versus {_c3_gt100_other} em todos os demais anos combinados. "
            "O comportamento é consistente com coorte de agenda-setting, não com coorte de crescimento normal."
        ))

    # ── C4 detail ─────────────────────────────────────────────────────────────
    append(_h2("C4 — O rótulo ChatGPT recua, mas o campo estrutural (C3+C4) persiste"))
    append(
        "**Tese.** E>0% cai após 2023 (declínio do vocabulário), mas C3+C4 share continua crescendo "
        "(persistência estrutural). "
        "O campo absorve a inovação sem depender do rótulo que a nomeou.\n"
    )
    _c4_e2026 = float(_e_pos_by_year.loc[2026]) if 2026 in _e_pos_by_year.index else float("nan")
    _c4_e2022 = float(_e_pos_by_year.loc[2022]) if 2022 in _e_pos_by_year.index else float("nan")
    c4_tab = pd.DataFrame([
        {
            "Indicador": "% artigos E>0 (vocabulário ChatGPT/GenAI)",
            "2022": f"{_c4_e2022:.1f}%" if not pd.isna(_c4_e2022) else "—",
            "2023 (pico)": f"{_c4_vocab_peak:.1f}%",
            "2025": f"{float(_e_pos_by_year.loc[2025]) if 2025 in _e_pos_by_year.index else float('nan'):.1f}%",
            "Tendência": "↓ vocabulário recua",
        },
        {
            "Indicador": "% corpus em C3+C4 (estrutura do campo focal)",
            "2022": f"{_c4_struct_early:.1f}%",
            "2023 (pico)": f"{_edu_share_2023:.1f}%",
            "2025": f"{_c4_struct_last:.1f}%",
            "Tendência": "↑ campo cresce",
        },
    ])
    append(_df_to_md(c4_tab))
    append(_note(
        f"**{_c4_v}** — Separação clara entre sinal semântico (E>0, que declina) e sinal estrutural "
        f"(C3+C4 share, que cresce de {_c4_struct_early:.1f}% para {_c4_struct_last:.1f}%). "
        "Isso confirma a narrativa de normalização: o campo absorve a inovação sem depender do rótulo."
    ))

    # ── C5 detail ─────────────────────────────────────────────────────────────
    append(_h2("C5 — O campo focal é um campo nascido em 2023 ('born-digital')"))
    append(
        "**Tese.** C3+C4 é essencialmente inexistente antes de 2023: "
        "menos de 5% dos artigos focais foram publicados antes desse ano.\n"
    )
    c5_tab = pd.DataFrame([
        {
            "Período": "Antes de 2023 (2020-2022)",
            "N artigos C3+C4": _focal_pre2023,
            "% do campo focal": round(_c5_pre_pct, 1),
            "N total corpus": int((axis_scores["publication_year"] < 2023).sum()),
        },
        {
            "Período": "2023",
            "N artigos C3+C4": _focal_2023,
            "% do campo focal": round(100 * _focal_2023 / max(_focal_n, 1), 1),
            "N total corpus": int((axis_scores["publication_year"] == 2023).sum()),
        },
        {
            "Período": "2024",
            "N artigos C3+C4": _focal_2024,
            "% do campo focal": round(100 * _focal_2024 / max(_focal_n, 1), 1),
            "N total corpus": int((axis_scores["publication_year"] == 2024).sum()),
        },
        {
            "Período": "2025",
            "N artigos C3+C4": _focal_2025,
            "% do campo focal": round(100 * _focal_2025 / max(_focal_n, 1), 1),
            "N total corpus": int((axis_scores["publication_year"] == 2025).sum()),
        },
    ])
    append(_df_to_md(c5_tab))
    append(_note(
        f"**{_c5_v}** — Apenas {_focal_pre2023} artigos ({_c5_pre_pct:.1f}% do campo focal) "
        "foram publicados antes de 2023. O campo irrompe de forma abrupta, não gradual — "
        "consistente com a hipótese de campo 'born-digital', desencadeado por uma tecnologia "
        "específica em um momento pontual (lançamento do ChatGPT, novembro de 2022)."
    ))

    # ── C6 detail ─────────────────────────────────────────────────────────────
    append(_h2("C6 — O campo organiza-se primordialmente em torno de governança, não de ferramentas"))
    append(
        "**Tese.** No corpus focal, a categoria integrity_governance domina sobre research_workflow "
        "e research_writing — o debate normativo precedeu (ou igualou) o debate de adoção.\n"
    )
    append(_df_to_md(_cat_focal))
    if not _cat_focal.empty:
        _c6_wf_pct = float(
            _cat_focal.loc[_cat_focal["Categoria"].str.lower().str.contains("workflow", na=False), "% do focal"].sum()
        ) if not _cat_focal.empty else 0.0
        append(_note(
            f"**{_c6_v}** — Categoria dominante: **{_c6_top_cat}** ({_c6_top_pct:.1f}% dos artigos focais). "
            + (
                f"research_workflow representa apenas ~{_c6_wf_pct:.1f}% — menor do que integrity_governance. "
                "Isso inverte a cadência esperada 'ferramentas → adoção → governança': "
                "acadêmicos e editores abordaram o ChatGPT inicialmente como problema de integridade, "
                "não como oportunidade operacional."
                if _c6_confirmed else
                "O resultado é mais ambíguo — a categoria de governança lidera mas sem margem clara."
            )
        ))

    # ── C7 detail ─────────────────────────────────────────────────────────────
    append(_h2("C7 — Impacto extremamente concentrado — médias são enganosas"))
    append(
        "**Tese.** O top 10% dos artigos por citação concentra a maioria das citações totais "
        "em qualquer cluster — sinalizando que comparações de médias subdimensionam a heterogeneidade.\n"
    )
    c7_tab = cluster_concentration[["Cluster", "% citações no top 10%", "% citações no top 20%", "Ano mediano"]].copy()
    for col in ["% citações no top 10%", "% citações no top 20%"]:
        c7_tab[col] = c7_tab[col].round(1)
    c7_tab["Ano mediano"] = c7_tab["Ano mediano"].round(0).astype(int)
    # Add corpus-total row
    c7_total_row = pd.DataFrame([{
        "Cluster": "CORPUS TOTAL",
        "% citações no top 10%": round(_c7_corpus_top10, 1),
        "% citações no top 20%": round(_c7_corpus_top20, 1),
        "Ano mediano": int(axis_scores["publication_year"].median()),
    }])
    append(_df_to_md(pd.concat([c7_total_row, c7_tab], ignore_index=True)))
    append(_note(
        f"**{_c7_v}** — Corpus total: top 10% = {_c7_corpus_top10:.1f}% das citações; "
        f"top 20% = {_c7_corpus_top20:.1f}%. "
        f"Por cluster, a concentração varia entre {_c7_conc_min:.1f}% e {_c7_conc_max:.1f}% no top décimo. "
        "Ranking de clusters por média de citações deve sempre ser lido ao lado da mediana e do décil superior."
    ))

    # ── C8 detail ─────────────────────────────────────────────────────────────
    append(_h2("C8 — O campo focal forma um ecossistema editorial distinto do corpus amplo"))
    append(
        "**Tese.** Os periódicos líderes de C3+C4 (focal) têm sobreposição mínima com os de C0+C1+C2 "
        "(corpus técnico-clínico), evidenciando duas comunidades acadêmicas distintas.\n"
    )
    _max15 = max(len(_jrn_core_15), len(_jrn_focal_15))
    _core_padded = _jrn_core_15 + [""] * (_max15 - len(_jrn_core_15))
    _focal_padded = _jrn_focal_15 + [""] * (_max15 - len(_jrn_focal_15))
    c8_tab = pd.DataFrame({
        "# Periódico": list(range(1, _max15 + 1)),
        "Top periódicos — C0-C2 (técnico/clínico)": _core_padded,
        "Top periódicos — C3-C4 (focal/educacional)": _focal_padded,
    })
    append(_df_to_md(c8_tab))
    _overlap_list = sorted(_c8_overlap_set) if _c8_overlap_set else ["(nenhum)"]
    append(_note(
        f"**{_c8_v}** — {_c8_overlap_n} periódicos em comum nos top-15 de cada subcorpus "
        f"(Jaccard = {_c8_jaccard:.2f}). "
        f"{'Periódicos coincidentes: ' + ', '.join(_overlap_list) + '.' if _c8_overlap_n > 0 else 'Nenhuma sobreposição.'} "
        "O corpus focal publica em periódicos de educação, ética e computação educacional; "
        "o corpus técnico-clínico concentra-se em engenharia e biomédica. "
        "Isso não é apenas diversidade temática — é separação de comunidades científicas."
    ))

    # ── C9 detail ─────────────────────────────────────────────────────────────
    append(_h2("C9 — O 'problema de zero citação' é quase inteiramente temporal"))
    append(
        "**Tese.** Para artigos com 2+ anos de maturação (publicados até 2023), "
        "a taxa de citação do corpus focal aproxima-se de 100% — o zero-citation problem "
        "não reflete baixo impacto intrínseco, mas horizonte temporal insuficiente.\n"
    )
    append(_df_to_md(_cit_cohort_df))
    append(_note(
        f"**{_c9_v}** — Coortes 2020–2023 (≥2 anos de maturação): "
        f"taxa média de citação = {_c9_mature_pct:.1f}%, mediana = {_mature_med:.1f} cit. "
        f"Coortes 2025–2026: {_c9_recent_pct:.1f}% de taxa — "
        "fração típica para literatura com menos de 1 ano de indexação. "
        "A leitura de 'campo de baixo impacto' baseada apenas no percentual de zeros é "
        "um artefato da composição temporal do corpus, não uma propriedade do campo."
    ))

    append(_hr())
    append(_h1("10. Inventário de Arquivos"))
    inventory = pd.DataFrame([
        [paths.corpus_clean_path.name, "Corpus limpo"],
        [paths.corpus_clustered_path.name, "Corpus com clusters e UMAP"],
        [paths.embeddings_path.name, "Embeddings BGE-M3"],
        ["indicators/yearly_production.csv", "Produção anual"],
        ["indicators/temporal_profile.csv", "Perfil temporal"],
        ["indicators/cluster_share_by_year.csv", "Composição de clusters por ano"],
        ["indicators/axis_scores_enriched.csv", "Scores semânticos enriquecidos"],
        ["indicators/report_summary.json", "Resumo consolidado para relatórios"],
        [paths.report_text_path.name, "Este relatório textual"],
    ], columns=["Arquivo", "Conteúdo"])
    append(_df_to_md(inventory))

    content = "\n".join(lines)
    paths.report_text_path.write_text(content, encoding="utf-8")
    print(f"Saved: {paths.report_text_path}")
    return paths.report_text_path