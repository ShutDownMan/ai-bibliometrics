from __future__ import annotations

import re


YEAR_MIN = 2020
YEAR_MAX = 2026
MIN_ABSTRACT_LENGTH = 50

# Curated labels for the current 5-cluster solution. These are applied after
# automatic topic extraction so downstream reports and figures use clearer names.
CLUSTER_METADATA: dict[int, dict[str, str]] = {
    0: {
        "label": "Applied AI Systems · Engineering and Environment",
        "description": "Artigos com foco predominante em aplicacoes de IA em engenharia, sensores/IoT, seguranca, meio ambiente e sistemas de monitoramento.",
    },
    1: {
        "label": "Clinical Risk and Prediction Models",
        "description": "Artigos com foco predominante em modelos clinicos de risco, prognostico, triagem, NLP/EHR e predicao de desfechos.",
    },
    2: {
        "label": "Medical Imaging and Diagnostic AI",
        "description": "Artigos com foco predominante em radiologia, radiomica, visao computacional medica, imagem diagnostica e IA para apoio ao diagnostico.",
    },
    3: {
        "label": "ChatGPT in Education and Research · Integrity and Writing",
        "description": "Artigos com foco predominante em ChatGPT/LLMs na educacao e pesquisa, integridade academica, escrita cientifica e uso institucional dessas ferramentas.",
    },
    4: {
        "label": "AI in Higher Education · Policy, Assessment and Literacy",
        "description": "Artigos com foco predominante em IA/GenAI no ensino superior, politicas, avaliacao, letramento critico, confianca e impactos sociotecnicos.",
    },
}

# ---------------------------------------------------------------------------
# Shared source cache
# ---------------------------------------------------------------------------
# Source fetches are cached under the repository root and reused across runs.
# Disable with env var BIBLIOMETRY_DISABLE_SOURCE_CACHE=1 when you want a fresh fetch.
SOURCE_CACHE_ENABLED = True
SOURCE_CACHE_DIRNAME = ".cache/source_fetch"

AI_QUERY_TERMS = (
    '"artificial intelligence" OR "inteligência artificial" OR "inteligencia artificial" OR '
    '"machine learning" OR "aprendizado de máquina" OR "aprendizaje automático" OR '
    '"large language model" OR "large language models" OR '
    '"modelo de linguagem" OR "modelos de linguagem" OR '
    '"modelo de lenguaje" OR "modelos de lenguaje" OR '
    '"generative AI" OR "IA generativa" OR "ChatGPT" OR "GPT" OR "LLM"'
)

# ---------------------------------------------------------------------------
# Additional data sources
# ---------------------------------------------------------------------------
# Set to True to also fetch from the Semantic Scholar Academic Graph API.
# Semantic Scholar is free to use without a key (rate-limited to 1 req/s).
# Register a free API key at https://www.semanticscholar.org/product/api
# to increase the limit to 10 req/s — useful for automation.
SEMANTIC_SCHOLAR_ENABLED = True
SEMANTIC_SCHOLAR_API_KEY = ""  # set your key here or via env var S2_API_KEY

# ---------------------------------------------------------------------------
# Scopus (Elsevier) — institutional access via CAFe/CAPES
# ---------------------------------------------------------------------------
# API key from https://dev.elsevier.com/ (API Key Management).
# If running from outside the institution's IP range, also set SCOPUS_INST_TOKEN
# (the X-ELS-Insttoken header value from your Elsevier dev account).
#
# Budget note: institutional keys typically allow ~20,000 requests/week on
# the Search API.  The client will attempt count=200 first, then automatically
# fall back to count=25 when the current service level rejects larger pages.
SCOPUS_ENABLED = True
SCOPUS_API_KEY = ""       # or set env var SCOPUS_API_KEY
SCOPUS_INST_TOKEN = ""    # or set env var SCOPUS_INST_TOKEN; needed off-campus
SCOPUS_ABSTRACT_BACKFILL_ENABLED = True
SCOPUS_ABSTRACT_BACKFILL_MAX_DOIS = 120

# These queries are intentionally narrow to reduce irrelevant EFL / medical noise.
# They still use TITLE-ABS-KEY, but no longer assume subject-area filters or a
# guaranteed 200-result page size because the current key's service level does
# not allow that consistently.
SCOPUS_QUERIES: list[str] = [
    # Research writing / manuscript production tools
    f'TITLE-ABS-KEY(("manuscript writing" OR "scientific manuscript" OR "manuscrito científico" OR "redação científica" OR "redacción científica") AND ({AI_QUERY_TERMS}))',
    f'TITLE-ABS-KEY(("scholarly publishing" OR "scientific publishing" OR "publicação científica" OR "publicación científica" OR "comunicação científica" OR "comunicación científica") AND ({AI_QUERY_TERMS}))',
    # Peer review automation
    f'TITLE-ABS-KEY(("peer review" OR "revisão por pares" OR "revisión por pares") AND ("automated" OR {AI_QUERY_TERMS}))',
    # Literature review / evidence synthesis automation
    f'TITLE-ABS-KEY(("systematic review" OR "revisão sistemática" OR "revisión sistemática") AND ("automation" OR "automated screening" OR {AI_QUERY_TERMS}))',
    f'TITLE-ABS-KEY(("evidence synthesis" OR "síntese de evidências" OR "síntesis de evidencia") AND ({AI_QUERY_TERMS}))',
    # Research integrity / paper mill / AI-text detection
    f'TITLE-ABS-KEY(("academic integrity" OR "integridade acadêmica" OR "integridad académica") AND ({AI_QUERY_TERMS}))',
    'TITLE-ABS-KEY(("paper mill" OR "AI-generated text" OR "AI generated manuscript") AND ("detection" OR "classifier" OR "machine learning"))',
    # Reference management / citation tools
    f'TITLE-ABS-KEY(("reference management" OR "gestão de referências" OR "gestión de referencias") AND ({AI_QUERY_TERMS}))',
    # Research workflow / research assistant tools
    f'TITLE-ABS-KEY(("research workflow" OR "research assistant" OR "assistente de pesquisa" OR "asistente de investigación" OR "fluxo de trabalho de pesquisa" OR "flujo de trabajo de investigación") AND ({AI_QUERY_TERMS}))',
]

# ---------------------------------------------------------------------------
# Europe PMC — abstract-rich, strongest for biomedical / evidence-synthesis spillover
# ---------------------------------------------------------------------------
EUROPE_PMC_ENABLED = True
EUROPE_PMC_QUERIES: list[str] = [
    f'("peer review" OR "revisão por pares" OR "revisión por pares") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
    f'("systematic review" OR "revisão sistemática" OR "revisión sistemática") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
    f'("evidence synthesis" OR "síntese de evidências" OR "síntesis de evidencia") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
    f'("academic integrity" OR "integridade acadêmica" OR "integridad académica") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
    f'("scholarly publishing" OR "scientific publishing" OR "publicação científica" OR "publicación científica") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
    f'("reference management" OR "gestão de referências" OR "gestión de referencias") AND ({AI_QUERY_TERMS}) AND FIRST_PDATE:[{YEAR_MIN}-01-01 TO {YEAR_MAX}-12-31]',
]

MIN_EMBED_ABSTRACT_LENGTH = 150
FETCH_RELEVANCE_THRESHOLD = 0.25  # realistic: max observed score ~0.38; 0.42 was never triggered
FETCH_MIN_FINAL = 30              # was 60; min_floor was forcing in low-quality EFL papers
FETCH_MAX_FINAL = 200
FETCH_CLEAN_TOPIC_OVERRIDE = 0.48
FETCH_SEMANTIC_MODEL = "BAAI/bge-m3"

AI_TITLE_SEARCH = (
    "artificial intelligence OR machine learning OR large language model OR "
    "generative AI OR ChatGPT OR GPT OR LLM OR inteligência artificial OR "
    "inteligencia artificial OR aprendizado de máquina OR aprendizaje automático OR "
    "modelo de linguagem OR modelos de linguagem OR modelo de lenguaje OR modelos de lenguaje OR IA generativa"
)

RESEARCH_SEARCH_TERMS = [
    # Manuscript / writing workflow
    "scientific manuscript",
    "manuscript preparation",
    "manuscript drafting",
    "manuscript screening",
    "academic editing",
    "scholarly communication",
    "scholarly publishing",
    "scientific publishing",
    # Peer review & journal workflow
    "peer review",
    "automated peer review",
    "AI peer reviewer",
    "reviewer comments",
    "journal submission",
    "journal policy",
    # Reference / evidence management
    "reference management",
    "citation management",
    "literature search assistance",
    "evidence synthesis",
    # Research integrity & fraud detection
    "academic integrity",
    "research integrity",
    "plagiarism detection",
    "paper mill detection",
    "retraction detection",
    "publication ethics",
    # Research workflow tools
    "research workflow",
    # Removed high-noise / low-precision terms:
    #   "academic journal writing"  (517 raw, 5.4% kept — mostly EFL)
    #   "academic paper writing"    (315 raw, 5.1% kept — mostly EFL)
    #   "scientific writing"        (459 raw, 5.2% kept — mostly EFL)
    #   "research paper writing"    (425 raw, 4.0% kept — mostly EFL)
    #   "systematic review automation" (190 raw, 1.1% kept — terrible precision)
    #   "review screening"          (201 raw, 2.5% kept — poor precision)
    #   "literature review services" (425 raw, 2.4% kept — poor precision)
    #   "research assistant"        (563 raw, 2.8% kept — too generic)
]

RESEARCH_SEARCH_TERMS_PT_ES = [
    "manuscrito científico",
    "redação científica",
    "redacción científica",
    "comunicação científica",
    "comunicación científica",
    "publicação científica",
    "publicación científica",
    "revisão por pares",
    "revisión por pares",
    "revisão sistemática",
    "revisión sistemática",
    "integridade acadêmica",
    "integridad académica",
    "gestão de referências",
    "gestión de referencias",
    "síntese de evidências",
    "síntesis de evidencia",
    "fluxo de trabalho de pesquisa",
    "flujo de trabajo de investigación",
    "assistente de pesquisa",
    "asistente de investigación",
]

ALL_RESEARCH_SEARCH_TERMS = RESEARCH_SEARCH_TERMS + RESEARCH_SEARCH_TERMS_PT_ES

POSITIVE_SCOPE_RULES = {
    "research_writing": re.compile(
        r"\b(?:academic journal writing|academic paper writing|research paper writing|"
        r"scientific manuscript|journal manuscript|manuscript (?:preparation|drafting|editing)|"
        r"academic editing|scientific writing|research writing|thesis writing|"
        r"dissertation writing|scholarly publishing|scientific publishing|"
        r"research and publishing|academic research and publishing|"
        r"manuscrito científico|redação científica|redacción científica|"
        r"comunicação científica|comunicación científica|"
        r"publicação científica|publicación científica)\b",
        re.IGNORECASE,
    ),
    "research_workflow": re.compile(
        r"\b(?:peer review|reviewer comments|reference management|citation management|"
        r"research workflow|literature search assistance|"
        r"abstract screening|reference screening|study selection|"
        r"evidence synthesis|literature search|scholarly communication|"
        r"journal submission|research assistant|"
        r"revisão por pares|revisión por pares|"
        r"revisão sistemática|revisión sistemática|"
        r"gestão de referências|gestión de referencias|"
        r"síntese de evidências|síntesis de evidencia|"
        r"fluxo de trabalho de pesquisa|flujo de trabajo de investigación|"
        r"assistente de pesquisa|asistente de investigación|"
        # Require AI/automated qualifier OR tool-noun suffix to avoid false positives
        # from papers that merely describe doing a literature review as a method.
        r"(?:automated|AI.{0,5}assisted|LLM.{0,5}powered|AI.{0,5}driven) literature review|"
        r"literature review (?:system|tool|software|platform|automation|assistant|support|services?)|"
        r"systematic literature review)\b",
        re.IGNORECASE,
    ),
    "integrity_governance": re.compile(
        r"\b(?:publication ethics|research integrity|research ethics|journal policy|"
        r"editorial policy|editorial guidelines?|authorship|authorship policy|"
        r"academic integrity|plagiarism detection|text similarity detection|"
        r"integridade acadêmica|integridad académica|"
        r"integridade científica|integridad científica|"
        r"ética de publicação|ética de publicación|"
        r"peer review manipulation|paper mill|manuscript screening|"
        r"AI-generated (?:paper|manuscript|text|content)|"
        r"LLM-generated (?:paper|manuscript|text|content)|"
        r"generated text detect|AI.{0,5}text detect|deepfake text|"
        r"authorship attribution)\b",
        re.IGNORECASE,
    ),
}

AI_SIGNAL_RULES = {
    "ai_general": re.compile(r"\b(?:artificial intelligence|inteligência artificial|inteligencia artificial|AI|IA)\b", re.IGNORECASE),
    "machine_learning": re.compile(r"\b(?:machine learning|aprendizado de máquina|aprendizaje automático)\b", re.IGNORECASE),
    "llm": re.compile(r"\b(?:large language models?|LLMs?)\b", re.IGNORECASE),
    "generative_ai": re.compile(r"\b(?:generative AI|IA generativa|GenAI|foundation models?)\b", re.IGNORECASE),
    "chatgpt": re.compile(r"\b(?:ChatGPT|GPT-4(?:o)?|GPT-?[0-9])\b", re.IGNORECASE),
    "nlp": re.compile(r"\b(?:natural language processing|NLP)\b", re.IGNORECASE),
}

HARD_NEGATIVE_SCOPE_RULES = {
    "language_learning": re.compile(
        r"\b(?:EFL|ESL|TESOL|TEFL|foreign language|second language|language education|"
        r"english language|arabic language|kazakh language|language teaching|language learning|"
        r"pronunciation|vocabulary|reading comprehension|speaking skills|"
        # Removed: translation|interpreting — scientific/academic translation IS in scope.
        r"sign language|language classroom|philology|linguocultural|"
        r"digital pedagogy|english teacher|language teacher)\b",
        re.IGNORECASE,
    ),
    "classroom_pedagogy": re.compile(
        r"\b(?:teacher attitudes?|student perceptions?|students'? perceptions?|classroom|"
        r"pedagog(?:y|ical)|curriculum|course design|learning outcomes|instructional|lesson|"
        # Removed: "writing skills" — too generic, catches legitimate research-writing papers.
        r"language skills|educational technology)\b",
        re.IGNORECASE,
    ),
    "medical": re.compile(
        r"\b(?:patient|clinical|medical|medicine|healthcare|hospital|nursing|dental|"
        r"orthodontic|surgery|surgical|oncology|pharmacy|rheumatology|anesthesia|"
        r"inpatient|dentistry|midwifery|gynecology|orthopaedic)\b",
        re.IGNORECASE,
    ),
    "industrial": re.compile(
        r"\b(?:marketing|manufacturing|supply chain|e-commerce|corporate|fisheries|farmers|"
        r"agricultur|tourism|hotel|service recovery|social media|finance|policing|"
        r"government document|news recommendation|geological|business|remote sensing|"
        r"geospatial|archaeolog|smart cities)\b",
        re.IGNORECASE,
    ),
}

HARD_OFFTOPIC_TITLE_RE = re.compile(
    # Trailing \b after group means plurals like "tumors" won't match "tumou?r";
    # use trailing s? inside the alternation for words that commonly appear plural.
    r"\b(?:cardiology|orthodontic|dental|dentist|surgery|surgical|plastic surg|"
    r"cancers?|tumou?rs?|oncol|cardio|cardiac|dermatol|ophthalm|gynecol|urol|"
    r"perinat|neonat|anaesth|patholog|radiolog|pharma|drug discovery|"
    r"food sector|food safety|food produc|food industry|crop|agriculture|"
    r"manufacturing system|reconfigur|supply chain|inpatient|patients? care|"
    r"clinical trials?|hospitals?|orthopaedic|anesth|tourism|hotel|marketing|"
    r"remote sensing|archaeolog|geospatial|psychiatric diagnoses|smoking|hernia)\b",
    re.IGNORECASE,
)

OFFTOPIC_PRIMARY_TOPIC_RE = re.compile(
    r"\b(?:healthcare|medical|dental|orthodontic|manufacturing|traffic|power forecasting|"
    r"service interactions|food|finance|market forecasting|patient|clinical|"
    r"educational technology and pedagogy|technology-enhanced education studies|"
    r"arabic language education studies|innovations in education and learning technologies)\b",
    re.IGNORECASE,
)

RETRACTED_TITLE_RE = re.compile(r"\bretracted\b|\[retracted\]|\bretraction\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
# Override the silhouette-argmax cluster selection with a fixed k.
# Set to 0 to let the algorithm pick the best k automatically (silhouette search).
# For this corpus (≥5000 papers, 2020-2026, narrow AI+academia topic) the
# silhouette always peaks at k=2 because all papers share a tight semantic
# neighbourhood — forcing a higher k gives semantically richer groups.
N_CLUSTERS: int = 5

LOW_QUALITY_ABSTRACT_RE = re.compile(
    r"(?:https?://|download link|conference proceedings|lsdexception|unhidewhenused|semihidden|<w:)",
    re.IGNORECASE,
)

AXIS_LABELS = {
    "axis_e_technology": "Eixo E — Enquadramento Tecnologico",
    "axis_n_domain": "Eixo N — Postura (Oportunidade→Risco/Governança)",
    "axis_r_scope": "Eixo R — Domínio (Acadêmico→Clínico)",
}

KEYWORD_STOPWORDS = {
    "computer science", "psychology", "mathematics", "mathematics education",
    "context (archaeology)", "relevance (law)", "field (mathematics)",
    "process (computing)", "cognitive science", "transformative learning",
    "perception", "generative grammar", "reading (process)",
    "context", "field", "process", "relevance", "history", "politics",
    "sociology", "philosophy",
}

RELEVANCE_POSITIVE_PROTOTYPES = [
    "Large language models supporting academic writing, manuscript drafting, and scholarly publishing.",
    "Artificial intelligence tools for peer review, reference management, abstract screening, and journal submission.",
    "Generative AI in academic integrity, plagiarism detection, scholarly communication, and research assistants.",
    "AI helping researchers write papers, manage citations, and automate evidence-synthesis workflows.",
    # More specific tool-description sentences to improve coverage of the in-scope class:
    "This paper presents a system that detects AI-generated text in submitted manuscripts to support "
    "journal editorial workflows and academic integrity enforcement.",
    "We evaluate an LLM-powered literature review service that converts research questions into structured "
    "evidence summaries, reducing systematic review screening time significantly.",
    "A machine learning classifier identifies paper mill submissions by analysing co-authorship patterns "
    "and textual anomalies in journal submission metadata.",
]

RELEVANCE_NEGATIVE_PROTOTYPES = [
    # Broad domain statements (original, good coverage)
    "Artificial intelligence for English language learning, EFL classrooms, sign language, and foreign language pedagogy.",
    "Large language models for clinical care, medicine, speech pathology, patients, and healthcare decision support.",
    "Artificial intelligence for cybersecurity, materials science, engineering, industry, or unrelated technical workflows.",
    "A systematic review of AI applications in a subject domain rather than AI tools supporting academic production.",
    # Specific EFL scenarios to push sem_neg higher for this dominant noise class
    "Undergraduate EFL students participated in a quasi-experimental study measuring improvements in English "
    "writing scores after using ChatGPT for guided composition feedback in a foreign language classroom.",
    "A survey of English language teachers examined attitudes toward adopting generative AI tools in "
    "foreign language classrooms, finding high anxiety and low self-efficacy among participants.",
    # Specific medical scenario
    "GPT-4 was evaluated on USMLE medical licensing exam questions and its potential for clinical "
    "decision support and discharge summary generation in inpatient care settings.",
    # Industrial to round out coverage
    "Transformer models were applied to financial sentiment analysis of social media posts to predict "
    "stock market movement and support e-commerce recommendation systems.",
]