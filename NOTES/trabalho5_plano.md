# Plano de Execução — Trabalho 5
## Revisão Bibliométrica sobre Ferramentas de Inteligência Artificial de Apoio à Produção Acadêmica

> **Disciplina:** Tecnologia de Informação · **Entrega:** 22 abr 2026 às 19:00
> **Prazo restante:** 13 dias · **Equipe:** individual ou dupla
> **Arquivo de entrega:** `<nome_aluno>_trabalho5.pdf`

---

## 1. Entendendo o que o Professor Quer

Na Aula 5 (a partir de ~01h58), o professor explicou a lógica do trabalho com um exemplo ao vivo:

> *"Primeiro seleciona qual tempo você quer pesquisar. Seleciona o termo da pesquisa, qual é o range. Quais são as fontes? Aí começa a pegar esses dados quantitativos, apresentar em gráficos — e o que a gente chama de Revisão Bibliométrica."*

> *"Dá para fazer uma coisa melhor do que só usar o R, ou só o PowerBI, ou o Excel, não é? Os amigos vão usar todo tipo de ferramenta. O que eu quero é o foco: fazer um bom artigo."*

**Mensagem-chave:** a diversidade de ferramentas conta pontos; o foco é apresentar dados quantitativos sobre o estado da arte de forma clara e visualmente rica.

---

## 2. Palavras-chave de Busca

### 2.1 Grupos Conceituais

| Grupo | Termos |
|-------|--------|
| **G1 — Tecnologia IA** | `"artificial intelligence"` · `"machine learning"` · `"large language model*"` · `"generative AI"` · `"ChatGPT"` · `"GPT-4"` · `"LLM"` · `"AI tool*"` |
| **G2 — Produção Acadêmica** | `"academic writing"` · `"scientific writing"` · `"research support"` · `"academic productivity"` · `"literature review"` · `"scholarly communication"` · `"scientific production"` |

**Período:** 2020–2026

---

### 2.2 Equação Final — OpenAlex (execução concluída em 09/04/2026)

> **Por que OpenAlex e não Scopus por API:** a API key gratuita do Scopus (dev.elsevier.com) tem um cap rígido de 5 000 registros por query — qualquer query relevante ultrapassa esse limite (erro 400). O acesso completo exige InstToken institucional (solicitar à biblioteca da UNIOESTE para trabalhos futuros). O Scopus continua disponível via interface web para spot-check e validação dos top resultados.

**Query executada em `fetch_corpus.py`:**

```
G1 (tecnologia IA) no TÍTULO:
  title.search: artificial intelligence OR machine learning OR
                large language model OR generative AI OR ChatGPT OR GPT OR LLM

G2 (domínio acadêmico) via busca padrão (título + abstract):
  default.search: academic writing OR scientific writing OR
                  research support OR academic productivity OR scholarly communication

Filtros: publication_year > 2019 | type: article OR review
```

**Resultado (corpus salvo em `corpus_clean.csv` após D3):**

| Etapa PRISMA | Script | N |
|---|---|---|
| Identificados (OpenAlex) | fetch_corpus.py | 631 |
| Excluídos — off-topic clínico/médico | fetch_corpus.py | −10 |
| Excluídos — sem abstract | fetch_corpus.py | −18 |
| Excluídos — títulos duplicados | clean_corpus.py | −7 |
| Excluídos — tópico off-topic (inspeção manual) | clean_corpus.py | −7 |
| **Corpus final limpo** | | **589** |
| dos quais 2026 (ano parcial) | | 58 |

**Distribuição temporal (corpus limpo):**

| Ano | N | Tendência |
|-----|---|-----------|
| 2020 | 7 | Período pré-ChatGPT |
| 2021 | 9 | → |
| 2022 | 17 | ↗ |
| 2023 | 78 | **Ruptura ChatGPT** |
| 2024 | 164 | ↑↑ |
| 2025 | 256 | ↑↑↑ |
| 2026 | 58 | (em andamento) |

Re-executar: `python fetch_corpus.py && python clean_corpus.py`

### 2.3 Scopus — validação manual via interface web

Usar Scopus (UNIOESTE via CAFe) para:
- Verificar se os top-10 citados no corpus estão presentes no Scopus
- Obter métricas de periódico (SJR, CiteScore) para a seção 4.4

```
TITLE-ABS-KEY( "artificial intelligence" OR "machine learning" OR "large language model*" OR "generative AI" OR "ChatGPT" OR "GPT" OR "LLM" )
AND
DEFAULT( "academic writing" OR "scientific writing" OR "research support" OR "academic productivity" OR "scholarly communication" )
AND PUBYEAR > 2019 AND DOCTYPE ( ar OR re )
```

### 2.4 Corpus Final

| Métrica | Valor |
|---------|-------|
| Registros identificados | 631 |
| Corpus final limpo | **589** |
| Arquivo | `corpus_clean.csv` |
| DOAJ-indexados | 133 (22%) — restantes em periódicos não-OA |
| Top país | CN — 71 papers |
| Top journal | Applied Mathematics and Nonlinear Sciences — 9 |
| Artigo mais citado | 727 cit — *ChatGPT and a new academic reality* (2023) |
| Categorias | 57% other · 32% language_learning · 9% higher_ed |

> **Nota metodológica:** 78% dos artigos estão em periódicos não indexados no DOAJ. Isso não implica baixa qualidade (muitas revistas Elsevier/Springer não são OA), mas deve ser mencionado na seção 3.3 como limitação da fonte OpenAlex vs. Scopus.

---

## 3. Fontes de Pesquisa

| # | Base | Registros indexados | Acesso | Papel neste trabalho |
|---|------|---------------------|--------|-----------------------|
| 1 | **OpenAlex** | ~250 M | **Gratuito / API** | **Fonte principal** — corpus coletado via `fetch_corpus.py`; 612 papers em `corpus.csv` |
| 2 | **Scopus** | 43 400 | UNIOESTE via CAFe/CAPES | **Validação / spot-check** — interface web; API gratuita não suporta query de grande volume |
| 3 | **Google Scholar** *(opcional)* | Aberto | Gratuito | Captura pré-prints e literatura cinza não coberta pelas outras |

> **Nota:** a Profa. Ediane menciona que "a Dimensions é mais abrangente" que WoS. OpenAlex tem cobertura ainda maior que Dimensions (inclui Crossref, PubMed, arXiv, DOAJ) e exporta metadados completos incluindo abstracts e contagem de citações sem custo.

---

## 4. Metodologia (Protocolo PRISMA-Simplificado)

```
Busca nas bases (Scopus + WoS)
        │
        ▼
Exportar registros em .CSV (Scopus) e .txt (WoS)
        │
        ▼
Limpeza de dados (remover duplicatas, registros sem autor/ano)
        │
        ▼
Triagem por critérios de inclusão/exclusão
        │
        ▼
Análise bibliométrica (geração de indicadores)
        │
        ▼
Geração de visualizações
        │
        ▼
Redação e formatação do artigo
```

### Critérios de Inclusão
- Publicados entre 2020 e 2026
- Idioma: inglês, português ou espanhol
- Tipo: artigo de periódico, revisão, conferência
- Tema: ferramentas de IA aplicadas à escrita, leitura, pesquisa ou revisão acadêmica

### Critérios de Exclusão
- Artigos sem resumo disponível
- Publicações de pesquisa básica de IA sem aplicação acadêmica explícita
- Capítulos de livros (difíceis de rastrear citações)

---

## 5. Ferramentas Recomendadas

| Etapa | Biblioteca/Ferramenta | Por que |
|-------|-----------------------|---------|
| Coleta de dados | `fetch_corpus.py` + `requests` | Script terminado; chama a API OpenAlex com cursor pagination; salva `corpus.csv` com 612 papers. Re-executar: `python fetch_corpus.py` |
| Análise bibliométrica | `pandas` + `collections` | Contagens, top-N, evolução temporal — tudo com operações vetorizadas |
| Gráficos estatísticos | `matplotlib` + `seaborn` | Controle total de cores, fontes e layout; exporta PNG de alta resolução |
| Mapa coropletro (países) | `plotly.express.choropleth` | Uma chamada gera o mapa; exporta PNG estático via `kaleido` |
| Rede de co-ocorrência de keywords | `networkx` + `pyvis` | **Não visto em sala** = diferencial; gráfico de rede interativo exportável |
| Referências | **Zotero** | Única ferramenta não-Python; gera lista ABNT automaticamente |

---

## 6. Indicadores Bibliométricos a Apresentar

Com base nos **Principais Indicadores** ensinados nos slides da Profa. Ediane Gheno (p. 21):

| Indicador | O que mede | Visualização |
|-----------|-----------|-------------|
| Produção científica por ano | Crescimento do campo | Gráfico de linha temporal |
| **Produção por país** | Colaboração/domínio geográfico | **Mapa coropletro** *(obrigatório)* |
| **Top 10 países — volume** | Protagonistas do tema | **Gráfico de barras** *(obrigatório)* |
| Top 10 periódicos | Onde o tema é publicado | Gráfico de barras horizontal |
| Top 20 artigos mais citados | Obras centrais | **Tabela** *(obrigatório)* |
| Co-ocorrência de keywords | Subtemas emergentes | Rede de co-ocorrência (`networkx` + `pyvis`) |
| Co-autoria por país | Colaborações internacionais | Rede de países (`networkx` + `pyvis`) |
| Índice H dos autores mais produtivos | Impacto individual | Tabela complementar |

---

## 6b. Análises Extras: Semântica de Embeddings (inspirado em Veredas)

A bibliometria clássica mede **onde** e **quanto** se publica. Embeddings semânticos medem **o que** o texto quer dizer.

O pipeline é o mesmo conceito do projeto Veredas: converter textos em vetores de alta dimensão e medir distâncias no espaço semântico. Lá eram versículos bíblicos em 25 traduções; aqui são abstracts de artigos ao longo de 6 anos.

> **Nota sobre as palavras-chave do indicadores.py:** as keywords extraídas do OpenAlex são *inferidas algoritmicamente* pelo sistema, não fornecidas pelos autores. Para o artigo, rotular como "palavras-chave atribuídas algoritmicamente (OpenAlex)" — não "palavras-chave dos autores". Isso é uma limitação metodológica a declarar na seção 3.4.

---

### Análise 0 — Eixos Semânticos (inspirado diretamente no Veredas)

**Quando definir os eixos:** *depois* da Análise 1 (clustering), não antes.

No Veredas os eixos foram pré-definidos porque a teoria de tradução fornecia um prior claro (espectro formal↔dinâmico). Aqui não temos esse prior — definir os eixos antes de ver os dados seria adivinhar. O momento correto é:

1. Rodar o clustering não-supervisionado (Análise 1)
2. Inspecionar os 5 artigos mais próximos do centroide de cada cluster
3. Observar **que dimensões separam os clusters** — essas dimensões viram os eixos
4. Redigir os pares de sentenças-polo com base nos clusters encontrados
5. Validar ortogonalidade e estabilidade

**Construção** (mesmo método do Veredas):
```python
import numpy as np

# Para cada eixo, embed os dois polos e subtraia:
neg_vec = model.encode(polo_negativo)
pos_vec = model.encode(polo_positivo)
axis_vec = (pos_vec - neg_vec)
axis_vec /= np.linalg.norm(axis_vec)  # normalizar

# Projetar cada abstract:
scores = embeddings @ axis_vec  # produto interno = coordenada no eixo
df["axis_nome"] = scores
```

**Validação interna (análogo ao Veredas):**
- Cosseno entre eixos < 0.30 (ortogonalidade)
- Leave-one-out: substituir sentença-polo por paráfrase → Spearman ρ > 0.90 nos rankings

**Visualização:** scatter 2D com eixo X = Eixo 1, eixo Y = Eixo 2, cada ponto um artigo, colorido por ano.

---

### Análise 1 — Clustering Semântico de Abstracts *(pré-requisito para definir os eixos)*

**Modelo:** `BAAI/bge-m3` — multilíngue (100+ idiomas, 1024D). Obrigatório aqui porque o corpus tem papers em árabe, chinês, russo, indonésio, turco etc. `all-MiniLM-L6-v2` é essencialmente inglês e distorceria a geometria para os 151 papers não-ingleses.

```python
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import umap, numpy as np

model = SentenceTransformer("BAAI/bge-m3")
embeddings = model.encode(df["abstract"].tolist(), show_progress_bar=True, batch_size=32)
np.save("embeddings_bgem3.npy", embeddings)  # salvar para reusar nas análises 2 e 3

# Escolher k via silhouette (não arbitrário)
scores = {}
for k in range(3, 10):
    labels_k = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(embeddings)
    scores[k] = silhouette_score(embeddings, labels_k)
k_best = max(scores, key=scores.get)
print("Melhor k:", k_best, "| silhouette:", scores[k_best])

labels = KMeans(n_clusters=k_best, random_state=42, n_init=10).fit_predict(embeddings)
coords = umap.UMAP(n_components=2, random_state=42, metric="cosine").fit_transform(embeddings)
```

**Inspecionar centroides** (este passo informa os eixos da Análise 0):
```python
# 5 papers mais próximos do centroide de cada cluster
for c in range(k_best):
    idx = np.where(labels == c)[0]
    centroid = embeddings[idx].mean(axis=0)
    dists = np.linalg.norm(embeddings[idx] - centroid, axis=1)
    top5 = idx[np.argsort(dists)[:5]]
    print(f"\n--- Cluster {c} ({len(idx)} papers) ---")
    for i in top5:
        print(f"  {df['title'].iloc[i][:80]}")
```

**Visualização:** scatter plot 2D (UMAP, métrica coseno) com clusters coloridos e rótulos manuais definidos após inspeção dos centroides.

---

### Análise 2 — Deriva Semântica Temporal (2020–2026)

**O que faz:** rastreia como o foco temático da literatura muda ao longo do tempo — análogo direto ao `d_centroide` do Veredas, mas sobre anos em vez de traduções.

```python
import numpy as np

# EXCLUIR 2026 do cálculo de deriva (ano parcial — distorceria a curva)
df_drift = df[df["publication_year"] < 2026]
years = sorted(df_drift["publication_year"].unique())
centroids = {y: embeddings[df_drift["publication_year"] == y].mean(axis=0) for y in years}

# Distância L2 de cada centroide anual ao centroide de 2020
drift = {y: float(np.linalg.norm(centroids[y] - centroids[2020])) for y in years}
```

**Visualização:** gráfico de duas séries sobrepostas — barras (volume de publicações) + linha (deriva semântica). A ruptura de 2022→2023 deve ser visível em ambas.

**Cuidado:** interpretar a deriva com cautela — pode ser parcialmente explicada pelo tamanho desigual dos grupos (n=7 em 2020 vs n=256 em 2025). Normalizar pelos tamanhos ou usar bootstrap se o resultado parecer instável.

---

### Análise 3 — Novidade Semântica vs. Impacto por Citações

**O que faz:** mede o quanto cada artigo era "diferente do mainstream" quando publicou, e correlaciona com suas citações.

```python
df["novelty"] = [
    float(np.linalg.norm(embeddings[i] - centroids[int(df["publication_year"].iloc[i])]))
    for i in range(len(df))
]
# Correlação de Spearman (não-paramétrica — citações têm distribuição de cauda pesada)
from scipy.stats import spearmanr
r, p = spearmanr(df["novelty"], df["cited_by_count"])
```

> Se ρ > 0 e p < 0.05: artigos mais originais semanticamente recebem mais citações — argumento para a Introdução. Se ρ ≈ 0: o campo premia reprodução de temas estabelecidos — igualmente interessante, conta história diferente.

---

### Stack adicional necessário

| Biblioteca | Instalação | Uso |
|------------|-----------|-----|
| `sentence-transformers` | `pip install sentence-transformers` | Gerar embeddings (BGE-M3) |
| `umap-learn` | `pip install umap-learn` | Redução 2D para scatter |
| `scikit-learn` | já instalado | KMeans + silhouette |
| `scipy` | já instalado | Spearman correlation |

> **Nota prática:** BGE-M3 em CPU leva ~5–8 min para 588 abstracts. Salvar o array com `np.save("embeddings_bgem3.npy", embeddings)` logo após rodar — as análises 0, 2 e 3 carregam com `np.load` sem precisar rodar o modelo de novo.
> 
> **Ordem de execução:** Análise 1 (clustering + inspeção) → definir eixos → Análise 0 (projeção nos eixos) → Análises 2 e 3.

---

## 7. Estrutura do Artigo (7–10 páginas)

```
Capa
Resumo (PT) + Abstract (EN)            ~0,3 pg
Palavras-chave

1. Introdução                          ~1,0 pg
   1.1 Contexto e motivação
   1.2 Objetivo do estudo
   1.3 Organização do artigo

2. Referencial Teórico                 ~1,5 pg
   2.1 Bibliometria: conceito e leis
       - Lei de Lotka (produtividade de autores)
       - Lei de Bradford (dispersão em periódicos)
       - Lei de Zipf (frequência de termos)
   2.2 IA na Produção Acadêmica

3. Metodologia                         ~1,0 pg
   3.1 Protocolo de busca
   3.2 Bases de dados e período
   3.3 Critérios de inclusão/exclusão
   3.4 Ferramentas de análise

4. Resultados e Discussão              ~3,5 pg
   4.1 Visão Geral do Corpus
       - Total de registros encontrados vs. incluídos
       - Tabela resumo do corpus ← TABELA #1
   4.2 Evolução Temporal das Publicações
       - Gráfico de linha (2020–2026)
   4.3 Distribuição Geográfica
       - Mapa coropletro por país ← MAPA #1
       - Gráfico de barras: Top 10 países ← GRÁFICO DE BARRAS #1
   4.4 Principais Periódicos e Autores
       - Gráfico de barras horizontal: top 10 journals
   4.5 Artigos de Alto Impacto
       - Tabela: top 20 por citações (título, autores, ano, citações, DOI) ← TABELA #2
   4.6 Análise Semântica do Corpus (extras)
       - Scatter UMAP com clusters temáticos
       - Deriva semântica temporal (2020–2026)
       - Novidade semântica × citações
   4.7 Análise Temática (Keywords)
       - Rede de co-ocorrência (networkx + pyvis) ← BÔNUS

5. Conclusão                           ~0,5 pg

Referências (ABNT)
```

---

## 8. Boas Práticas de Visualização

Direto do que o professor ensinou na Aula 5 ao revisar os dashboards:

### O que FAZER
- **Atributos pré-atentivos:** use cor, tamanho ou forma para direcionar o olhar para o ponto central de cada gráfico (ex.: barra do país líder em cor destaque)
- **Paleta de no máximo 3 cores** com identidade coerente no artigo inteiro
- **Eixo Y começa em zero** sempre — "a gente não faz isso, né" (escala truncada é desonesta)
- **Títulos grandes e descritivos** em cada gráfico ("Distribuição de publicações por país — 2020–2026", não "Gráfico 1")
- **Mapa em área generosa** — o professor disse: "tira o mapa de um canto pequeno, joga numa página ou área grande, deixa ele grandão"
- Rótulos legíveis; evite usar só legenda quando um rótulo direto na barra é possível

### O que EVITAR
- Gráfico de pizza com muitas fatias — "se tem muitas variáveis, fica espremido e é horrível"
- Gráfico de barras empilhadas com 5+ categorias de cor — "gera mais confusão do que ajuda"
- Excesso de informação em uma única visualização — "não adianta querer colocar tudo"
- Fundo escuro que conflita com elementos do gráfico

---

## 9. Cronograma (13 dias)

| Dias | Datas | Tarefa | Responsável |
|------|-------|--------|-------------|
| **D1–2** | 09–10 abr | Equação de busca definida; corpus coletado via OpenAlex API (`fetch_corpus.py`); 603 papers após exclusão off-topic e sem abstract; `corpus.csv` gerado | ✅ |
| **D3** | 09 abr | `clean_corpus.py`: dedup (7 títulos), exclusão por tópico off-topic (7 papers inspecionados manualmente); DOAJ audit; `corpus_clean.csv` com **589 papers** | ✅ |
| **D4–5** | 09 abr | `indicators.py`: 9 indicadores gerados em `indicators/` — produção anual, 78 países, 453 periódicos (Bradford), 1532 autores (Lotka), top 20 citados, 143 pares de co-ocorrência de keywords, 171 pares de co-autoria entre países | ✅ |
| **D5b** | 13 abr | Gerar embeddings dos abstracts (`sentence-transformers`); clustering UMAP; deriva temporal; novidade × citações | — |
| **D6–7** | 14–15 abr | Gerar e refinar todas as visualizações (`seaborn`, `plotly`, `networkx`) | — |
| **D8–10** | 16–18 abr | Redigir seções 1, 2, 3 e 4 do artigo | — |
| **D11** | 19 abr | Redigir Conclusão, Resumo e Abstract; exportar referências do Zotero → ABNT | — |
| **D12** | 20 abr | Revisão geral; ajustes de layout; verificar se todas as 3 visualizações obrigatórias estão OK | — |
| **D13** | 21–22 abr | Exportar PDF final; renomear `<nome>_trabalho5.pdf`; enviar via Teams antes das 19:00 | — |

> **Buffer:** os dias 21–22 são colchão para imprevistos. Não deixe para o dia 22.

---

## 10. Recomendações Finais

1. **Escolha um nicho claro dentro do tema.** Em vez de "toda IA acadêmica", foque em, por exemplo, ferramentas de IA para *escrita e revisão* ou IA para *busca e síntese de literatura*. Nicho menor → corpus mais manejável (~100–300 artigos) → análise mais profunda.

2. **Menos artigos, mais qualidade de análise.** Se a busca retornar 2 000+ registros, adicione um critério de refinamento (ex.: só periódicos Q1/Q2 no Scopus). O professor quer **qualidade de discussão**, não volume.

3. **Comente os gráficos no texto.** Cada figura deve ter pelo menos um parágrafo de interpretação: "O gráfico X revela que os EUA concentram 34% das publicações, seguidos pela China (18%), o que indica..."

4. **Seja consistente com a numeração e referenciação** das figuras e tabelas ao longo do artigo.

5. **Se for dupla:** a divisão sugerida é — uma pessoa lidera a coleta/análise de dados e geração de gráficos (tarefas D1–D7); a outra lidera a redação (D8–D11); as duas revisam juntas (D12–D13).

---

*Referência de conteúdo: slides "Treinamento\_Bibliometria e Cientometria — Profa. Dra. Ediane Maria Gheno" e Aula 5 TI (TI\_L5). Boas práticas de visualização conforme feedback do professor na revisão dos dashboards (TI\_L5, 00:00–00:55).*
