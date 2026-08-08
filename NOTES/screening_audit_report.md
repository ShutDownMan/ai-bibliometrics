# Screening Audit Report — v14 Corpus Clustering (Latin.Science 2026)

**Date:** 2026-08-08
**Auditor:** Claude Code (semi-automated; human-judgement review of stratified samples)
**Corpus:** `runs/academic_production_v14/corpus_clustered.csv` (6,261 papers)
**Scope definition:** `NOTES/latin_science_full_paper_plan.md` — AI/GenAI applied to scholarly
communication, academic writing, peer review, evidence synthesis as research activity,
research/academic integrity, and institutional GenAI use in higher education linked to
academic writing, assessment, AI literacy, or integrity.

---

## 1. Executive Summary

### Key counts

| Item | Count |
|---|---|
| Total corpus (v14) | 6,261 |
| Cluster 0 "Applied AI Systems · Engineering and Environment" (expected OUT) | 1,326 |
| Cluster 1 "Clinical Prediction and Risk Modeling" (expected OUT) | 1,215 |
| Cluster 2 "Medical Imaging and Diagnostic Applications" (expected OUT) | 2,011 |
| Cluster 3 "ChatGPT in Academic Communication · Education and Writing" (expected IN) | 607 |
| Cluster 4 "Higher Education · Policy, Assessment and AI Literacy" (expected IN) | 1,102 |
| **Clusters 3+4, papers flagged by a negative scope rule** | **877** |
| — flagged but also carrying a positive scope hit (conflicted) | 611 |
| — flagged with negative hit only | 266 |

### Main findings

1. **The IN clusters (3+4) are contaminated.** Of the 877 negative-flagged papers in
   clusters 3+4, a stratified, manually reviewed sample (n = 94) supports the estimate
   that **~387 (44%) are genuinely out of scope**, ~250 (29%) are genuinely borderline,
   and **~240 (27%) are false alarms — they triggered a negative rule but are actually
   in scope.** Translated to cluster level, the IN clusters contain roughly **387–400
   out-of-scope papers (~23% of 1,709)**, the majority being clinical/medical-education,
   EFL/language-teaching, and industrial/marketing papers.

2. **The OUT clusters (0–2) contain real false negatives.** Of the 1,411 positive-flagged
   papers there, an estimated **~134 (9.5%) are genuinely in scope**, and a refined
   cluster-by-cluster review puts the total at **~152 false negatives (~3.3% of 4,552)**,
   concentrated in cluster 0 (~110) and cluster 2 (~22). These are authorship-misconduct,
   research-integrity, paper-mill-fraud, AI-text-detection, editorial-policy, peer-review,
   and systematic-review-automation papers that got clustered with engineering/clinical
   topics.

3. **The dominant systematic error is one token: `paper mill` in the positive
   `integrity_governance` rule.** In clusters 0–2 it alone pulled 142 papers into the
   "integrity" bucket — most of them pulp-and-paper industry papers (wastewater, sludge,
   kraft-mill chemistry). A further 46 integrity flags come from the word **`authorship`**
   matching the boilerplate disclosure *"interest with respect to the research, authorship,
   and/or publication of this article"* that appears in nearly every biomedical paper, and
   ~80 come from `AI-generated (?:paper|manuscript|text|content)` matching AIGC/marketing
   papers. These three false-positive generators inflate `scope_positive_hits` in the OUT
   clusters and distort any analysis that uses `relevance_index` or positive-hit counts.

4. **The negative rules are context-blind.** `medical` fires on journal/domain words
   (e.g., *Cureus Journal of Medical Science*, *American Journal of Nursing*) even when the
   paper is about editorial policy, manuscript detection, or peer review in that journal;
   `classroom_pedagogy` fires on `perceptions`, `classroom`, `pedagogy` in higher-education
   AI-literacy and academic-integrity papers; `language_learning` fires on L2 *academic
   writing* papers that the plan explicitly wants to keep when they concern academic
   writing or integrity.

### Recommendations (headline)

- **Split `paper mill`** into fraud-context ("research paper mills", "paper mill" co-occurring
  with authors/manuscripts/fraud) vs. industry context.
- **Anchor `authorship`** to misconduct/policy phrases, not the bare word.
- **Make the `medical` negative rule conditional**: clinical-application tokens should
  exclude *unless* scholarly-communication tokens are present.
- **Add positive rules** for abstract screening, study selection, evidence-synthesis
  automation, medical-journal policy, medical/scientific writing, and AI-text detection —
  these are today's largest false-negative sources.
- **The cluster labels themselves should not drive the scope decision.** The plan already
  states clusters are auxiliary (silhouette ≈ 0.058). The screening rules must decide scope;
  clusters 0–2 still contain ~152 in-scope papers and clusters 3+4 still contain ~387
  out-of-scope papers.

---

## 2. False Positive Analysis — Clusters 3+4

### 2.1 Method

- Population: 877 papers in clusters 3+4 with non-empty `scope_negative_hits`.
- A manually reviewed stratified sample (n = 94) was built by strata
  `has_positive_hit × primary_negative_category` (`medical`, `classroom_pedagogy`,
  `industrial`, `language_learning`) and re-weighted to the population.
- Each reviewed paper was assigned: `FALSE_ALARM` (in scope despite the flag),
  `BORDERLINE`, or `OUT`.

### 2.2 Results

| Category | Papers flagged | Estimated FALSE_ALARM (in scope) | Estimated BORDERLINE | Estimated OUT |
|---|---|---|---|---|
| medical | 387* | ~200 (52%) | ~70 (18%) | ~117 (30%) |
| classroom_pedagogy | 329* | ~95 (29%) | ~110 (33%) | ~124 (38%) |
| industrial | 208* | ~27 (13%) | ~40 (19%) | ~141 (68%) |
| language_learning | 80* | ~23 (29%) | ~23 (29%) | ~34 (42%) |
| **Overall (unique papers)** | **877** | **~240 (27.4%)** | **~250 (28.5%)** | **~387 (44.1%)** |

\* Category counts overlap (some papers carry 2–3 negative categories), so rows sum above 877.

95% CI on the overall split (binomial approx., n = 94): FALSE_ALARM 18–36%, BORDERLINE
19–38%, OUT 34–54%. The estimate is directionally robust: roughly a quarter of the flags
are wrong, roughly two-fifths are right, and the rest are genuinely ambiguous.

### 2.3 Medical — the largest false-alarm source

The `medical` rule (`patient|clinical|medical|medicine|healthcare|hospital|nursing|dental|
surgery|…`) is pure word-matching. It fires on journal names and domain vocabulary even when
the unit of analysis is scholarly communication. Manually reviewed examples that are **in
scope (false alarms):**

| Title (truncated) | Why in scope | Negative token that fired |
|---|---|---|
| Defining the Boundaries of AI Use in Scientific Writing: Comparative Review of Editorial Policies | editorial policy / scientific writing | medical (journal context) |
| Artificial intelligence in scholarly peer review: scoping review | peer review / publishing workflows | medical |
| The great detectives: humans vs AI detectors … LLM-generated medical writing | AI-text detection in medical writing | medical |
| Using Artificial Intelligence for Scholarly Writing — Guidelines for nurse authors | scientific writing | medical (journal *American Journal of Nursing*) |
| A review of top cardiology … journal guidelines regarding generative AI | journal editorial policy | medical |
| Can OMFS experts distinguish AI from human manuscripts? | manuscript authorship detection | medical |
| What is the rate of text generated by AI … Orthopedics journal? | AI-text detection in publications | medical |
| LLMs show promising performance for some systematic review tasks | evidence-synthesis automation | medical |

Conversely, the **genuinely out-of-scope** medical flags are clinical-application papers:
*"ChatGPT in healthcare: a taxonomy and systematic review"*, *"LLMs for Chatbot Health
Advice"*, *"Evolving Role of ChatGPT in General Surgery"*, *"GPT in Dentistry"*, *"AI in
pharmacovigilance: predicting ADRs"*.

**Pattern:** medical + a scholarly-communication positive hit (research_writing /
integrity_governance) ⇒ ~75–80% are in scope. medical with no positive hit ⇒ ~85% are out.

### 2.4 Classroom pedagogy — fires on higher-education AI-literacy/integrity papers

`classroom_pedagogy` fires on `student perceptions`, `pedagogy`, `classroom`, `curriculum`.
Manually reviewed examples that are **in scope (false alarms):**

| Title | Why in scope |
|---|---|
| Generative AI and Higher Education: Trends, Challenges … SLR | higher ed + integrity/governance |
| GenAI et al.: Cocreation, Authorship, Ownership, Academic Ethics and Integrity | academic ethics/integrity |
| The impact of artificial intelligence on academic writing: a systematic literature review | academic writing |
| A pedagogical design for self-regulated learning in academic writing using GenAI | academic writing + HE |
| AI and Academic Integrity: Exploring Student Perceptions | integrity |
| Artificial Reviewers: Teaching Academic Writing with ChatGPT | academic writing |

Genuinely out-of-scope classroom flags are teaching-tool/application papers:
*"Teaching and learning computer programming using ChatGPT"*, *"Enhancing Engineering
Education Through LLM-Driven Adaptive Quiz Generation"*, *"AI in Computer Science Education"*,
*"Integrating AI into Art Education"*.

### 2.5 Language learning — mostly correct, with academic-writing exceptions

The rule correctly excludes *"Learner emotions in AI-assisted EFL"*, *"GenAI in language
teaching"*, *"LLM-based tools in Language Teaching"*. But it wrongly fired on:

| Title | Why in scope |
|---|---|
| Is ChatGPT-4 Accurate in Proofread a Manuscript in Otolaryngology? | manuscript editing/proofreading = scholarly writing |
| More human than human? … academic essays produced by ChatGPT-3.5 and human L2 writers | academic integrity + academic writing |
| Perceptions and detection of AI use in manuscript preparation for academic journals | manuscript norms/detection |

The plan explicitly keeps EFL/L2 work *with substantive relation to academic writing or
integrity* — the rule currently cannot express that nuance.

### 2.6 Industrial — mostly correct, occasional false alarm

Industrial flags are largely genuine OUT (tourism marketing, HR, portfolio management,
disaster management). Notable false alarms:

| Title | Why in scope |
|---|---|
| Can ChatGPT be used to predict citation counts, readership, social media interaction? | scientometrics / scholarly communication |
| The false positives and false negatives of generative AI detection tools in education and academic research | integrity / detection |
| Enhancing academic integrity among students in the GenAI era: a holistic framework | integrity |
| Unfolding the Potential of Generative AI: Design Principles for Chatbots in Academic Teaching and Research | academic teaching/research |

### 2.7 Suggested rule refinements (false-positive side)

1. **Make negative rules conditional on scholarly-communication context.** Compute a
   `scholarly_comm` boolean from positive rules (research_writing, integrity_governance,
   or the new evidence-synthesis rule). A negative category should *downgrade* (not veto)
   when `scholarly_comm` is true. Concretely: a paper about "medical writing",
   "nursing journal policy", or "peer review in dermatology" must NOT be excluded by the
   `medical` rule.
2. **Narrow `classroom_pedagogy`:** drop the bare word `perceptions` (fires on HE
   AI-literacy surveys) and `pedagogy` (fires on HE academic-writing pedagogy). Keep
   `K-12`, `secondary school`, `middle school`, `high school`, and teaching-tool phrases
   (`tutoring`, `quiz generation`, `lesson plan`, `learning analytics`) as the real
   exclusion signal.
3. **Narrow `language_learning`:** keep EFL/ESL/TESOL and language-teaching tokens but add
   a carve-out for `academic writing`, `academic essays`, `manuscript`, `scientific
   writing`, `academic integrity` co-occurring in the same abstract.
4. **Narrow `industrial`:** `social media` fires on scientometrics papers; restrict to
   marketing/advertising contexts (`social media marketing`, `consumer`, `brand`,
   `influencer`).

---

## 3. False Negative Analysis — Clusters 0–2

### 3.1 Method

- Population: 1,411 papers in clusters 0–2 with non-empty `scope_positive_hits`.
- Reviewed stratified sample (n = 48, by cluster × "specific" vs "generic" positive hits)
  plus full-title review of all 385 "specific" (research_writing/integrity) papers.
- Result: ~134 of the 1,411 (9.5%) are in scope. A refined cluster-level estimate adds
  no-positive-hit candidates (~10) for a total of **~152 false negatives (3.3% of 4,552).**

### 3.2 Distribution by cluster

| Cluster | Pos-hit papers | Est. in-scope (FN) | Typical content |
|---|---|---|---|
| 0 (engineering/env) | 585 | **~110** | authorship misconduct, paper-mill fraud, AI-text detection, editorial policy, peer review, publishing, abstract-screening automation |
| 1 (clinical prediction) | 322 | **~10** | ML tools for systematic reviews; rare LLM-in-research papers |
| 2 (medical imaging) | 504 | **~22** | medical-journal AI policies, medical peer review, AI-text detection in journals, medical/scientific writing |

### 3.3 Concrete false negatives (examples)

**Cluster 0 (research integrity / publishing):**
- *A review of annual statements on research integrity from UK institutions … research fraud*
- *Ghost and Honorary Authorship among social scientists* / *in Ophthalmology*
- *Publication and collaboration anomalies in academic papers originating from a paper mill*
- *Digital magic … how can journals and peer reviewers detect manuscripts from paper mills*
- *The raw truth about paper mills* / *How to fight fake papers*
- *Abuse of ORCID's weaknesses by authors who use paper mills*
- *On (Conflating) Predatory Journals … 'Compass to Publish'*
- *Plagiarism: A Bird's Eye View*; *Detection of AI-Generated Texts*
- *Paraphrasing evades detectors of AI-generated text*
- *Editorial stances on large language models in leading nursing publications*
- *Evaluation of LLMs for Peer Review in Transplantation Research*
- *Recent Issues in Medical Journal Publishing and Editing Policies*
- *The scope of open peer review in the scholarly publishing ecosystem*

**Cluster 2 (medical-journal scholarly communication):**
- *Neurosurgical journals' policies on AI use in manuscript preparation and peer review*
- *Variability of Guidelines and Disclosures for AI-Generated Content in Top Surgical Journals*
- *Experts in Shoulder Surgery Do Not Consistently Detect AI-Generated Scientific Abstracts*
- *Rise of the Machines: Prevalence and Disclosure of AI-Generated Text in High-Impact
  Orthopaedic Journals*
- *Assessment of Generative AI Policies across Dermatology Journals*
- *Artificial Intelligence as a Safeguard for Clinical Scientific Integrity: A Human-AI
  Hybrid Model for Medical Peer Review*

**Evidence-synthesis automation (straddles clusters 0/1/2):**
- *High-performance automated abstract screening with large language model ensembles* (c0)
- *The landscape of artificial intelligence tools and platforms for evidence synthesis* (c0)
- *A narrative review of recent tools … toward automating living systematic reviews* (c0)
- *Machine learning computational tools to assist the performance of systematic reviews* (c1)
- *Automated systematic reviews using machine learning and LLMs in clinical practice
  guideline development* (c0)

### 3.4 Why the positive rules miss these — and the polluting tokens

The "specific" bucket in clusters 0–2 (385 papers) is dominated by **false positives of the
positive rules**, not by true scholarly-communication papers:

| Trigger | Papers flagged in c0–2 | Problem |
|---|---|---|
| `paper mill` (integrity_governance) | 142 | pulp/paper industry papers, not fraud |
| `authorship` (integrity_governance) | 46 from disclosure boilerplate alone | *"interest with respect to the research, authorship, and/or publication"* is standard in every biomedical paper |
| `AI-generated (?:paper\|manuscript\|text\|content)` | 80 | AIGC/marketing/design papers |
| `systematic literature review` (research_workflow) | ~1,026 generic bucket | fires on any SR, regardless of automation or topic |

Because the positive rules are simultaneously too loose (paper mill, authorship, AIGC) and
too narrow (miss "abstract screening", "medical writing", "AI-text detection", "journal
policy"), the OUT clusters both absorb large numbers of irrelevant "specific" flags **and**
fail to surface the genuinely in-scope minority.

### 3.5 Suggested rule refinements (false-negative side)

1. **Add a dedicated `evidence_synthesis` positive rule:**
   `abstract screening|study selection|reference screening|evidence synthesis|systematic
   review automation|automated systematic review|living systematic review|title.{0,10}abstract screening|PICO.{0,20}(generation|queries)`
   This is the plan's explicitly in-scope activity ("busca bibliográfica, triagem ou
   síntese de evidências como atividade de pesquisa") and is currently the largest
   missed category.
2. **Add a `scholarly_publishing` positive rule:**
   `medical writing|scientific writing|journal polic|editorial polic|publishing polic|
   author guidelines|manuscript preparation|publication ethics|predatory journal|paper
   mill (in fraud context)|ORCID|authorship misconduct|authorship dispute|honorary
   authorship|ghost authorship|gift authorship|authorship attribution|AI-generated text
   detection|AI-text detection|machine-generated text detection|content detection`.
3. **Fix `integrity_governance`:**
   - Replace bare `paper mill` with `research paper mill|paper mill(s)? (fraud|blacklist|threat)|paper mill.{0,60}(manuscript|authors|publication)`.
   - Replace bare `authorship` with `authorship (misconduct|dispute|polic|guidelines|
     dilemma|equity|attribution|credits?|practices|conflict)|honorary authorship|ghost
     authorship|gift authorship|authorship-for-sale|authorship of`.
   - Restrict `AI-generated (?:paper|manuscript|text|content)` to detection contexts:
     `(detect|detection|identify|identifying|prevalence|disclosure|polic) .{0,40}AI-generated`.
4. **Fix `research_workflow`:** replace the unconditional `systematic literature review`
   with `(automated|AI.{0,5}assisted|LLM.{0,5}powered|tool.{0,10}) systematic (literature
   )?review` so a clinical SR of "X for diagnosis" no longer qualifies on its own.

---

## 4. Borderline Case Taxonomy

The single most important judgment call in this corpus is **"is AI the subject of
scholarly communication, or the object of a domain application?"** The following taxonomy
with decision guidance is used in `NOTES/screening_audit_borderline.csv` (60 cases).

### 4.1 Medical / health-professions education

- **IN if** the paper concerns academic writing, assessment integrity, AI literacy, or
  editorial policy in a medical/nursing/dental school.
  - *Academic Integrity Within the Medical Curriculum in the Age of GenAI* → IN
  - *Artificial Intelligence in Medical Education Assessments: Navigating the Challenges to
    Academic Integrity* → IN
  - *Navigating AI writing tools in medical education: SWOT of L2 academic writing* → IN
- **OUT if** AI is a teaching tool (content explanation, exam simulation, virtual patients,
  MCQ generation for instruction, clinical-skills training).
  - *Educational Applications of ChatGPT in University-Based Dental Education* → OUT
  - *ChatGPT and Other LLMs in Medical Education* → OUT
  - *AI in Medical Education: Transforming Learning and Practice* → OUT
- **Borderline if** education, research, and practice are bundled.
  - *ChatGPT Utility in Healthcare Education, Research, and Practice* → BORDERLINE

### 4.2 Systematic reviews: methodological vs. clinical application

- **IN (methodological):** the paper studies AI/LLM *doing* the review — abstract
  screening, study selection, evidence synthesis, PICO generation, living reviews.
  - *AI-Assisted Systematic Review: Humans Still Need to Review All Abstracts* → IN
  - *High-performance automated abstract screening with LLM ensembles* → IN
- **OUT (clinical application):** the paper *uses a systematic review as its method* to
  survey AI in some clinical task (diagnosis, prediction).
  - *ML for myocarditis diagnosis: a systematic review* → OUT
  - *AI for diabetes complication prediction: systematic review* → OUT
- **Borderline:** clinical topic but the unit is literature-review automation in that
  specialty (e.g., *GPT meets PubMed … literature review of migraine medications*,
  *LLMs in study selection for systematic review in obstetrics*).

### 4.3 Academic integrity in professional schools

- **IN:** integrity/authorship/plagiarism/detection regardless of the professional school —
  medicine, engineering, economics, nursing.
  - *GenAI in pharmacy education: implications for academic integrity* → IN
  - *AI integrity of graduation works in economics* → IN (borderline)
  - *AI and Academic Integrity: Exploring Student Perceptions in Higher Education* → IN
- **OUT:** the school/professional context is incidental to a teaching/practice question.
  - *AI-based teaching pedagogies in nursing education* → OUT

### 4.4 EFL / L2 academic writing

- **IN:** L2 papers centered on academic essays, manuscript preparation, academic integrity,
  or academic-writing pedagogy.
- **OUT:** L2 papers centered on language acquisition, fluency, speaking/reading skills,
  classroom emotion, or teacher training.
- **Borderline:** *Potentials and Implications of ChatGPT for ESL Writing Instruction*,
  *Critical Thinking in Vietnamese EFL Students' Use of GenAI for Academic Learning*,
  *Developing writing skills and feedback in foreign language education with ChatGPT*.

### 4.5 Decision guidance summary

| Signal | Lean |
|---|---|
| Title/abstract: writing, peer review, editorial, manuscript, journal policy, integrity, detection, evidence synthesis | IN |
| Title/abstract: diagnosis, patient outcome, treatment, teaching tool, classroom, EFL acquisition, marketing, supply chain | OUT |
| Both present | BORDERLINE — inspect unit of analysis: is AI helping *do research/communicate* or is it the *domain object*? |
| `scope_positive_hits` non-empty AND negative flag from domain words | check for FALSE_ALARM — likely IN |
| Negative flag present with NO positive hit | likely OUT (esp. medical/industrial) |

---

## 5. Recommended Screening Rules for `screening.py`

Implement as a new/updated module (today the logic lives in
`bibliometry_pipeline/config.py` + `bibliometry_pipeline/fetch.py`). Rules are regexes
applied to `title + primary_topic + keyword_terms + topic_terms + abstract`.

### 5.1 Positive scope rules (revised)

```python
POSITIVE_SCOPE_RULES = {
    # 1. Scientific / scholarly writing (existing, keep)
    "research_writing": r"...existing regex...",

    # 2. Research workflow — tightened: no bare "systematic literature review"
    "research_workflow": r"""
        \b(?:peer review|reviewer comments|reference management|citation management|
        research workflow|scholarly communication|journal submission|research assistant|
        (?:automated|AI.{0,5}assisted|LLM.{0,5}powered|tool.{0,10})
          systematic\ (literature\ )?review |
        literature review (?:system|tool|software|platform|automation|assistant|support|
          services?))\b
    """,

    # 3. NEW: evidence synthesis as research activity
    "evidence_synthesis": r"""
        \b(?:abstract screening|study selection|reference screening|evidence synthesis|
        systematic review (?:automation|tool|assistant|support)|automated systematic
        review|living systematic review|title.{0,15}abstract screening|
        PICO.{0,25}(?:generation|queries)|meta-analysis automation)\b
    """,

    # 4. Integrity / governance — anchored to fraud/policy/detection contexts
    "integrity_governance": r"""
        \b(?:publication ethics|research integrity|research ethics|journal polic|
        editorial polic|editorial guidelines?|authorship (?:misconduct|dispute|polic|
        guidelines?|dilemma|equity|attribution|practices|conflict|credits?)|academic
        integrity|integrity acad|integrity cient|plagiarism detection|text similarity
        detection|peer review manipulation|manuscript screening|research paper mill|
        paper mill(?:s)?\ (?:fraud|blacklist|threat)|paper mill.{0,60}(?:manuscript|
        authors?|publication)|predatory journal|(?:detect|detection|identify|identifying|
        prevalence|disclosure|polic).{0,40}AI-generated|AI-generated (?:paper|manuscript)|
        AI.{0,5}text detect|machine-generated text detection|authorship attribution|
        ORCID|ghost authorship|honorary authorship|gift authorship|authorship-for-sale)\b
    """,
}
```

### 5.2 Negative scope rules (revised, context-aware)

```python
# Compute first:  in_scope = any positive rule matched (incl. evidence_synthesis)
# A negative category ONLY vetoes when the paper is NOT already in scope on its own.

HARD_NEGATIVE_SCOPE_RULES = {
    "language_learning": r"""
        \b(?:EFL|ESL|TESOL|TEFL|foreign language|second language|language education|
        english language|arabic language|kazakh language|language teaching|language
        learning|pronunciation|vocabulary|reading comprehension|speaking skills|sign
        language|language classroom|philology|linguocultural|english teacher|language
        teacher)\b
    """,   # + carve-out: do not veto if (academic writing|academic essay|manuscript|
           #   scientific writing|academic integrity) present

    "classroom_pedagogy": r"""
        \b(?:K-?12|secondary (?:education|school)|middle school|high school|primary
        school|lesson plan|tutoring|quiz generation|intelligent tutoring|learning
        analytics|instructional design|educational technology)\b
    """,   # removed: bare "perceptions", "classroom", "pedagogy", "curriculum", "course design"

    "medical": r"""
        \b(?:patient|clinical|medical|medicine|healthcare|hospital|nursing|dental|
        orthodontic|surgery|surgical|oncology|pharmacy|rheumatology|anesthesia|
        inpatient|dentistry|midwifery|gynecology|orthopaedic)\b
    """,   # veto ONLY if no in_scope positive hit; otherwise treat as weak negative

    "industrial": r"""
        \b(?:marketing|manufacturing|supply chain|e-commerce|corporate|fisheries|
        farmers|agricultur|tourism|hotel|service recovery|social media (?:marketing|
        consumer|brand|influencer)|finance|policing|government document|news
        recommendation|geological|business|remote sensing|geospatial|archaeolog|
        smart cities)\b
    """,
}
```

### 5.3 Operational decision logic

```python
def screen(text):
    pos = matched_positive_rules(text)
    in_scope = bool(pos)
    neg = matched_negative_rules(text)
    if not in_scope:
        veto = neg        # negative rules decide exclusion when no positive signal
    else:
        # positive signal present: negative flags only matter if they indicate the
        # DOMAIN object rather than the scholarly-communication unit.
        veto = neg and not scholarly_communication_context(text)
    return {"in_scope": in_scope and not veto,
            "positive": pos, "negative": neg,
            "borderline": bool(pos) and bool(neg)}
```

**Audit loop (per the plan):** regenerate `screening_decisions.csv`, blind-review ≥50
included + ≥50 excluded, target inclusion precision ≥90%. The two token-level fixes above
(`paper mill` split, `authorship` anchoring) plus the `medical`-vetoes-only-when-no-positive
change are expected to remove the bulk of the 387 cluster 3+4 contaminants and recover most
of the ~152 cluster 0–2 false negatives.

---

## 6. Deliverables

- **This report:** `NOTES/screening_audit_report.md`
- **Borderline case list (60 papers):** `NOTES/screening_audit_borderline.csv`
  (columns: id, title, cluster, scope_positive_hits, scope_negative_hits, audit_notes,
  recommended_decision; decisions: IN / BORDERLINE / OUT)

### Caveats

- Estimates come from manual review of 94 (Task 1) + 48 (Task 2) stratified papers plus
  full-title review of the 385 "specific" papers in clusters 0–2; CIs are wide (n small)
  and reported above. The **direction and mechanism** of the errors are certain; the exact
  counts are point estimates.
- Decisions in the borderline CSV are audit recommendations, not final screening decisions;
  a second reviewer and the 20-paper pilot (per the plan's Day-2 step) should confirm before
  freezing the rules.
