"""Paper axes for the Latin.Science 2026 study.

This module implements the TWO theory-guided semantic dimensions used in the
paper (not the four exploratory axes in ``semantic_axes.py``):

* **Axis T — technological specificity**: Generic/non-named AI  →
  ChatGPT / GPT-4 / Claude / named GenAI model as the central object.
* **Axis G — governance orientation**: Workflow/task support (search, writing,
  review, synthesis)  →  governance, integrity, authorship, disclosure,
  detection, policy and safeguards.

Both axes are computed with the prototype method: each pole is anchored by a
balanced set of 4–6 realistic abstract prototypes written in English *before*
looking at any results.  The axis is the unit vector between the two pole
centroids; scores are the projection of each document embedding onto that
vector, centered at the midpoint between the two pole centroids.

Sensitivity is assessed by leave-one-prototype-out (LOO): the axis is rebuilt
dropping each prototype in turn and the Spearman rank correlation between the
resulting ordering and the primary ordering is reported.  The paper's target is
a minimum LOO rho >= .80; below .70 the axis should be revised or dropped.

Outputs (written to ``RunPaths.indicators_dir``):

* ``axis_scores.csv``        — per-document raw centered scores plus z-scores.
* ``axis_validation.txt``    — LOO stability, orthogonality and center values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr
from sentence_transformers import SentenceTransformer

from .paths import RunPaths, ensure_run_dirs

# ---------------------------------------------------------------------------
# Axis T — technological specificity
# Generic AI / ML with no named generative model  →  named GenAI model central
# ---------------------------------------------------------------------------

# Pole 1 (Likert 1): generic AI/ML, no named generative model is central.
T_AXIS_NEG_PROTOTYPES = [
    "This study develops machine learning models to automate the classification "
    "and screening of scientific publications, using text features and supervised "
    "classifiers to support systematic reviews and literature search without "
    "referring to any specific generative AI system.",
    "The authors apply natural language processing and automated summarization "
    "techniques to academic manuscripts, evaluating generic algorithms for "
    "extracting key findings and recommending suitable journals without testing "
    "a named commercial language model.",
    "This paper investigates how artificial intelligence can assist peer review "
    "and editorial workflows, describing prototype systems for manuscript triage, "
    "reviewer suggestion, and quality assessment built on generic machine "
    "learning methods rather than a particular generative model.",
    "Researchers examine the use of text-mining and machine learning approaches "
    "for detecting plagiarism and duplicate publication in scholarly research, "
    "comparing several algorithmic strategies while treating the underlying "
    "technology as generic artificial intelligence.",
    "The article surveys artificial intelligence applications in scholarly "
    "communication, covering natural language processing, automated indexing, "
    "and predictive analytics for citation impact, and discusses these "
    "technologies without reference to any specific generative AI product.",
]

# Pole 5 (Likert 5): one or more named models are centrally evaluated/compared.
T_AXIS_POS_PROTOTYPES = [
    "This paper systematically evaluates ChatGPT and GPT-4 on title and abstract "
    "screening for systematic reviews, quantifying their agreement with human "
    "reviewers and comparing the two models' precision and recall across "
    "thousands of records.",
    "The authors test how well ChatGPT, Claude, and Gemini generate scientific "
    "manuscript drafts and peer review feedback, reporting side-by-side "
    "comparisons of the models' outputs against human-written text on accuracy, "
    "style, and factual reliability.",
    "This study measures the performance of GPT-4 and other named large language "
    "models in identifying methodological flaws and fabricated references in "
    "submitted manuscripts, assessing their readiness as assistive tools in "
    "journal peer review.",
    "Researchers compare ChatGPT, GPT-4, and LLaMA on literature synthesis "
    "tasks, examining how each named model summarizes evidence, handles "
    "conflicting findings, and generates citations for systematic review "
    "updates.",
    "This paper documents the capabilities and failure modes of ChatGPT and "
    "GPT-4 in academic writing, focusing on hallucinated citations, biased "
    "reasoning, and inconsistency in the models' output across repeated trials "
    "in scholarly contexts.",
]

# ---------------------------------------------------------------------------
# Axis G — governance orientation
# Workflow/task support (search, writing, review, synthesis)  →  governance
# / integrity / authorship / disclosure / detection / policy / safeguards
# ---------------------------------------------------------------------------

# Pole 1 (Likert 1): centrally task support for research/writing/review/synthesis.
G_AXIS_NEG_PROTOTYPES = [
    "This paper evaluates how large language models can support researchers "
    "throughout the manuscript writing process, testing AI-assisted drafting, "
    "abstract generation, literature searching, and reference formatting to help "
    "authors produce publications more efficiently.",
    "The study examines the use of artificial intelligence for systematic review "
    "workflows, measuring how well AI-assisted tools screen titles and "
    "abstracts, extract data, and synthesize evidence, with the goal of reducing "
    "the time researchers spend on evidence synthesis.",
    "Researchers assess generative AI as a writing assistant for students and "
    "academics, focusing on how it improves drafting, revision, proofreading, "
    "and feedback in academic writing courses and scholarly communication tasks.",
    "This article investigates AI-supported peer review, examining how automated "
    "systems draft reviewer comments, check manuscript quality, and assist "
    "editors in assigning and evaluating submissions, treating the technology as "
    "a practical aid to the review process.",
    "The authors develop and test an AI-assisted tool for literature search and "
    "citation management, describing how it helps researchers discover relevant "
    "papers, organize references, and summarize findings for research projects "
    "and publications.",
]

# Pole 5 (Likert 5): centrally governance/integrity/policy; task support secondary.
G_AXIS_POS_PROTOTYPES = [
    "This paper examines academic integrity in the age of generative AI, "
    "analyzing how ChatGPT use in student writing affects plagiarism, "
    "ghostwriting, and honest attribution, and calls for institutional policies, "
    "detection tools, and disclosure requirements to protect scholarly standards.",
    "The study investigates authorship and disclosure rules for AI-generated "
    "content in scientific publishing, reviewing journal policies on ChatGPT "
    "co-authorship, fabricated references, and the need for transparent "
    "reporting of AI assistance in manuscripts.",
    "Researchers analyze institutional governance of generative AI in higher "
    "education, surveying university guidelines, responsible-use frameworks, and "
    "integrity offices' responses to ChatGPT, and propose safeguards for "
    "assessment and research conduct.",
    "This article addresses the risks generative AI poses to scholarly "
    "communication, including AI-generated paper mills, fake peer reviews, and "
    "manipulated citation networks, and advocates for governance mechanisms, "
    "detection systems, and editorial safeguards.",
    "The paper evaluates policies for using generative AI in academic research, "
    "focusing on ethical review, data protection, accountability for "
    "AI-generated outputs, and institutional guardrails that balance innovation "
    "with integrity and public trust in science.",
]


def _encode(model: SentenceTransformer, text: str) -> np.ndarray:
    return model.encode(text, normalize_embeddings=True).astype(np.float32)


def _make_prototype_axis(
    model: SentenceTransformer, neg_texts: list[str], pos_texts: list[str]
) -> tuple[np.ndarray, float]:
    """Direction vector between pole centroids, centered at their midpoint.

    Returns ``(vector, center)`` where a document's centered score is
    ``(embedding @ vector) - center`` (negative near the ``neg`` pole,
    positive near the ``pos`` pole, zero at the midpoint).
    """
    neg_vec = np.stack([_encode(model, text) for text in neg_texts], axis=0).mean(axis=0)
    pos_vec = np.stack([_encode(model, text) for text in pos_texts], axis=0).mean(axis=0)
    vector = pos_vec - neg_vec
    vector /= np.linalg.norm(vector)
    center = float(((pos_vec @ vector) + (neg_vec @ vector)) / 2.0)
    return vector.astype(np.float32), center


def _loo_prototype_axis(
    model: SentenceTransformer,
    embeddings: np.ndarray,
    primary_scores: np.ndarray,
    neg_texts: list[str],
    pos_texts: list[str],
) -> tuple[float, float]:
    """Leave-one-prototype-out stability: mean and min Spearman rho."""
    rhos: list[float] = []
    for idx in range(len(neg_texts)):
        sampled_neg = neg_texts[:idx] + neg_texts[idx + 1 :]
        sampled_vec, sampled_center = _make_prototype_axis(model, sampled_neg, pos_texts)
        rho, _ = spearmanr(primary_scores, (embeddings @ sampled_vec) - sampled_center)
        rhos.append(float(rho))
    for idx in range(len(pos_texts)):
        sampled_pos = pos_texts[:idx] + pos_texts[idx + 1 :]
        sampled_vec, sampled_center = _make_prototype_axis(model, neg_texts, sampled_pos)
        rho, _ = spearmanr(primary_scores, (embeddings @ sampled_vec) - sampled_center)
        rhos.append(float(rho))
    return float(np.mean(rhos)), float(np.min(rhos))


def _standardize(values: pd.Series) -> pd.Series:
    return (values - values.mean()) / values.std(ddof=0)


def run(paths: RunPaths) -> None:
    """Compute and save the paper's T and G axis scores."""
    ensure_run_dirs(paths)

    df = pd.read_csv(paths.corpus_clustered_path)
    embeddings = np.load(paths.embeddings_path)

    if len(df) != len(embeddings):
        raise ValueError(
            f"Corpus ({len(df)} rows) and embeddings ({len(embeddings)}) do not align."
        )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    model.eval()

    vec_t, center_t = _make_prototype_axis(model, T_AXIS_NEG_PROTOTYPES, T_AXIS_POS_PROTOTYPES)
    vec_g, center_g = _make_prototype_axis(model, G_AXIS_NEG_PROTOTYPES, G_AXIS_POS_PROTOTYPES)

    df["axis_t_technology"] = (embeddings @ vec_t) - center_t
    df["axis_g_governance"] = (embeddings @ vec_g) - center_g

    # Standardized scores kept for presentation only; raw centered scores remain
    # the reproducible values used in all inferential analyses.
    df["axis_t_technology_z"] = _standardize(df["axis_t_technology"])
    df["axis_g_governance_z"] = _standardize(df["axis_g_governance"])

    # Orthogonality context (H3 models G as a function of T, so their
    # correlation is reported descriptively rather than assumed to be zero).
    r_tg, _ = pearsonr(df["axis_t_technology"], df["axis_g_governance"])

    loo_t = _loo_prototype_axis(
        model, embeddings, df["axis_t_technology"].values,
        T_AXIS_NEG_PROTOTYPES, T_AXIS_POS_PROTOTYPES,
    )
    loo_g = _loo_prototype_axis(
        model, embeddings, df["axis_g_governance"].values,
        G_AXIS_NEG_PROTOTYPES, G_AXIS_POS_PROTOTYPES,
    )

    out = df[[
        "id", "title", "publication_year", "cluster",
        "axis_t_technology", "axis_g_governance",
        "axis_t_technology_z", "axis_g_governance_z",
    ]].copy()
    out.to_csv(paths.indicators_dir / "axis_scores.csv", index=False)

    report_lines = [
        "SEMANTIC AXIS VALIDATION REPORT — LATIN.SCIENCE 2026 PAPER",
        "=" * 62,
        "",
        "Two theory-guided prototype axes (written before inspecting results):",
        "",
        "  Axis T — technological specificity (Generic AI -> Named GenAI model)",
        f"    NEG pole (1): {len(T_AXIS_NEG_PROTOTYPES)} prototypes, generic AI/ML, no named model.",
        f"    POS pole (5): {len(T_AXIS_POS_PROTOTYPES)} prototypes, ChatGPT/GPT-4/Claude/etc. central.",
        f"    centered at midpoint: center={center_t:+.4f}",
        "",
        "  Axis G — governance orientation (Workflow support -> Governance/Integrity)",
        f"    NEG pole (1): {len(G_AXIS_NEG_PROTOTYPES)} prototypes, workflow/task support.",
        f"    POS pole (5): {len(G_AXIS_POS_PROTOTYPES)} prototypes, governance/integrity/policy.",
        f"    centered at midpoint: center={center_g:+.4f}",
        "",
        f"Orthogonality (Pearson r between centered scores):  T x G = {r_tg:+.4f}",
        "",
        "LOO stability is leave-one-prototype-out: the axis is rebuilt dropping",
        "each prototype in turn and the Spearman rho vs the primary ordering is",
        "reported. Paper target: minimum rho >= .80; below .70 the axis is weak.",
        "",
        "LOO Stability:",
    ]

    loo_results = {"T": loo_t, "G": loo_g}
    for axis_name, (mean_rho, min_rho) in loo_results.items():
        status = "PASS" if min_rho > 0.80 else ("MARGINAL" if min_rho > 0.70 else "WEAK")
        report_lines.append(f"  Axis {axis_name}: mean={mean_rho:.3f}  min={min_rho:.3f}  [{status}]")

    report_lines.append("")
    report_lines.append("Prototypes used (also in the paper appendix):")
    for label, prototypes in (
        ("T_NEG", T_AXIS_NEG_PROTOTYPES),
        ("T_POS", T_AXIS_POS_PROTOTYPES),
        ("G_NEG", G_AXIS_NEG_PROTOTYPES),
        ("G_POS", G_AXIS_POS_PROTOTYPES),
    ):
        report_lines.append(f"  [{label}]")
        for idx, proto in enumerate(prototypes, start=1):
            report_lines.append(f"    {idx}. {proto}")

    (paths.indicators_dir / "axis_validation.txt").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )

    print(f"Saved: {paths.indicators_dir / 'axis_scores.csv'}")
    print(f"Saved: {paths.indicators_dir / 'axis_validation.txt'}")
