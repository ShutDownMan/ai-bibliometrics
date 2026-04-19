"""
axis_tournament.py — Probe many hand-crafted axis candidates. 

For each axis we report:
  - std of projected scores (spread)
  - LOO stability: min Spearman rho across 6 paraphrase variants
  - Orthogonality to every other axis (Pearson r of scores)
  - Named top/bottom-3 papers so we can sanity-check

We then rank candidates and identify the 2-3 best non-redundant axes.

Design principle:
  - Poles are CONCRETE ACTIONS, not abstract concepts
  - We predict a priori where the bulk of the corpus lands
  - The interesting signal is the DRIFT toward the minority pole
  - Poles must be semantically irreducible (no text is 50/50)
"""

import argparse
from pathlib import Path


def _resolve_run_dir() -> Path:
    parser = argparse.ArgumentParser(description="Probe many handcrafted semantic axis candidates.")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory. Defaults to the repository root.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    run_dir = Path(args.run_dir) if args.run_dir else repo_root
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    return run_dir.resolve()


ROOT = _resolve_run_dir()

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from scipy.stats import spearmanr, pearsonr

df = pd.read_csv(ROOT / "corpus_clustered.csv")
emb = np.load(ROOT / "embeddings_bgem3.npy")

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-m3", device=device)
model.eval()

def encode(text):
    return model.encode(text, normalize_embeddings=True).astype(np.float32)

def axis_vec(neg, pos):
    v = encode(pos) - encode(neg)
    v /= np.linalg.norm(v)
    return v

def loo_score(primary_scores, variants_neg, variants_pos, axis_neg, axis_pos):
    """Compute mean and min Spearman rho when each variant replaces one pole."""
    rhos = []
    for var_neg in variants_neg:
        v = axis_vec(var_neg, axis_pos)
        rho, _ = spearmanr(primary_scores, emb @ v)
        rhos.append(rho)
    for var_pos in variants_pos:
        v = axis_vec(axis_neg, var_pos)
        rho, _ = spearmanr(primary_scores, emb @ v)
        rhos.append(rho)
    return np.mean(rhos), np.min(rhos), rhos

# ═══════════════════════════════════════════════════════════════════════════
# AXIS CANDIDATES
# Format: (name, expected_lean_note, neg_pole, pos_pole, [neg_variants], [pos_variants])
# ═══════════════════════════════════════════════════════════════════════════

CANDIDATES = [

    # ── A: WHO benefits from the AI tool
    # Expected: bulk leans NEGATIVE (students in class)
    # Insight: field frames AI as student tool, not researcher tool
    (
        "A_who_benefits",
        "BULK expected: student/learner side",
        # neg pole — student as beneficiary
        "A student uses an AI chatbot in a language class to improve speaking fluency, "
        "grammar accuracy and written composition skills assigned by the teacher.",
        # pos pole — researcher/author as beneficiary
        "A researcher uses AI to read and summarise papers, draft manuscript sections, "
        "check citations and accelerate the completion of a scientific article.",
        # neg variants
        [
            "Learners interact with an AI assistant during a language lesson and the "
            "teacher records improvements in their conversational and grammatical competence.",
            "Students in an EFL classroom practise pronunciation and vocabulary with an "
            "AI tutor and submit written assignments assisted by the tool.",
            "Secondary school pupils use an AI writing assistant to correct their essays "
            "and receive personalised feedback on their language errors.",
        ],
        # pos variants
        [
            "A professor feeds PDF articles into an AI tool to extract key arguments, "
            "identify research gaps and organise them into a literature review outline.",
            "PhD candidates use large language models to paraphrase dense academic texts, "
            "generate hypotheses and write the introduction of their dissertation.",
            "Scientists use AI to process large datasets, auto-generate experiment "
            "summaries and prepare the first draft of a journal submission.",
        ],
    ),

    # ── B: WHAT is being measured
    # Expected: bulk leans NEGATIVE (attitudes / perceived usefulness)
    # Insight: field measures feelings, not objective outcomes
    (
        "B_what_measured",
        "BULK expected: attitudes/perceptions side",
        # neg pole — subjective perception / attitudes
        "The study surveys students and teachers about their perceptions, attitudes "
        "and self-reported confidence when using AI tools in educational settings.",
        # pos pole — objective measured outcomes
        "The study administers standardised pre-tests and post-tests to measure "
        "actual changes in writing quality, error rate, or reading assessment scores.",
        # neg variants
        [
            "Participants complete Likert-scale questionnaires rating their satisfaction, "
            "motivation and perceived ease of use after interacting with AI tools.",
            "Researchers use interviews and focus groups to capture teachers' beliefs "
            "and concerns about adopting AI in their language classrooms.",
            "The paper reports students' self-efficacy ratings and attitudinal surveys "
            "after a semester of using an AI-assisted learning platform.",
        ],
        # pos variants
        [
            "Researchers compare essay scores graded by blind raters before and after "
            "an AI writing intervention to measure objective quality gains.",
            "The intervention is evaluated with standardised proficiency tests administered "
            "to both experimental and control groups to measure learning outcomes.",
            "Accuracy, fluency and coherence are scored by independent raters to quantify "
            "real improvement in student language production after AI use.",
        ],
    ),

    # ── C: SCOPE of evidence
    # Expected: bulk leans NEGATIVE (single context)
    # Insight: field dominated by narrow case studies; synthesis papers are rare but high-cited
    (
        "C_scope_of_evidence",
        "BULK expected: single-context side",
        # neg pole — single classroom / one course
        "This study describes a single experiment conducted in one classroom at one "
        "university, observing one cohort of students using one AI tool over one semester.",
        # pos pole — multi-study synthesis
        "This systematic review applies PRISMA screening criteria across multiple "
        "databases to synthesise findings from dozens of independent studies and derive "
        "cumulative conclusions about AI in education.",
        # neg variants
        [
            "The authors report on a pilot study with thirty students in one English "
            "writing course to explore how they responded to AI feedback.",
            "A case study at a single Indonesian university describes how ten teachers "
            "incorporated ChatGPT into their language syllabus for one term.",
            "Forty undergraduate students at one college were observed over eight weeks "
            "to document how they used an AI chatbot in their writing assignments.",
        ],
        # pos variants
        [
            "A meta-analysis pools effect sizes from randomised controlled trials to "
            "estimate the average impact of AI tools on academic writing proficiency.",
            "The bibliometric analysis examines publication patterns across hundreds of "
            "peer-reviewed articles to map the intellectual structure of the AI-in-education field.",
            "By synthesising empirical findings from over fifty articles, the review "
            "identifies consistent moderators and boundary conditions of AI effectiveness.",
        ],
    ),

    # ── D: STANCE toward AI adoption
    # Expected: bulk leans NEGATIVE (prescriptive adoption)
    # Insight: field overwhelmingly tells HOW to adopt, rarely asks WHETHER to; 
    #          the few critical papers are highly cited
    (
        "D_stance_toward_AI",
        "BULK expected: prescriptive adoption side",
        # neg pole — prescriptive: how to integrate
        "This article recommends practical strategies, lesson plans and implementation "
        "frameworks to help teachers successfully integrate AI tools into their courses.",
        # pos pole — critical: questioning adoption
        "This article questions the uncritical adoption of AI in education, documents "
        "risks of dependency, plagiarism and the erosion of thinking skills, and calls "
        "for regulatory guidelines and ethical oversight.",
        # neg variants
        [
            "The paper provides guidelines for designing AI-assisted language curricula "
            "and describes which tools work best for different proficiency levels.",
            "The authors propose a step-by-step framework for educators to adopt "
            "chatbots in their classrooms while maximising student engagement.",
            "The study offers actionable recommendations for institutions planning to "
            "integrate AI writing assistants into their academic programmes.",
        ],
        # pos variants
        [
            "The article analyses how AI-generated text enables academic dishonesty, "
            "undermines assessment validity and threatens the integrity of education.",
            "The authors challenge optimistic narratives about AI and argue that "
            "over-reliance on these tools reduces students' critical thinking capacity.",
            "The paper raises concerns about algorithmic bias, data privacy and the "
            "commodification of education through AI platforms.",
        ],
    ),

    # ── E: TECHNOLOGY framing (named GenAI vs generic AI)
    # Expected: bulk leans POSITIVE (ChatGPT/GenAI) post-2022; temporal signal
    # Insight: this axis should expose the pre/post ChatGPT rupture in the temporal drift
    (
        "E_technology_framing",
        "BULK expected: GenAI-specific side (2023-2026); temporal drift axis",
        # neg pole — generic / traditional AI / ML systems
        "This paper discusses artificial intelligence and machine learning systems "
        "in education without naming a specific product, using AI as a general concept "
        "for intelligent tutoring, adaptive learning or speech recognition.",
        # pos pole — ChatGPT / GenAI specific
        "This paper focuses specifically on ChatGPT, GPT-4 or other named generative "
        "AI large language models and documents how students and teachers use these "
        "tools to generate text, answer questions and support academic writing.",
        # neg variants
        [
            "The article explores how machine learning algorithms personalise instruction "
            "and adapt content difficulty without naming a specific commercial AI product.",
            "The study evaluates an AI-powered tutoring system that uses neural networks "
            "to track student progress and recommend exercises automatically.",
            "Researchers test whether an intelligent tutoring system improves reading "
            "comprehension scores compared to conventional instruction.",
        ],
        # pos variants
        [
            "Students interact with ChatGPT by typing prompts to generate essay drafts, "
            "grammar corrections and model answers for their language assignments.",
            "The study asks learners to use ChatGPT or Gemini to produce academic texts "
            "and then reflects on how these outputs affect their own writing process.",
            "Teachers in the study use large language models such as GPT-4 to create "
            "lesson materials, design exercises and provide feedback on student essays.",
        ],
    ),

    # ── F: EDUCATIONAL LEVEL (K-12 / EFL school vs. Higher education / research)
    # Expected: bulk leans NEGATIVE (school / EFL level)
    # Insight: when framed as "academic production", most papers are actually K-12 or language school
    (
        "F_educational_level",
        "BULK expected: K-12/EFL side",
        # neg pole — school-level language learners
        "Secondary school or undergraduate foreign language students practise English "
        "grammar, conversation and writing in class activities using AI chatbots as "
        "a substitute for or supplement to their classroom teacher.",
        # pos pole — graduate / research level
        "Graduate students, postdoctoral researchers and university professors use "
        "AI tools to manage literature, draft academic papers, respond to peer review "
        "and navigate the publication process in scholarly journals.",
        # neg variants
        [
            "High school EFL students in Indonesia, Turkey or China use AI apps "
            "to complete homework assignments and practise for standardised English tests.",
            "Primary or secondary school language learners interact with AI tutors "
            "to build basic vocabulary, pronunciation and reading comprehension.",
            "Undergraduate students in language courses use AI writing assistants "
            "to draft paragraphs and receive corrective feedback on their grammar.",
        ],
        # pos variants
        [
            "PhD students use AI to conduct literature searches, manage Zotero libraries "
            "and generate structured outlines of their thesis chapters.",
            "Academics use AI to respond to reviewer comments, reformulate arguments "
            "and polish the language of manuscripts before resubmission.",
            "University researchers use generative AI during the peer review process, "
            "to check methodological consistency and to strengthen their discussion sections.",
        ],
    ),

    # ── G: TEMPORAL FRAME (immediate classroom vs. longitudinal / future)
    # Expected: bulk leans NEGATIVE (immediate, one shot)
    # Conceptually different from C (scope of evidence); about time horizon, not number of studies
    (
        "G_time_horizon",
        "BULK expected: immediate classroom snapshot side",
        # neg pole — immediate, snapshot
        "The study takes a snapshot of one semester in one class and reports what "
        "happened when students used AI tools during that specific period.",
        # pos pole — longitudinal, future-looking
        "The paper tracks changes over multiple years or projects future trajectories, "
        "modelling how AI will transform academic writing and research over the next decade.",
        # neg variants
        [
            "The intervention runs for eight weeks, after which perceptions are collected "
            "through a post-test questionnaire from the participating students.",
            "Data were collected at one point in time from students who completed a "
            "survey about their experience using AI during the current academic term.",
            "A single-semester study observes how one cohort of students responds "
            "to an AI writing tool introduced for the first time in their class.",
        ],
        # pos variants
        [
            "The authors model future adoption curves and forecast how AI will reshape "
            "university curricula and academic assessment policies by 2030.",
            "A three-year longitudinal study tracks the same cohort of students to "
            "document how their use of AI tools evolves from first year to graduation.",
            "The paper proposes a roadmap for higher education institutions to prepare "
            "for the next generation of AI and its long-term implications for research.",
        ],
    ),

]

# ═══════════════════════════════════════════════════════════════════════════
# RUN THE TOURNAMENT
# ═══════════════════════════════════════════════════════════════════════════

scores_matrix = {}   # axis_name -> np.array of shape (n,)
results = []

print("Encoding axes and running LOO validation...\n")
for name, lean_note, neg, pos, neg_vars, pos_vars in CANDIDATES:
    av = axis_vec(neg, pos)
    s = emb @ av
    scores_matrix[name] = s

    mean_rho, min_rho, all_rhos = loo_score(s, neg_vars, pos_vars, neg, pos)
    df[name] = s

    results.append({
        "name": name,
        "lean": lean_note,
        "std": float(s.std()),
        "range": float(s.max() - s.min()),
        "mean_rho": float(mean_rho),
        "min_rho": float(min_rho),
        "rhos": all_rhos,
    })
    print(f"{name}: std={s.std():.4f}  range={s.max()-s.min():.3f}  LOO mean={mean_rho:.3f} min={min_rho:.3f}")

# ── Stability summary ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("AXIS RANKING  (sorted by min LOO rho × std — best first)")
print("=" * 70)

for r in sorted(results, key=lambda x: x["min_rho"] * x["std"], reverse=True):
    status = "PASS" if r["min_rho"] > 0.90 else ("OK" if r["min_rho"] > 0.80 else "WEAK")
    print(f"  [{status:4s}] {r['name']:36s}  std={r['std']:.4f}  LOO min={r['min_rho']:.3f}")

# ── Correlation matrix between all axes ───────────────────────────────────
names = [r["name"] for r in results]
print("\n\n" + "=" * 70)
print("CROSS-AXIS PEARSON CORRELATION (want < 0.35 between chosen pair)")
print("=" * 70)
header = "  " + "".join([f"{n[0]:>8s}" for n in names])
print(header)
for n1 in names:
    row = f"{n1[0]} "
    for n2 in names:
        r, _ = pearsonr(scores_matrix[n1], scores_matrix[n2])
        row += f"  {r:+.3f}"
    print(row)

# ── Per-cluster means to see which axis separates clusters ────────────────
print("\n\n" + "=" * 70)
print("CLUSTER MEANS PER AXIS")
print("=" * 70)
row_header = f"  {'Axis':36s}" + "".join([f"  C{c}" for c in sorted(df['cluster'].unique())])
print(row_header)
for r in results:
    row = f"  {r['name']:36s}"
    for c in sorted(df["cluster"].unique()):
        m = df.loc[df["cluster"] == c, r["name"]].mean()
        row += f"  {m:+.3f}"
    print(row)

# ── Top/bottom-3 papers per axis ──────────────────────────────────────────
print("\n\n" + "=" * 70)
print("TOP/BOTTOM 3 PAPERS PER AXIS (sanity check)")
print("=" * 70)
for r in results:
    s = scores_matrix[r["name"]]
    print(f"\n{r['name']}  [{r['lean']}]")
    pole_pos = r["name"].split("_vs_")[-1] if "_vs_" in r["name"] else "pos"
    pole_neg = r["name"].split("_vs_")[0].split("_", 1)[-1] if "_vs_" in r["name"] else "neg"
    print(f"  TOP 3 → {r['name'].upper()}+:")
    for i in np.argsort(s)[-3:][::-1]:
        row = df.iloc[i]
        print(f"    [{row['publication_year']} C{row['cluster']} {s[i]:+.3f}] {str(row['title'])[:72]}")
    print(f"  BOT 3 → {r['name'].upper()}-:")
    for i in np.argsort(s)[:3]:
        row = df.iloc[i]
        print(f"    [{row['publication_year']} C{row['cluster']} {s[i]:+.3f}] {str(row['title'])[:72]}")
