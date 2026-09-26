# S6. Prototype-selection audit

## Candidate pool

Four sets of five anchors define the two axes: T negative, T positive, G
negative, and G positive. Each position had seven candidate variants, producing
140 candidate texts. The variants are in
`S5_ALL_PROTOTYPE_CANDIDATES.csv`.

| Variant | Description |
|---:|---|
| 1 | Original construct wording |
| 2 | Decontaminated wording |
| 3 | Alternative framing |
| 4--5 | Independently drafted alternatives |
| 6 | Adversarial construct mixing |
| 7 | Orthogonal vocabulary control |

Variants 6 and 7 are negative controls. They were used to probe sensitivity but
were **excluded from the selection pool**, so the final configuration is drawn
entirely from variants 1--5.

## Final configuration

| Pole | Position 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|
| T negative | 4 | 4 | 3 | 1 | 1 |
| T positive | 5 | 3 | 1 | 5 | 2 |
| G negative | 1 | 4 | 1 | 2 | 1 |
| G positive | 1 | 1 | 1 | 1 | 1 |

The procedure iterated through positions and selected, at each step, the
variant that minimised the **absolute** T--G axis cosine (the magnitude of the
cosine between the two unit vectors), subject to leave-one-prototype-out
Spearman stability of at least 0.97 for both axes. The objective used only the two anchor vectors. The stability acceptance
constraint used corpus document-score ranks. Neither the document-level T-G
coefficient nor human-validation labels entered the final objective or
acceptance criterion. BGE-M3 embeddings for all 140 prototypes were
pre-computed; the search continued until no position could be improved.

Because the objective minimises the absolute axis cosine, a near-zero cosine is
a property of the selection procedure, not an independent finding. The
document-level T--G association was estimated on the resulting axes after the
configuration was frozen; no association threshold was imposed by the final selector.

## Diagnostics for the reported configuration

| Quantity | Value |
|---|---:|
| Absolute T--G axis cosine | 0.0007 |
| T leave-one-out Spearman: mean / minimum | 0.9904 / 0.9828 |
| G leave-one-out Spearman: mean / minimum | 0.9914 / 0.9888 |
| Pearson correlation of document scores | 0.162 |
| OLS coefficient for T in G ~ T + year | 0.206 |
| 95% CI for the OLS coefficient | [0.119, 0.300] |
| Partial correlation | 0.165 |
| Model n | 711 |

Near-zero cosine is a property of the two anchor vectors. It does not make the
document scores independent; the observed document-score association is a
result to be interpreted and tested.

## Selection and final projection representations

The selection script evaluated LOO rank stability using freshly encoded corpus
texts joined with a space. Final projection and the diagnostics reported here
used the preserved document embeddings from broad-corpus processing (title,
period and space, abstract truncated to 6,000 characters). The final anchor
configuration was retained when applied to that preserved matrix. The final
selector minimised absolute anchor cosine subject to LOO stability, without an
association floor; control variants 6 and 7 were excluded. Final statistical
inference and validation consistently use the latter, frozen document scores.
The two representations and diagnostic runs must not be silently conflated.
