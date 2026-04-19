# PROGRESS — Trabalho 5: Revisão Bibliométrica (IA na Produção Acadêmica)

> **Entrega:** 22 abr 2026 às 19:00 · **Dias restantes:** 8
> **Último update:** 14 abr 2026 (sessão 12)

---

## Status Geral

| Fase | Status | Output |
|------|--------|--------|
| D1 — Coleta (OpenAlex) | ✅ DONE | `corpus.csv` (603 papers pós-fetch; 631 identificados) |
| D1b — Fetch multifuente v12 | ✅ DONE | `runs/academic_production_v12/fetch_log.json` (1.648 únicos → 136 no fetch; cache global + Europe PMC + Scopus + BGE-M3) |
| D1c — Run limpo v13 (pipeline completo) | ✅ DONE | `runs/academic_production_v13/` (136 fetch → 134 clean → 130 semantic; `report_text.md` gerado) |
| D1d — Busca manual + parse (manual/) | ✅ DONE | `manual/normalized.csv` — 7.031 registros novos (6.789 c/ abstract), fontes: WoS, PubMed MEDLINE, ACM, IEEE, Scopus PDF |
| D1e — Pipeline v14 (corpus expandido) | ✅ DONE | `runs/academic_production_v14/` — **6.261 papers semânticos**, citações backfilled e relatório regenerado |
| D2 — Auditoria manual | ✅ DONE | `fetch_log.json` (−28 no fetch: 10 off-topic clínico + 18 sem abstract) |
| D3 — Corpus limpo | ✅ DONE | `corpus_clean.csv` (**6.483 papers**, v14) |
| D4 — Indicadores bibliométricos clássicos | ✅ DONE | `runs/academic_production_v14/indicators/` + **h-index** adicionado a `top_authors.csv` |
| D4b — Lei de Zipf | ✅ DONE | `zipf_stats.csv` (α=0.822, R²=0.970 sobre vocabulário nuclear); `zipf_analysis.csv` (top 50 termos) |
| D5a — Clustering semântico (BGE-M3) | ✅ DONE | `corpus_clustered.csv` (**6.261 papers**, k=5, silhouette=0.058) |
| D5b — Eixos semânticos | ✅ DONE | `indicators/axis_scores.csv` (3 eixos: E, N, R) |
| D5c — Análises 2 & 3 (temporal + citações) | ✅ DONE | `indicators/temporal_profile.csv`, `axis_scores_enriched.csv` |
| D5d — Deep-dive clusters focais | ✅ DONE | `cluster_focus_papers.csv`, `cluster_focus_journals.csv`, `cluster_focus_keywords.csv` (top por cluster) |
| D6 — Visualizações | ✅ DONE | `NOTES/report.md` + `NOTES/report_light.md` + PDFs (v14, pós-backfill de citações) |
| D7 — Redação do artigo | ❌ PENDENTE | — |

---

## Sessão 12 — Bibliometria Clássica Completa + Análise Clusters Focais (v14)

### Motivação

Professor questionou se o "bread and butter" (fundamentos bibliométricos) estava devidamente coberto e pediu análise aprofundada dos 2 clusters focais do estudo (C3 e C4).

### O que foi feito

**Diagnóstico:**
- Bradford's Law (§7.2) e Lotka's Law (§7.3) já estavam presentes e corretos.
- Constatados dois gaps: **Lei de Zipf** nunca analisada formalmente; **índice h** planejado no `trabalho5_plano.md` mas não implementado.
- §11.5 (artigos de maior impacto por cluster) ausente do relatório, apesar de §11.1–11.4 e §12 já existirem.

**`bibliometry_pipeline/indicators.py`:**
- Adicionado rastreador de citações por autor: `author_paper_citations: defaultdict(list)`
- Adicionada função `_h_index(citations: list[int]) -> int` (maior n tal que ≥n artigos com ≥n citações)
- `top_authors.csv` passou de 3 para 4 colunas: `author, n_papers, total_cit, h_index`

**`bibliometry_pipeline/analyses.py`:**
- Adicionado bloco de análise de Zipf:
  - Lê `keyword_freq.csv`; filtra vocabulário nuclear (freq ≥ 2; 33 termos dos 6.272 totais)
  - Ajuste log-log `log(freq) ~ slope × log(rank)` → α=0.822, R²=0.970
  - Produz `zipf_analysis.csv` (rank, keyword, freq, freq_expected — top 50) e `zipf_stats.csv`
  - **Nota:** vocab completo dá α≈0 pois 99,5% são hapax legomena (freq=1); ajuste correto exige vocab nuclear
- Adicionado loop de deep-dive por cluster:
  - `cluster_focus_papers.csv`: top 10 citados por cluster (50 linhas, 5 clusters)
  - `cluster_focus_journals.csv`: top 5 periódicos por cluster
  - `cluster_focus_keywords.csv`: top 10 keywords por cluster
  - Guards `_has_journal` / `_has_doi` para retrocompatibilidade

**`bibliometry_pipeline/report_text.py`:**
- **§7.3 atualizado:** coluna `Índice h` adicionada à tabela de top autores (condicional à existência da coluna)
- **§7.5 adicionado (NOVO):** carrega `zipf_stats.csv` + `zipf_analysis.csv`; tabela top-20 rank/keyword/freq/freq_expected; nota sobre α, R² e hapax
- **§11.5 adicionado (NOVO):** carrega `cluster_focus_papers.csv`; tabelas de top-10 citados para C3 e C4 com título, ano, citações, periódico
- Fix de sintaxe: `_hapax_note` extraído como variável para evitar erro em f-string com concatenação implícita

**Pipeline regenerado (v14):**
- `indicators` → `top_authors.csv` com h_index
- `analyses` (2ª execução, após fix do Zipf) → todos os CSVs de cluster
- `summary` → `report_summary.json` atualizado
- `report-text` → `NOTES/report_text.md` com §7.5 e §11.5
- `report-viz` → `report.md` + `report_light.md` (20 figuras)
- `report-pdf` → `report.pdf` (3.787 KB) + `report_light.pdf` (5.721 KB)
- NOTES sincronizados para raiz

### Resultados validados

| Item | Resultado |
|------|-----------|
| Índice h máximo no corpus | Klang, Eyal — 19 artigos, 670 cit., **h=11** |
| Zipf α (vocab nuclear, freq≥2) | **0.822** |
| Zipf R² | **0.970** |
| Hapax legomena no corpus | 6.239 / 6.272 = **99,5%** |
| C3 artigo mais citado | ChatGPT Utility in Healthcare Education... (2023, **1.603 cit.**) |
| C4 artigo mais citado | Explainable AI: A Review of ML Interpretability Methods (2020, **2.613 cit.**) |

### Estado dos fundamentos bibliométricos (pós-sessão 12)

| Lei | Status | Seção |
|-----|--------|-------|
| Bradford | ✅ presente | §7.2 |
| Lotka | ✅ presente | §7.3 |
| Zipf | ✅ adicionado | §7.5 |
| Índice h | ✅ adicionado | §7.3 |

---

## Sessão 11 — Backfill de Citações + Relatório Corrigido (v14)

### O que foi feito

- **`bibliometry_pipeline/enrich.py` estendido** com cache por run:
  - `.enrich_oa_cache.json` para DOIs resolvidos no OpenAlex (`doi -> cited_by_count, countries`)
  - `.enrich_epmc_cache.json` para PMIDs resolvidos no Europe PMC (`pmid -> cited_by_count`)
- **Hidratação manual do cache OpenAlex** a partir de `runs/academic_production_v14/corpus_clean.csv`, para evitar reconsultar DOIs já resolvidos ou DOIs que genuinamente têm `0` citações.
- **Fallback Europe PMC para PubMed sem DOI**:
  - parsing dos PMIDs a partir dos arquivos MEDLINE em `manual/pubmed/`
  - consulta dos 29 registros `pubmed_manual` sem DOI por PMID
- **Regeneração downstream** após corrigir a camada de citações:
  - `enrich`
  - `analyses`
  - `summary`
  - `report-text`
  - `report-viz`
  - `report-pdf`
- **Sincronização final** dos arquivos em `runs/academic_production_v14/NOTES/` para `NOTES/` na raiz.

### Resultado do backfill

| Item | Valor |
|------|-------|
| Cache OpenAlex hidratado | **6.364 DOIs** |
| Fallback Europe PMC | **29 PMIDs** consultados |
| Citações recuperadas via Europe PMC | **17** |
| PubMed com pelo menos 1 citação | **3.433 / 4.088** (84,0%) |
| PubMed sem DOI com citação recuperada | **17 / 29** |
| Cobertura DOI no corpus semântico | **6.149 / 6.261** (98,2%) |
| Potencialmente sem resolução externa | **58** papers (0,9%) |

### Métricas atuais do v14 (pós-backfill)

| Métrica | Valor |
|---------|-------|
| N papers semânticos | **6.261** |
| N corpus limpo | 6.483 |
| Países representados | 144 |
| Clusters | **5** |
| Cluster dominante | Diagnostic Imaging · Magnetic Resonance (**2.011 papers; 32,1%**) |
| Silhouette (k=5) | 0.058 |
| Zero citations | **19,2%** (1.205) |
| Artigo mais citado | **2.613 cit.** |
| Eixo E × citações (Spearman ρ) | +0.034, p=0.007 ✅ |
| Eixo N × citações | −0.003, p=0.801 ❌ |
| Eixo R × citações | +0.145, p<0.001 ✅ |
| Hipótese E (Q4>Q1) | ✅ confirmada (p=0.040) |
| Hipótese N (Q4>Q1) | ❌ não confirmada |
| Hipótese R (Q4>Q1) | ✅ confirmada |

### Implicação prática

- A taxa de **19,2% de zero-citações não deve mais ser lida como falha de cobertura**. Após o backfill, apenas **58 artigos (0,9%)** seguem potencialmente sem resolução externa.
- As análises por citação voltaram a ser defensáveis no relatório:
  - cobertura de citações explicitada em `report_text.md`
  - análise de impacto por domínio (Eixo R)
  - análise de impacto por cluster
  - restauração da figura **Eixo R × citações** em `report.md` / `report_light.md`

---

## Sessão 10 — Busca Manual + Pipeline v14 (corpus 6.261 papers)

> **Nota:** os números de citação, cobertura geográfica e clustering registrados nesta sessão foram superados pelos artefatos corrigidos na **Sessão 11**, após backfill de citações e rerun de `analyses`/`summary`.

### O que foi feito

**Parser de exportações manuais (`parse_manual_exports.py`):**
- Reescrito completamente para os formatos reais depositados em `manual/`:
  - WoS: TSV 71-colunas (pandas, cabeçalho 2 letras: TI/AB/DI/PY/AU/SO/TC/DE/SC)
  - PubMed: CSV sem abstract → substituído por MEDLINE tagged `.txt` (com abstract, ≥2019, DOI de `LID`)
  - BibTeX: normalizador de formato compacto IEEE (inserção `\n` antes de `@`) + extrator de campos com `{}` aninhados
  - Scopus: extração de título+ano a partir do nome do arquivo PDF
  - RIS: parser genérico mantido
- Detecção de formato dinâmica (`_detect_format`) para `.txt`, `.csv`, `.bib`, `.pdf`, `.ris`
- Scan recursivo de subdiretórios (`rglob`)
- Dedup interno por DOI e título; dedup contra `corpus_clean.csv` existente

**Resultado do parse:**
| Fonte | Registros | c/ abstract |
|-------|-----------|-------------|
| PubMed MEDLINE | 4.300 | ✅ todos |
| WoS TSV | 1.983 | ✅ todos |
| BibTeX (ACM+IEEE) | 734 | ✅ todos |
| Scopus PDF | 16 | ❌ sem abstract |
| **Total** | **7.031 novos** | **6.789** |

**Integração no pipeline (`bibliometry_pipeline/fetch.py`):**
- Registros do `manual/normalized.csv` injetados como fonte adicional no estágio fetch
- `data_source` preservado (`pubmed_manual`, `wos_manual`, `bibtex_manual`, `scopus_pdf`)
- Dedup automático contra candidatos da API antes do scoring

**Cache global de embeddings (`embeddings_cache/`):**
- Implementado cache workspace-level em `embeddings_cache/index.csv` + `vectors.npy`
- Chave: `sha256(title + ". " + abstract[:6000])`
- Registros já codificados em runs anteriores são recuperados diretamente, sem re-encoding
- Back-fill automático: quando run-dir cache é válido, entradas novas são adicionadas ao cache global

**Fix de visualizações (`visualizations.py`):**
- `C_LABELS` agora construído dinamicamente a partir de `cluster_share_by_year.csv`
- Elimina crash quando KMeans produz clusters com nomes diferentes de versão para versão

**Run v14 — pipeline completo:**
- Fetch: 6.579 candidatos (todos c/ abstract)
- Clean: 6.483 (−31 fora de range, −20 retracted, −45 off-topic)
- Embed: BGE-M3, 6.261 papers (−222 abstracts curtos excluídos)
- Report: `report.md` (2.358 KB dark) + `report_light.md` (3.756 KB light)

### Métricas do corpus v14

| Métrica | Valor |
|---------|-------|
| N papers semânticos | **6.261** |
| N corpus limpo | 6.483 |
| Período | 2020–2026 |
| Países representados | 13 |
| Cluster 0 — Integrity Governance | 2.497 (39,9%) |
| Cluster 1 — Other Relevant | 3.764 (60,1%) |
| Silhouette (k=2) | 0.116 |
| Zero citations | 81,2% (5.083) |
| Artigo mais citado | 1.603 cit. |
| Eixo E × citações (Spearman ρ) | +0.158, p<0.001 ✅ |
| Eixo N × citações | +0.038, p=0.003 ✅ |
| Eixo R × citações | −0.053, p<0.001 |
| Hipótese E (Q4>Q1) | ✅ confirmada (p<0.001) |
| Hipótese N (Q4>Q1) | ✅ confirmada (p=0.004) |
| Hipótese R (Q4>Q1) | ❌ não confirmada |
| E×N ortogonalidade | 0.081 ✅ |
| E×R | 0.070 ✅ |
| N×R | 0.137 ✅ |

### Diferenças críticas v13 → v14

| | v13 | v14 |
|-|-----|-----|
| Papers semânticos | 130 | **6.261** |
| Fontes | API only (OA, EPMC, Scopus) | API + WoS + PubMed MEDLINE + ACM + IEEE |
| Abstracts disponíveis no fetch | ~12,5% (130/1.042 c/ abs) | **100%** (todos c/ abstract) |
| Clusters | Research Writing 55% / Research Workflow 45% | Integrity Governance 40% / Other Relevant 60% |
| Max citações | 76 | 1.603 |
| Países | 20 | 13 |

---

---

## Sessão 9 — Audit & Revisão Completa do Relatório (v13)

### O que foi feito

- **Auditoria de consistência:** confirmado que os arquivos raiz (`corpus*.csv`, `indicators/`, `NOTES/report*.md`) ainda referenciavam o corpus legado (586 papers, EFL-contaminado). Sincronizados com `runs/academic_production_v13/`.
- **Sincronização de artefatos:** copiados `corpus.csv`, `corpus_clean.csv`, `corpus_clustered.csv`, embeddings e todos os CSVs de `indicators/` do v13 para a raiz do projeto.
- **Revisão de `visualizations.py`:**
  - Paleta e labels de clusters atualizados: 5 clusters EFL → **2 clusters** (Research Writing, Research Workflow).
  - `fig_temporal`: range dinâmico lido de `yearly_production.csv` (antes hard-coded 2020–2025).
  - `fig_cluster_composition`: `n_per_year` agora lido dos dados; cluster cols corrigidos.
  - `fig_geo`: mapeamento de países e cores de região atualizados para o novo corpus (US lidera, não CN/ID).
  - `fig_umap` / `fig_scatter_ea`: `range(5)` → `range(n_clusters)` dinâmico; labels dos quadrantes corrigidos.
  - `fig_orthogonality`: matriz de correlação atualizada com valores reais do v13 (E×A=−0.381, E×D=−0.033, A×D=+0.254).
  - `_write_findings_summary`: 4 achados completamente reescritos para o novo corpus (data-driven).
  - `_write_prisma`: adaptado para fluxo multi-stage do fetch híbrido (weak_alignment + low_relevance como etapas intermediárias).
  - Textos narrativos (callouts Q/M/R) atualizados em todas as figuras.
- **Relatórios regenerados:**
  - `NOTES/report.md` (dark, 1.462 KB)
  - `NOTES/report_light.md` (light, 2.242 KB)
  - `NOTES/report_text.md` sincronizado do v13

### Novos achados (corpus v13 — 130 papers)

| Métrica | Valor |
|---------|-------|
| N papers semânticos | 130 |
| Período | 2021–2026 |
| Países representados | 20 |
| Cluster 0 — Research Writing | 71 (54.6%) |
| Cluster 1 — Research Workflow | 59 (45.4%) |
| Silhouette (k=2) | 0.113 |
| Zero citations | 56.2% |
| Artigo mais citado | 76 cit. (JMIR 2023, best practices AI) |
| Eixo E × citações (Spearman ρ) | +0.237, p=0.007 ✅ |
| Eixo A × citações | −0.093, ns |
| Eixo D × citações | +0.112, ns |
| E×A ortogonalidade | −0.381 (limite limiar) |

### Diferenças críticas em relação ao corpus anterior (586 papers)

| | Legado (EFL-contaminado) | v13 (filtrado BGE-M3) |
|-|---|----|
| Papers | 586 | 130 |
| Clusters | 5 (EFL Teaching dominante 42%) | 2 (Research Writing 55%) |
| Países | 78 (incl. CN, ID, PK) | 20 (US lidera 33%) |
| Achado central | "campo é sobre EFL, não produção acadêmica" | **campo genuinamente sobre IA em produção científica** |
| Max citações | 727 | 76 |
| Fontes | OpenAlex only | Europe PMC 75%, Scopus 17%, OA 8% |

---

## Sessão 7 — Validação Final do Fetch v12

### Objetivo

Fechar a lacuna que ainda faltava após a refatoração do fetch: validar o pipeline no **`.venv` selecionado do workspace**, com scoring semântico realmente ativo, caches globais reaproveitados e sem processos Python concorrentes disputando recursos.

### O que foi concluído

- Instalados no `.venv` os pacotes que faltavam para o scoring semântico: `torch` e `sentence-transformers`.
- Validado o run `runs/academic_production_v12` usando o interpretador do próprio `.venv`.
- Confirmado que o fetch **não** caiu mais para fallback lexical: o `relevance_model` final passou a ser **`BAAI/bge-m3`**.
- Confirmado reaproveitamento do cache global em `.cache/source_fetch/` para OpenAlex, Europe PMC e Scopus.
- Verificado que **não existem** artefatos `openalex_cache*.csv/json` sobrando no repositório; só restaram referências legadas de compatibilidade em `bibliometry_pipeline/fetch.py`.

### Métricas do run validado (`academic_production_v12`)

| Métrica | Valor |
|---------|-------|
| `n_openalex_unique` | 60 |
| `n_europe_pmc_candidates` | 507 |
| `n_europe_pmc_new` | 506 |
| `n_scopus_candidates` | 1.160 |
| `n_scopus_new` | 1.082 |
| `n_identified_unique` | **1.648** |
| `n_candidates_ranked` | 257 |
| `n_excluded_noabstract` | 1.042 |
| `n_excluded_offtopic` | 121 |
| `n_excluded_weak_alignment` | 228 |
| `n_excluded_low_relevance` | 121 |
| `n_final_fetch` | **136** |
| `relevance_threshold_applied` | 0.2511 |
| `relevance_model` | **BAAI/bge-m3** |

### Estado técnico confirmado

- **OpenAlex:** cache hit
- **Europe PMC:** cache hit
- **Scopus:** cache hit
- **Semantic Scholar:** `miss_no_key` — continua desativado sem `S2_API_KEY`
- **Scoring semântico:** ativo no `.venv`, executando em CPU

### Implicação prática

O fetch agora está **tecnicamente estabilizado** no ambiente correto do projeto: coleta multifuente, cache global, backfill de abstracts do Scopus e ranking híbrido com BGE-M3 funcionando de ponta a ponta.

O próximo passo de conteúdo, se o corpus v12 for adotado como base principal do trabalho, é **rerodar D2–D6** para substituir os artefatos antigos (`corpus_clean.csv`, embeddings, eixos, análises e visualizações) pelos números coerentes com este novo fetch de 136 papers.

---

## Sessão 8 — v13 Limpo (pipeline completo)

### O que foi feito

- Criado um run isolado em `runs/academic_production_v13`.
- Reaproveitado o fetch multifuente validado no `.venv` com cache global.
- Corrigido `bibliometry_pipeline/indicators.py` para funcionar com o schema multifuente atual:
  - não assumir mais que `authorships` existe em todos os registros;
  - usar `keyword_terms` como fallback quando `keywords` bruto não existe;
  - evitar `KeyError` quando a tabela de autores fica vazia.
- Instaladas no `.venv` as dependências que faltavam para os estágios downstream: `umap-learn` e `tabulate`.

### Resultado do run v13

| Etapa | Resultado |
|------|-----------|
| Fetch | 136 papers |
| Clean | 134 papers |
| Embed | 130 papers |
| Clustering | `k_best = 2`, silhouette = **0.113** |
| Summary | `indicators/report_summary.json` gerado |
| Report text | `NOTES/report_text.md` gerado |

### Métricas centrais do v13

| Métrica | Valor |
|---------|-------|
| `n_identified_unique` | 1.648 |
| `n_final_fetch` | 136 |
| `n_final_clean` | 134 |
| `n_final_semantic` | 130 |
| `zero_citations_pct` | 56,2% |
| `max_citations` | 76 |
| cluster 0 | 71 papers (54,6%) — `Research Writing` |
| cluster 1 | 59 papers (45,4%) — `Research Workflow` |

### Limitação observada

- Os indicadores baseados em autores (`top_authors.csv` e `lotka.csv`) ficaram vazios no v13 porque o corpus multifuente atual não preserva metadados brutos de autoria em todos os registros. O pipeline agora **não quebra**, mas essa parte analítica ainda está degradada para runs mistos.

### Artefatos principais gerados em `runs/academic_production_v13/`

- `corpus.csv`
- `corpus_clean.csv`
- `corpus_clustered.csv`
- `embeddings_bgem3.npy`
- `embeddings_bgem3_meta.json`
- `fetch_log.json`
- `indicators/report_summary.json`
- `NOTES/report_text.md`

---

## Sessão 4 — Redesenho do Fetch

### Diagnóstico

- O run `runs/academic_production_v8` não falhou por falta de candidatos: a união das queries gerou **1.296** registros únicos.
- O colapso para **7 papers** ocorreu porque o fetch usava exclusões binárias (`missing_academic_scope` + `negative_scope`) cedo demais, descartando artigos plausíveis assim que aparecia um termo clínico, pedagógico ou lateral no título/abstract.

### Decisões tomadas

- Substituir o gate binário do fetch por um **`relevance_index` híbrido**: cobertura de queries + sinais lexicais de escopo + similaridade semântica com protótipos positivos/negativos usando **BGE-M3**.
- Manter como exclusões duras apenas `no_abstract` e `offtopic_title`; o restante entra em ranking e auditoria.
- Salvar dois artefatos de auditoria no fetch: `indicators/fetch_exclusions.csv` (excluídos) e `indicators/fetch_relevance_audit.csv` (todos os candidatos ranqueados).
- Proteger no `clean.py` artigos com `relevance_index` alto contra remoção automática por `primary_topic` off-topic quando houver sinal forte de alinhamento.
- Trocar os termos de busca mais abertos (`research support`, `literature review`, `evidence synthesis`, etc.) por termos mais específicos de fluxo editorial e apoio à produção acadêmica (`manuscript screening`, `scientific publishing`, `research assistant`, `academic integrity`).

### Verificação do novo fluxo

- Run de teste: `runs/academic_production_v11`
- Resultado: **6.774** hits brutos → **1.412** candidatos únicos → **87** com alinhamento central → **60** no fetch → **48** no `corpus_clean.csv`
- Leitura metodológica: o novo fetch recupera um corpus muito maior que os 7 papers do v8, mas ainda com algum ruído lateral. O ganho desta sessão foi **recall controlado com transparência de ranking**, não precisão perfeita.
- Próximo ponto de ajuste, se necessário: mexer primeiro em `FETCH_RELEVANCE_THRESHOLD`, `FETCH_MIN_FINAL` e `RESEARCH_SEARCH_TERMS`, não voltar ao filtro binário antigo.

---

## Sessão 5 — Auditoria e Correção do Pipeline v11

### Diagnóstico via `fetch_relevance_audit.csv` (v11)

Auditoria completa dos 1.412 candidatos únicos revelou 8 problemas no pipeline:

| # | Problema | Evidência |
|---|----------|-----------|
| 1 | `FETCH_RELEVANCE_THRESHOLD=0.42` nunca ativado — score máximo observado = 0.381; `min_floor=60` sempre acionado | análise de sensibilidade de threshold |
| 2 | `min_floor=60` forçava ~40 papers EFL de baixa qualidade (ranks 21–60 com sinais `language_learning`/`classroom_pedagogy`) | lista dos 60 kept |
| 3 | ADVISE (evidence synthesis, sem_pos=0.709) excluído por `weak_domain_alignment` porque "evidence syntheses" ≠ "evidence synthesis automation" | audit CSV |
| 4 | LLM Literature Review Services (relevance=0.38) perdia positive scope match — regra exigia "literature review services?" que foi removida sem substituto | trace de regras |
| 5 | 8 termos de busca com precision < 10% (alinhamento) geravam ruído EFL ou low-ROI | tabela de precision por termo |
| 6 | `translation\|interpreting` na regra negativa bloqueava artigos de tradução científica (em escopo) | análise de regras |
| 7 | `writing skills` na regra classroom_pedagogy bloqueava artigos legítimos de pesquisa-escrita | análise de regras |
| 8 | `HARD_OFFTOPIC_TITLE_RE` não detectava plurais: "Tumors" não casava com `tumou?r\b` (word boundary final bloqueia "tumors") | teste regex: "CAR-T Cells for Solid Tumors" → False |

### Correções implementadas em `bibliometry_pipeline/config.py`

**Thresholds e floors:**
- `FETCH_RELEVANCE_THRESHOLD`: 0.42 → **0.25** (threshold agora funcional: 24 papers acima no dado v11)
- `FETCH_MIN_FINAL`: 60 → **30** (stop forcing-in low-quality papers)
- `FETCH_MAX_FINAL`: 180 → **200**

**`RESEARCH_SEARCH_TERMS` (28 → 25 termos):**
- Removidos (EFL-heavy, < 10% precision): `"academic journal writing"` (517 raw, 5.4% kept), `"academic paper writing"` (315, 5.1%), `"scientific writing"` (459, 5.2%), `"research paper writing"` (425, 4.0%)
- Removidos (low-ROI, < 3% kept): `"systematic review automation"` (190, 1.1%), `"review screening"` (201, 2.5%), `"literature review services"` (425, 2.4%), `"research assistant"` (563, 2.8%)
- Adicionados (alta precision): `"automated peer review"`, `"AI peer reviewer"`, `"paper mill detection"`, `"retraction detection"`, `"evidence synthesis"`

**`POSITIVE_SCOPE_RULES`:**
- `research_workflow`: Removidos "systematic review automation", "review screening", "literature review services?"; Adicionados "evidence synthesis", "systematic literature review", "literature review (?:system|tool|software|platform|automation|assistant|support|services?)"
- `integrity_governance`: Adicionados "LLM-generated (?:paper|manuscript|text|content)", "generated text detect", "AI.{0,5}text detect", "deepfake text", "authorship attribution"

**`HARD_NEGATIVE_SCOPE_RULES`:**
- `language_learning`: Removidos `translation|interpreting` (tradução científica é in-scope)
- `classroom_pedagogy`: Removido `writing skills` (muito genérico, bloqueava pesquisa-escrita)

**`HARD_OFFTOPIC_TITLE_RE`:** Corrigidos plurais: `tumou?r` → `tumou?rs?`, `cancer` → `cancers?`, `patient care` → `patients? care`, `clinical trial` → `clinical trials?`, `hospital` → `hospitals?`

### Métricas: simulação com dados v11 + config novo

| Métrica | Antes (v11) | Depois (simulado) | Δ |
|---------|-------------|---------------------|---|
| Papers no gate core_alignment | 87 | 132 | +52% |
| Papers acima do threshold | 0 (@ 0.42) | **24** (@ 0.25) | threshold funcional |
| Strategy | min_floor → 60 | **score_threshold** (24) + min_floor até 30 | melhora |
| Mean relevance_index | 0.184 | **0.284** | +54% |
| Min relevance_index | 0.054 | **0.217** | +302% |
| Papers sem sinal negativo | ~5/60 (8%) | **15/30 (50%)** | +6× |
| ADVISE (evidence synthesis) | ❌ excluído | ✅ rank 5 (0.337) | resgatado |
| LLM Literature Review Services | ✅ rank 2 (0.381) | ✅ rank 2 (0.381) | mantido |

### Nota: simulação vs run real

A simulação reutiliza os **scores semânticos do v11** (BGE-M3 já computados). Um run real com os novos `RESEARCH_SEARCH_TERMS` geraria um pool de candidatos diferente, potencialmente com melhor precision desde a coleta. O próximo run de validação recomendado: `academic_production_v12`.

---

## Sessão 6 — Sinal Semântico & Fonte Adicional (Semantic Scholar)

### Diagnóstico do sinal semântico

Análise dos scores no `fetch_relevance_audit.csv` (v11, 1.412 candidatos):

| Grupo | sem_pos mean | sem_neg mean | margin mean | margin > 0.05 |
|-------|-------------|-------------|-------------|---------------|
| kept (n=60) | 0.628 | 0.619 | +0.009 | 20% |
| EFL excluded (n=775) | 0.588 | 0.653 | −0.066 | 1.4% |

**Problema estrutural identificado:** BGE-M3 (modelo multilingual geral) posiciona tanto papers de ferramentas para pesquisadores quanto papers EFL em uma região semântica sobreposta ("IA + linguagem + acadêmico"). O gap de 0.075 no margin é real mas captura apenas 20% dos papers mantidos.

**Experimento: novos protótipos (estilo de abstract)**
- Testados 13 protótipos positivos concretos (citando Zotero, PICO, paper mill, etc.) + 8 negativos específicos
- Resultado: gap de margin **ficou pior** (0.059 vs 0.075); protótipos muito específicos abaixam o score positivo para todos os papers
- Conclusão: **não há sentença de protótipo que resolva o problema sem fine-tuning ou centroide discriminante**

**Solução adotada (compromisso):**
- Mantidos os 4 protótipos genéricos originais (que deram o gap 0.075)
- Adicionados 3 protótipos positivos moderadamente específicos (AI-text detection, literature review service, paper mill)
- Adicionados 4 protótipos negativos específicos (EFL quasi-experiment, EFL survey, medical, industrial) para puxar o `negative_max` para cima nos papers EFL
- Agregação positiva mudada de `max` para `mean_top2` (mais estável)

### Nova fonte de dados: Semantic Scholar

O usuário tem acesso institucional CAFe (SAML/SSO para portais web). **Importante:** CAFe autentica portais web, não fornece acesso programático a APIs de bases de dados. As APIs bibliográficas precisam de chaves separadas.

**Semantic Scholar Academic Graph API** implementado:
- Arquivo: `bibliometry_pipeline/semantic_scholar.py`
- Grátis sem chave (1 req/s, pode gerar 429 consistentes); chave gratuita em semanticscholar.org/product/api (10 req/s)
- Mesma interface de colunas que `openalex.flatten_records`
- Deduplicação por DOI normalizado + título (OpenAlex tem prioridade)
- Falha gradual: se o endpoint retorna 429 sem chave, pula queries restantes e reporta instrução para obter chave

**Configuração:**
```python
# config.py
SEMANTIC_SCHOLAR_ENABLED = True       # habilitar/desabilitar
SEMANTIC_SCHOLAR_API_KEY = ""         # ou variável de ambiente S2_API_KEY
```

**Integração em `fetch.py`:**
- Novo Step 1b inserido após OpenAlex fetch
- DataFrame SS mesclado por DOI/título antes da construção do `text_blob` e scoring
- `data_source` column adicionada ao corpus (`"openalex"` ou `"semantic_scholar"`)
- `fetch_log.json` agora inclui `sources_enabled`, `n_openalex_unique`, `n_semantic_scholar_candidates`, `n_semantic_scholar_new`

**Para obter uma chave gratuita Semantic Scholar:**
1. Acesse semanticscholar.org/product/api
2. Clique em "Get Started" → "Request an API Key"
3. Formulário simples (nome, afiliação, propósito de uso)
4. Aprovação geralmente em < 24h
5. Configure a chave no campo vazio `SEMANTIC_SCHOLAR_API_KEY` em `config.py`
  ou defina a variável de ambiente `S2_API_KEY` antes de rodar o pipeline



| Métrica | Valor |
|---------|-------|
| Papers identificados | 631 |
| Papers no corpus final | **586** (embeddings) · **589** (corpus_clean.csv) |
| Diferença | 3 papers dropados no embedding (sem embedding válido) |
| Anos completos para análise | 2020–2025 (n=531); 2026 excluído de tendências (n=58, ano parcial) |
| Silhouette score (k=5) | 0.069 — corpus homogêneo (todos "AI + educação + linguagem") |
| Artigo mais citado | *ChatGPT and a new academic reality* (2023) — **727 citações** |

---

## Clusters (k=5, KMeans + BGE-M3)

| Cluster | Label | n | Característica principal |
|---------|-------|---|--------------------------|
| C0 | **EFL teaching** | 244 | Integração de IA genérica em salas de aula de inglês; metodologias pedagógicas |
| C1 | **ChatGPT surveys** | 67 | Percepções, adoção e ética do ChatGPT; levantamentos pós-2023 |
| C2 | **NLP/translation** | 92 | Tradução automática, PLN, processamento de fala; domínio instrumental |
| C3 | **EFL outcomes** | 134 | Efeitos da IA em aprendizes de L2; dependência, literacia, habilidades |
| C4 | **LLMs in HE** | 49 | LLMs no ensino superior e pesquisa; ChatGPT na academia |

**Nota:** C0 domina a produção (42% do corpus). O campo é nominalmente "IA para produção acadêmica" mas na prática é "IA para o aluno de inglês como L2".

---

## Eixos Semânticos

Três eixos selecionados de um torneio de 7 candidatos. Método: embedding de sentenças-polo (BGE-M3), projeção dos 586 abstracts, validação LOO com 6 paráfrases por eixo.

### Eixo E — Enquadramento Tecnológico
**Polo negativo (−):** IA genérica ("AI", "machine learning", sem nome específico)
**Polo positivo (+):** ChatGPT / IA Generativa (nomeada)

| Métrica | Valor |
|---------|-------|
| std (dispersão) | 0.070 |
| LOO mean ρ | 0.758 |
| LOO min ρ | 0.677 — **MARGINAL** |
| Correlação E×A | r = −0.032 ✅ quase ortogonal |
| Correlação E×D | r = +0.131 ✅ |

**Cluster means:** C1 (ChatGPT surveys) +0.102 ← isolado no polo positivo; C0 (EFL) −0.060.

---

### Eixo A — Beneficiário
**Polo negativo (−):** Aluno / sala de aula de inglês L2
**Polo positivo (+):** Pesquisador / produção científica

| Métrica | Valor |
|---------|-------|
| std (dispersão) | 0.065 |
| LOO mean ρ | 0.822 |
| LOO min ρ | 0.749 — **PASS** |
| Nota | Eixo F (nível educacional) foi descartado: r=0.811 com A — mesma dimensão |

**Cluster means:** C2 (NLP) +0.007, C4 (LLMs in HE) +0.009 ← polo pesquisador; C0 −0.079, C1 −0.123, C3 −0.066 ← polo aluno.

---

### Eixo D — Postura
**Polo negativo (−):** Prescritivo (como adotar, guias práticos)
**Polo positivo (+):** Crítico (questionamentos éticos, epistemológicos)

| Métrica | Valor |
|---------|-------|
| std (dispersão) | 0.052 |
| LOO mean ρ | 0.708 |
| LOO min ρ | 0.549 — **WEAK** |
| Nota: polo negativo instável | Ética e epistemologia puxam em direções ligeiramente diferentes |

**Uso recomendado:** apenas como histograma 1D — não usar como eixo 2D. A instabilidade no polo crítico impede ranqueamento fino.

---

## Findings — Análise 2: Perfil Temporal

> Script: `analyses_2_3.py` → `indicators/temporal_profile.csv`, `indicators/cluster_share_by_year.csv`

### Achado principal: a ruptura do ChatGPT é estrutural, não semântica

Nenhum eixo mostra tendência temporal significativa (todos p > 0.06). O que mudou em 2023 não foi a linguagem dos artigos, mas a composição do campo:

| Ano | n | EFL teaching | ChatGPT surveys | NLP/translation | EFL outcomes | LLMs in HE |
|-----|---|---|---|---|---|---|
| 2020 | 7 | 14% | 14% | 14% | 43% | 14% |
| 2021 | 9 | 22% | 0% | **67%** | 11% | 0% |
| 2022 | 17 | 18% | 6% | **41%** | 35% | 0% |
| **2023** | **77** | 42% | **16%** | 18% | 17% | 8% |
| 2024 | 164 | 41% | 12% | 18% | 23% | 6% |
| 2025 | 255 | 45% | 10% | 12% | 23% | 11% |

**Interpretação para o artigo:**
> "O ChatGPT não converteu a literatura existente — criou uma corrente paralela (C1, 16% em 2023), enquanto o fluxo de artigos sobre ensino de inglês com IA genérica continuou crescendo. Em 2024–2025, o C0 inundou o campo, diluindo a proporção de artigos ChatGPT-específicos de volta para ~10%."

**Padrão secundário:** NLP/tradução dominava 2021–2022 (era pré-ChatGPT). A proporção caiu de 67% → 12%. Isso indica que a agenda de PLN instrumental caiu de relevância relativa após a emergência dos LLMs.

---

## Findings — Análise 3: Eixos × Citações

> Script: `analyses_2_3.py` → `indicators/axis_scores_enriched.csv`

### Hipóteses testadas (Mann-Whitney unilateral)

| Hipótese | Resultado | p-value | Interpretação |
|----------|-----------|---------|---------------|
| Artigos ChatGPT-específicos (E Q4) > genéricos (E Q1) em citações | **CONFIRMADA** | p = 0.003 | med Q4=1.0 vs Q1=0.0 |
| Artigos voltados ao pesquisador (A Q4) > ao aluno (A Q1) | não confirmada | p = 0.38 | — |
| Artigos críticos (D Q4) > prescritivos (D Q1) | não confirmada | p = 0.86 | Prescritivos têm mediana maior |

### Correlação Spearman eixo × citações

| Eixo | ρ (todos) | p | ρ (só citados≥1) |
|------|-----------|---|-----------------|
| E (tecnologia) | +0.133 | **p = 0.001** | +0.128 |
| A (beneficiário) | +0.039 | p = 0.35 | +0.060 |
| D (postura) | −0.038 | p = 0.36 | +0.019 |

### Quartis de citações por Eixo E

| Quartil | n | Mediana cit | Média cit |
|---------|---|------------|-----------|
| Q1 — IA genérica | 147 | 0.0 | 6.5 |
| Q2 | 146 | 0.5 | 7.3 |
| Q3 | 146 | 1.0 | 8.2 |
| Q4 — ChatGPT/GenAI | 147 | 1.0 | **13.1** |

**Interpretação para o artigo:**
> "Nomear uma tecnologia específica (ChatGPT, GPT-4, GenAI) no abstract está associado a maior impacto por citações (ρ=+0.13, p=0.001). Artigos com framing genérico têm mediana de **zero** citações — a maioria ainda não recebeu nenhuma. O artigo mais citado do corpus (727 cit.) é um ChatGPT-específico em C1."

> "A postura crítica não se traduz em mais citações na amostra atual. Os 6 artigos mais críticos (D > +0.16) somam 36 citações no total; o artigo prescritivo mais citado sozinho tem 153."

---

## Top-5 Artigos Mais Citados (com posições nos eixos)

| # | Cit. | Ano | Cluster | E | A | D | Título (resumido) |
|---|------|-----|---------|---|---|---|-------------------|
| 1 | 727 | 2023 | C1 ChatGPT surveys | +0.247 | −0.062 | +0.062 | *ChatGPT and a new academic reality* |
| 2 | 367 | 2023 | C0 EFL teaching | −0.079 | −0.112 | −0.038 | *AI in language instruction: achievement, L2 motivation...* |
| 3 | 291 | 2020 | C3 EFL outcomes | +0.017 | +0.007 | +0.068 | *Assessing the Attitude Towards Artificial Intelligence* |
| 4 | 198 | 2023 | C0 EFL teaching | −0.052 | −0.111 | +0.002 | *The Role Of AI In Developing ELL Communication Skills* |
| 5 | 153 | 2023 | C0 EFL teaching | −0.117 | −0.068 | −0.028 | *AI technologies and applications for language learning* |

**Padrão:** os 4 mais citados depois do #1 são todos polo estudante (A negativo). O campo "vende" para o leitor EFL, não para o pesquisador.

---

## Arquivos de Saída Gerados

| Arquivo | Conteúdo |
|---------|----------|
| `corpus_clean.csv` | Corpus limpo (589 linhas) |
| `corpus_clustered.csv` | 586 papers + cluster (0–4) + umap_x/umap_y |
| `embeddings_bgem3.npy` | Embeddings 586×1024 float32 (BGE-M3, L2-norm) |
| `indicators/yearly_production.csv` | Produção por ano |
| `indicators/geo_countries.csv` | Papers por país |
| `indicators/journals.csv` | Top journals |
| `indicators/top20_cited.csv` | Top 20 artigos mais citados |
| `indicators/keyword_freq.csv` | Frequência de keywords |
| `indicators/keyword_cooc.csv` | Co-ocorrência de keywords |
| `indicators/umap_coords.csv` | ID, cluster, umap_x, umap_y |
| `indicators/axis_scores.csv` | 586 papers × 3 eixos (E, A, D) |
| `indicators/axis_scores_enriched.csv` | + cluster_label + cited_by_count |
| `indicators/axis_validation.txt` | LOO e ortogonalidade completos |
| `indicators/temporal_profile.csv` | n, %E>0, mean E/A/D por ano (2020–2025) |
| `indicators/cluster_share_by_year.csv` | % de cada cluster por ano |

---

## D6 — Visualizações (CONCLUÍDO)

> Script: `visualizations.py` → `NOTES/report.md` (1752 KB, dark mode, DPI=150)

### Figuras e Seções Geradas

| Item | Tipo | Conteúdo |
|------|------|----------|
| KPI Cards | HTML | 6 cartões: 586 papers, 2020–26, 78 países, 727 max cit., C0 dominante, 51% sem cit. |
| Achados | HTML | 4 callout boxes com achados-chave |
| PRISMA | HTML | Fluxo de exclusão 631→603→589→586 em caixas estilizadas |
| Fig 2 | matplotlib | Produção anual + % ChatGPT-específico (linha secundária) |
| Fig 3 | matplotlib | Área empilhada (contagens absolutas) — composição de clusters por ano |
| Fig 4 | matplotlib | Top 15 países (barras horizontais, coloridas por continente) |
| Fig 5 | matplotlib | UMAP scatter 2D + estrelas por cluster (sem elipses — silhouette=0.069) |
| Fig 6 | matplotlib | Scatter E×A + anotações por cluster + estrelas (posições axes-fraction) |
| Fig 7 | matplotlib | Box+strip Eixo E × citações (escala symlog) |
| Fig 8 | matplotlib | Histograma Eixo D + sparkline de mediana por bin |
| Fig 9 | matplotlib | Heatmap 3×3 ortogonalidade (cor de texto WCAG automática) |
| Fig 10 | matplotlib | Top 12 periódicos (barras DOAJ vs não-DOAJ) |
| Tabela 1 | HTML | Top 20 artigos mais citados (com link DOI) |
| Fig 11 | matplotlib/networkx | Rede co-ocorrência keywords (top 20 nós, arestas ≥ 8, greedy modularity) |
| Tabela 2 | HTML | Top 15 autores + Lei de Lotka side-by-side |

### Polimentos Aplicados (sessões 2–3)

- Elipses removidas do UMAP e E×A (silhouette=0.069 não justifica)
- Estrelas por cluster adicionadas (Figs 5 e 6), coloridas por cluster
- Fig 6: anotações top paper por cluster com `textcoords='axes fraction'` (posições hardcoded)
- Fig 8: bin edges compartilhados entre histplot e sparkline; mediana corrigida (era média)
- Fig 9: contraste de texto automático via fórmula de luminância WCAG
- Achado 4 p-value corrigido: p=0.86 → p=0.35 (Mann-Whitney unilateral)
- Callouts: emojis substituídos por `Q:`, `M:`, `R:`
- Fig 11: grafos inicial (30 nós, 143 arestas) simplificado → 20 nós, ~20 arestas, layout mais espaçado

---

## Próximos Passos

### D7 — Redação do Artigo

**Deadline:** 22 abr 2026 · **Dias restantes:** 13

Todas as figuras e tabelas estão prontas em `NOTES/report.md`. O artigo pode ser escrito diretamente com base nos achados documentados neste arquivo e nos callouts do report.

**Estrutura sugerida:**
1. Introdução — motivação, gap, objetivo
2. Metodologia — PRISMA, OpenAlex, BGE-M3, eixos semânticos
3. Resultados
   - 4.1 Visão geral do corpus (KPIs + PRISMA)
   - 4.2 Perfil temporal (Figs 2–3)
   - 4.3 Distribuição geográfica (Fig 4)
   - 4.4 Clusters semânticos (Figs 5–6)
   - 4.5 Top-20 artigos (Tabela 1)
   - 4.6 Impacto por framing tecnológico (Figs 7–8)
   - 4.7 Rede de keywords (Fig 11)
   - 4.8 Autores e Lei de Lotka (Tabela 2)
   - 4.9 Periódicos (Fig 10)
4. Discussão — 4 achados centrais (já escritos nos callouts do report)
5. Conclusão

---

### D6 — Plano de Visualizações (referência histórica)

#### Arquitetura geral do script (`visualizations.py`)

Inspirado no `charts.py` + `dashboard.py` + `writer.py` do Veredas:

- **Um script, uma saída:** `visualizations.py` gera `NOTES/report.md` — arquivo único com figuras
  embarcadas como PNG base64 (`data:image/png;base64,...`), igual ao padrão `fig_to_base64` +
  `embed_fig` do Veredas. Legível no GitHub/VSCode sem dependências; PNGs extraíveis para o LaTeX.
- **Extrator de figuras:** copiar o padrão `_extract_report_figs.py` do Veredas — regex busca todas
  as `<img src="data:image/png;base64,...">` e salva em `figures/figNN_<alt>.png` para incluir no artigo.
- **Dois modos de estilo:**
  - `--dark` (padrão): fundo `#1a1a2e`, texto `#d4d4d4`, grid `#2a3a4e` — idêntico ao Veredas, bom para tela
  - `--light`: fundo branco, texto escuro, `dpi=220` — para exportação ao artigo PDF
  Implementado via `setup_mpl(light=True/False)`, igual à função `set_light_mode` do Veredas.
- **Paleta de 5 clusters** (fixa em todo o script):
  ```
  C0 EFL teaching    #58a6ff  (azul)
  C1 ChatGPT surveys #f0883e  (laranja)
  C2 NLP/translation #3fb950  (verde)
  C3 EFL outcomes    #d2a8ff  (lilás)
  C4 LLMs in HE      #39d2c0  (teal)
  ```
- **Cada figura tem um bloco de texto antes da imagem** com três callout boxes (inspirado nas seções do
  `dashboard.py`):
  - 🔵 `Pergunta` — o que esta figura responde
  - ⚙️ `Método` — como os dados foram calculados
  - 📖 `Como ler` — orientação de leitura para o leitor do artigo

---

#### Figures

---

**Fig 1 — KPI Cards + Visão Geral do Corpus**
*Seção do artigo: 4.1* · *Script: `visualizations.py`*

Inspirado diretamente no `_section_executive` / `.kpi-grid` CSS do Veredas dashboard.
Um grid de 6 cartões HTML (não matplotlib): N papers, anos cobertos, N países, artigo mais citado,
cluster dominante, % sem citação.
Gerado como HTML inline no `report.md`; não exportado como PNG (é texto formatado).

```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│   586   │ │ 2020–26 │ │   78   │ │  727   │ │  C0    │ │  51%   │
│ Papers  │ │  Anos   │ │ Países  │ │Max cit.│ │ maior  │ │0 cit.  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

---

**Fig 2 — Produção Científica Anual (área + ruptura sombreada)**
*Seção 4.2* · *Dados: `yearly_production.csv`* · *Output: `fig02_temporal.png`*

- Tipo: área `fill_between` + linha, **idêntico ao padrão do Veredas** `_section_corpus_timeseries`
  (fill_between com `alpha=0.3`, linha fina por cima, hotspot shading em vermelho)
- Eixo X: anos 2020–2026. Eixo Y: N papers publicados
- **Banda sombreada vertical** em 2022.5–2023.5 com anotação "ChatGPT (nov 2022)" —
  igual ao padrão `ax.axvline` + `ax.fill_betweenx` do Veredas (usado para marcar fronteiras de livros)
- Segunda série pontilhada: % de papers com Axis E > 0 (escala Y direita secundária / `ax.twinx()`)
- Bootstrap CI nas médias anuais do Eixo E (reamostragem, n=2000), plotado como banda de erro —
  inspirado em `_bootstrap_ci` de `scale_decomposition.py`

**Pergunta:** O campo cresceu de forma contínua ou há uma ruptura discernível?
**Achado esperado:** salto 5× de 2022→2023, banda de ChatGPT confirma visualmente.

---

**Fig 3 — Composição por Cluster ao Longo do Tempo (barras empilhadas 100%)**
*Seção 4.2* · *Dados: `cluster_share_by_year.csv`* · *Output: `fig03_cluster_composition.png`*

- Tipo: stacked bar 100% (`bar` + `bar` empilhado com `bottom=`)
- 5 barras (2020–2022 agrupadas opcionalmente dado n pequeno), cada barra = 100%
- Cores fixas por cluster (paleta acima)
- Anotações de N total no topo de cada barra (inspirado nos rótulos `.text()` do `_gen_proposta_figs.py`)
- **Linha vertical tracejada** separando o período pré/pós ChatGPT — igual às `axvline` do Veredas

**Pergunta:** A ruptura do ChatGPT alterou a composição temática do campo?
**Achado:** NLP/tradução dominava 2021–22 (67%), C1 ChatGPT surveys emergiu em 2023 (16%), C0 EFL
 teaching inundou o campo em 2024–25, diluindo o sinal. Argumento central da seção 4.2.

---

**Fig 4 — Mapa Coropletro + Top 10 Países (painel duplo)**
*Seção 4.3* · *Dados: `geo_countries.csv`* · *Output: `fig04_geo.png`*

- **Painel duplo** (`plt.subplots(1, 2)`), largura 16×5 — inspirado nos painéis duplos do Veredas
  (ex. histograma + z-score em `_section_dispersion_distribution`)
- Painel esquerdo: `plotly.express.choropleth` → salvo como PNG via `kaleido`; recarregado
  como imagem e inserido no subplot com `ax.imshow` (ou gerado separado)
- Painel direito: barras horizontais Top 10 países, **coloridas por continente** (azul = Ásia,
  verde = América, laranja = Europa — mesma ideia das `REGISTER_COLOURS` do Veredas)
- Valor anotado ao lado de cada barra (padrão `bar.get_width() + offset` do Veredas)
- Barra do CN destacada com cor diferente (maior volume, pré-atentivo — princípio do professor)

---

**Fig 5 — UMAP Scatter 2D (clusters semânticos)**
*Seção 4.6* · *Dados: `corpus_clustered.csv` (umap_x, umap_y, cluster, cited_by_count)* · *Output: `fig05_umap.png`*

- Scatter `ax.scatter(umap_x, umap_y, c=cluster_colour, s=marker_size, alpha=0.55)`
- `marker_size = 3 + np.log1p(cited_by_count) * 2` — papers mais citados = ponto maior
  (igual ao "tamanho = citações" mencionado no plano original; o log1p suaviza outliers)
- Opacidade 0.55 deixa visível a densidade, igual aos scatter plots do Veredas
- **Elipses de 1σ por cluster** (`matplotlib.patches.Ellipse` com covariância calculada) —
  substitui a legenda densa, deixa claro onde cada cluster está concentrado
- Labels de centroide (texto com seta curta) para C0–C4
- Ponto #1 (727 cit.) destacado com marcador ★ e anotação

**Nota de implementação:** gerar elipses via `np.cov(umap_x[mask], umap_y[mask])`, extrair autovalores
e autovetores para largura/altura/ângulo da elipse. Padrão common em scatter semantics plots.

---

**Fig 6 — Scatter Semântico E×A (projeção nos eixos, o "mapa de risco")**
*Seção 4.6* · *Dados: `axis_scores_enriched.csv`* · *Output: `fig06_scatter_EA.png`*

Figura central da análise semântica — análogo direto ao diagrama de dispersão de traduções do Veredas.

- Eixo X = Axis E (−=IA genérica, +=ChatGPT/GenAI); Eixo Y = Axis A (−=aluno, +=pesquisador)
- **4 quadrantes** com rótulos (caixas de texto nos cantos):
  ```
  Q2: IA genérica         | Q1: ChatGPT
      → pesquisador        |     → pesquisador
  ─────────────────●───────────── 0 (Y)
  Q3: IA genérica         | Q4: ChatGPT
      → aluno EFL          |     → aluno EFL
  ```
- Ponto colorido por cluster, tamanho = log1p(cited_by_count)
- **Linhas de grade nos eixos (0,0)** com `ax.axhline(0)` + `ax.axvline(0)` em branco/cinza
- Top-5 papers mais citados anotados por nome
- **Elipses de 1σ por cluster** (mesmas do Fig 5 mas no espaço E×A)
- Argumento visual: corpus empacotado no Q3 (maioria C0+C3); C1 isolado no Q4 inferior direito;
  C2+C4 no lado pesquisador

---

**Fig 7 — Eixo E por Quartil × Citações (box plot + swarm overlay)**
*Seção 4.6* · *Dados: `axis_scores_enriched.csv`* · *Output: `fig07_axis_e_citations.png`*

- Dividir corpus em 4 quartis do Axis E (Q1=IA genérica → Q4=ChatGPT/GenAI)
- Box plot horizontal (violins muito comprimidos para dados com muitos zeros)
- **Swarm overlay** com `seaborn.stripplot(dodge=True, alpha=0.35, jitter=0.2)` para mostrar
  distribuição real (ideia do Veredas: sempre mostrar os dados brutos junto com sumário)
- Escala Y log (`ax.set_yscale("log")`) — necessário dado a cauda (0→727 cit.)
- Anotação da mediana e N em cada quartil
- Faixa sombreada destacando Q4 (cor laranja/chatgpt) com rho e p anotados

**Achado:** mediana Q1=0.0, mediana Q4=1.0, U test p=0.003, mean Q4=13.1 vs Q1=6.5.

---

**Fig 8 — Histograma do Eixo D com Sobreposição de Citações**
*Seção 4.6* · *Dados: `axis_scores_enriched.csv`* · *Output: `fig08_axis_d.png`*

- 1D histogram do Eixo D com KDE sobreposta (mesma apresentação do `_section_zscore` do Veredas:
  `sns.histplot` + KDE + linha vertical limiar)
- **Linha vertical** em D=0 separando prescritivo (−) de crítico (+)
- Marcadores ️★ acima do histograma na posição dos top-6 papers por citações
  (inspira-se no padrão `ax.text` de anotação de hotspots do Veredas)
- Segunda barra laranja à direita mostrando citações médias por bin (twin axis)
- Chama atenção que os 6 papers críticos (D > +0.16) somam apenas 36 cit. no total

---

**Fig 9 — Heatmap de Ortogonalidade dos Eixos** *(mini-figura para seção metodológica)*
*Seção 3.4 ou Apêndice* · *Dados: calculados inline* · *Output: `fig09_orthogonality.png`*

Diretamente inspirado na tabela HTML `_ortho_bg` / `_bar_html_axis` do `axes.py` do Veredas —
mas como figura matplotlib para o artigo (heatmap 3×3).

- `plt.imshow(corr_matrix, cmap="RdBu_r", vmin=-1, vmax=1)`
- Células anotadas com valor r (2 decimais)
- Diagonal = "—"; off-diagonal colorido: azul=orthogonal, vermelho=correlacionado
- Tabela: `[[1.0, -0.032, 0.131], [-0.032, 1.0, 0.381], [0.131, 0.381, 1.0]]`
- Rótulos: "E (GenAI)", "A (Beneficiário)", "D (Postura)"

---

**Fig 10 — Rede de Co-ocorrência de Keywords** *(bônus — networkx + pyvis)*
*Seção 4.7* · *Dados: `keyword_cooc.csv`* · *Output: `figures/keywords_network.html` + PNG*

- Nós = keywords, arestas = co-ocorrência em ≥3 papers
- Tamanho do nó = frequência; espessura da aresta = força de co-ocorrência
- Colorir nós por cluster de destino (qual cluster usa mais aquela keyword)
- Exportar HTML interativo com `pyvis` e estático PNG com `matplotlib` + `networkx`

---

#### Entregáveis do D6

```
visualizations.py          ← script principal (modo dark + light)
extract_report_figs.py     ← extrator base64→PNG (padrão Veredas)
NOTES/report.md            ← relatório único com figuras embarcadas
figures/
  fig02_temporal.png
  fig03_cluster_composition.png
  fig04_geo.png
  fig05_umap.png
  fig06_scatter_EA.png
  fig07_axis_e_citations.png
  fig08_axis_d.png
  fig09_orthogonality.png
  keywords_network.html    (bônus)
```

#### Ordem de implementação recomendada

1. Montar `setup_mpl(light)` e paleta de cluster → **shared infra**
2. Fig 2 (temporal + ruptura) — valida os dados antes de tudo
3. Fig 5 (UMAP) + Fig 6 (scatter E×A) — as duas figuras semânticas centrais
4. Fig 3 (composição temporal) — usa os mesmos dados da Fig 2
5. Fig 7 + Fig 8 (eixos × citações) — análise 3
6. Fig 4 (geo) — mais trabalhosa por causa do choropleth; deixar por último
7. Fig 9 (ortogonalidade) — trivial, 10 min
8. Fig 1 (KPI cards) — HTML puro, 5 min
9. Fig 10 (rede) — bônus, fazer se sobrar tempo

---

### D7 — Redação

Seções prontas para escrever (dados já disponíveis):
- **4.1** Visão geral (corpus, PRISMA simplificado)
- **4.2** Evolução temporal + ruptura ChatGPT (Análise 2)
- **4.3** Distribuição geográfica
- **4.4** Periódicos e autores
- **4.5** Artigos de alto impacto (Top 20 + posições nos eixos)
- **4.6** Análise semântica — clusters UMAP, eixos E×A, eixo D histograma, temporal de composição
- **4.7** Análise temática (keywords)

---

## Decisões Metodológicas (para a seção 3)

| Decisão | Justificativa |
|---------|---------------|
| OpenAlex como fonte principal (não Scopus) | API Scopus gratuita: cap de 5.000 registros; sem InstToken institucional da UNIOESTE |
| BGE-M3 (não MiniLM) | Corpus multilíngue: árabe, chinês, russo, indonésio, turco. MiniLM é essencialmente inglês |
| k=5 clusters (não 3 ou 7) | Silhouette máximo em k=5; interpretabilidade boa (5 temas distintos e nomeáveis) |
| LOO threshold ρ > 0.70 (não 0.90) | Corpus homogêneo: todos os papers compartilham "AI + educação + linguagem". Threshold 0.90 do Veredas foi calibrado sobre 25 traduções bíblicas radicalmente distintas — não aplicável aqui |
| Keywords OpenAlex = algorítmicas | Atribuídas por inferência do sistema, não pelos autores. Declarar como limitação metodológica na seção 3.4 |
| 2026 excluído de tendências temporais | Ano parcial (57 papers até abril) — distorceria curvas de crescimento e deriva semântica |
