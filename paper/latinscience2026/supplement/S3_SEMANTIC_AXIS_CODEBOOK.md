# S3. Semantic-axis codebook

Each record was represented by a BGE-M3 embedding of its title plus abstract.
The two axes were defined before article-level interpretation. They are not
topic clusters, labels, or estimates of causal effects.

| Axis | Negative pole | Positive pole |
|---|---|---|
| T: technological specificity | Generic AI/ML without a named generative model as the central object | A named generative model or model family is central |
| G: governance orientation | Workflow or task support for writing, search, review, or synthesis | Integrity, authorship, disclosure, detection, policy, or institutional safeguards |

For each pole, five anchor texts were embedded and averaged into a centroid.
The unit vector from the negative centroid to the positive centroid defined the
axis. A record score was the projection of its embedding onto that unit vector,
centred at the midpoint of the two centroids:

```text
score = (v_record - midpoint) dot unit_axis
```

Higher scores indicate greater similarity to the positive pole. They do not
indicate quality, ethical merit, prevalence in the population, or membership in
a discrete topic.

The anchor texts are controlled measurement inputs. Their wording is reported
exactly in `S4_SELECTED_PROTOTYPE_TEXTS.csv`. The candidate pool and final
selection are reported in `S5_ALL_PROTOTYPE_CANDIDATES.csv` and
`S6_PROTOTYPE_SELECTION_AUDIT.md`.

## Exact scoring and encoding implementation

For A in {T,G}, let p[A,pole,j] be an L2-normalised prototype embedding.
The final scorer uses:

```text
c[A,-] = mean(p[A,-,1], ..., p[A,-,5])
c[A,+] = mean(p[A,+,1], ..., p[A,+,5])
m[A] = (c[A,-] + c[A,+]) / 2
u[A] = (c[A,+] - c[A,-]) / norm(c[A,+] - c[A,-])
s[A](v) = (v - m[A]) dot u[A]
```

Centroids are not re-normalised after averaging. Record and prototype vectors
are the dense 1,024-dimensional SentenceTransformer embeddings of BAAI/bge-m3,
not its sparse or multi-vector retrieval outputs. Archived document inputs
use title + ". " + abstract[:6000]. The stored encoder configuration has a
maximum of 8,192 tokens; the encoder truncates inputs exceeding its limit.
Prototypes are encoded as their literal text without a title prefix.

The cached checkpoint revision is
`5617a9f61b028005a4858fdac845db406aefb181`. Fresh encoding of the published
anchors with this revision reproduces all 711 frozen scores within 1e-6
when applied to the preserved document matrix. S12 records the final check's
runtime versions, not an invented acquisition-time software history.

Use `score_final_axes.py` for the published configuration. The legacy general
pipeline module's initial anchors are not the selected anchors in S4. The
statistical reproduction script operates on released final scalar scores and
does not require access to raw texts or the embedding matrix.
