from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr
from sentence_transformers import SentenceTransformer

from .paths import RunPaths, ensure_run_dirs


# Axis E — Technology specificity: Generic AI  →  ChatGPT/Named GenAI
NEG_E = (
    "This paper benchmarks multiple AI systems on academic tasks without referring "
    "to a specific commercial model, comparing accuracy and efficiency across "
    "general-purpose language models and AI-assisted research workflows."
)
POS_E = (
    "This paper specifically tests ChatGPT, GPT-4, or Claude on peer review, "
    "manuscript drafting, or systematic literature screening tasks and documents "
    "their real-world performance for researchers and academic authors."
)
NEG_E_VARIANTS = [
    "The study evaluates AI-assisted literature screening tools without naming "
    "a specific large language model, comparing recall and precision across systems.",
    "Researchers compare the accuracy of several AI writing assistants on "
    "manuscript revision tasks without attributing results to a named model.",
    "The article reviews AI applications in academic workflows using generic "
    "terminology for language models without specifying any commercial product.",
]
POS_E_VARIANTS = [
    "The authors ask researchers to use ChatGPT to draft abstract sections and "
    "report how GPT-4 outputs compare to human-written scientific prose.",
    "The study measures how accurately ChatGPT identifies methodological flaws "
    "when acting as a peer reviewer for submitted journal manuscripts.",
    "Participants use GPT-4 or Claude to perform systematic review screening "
    "and the paper quantifies agreement with expert human raters.",
]

# Axis N — Posture: Opportunity/productivity framing  →  Risk/harm/governance framing
# Central rhetorical divide: papers championing AI adoption vs papers scrutinising harm.
NEG_N = (
    "This paper presents generative AI and ChatGPT as transformative tools for"
    " researchers and students, argues that AI will improve scientific productivity,"
    " accelerate literature review, and help with manuscript drafting, and encourages"
    " academic communities to adopt AI to advance research and education."
)
POS_N = (
    "This paper documents how AI-generated text and ChatGPT undermine academic"
    " integrity, reports hallucinated references, ghost-written manuscripts, and"
    " AI-assisted cheating, and calls for institutional policies, detection mechanisms,"
    " and governance frameworks to protect scholarly publishing and research ethics."
)
NEG_N_VARIANTS = [
    "The study highlights benefits of ChatGPT for academic work: AI personalises learning,"
    " reduces repetitive writing tasks, and makes research tools accessible to students"
    " and junior researchers, suggesting universities should support AI adoption.",
    "Classroom experiments reveal that students who use ChatGPT submit higher-quality"
    " drafts in less time, complete writing assignments with less stress, and report"
    " greater academic confidence, pointing to clear productivity gains from AI adoption.",
    "Evidence from surveys shows that students and researchers using ChatGPT produce"
    " higher-quality writing faster, report reduced workload, and perceive AI as a"
    " net positive for academic productivity and educational outcomes.",
]
POS_N_VARIANTS = [
    "The paper measures academic misconduct enabled by generative AI: ChatGPT fabricated"
    " references in a majority of test cases, AI text bypassed plagiarism checks, and"
    " ghost-written student submissions successfully deceived educators.",
    "Survey evidence shows widespread undisclosed AI use in student submissions:"
    " professors could not reliably identify AI-generated essays, academic integrity"
    " offices reported increased violations, and scholarly trust was undermined.",
    "The paper evaluates ChatGPT-generated academic content and finds that the model"
    " consistently produces fabricated citations, presents incorrect claims as established"
    " facts, and makes it unsafe to use AI output in scientific manuscripts without"
    " expert verification, calling for urgent safeguards in scholarly publishing.",
]

# Axis G — Scholarly use: Workflow/tool enablement  →  Guardrails/risk-assessment focus
# This axis is intentionally written as a clean textual contrast rather than derived from tags.
# The goal is to separate papers that mainly treat GenAI as a research/writing aid from papers
# that mainly frame GenAI around guardrails, risk assessment, integrity, disclosure, and policy.
NEG_G = (
    "This paper evaluates ChatGPT and other large language models as tools for academic "
    "workflows such as literature search, title and abstract screening, systematic reviews, "
    "manuscript drafting, academic writing support, revision, feedback generation, and peer "
    "review assistance. The central question is how generative AI can help researchers, "
    "reviewers, and students perform scholarly tasks more effectively."
)
POS_G = (
    "This paper examines responsible use of ChatGPT in higher education and scholarly "
    "publishing, focusing on academic integrity, AI literacy, detection of AI-generated text, "
    "hallucinated references, disclosure and authorship rules, assessment redesign, journal or "
    "university guidelines, and institutional guardrails for governing generative AI in "
    "academic work."
)
NEG_G_VARIANTS = [
    "The study tests large language models as assistants for academic writing, abstract "
    "screening, systematic review workflows, literature synthesis, and manuscript preparation, "
    "with emphasis on practical task support.",
    "Researchers assess whether ChatGPT can support peer review, feedback writing, database "
    "searching, editing, and drafting in scholarly communication and research workflows.",
    "The paper treats generative AI as a copilot for academic work, helping with writing, "
    "reviewing, screening, summarising, and other research tasks rather than discussing policy "
    "or integrity rules.",
]
POS_G_VARIANTS = [
    "The study asks how universities should set rules for ChatGPT use, emphasising academic "
    "integrity, disclosure, student assessment policies, AI literacy, and responsible-use "
    "guidelines.",
    "Researchers evaluate guardrails for generative AI in scholarly publishing, including "
    "authorship disclosure, fabricated references, plagiarism concerns, detection of "
    "AI-generated text, and editorial policy.",
    "The paper focuses on governance of generative AI in academic settings: responsible use, "
    "risk assessment, institutional policy, integrity protection, and rules for using ChatGPT "
    "in education and research.",
]
NEG_G_PROTOTYPES = [NEG_G, *NEG_G_VARIANTS]
POS_G_PROTOTYPES = [POS_G, *POS_G_VARIANTS]

# Axis R — Domain: Academic/scholarly/education context  →  Clinical/biomedical/healthcare context
# Two major discourse communities in this corpus with near-zero lexical overlap.
NEG_R = (
    "This paper examines generative AI in the context of academic writing, scholarly"
    " publishing, and higher education, discussing how universities and journals should"
    " respond to ChatGPT through policy changes on authorship, assessment, plagiarism,"
    " and the protection of academic integrity in student and faculty work."
)
POS_R = (
    "This paper evaluates the performance of artificial intelligence models on clinical"
    " tasks, measures diagnostic accuracy using patient data from hospital settings,"
    " assesses how machine learning predicts health outcomes or assists physician"
    " decision-making, and discusses implications for clinical practice and patient care."
)
NEG_R_VARIANTS = [
    "The study surveys academics and students about AI use in academic writing contexts,"
    " examines faculty attitudes towards AI-assisted assignments, and proposes redesigns"
    " to preserve learning outcomes at universities in the generative AI era.",
    "The research investigates how journal editors and peer reviewers are responding"
    " to AI-generated manuscript submissions, analyses publisher policies, and explores"
    " how peer review must evolve given ChatGPT-assisted scientific writing.",
    "The authors review generative AI in educational settings, examining how ChatGPT"
    " affects student learning, academic dishonesty, and teaching practices across"
    " secondary and higher education institutions worldwide.",
]
POS_R_VARIANTS = [
    "The study trains a deep learning model on electronic health records and medical"
    " images to detect early-stage disease, reports sensitivity and specificity"
    " compared to physician diagnosis, and demonstrates clinical value for patient screening.",
    "The research develops a machine learning algorithm to predict readmission or"
    " mortality risk using clinical data, benchmarks it against established medical"
    " risk scores, and discusses integrating AI tools into routine care pathways.",
    "The paper evaluates a large language model's accuracy in answering clinical"
    " questions, differential diagnosis, and medical licensing examinations, reporting"
    " performance metrics relevant to clinicians and healthcare educators.",
]


def _encode(model: SentenceTransformer, text: str) -> np.ndarray:
    return model.encode(text, normalize_embeddings=True).astype(np.float32)


def _make_axis(model: SentenceTransformer, neg: str, pos: str) -> np.ndarray:
    vector = _encode(model, pos) - _encode(model, neg)
    vector /= np.linalg.norm(vector)
    return vector


def _make_centered_axis_from_vectors(neg_vec: np.ndarray, pos_vec: np.ndarray) -> tuple[np.ndarray, float]:
    vector = pos_vec - neg_vec
    vector /= np.linalg.norm(vector)
    center = float(((pos_vec @ vector) + (neg_vec @ vector)) / 2.0)
    return vector.astype(np.float32), center


def _make_centered_text_axis(model: SentenceTransformer, neg: str, pos: str) -> tuple[np.ndarray, float]:
    return _make_centered_axis_from_vectors(_encode(model, neg), _encode(model, pos))


def _make_prototype_axis(model: SentenceTransformer, neg_texts: list[str], pos_texts: list[str]) -> tuple[np.ndarray, float]:
    neg_vec = np.stack([_encode(model, text) for text in neg_texts], axis=0).mean(axis=0)
    pos_vec = np.stack([_encode(model, text) for text in pos_texts], axis=0).mean(axis=0)
    return _make_centered_axis_from_vectors(neg_vec, pos_vec)


def _loo(model: SentenceTransformer, embeddings: np.ndarray, primary_scores, neg_variants, pos_variants, neg_pole, pos_pole):
    rhos = []
    for variant in neg_variants:
        rho, _ = spearmanr(primary_scores, embeddings @ _make_axis(model, variant, pos_pole))
        rhos.append(rho)
    for variant in pos_variants:
        rho, _ = spearmanr(primary_scores, embeddings @ _make_axis(model, neg_pole, variant))
        rhos.append(rho)
    return float(np.mean(rhos)), float(np.min(rhos))


def _loo_prototype_axis(model: SentenceTransformer, embeddings: np.ndarray, primary_scores, neg_texts, pos_texts):
    rhos: list[float] = []
    for idx in range(len(neg_texts)):
        sampled_neg = neg_texts[:idx] + neg_texts[idx + 1:]
        sampled_vec, sampled_center = _make_prototype_axis(model, sampled_neg, pos_texts)
        rho, _ = spearmanr(primary_scores, (embeddings @ sampled_vec) - sampled_center)
        rhos.append(float(rho))
    for idx in range(len(pos_texts)):
        sampled_pos = pos_texts[:idx] + pos_texts[idx + 1:]
        sampled_vec, sampled_center = _make_prototype_axis(model, neg_texts, sampled_pos)
        rho, _ = spearmanr(primary_scores, (embeddings @ sampled_vec) - sampled_center)
        rhos.append(float(rho))
    return float(np.mean(rhos)), float(np.min(rhos))


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)

    df = pd.read_csv(paths.corpus_clustered_path)
    embeddings = np.load(paths.embeddings_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    model.eval()

    vec_e = _make_axis(model, NEG_E, POS_E)
    vec_n = _make_axis(model, NEG_N, POS_N)
    vec_r = _make_axis(model, NEG_R, POS_R)
    vec_g, center_g = _make_prototype_axis(model, NEG_G_PROTOTYPES, POS_G_PROTOTYPES)

    df["axis_e_technology"] = embeddings @ vec_e
    df["axis_g_guardrails"] = (embeddings @ vec_g) - center_g
    df["axis_n_domain"] = embeddings @ vec_n
    df["axis_r_scope"] = embeddings @ vec_r

    r_eg, _ = pearsonr(df["axis_e_technology"], df["axis_g_guardrails"])
    r_en, _ = pearsonr(df["axis_e_technology"], df["axis_n_domain"])
    r_er, _ = pearsonr(df["axis_e_technology"], df["axis_r_scope"])
    r_gn, _ = pearsonr(df["axis_g_guardrails"], df["axis_n_domain"])
    r_gr, _ = pearsonr(df["axis_g_guardrails"], df["axis_r_scope"])
    r_nr, _ = pearsonr(df["axis_n_domain"], df["axis_r_scope"])

    loo_results = {
        "E": _loo(model, embeddings, df["axis_e_technology"].values, NEG_E_VARIANTS, POS_E_VARIANTS, NEG_E, POS_E),
        "G": _loo_prototype_axis(model, embeddings, df["axis_g_guardrails"].values, NEG_G_PROTOTYPES, POS_G_PROTOTYPES),
        "N": _loo(model, embeddings, df["axis_n_domain"].values, NEG_N_VARIANTS, POS_N_VARIANTS, NEG_N, POS_N),
        "R": _loo(model, embeddings, df["axis_r_scope"].values, NEG_R_VARIANTS, POS_R_VARIANTS, NEG_R, POS_R),
    }

    out = df[[
        "id", "title", "publication_year", "cluster",
        "axis_e_technology", "axis_g_guardrails", "axis_n_domain", "axis_r_scope",
    ]].copy()
    out.to_csv(paths.indicators_dir / "axis_scores.csv", index=False)

    report_lines = [
        "SEMANTIC AXIS VALIDATION REPORT",
        "=" * 50,
        "",
        "Selected axes:",
        "  E: Generic AI framing -> ChatGPT/Named GenAI specific",
        "  G: Workflow/tool enablement -> Guardrails/risk-assessment focus (hand-written prototype sets)",
        "  N: Opportunity/productivity framing -> Risk/harm/governance framing (Posture)",
        "  R: Academic/scholarly/education context -> Clinical/biomedical/healthcare context (Domain)",
        "",
        "Orthogonality (Pearson r between projected scores):",
        f"  E x G: {r_eg:+.4f}",
        f"  E x N: {r_en:+.4f}",
        f"  E x R: {r_er:+.4f}",
        f"  G x N: {r_gn:+.4f}",
        f"  G x R: {r_gr:+.4f}",
        f"  N x R: {r_nr:+.4f}",
        "",
        f"Guardrails axis centered at the midpoint between its written negative and positive prototype sets: center={center_g:+.4f}.",
        "Stability for E, N, and R uses leave-one-out paraphrases of the text poles; G uses leave-one-out over its written prototype sentences.",
        "",
        "LOO Stability:",
    ]
    for axis_name, (mean_rho, min_rho) in loo_results.items():
        status = "PASS" if min_rho > 0.70 else ("MARGINAL" if min_rho > 0.60 else "WEAK")
        report_lines.append(f"  Axis {axis_name}: mean={mean_rho:.3f}  min={min_rho:.3f}  [{status}]")
    (paths.indicators_dir / "axis_validation.txt").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Saved: {paths.indicators_dir / 'axis_scores.csv'}")
    print(f"Saved: {paths.indicators_dir / 'axis_validation.txt'}")