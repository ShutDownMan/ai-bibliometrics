# Protocol — Latin.Science 2026

**Status:** draft locked for the first manuscript version; record any material
change below as an amendment.

## Study purpose

Map the 2020–2026 literature on AI used in scholarly communication and research
workflows, and describe two theory-guided semantic dimensions:

- **T — technological specificity:** generic AI/ML → named GenAI model central;
- **G — work orientation:** workflow/task support → governance, integrity and
  institutional guardrails.

## Analytical population

The source is the frozen broad v14 corpus. The article's provisional final
population is the 711 records marked `include` in
`runs/latin_science_2026/screening_decisions.csv` (generated 2026-08-08).

Included work concerns scientific writing, scholarly publishing, peer review,
research integrity, AI-text detection, evidence-synthesis automation, or
institutional GenAI use in higher education connected to academic work.

Clinical AI, diagnostic/imaging AI, unrelated engineering/industry, general
education technology, and language-learning studies are excluded unless AI's
central object is a scholarly task or its governance. Eight unresolved records
remain `needs_review`; they are excluded from all current analyses.

## Research questions

1. How did the volume and composition of this literature change from 2020–2026?
2. How are generic/named AI and workflow/governance orientations distributed?
3. Are T and G associated after accounting for publication year?
4. Exploratorily, how are these dimensions associated with citations after
   accounting for recency?

## Confirmatory and descriptive commitments

- Describe the 2023+ expansion as a **cohort/compositional change**, not as a
  linear trend unless a specified trend model supports it.
- Estimate the T–G association with year included as a covariate.
- Treat citation results as exploratory, age-confounded associations; they do
  not measure quality or causality.
- Do not use low-separation clusters as substantive findings.

## Semantic measurement

Documents are embedded with `BAAI/bge-m3`. Each axis is the centred projection
onto the direction between the centroids of five written prototypes at each
pole. Prototype sensitivity is assessed through leave-one-prototype-out rank
stability. The current scores are embedding-derived measurements, not yet
human-validated measures.

## Human validation plan

A blinded 130-record Excel sample has been created from included records. Two
independent human raters will score T and G on 1–5 Likert scales. The final
validation report will include ordinal inter-rater agreement, convergence with
automatic scores, calibration and uncertainty intervals. Until then, human
validation is a planned confirmatory component, not a result.

## Amendments

| Date | Change | Rationale |
|---|---|---|
| 2026-08-08 | narrowed broad v14 corpus through recorded screening rules | original broad corpus was materially out of scope |
