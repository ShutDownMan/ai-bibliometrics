# Plano do artigo completo — Latin.Science 2026

## Decisão editorial

**Modalidade:** Full Paper (6–10 páginas)  
**Prazo de submissão:** 14 de agosto de 2026  
**Idioma de redação:** inglês  
**Princípio:** o artigo não é uma apresentação do pipeline inteiro. É um estudo
bibliométrico reproduzível, com uma análise semântica dirigida por teoria e
validada por avaliação humana.

## Proposta do artigo

### Título de trabalho

**From Named Models to Institutional Guardrails: A Validated Semantic
Bibliometric Map of Generative AI in Scholarly Communication, 2020–2026**

Alternativa mais conservadora:

**Mapping Generative AI in Scholarly Communication: A Reproducible
Bibliometric Study with Human-Validated Semantic Dimensions**

### Problema

O crescimento da literatura sobre IA generativa tornou difícil distinguir
trabalhos que tratam a IA como ferramenta para tarefas de comunicação
científica daqueles que a discutem como problema de integridade, autoria,
política e governança. Indicadores bibliométricos descrevem volume e impacto,
mas não capturam bem essa diferença de enquadramento.

### Objetivo

Mapear a produção científica sobre IA/IA generativa em comunicação científica
e ensino superior entre 2020 e 2026 e medir, com dimensões semânticas
interpretáveis e validadas por humanos, a mudança do campo entre:

1. IA genérica → IA generativa/modelos nomeados; e
2. apoio ao fluxo de trabalho → governança, integridade e salvaguardas.

### Contribuições que o artigo deve entregar

1. Um corpus multilíngue, deduplicado, versionado e estritamente definido para
   comunicação científica e ensino superior — não um corpus geral de IA.
2. Um mapa bibliométrico reprodutível: produção anual, fontes, países,
   coocorrência de termos e impacto descritivo.
3. Duas escalas semânticas contínuas, calculadas com embeddings e protótipos
   escritos antes da análise de resultados.
4. Validação humana cega dessas escalas por rubricas Likert e medida de
   concordância entre avaliadores.
5. Uma análise temporal e de associação que responda hipóteses explícitas, sem
   inferir causalidade a partir de citações.

## Escopo: decisão irreversível antes das análises

### População de interesse

Artigos e revisões publicados entre 2020 e a data de corte do estudo, cujo
título e resumo discutam IA aplicada a pelo menos um dos seguintes contextos:

- comunicação científica, publicação acadêmica ou autoria;
- redação de manuscritos, revisão editorial ou revisão por pares;
- busca bibliográfica, triagem ou síntese de evidências como **atividade de
  pesquisa**, não como aplicação clínica de IA;
- integridade acadêmica/científica, detecção de texto gerado por IA, autoria,
  disclosure e política editorial;
- uso institucional de IA generativa no ensino superior quando ligado a escrita
  acadêmica, avaliação, literacia em IA ou integridade.

### Exclusões

Excluir antes de qualquer análise semântica:

- IA aplicada a diagnóstico, imagem médica, cuidado clínico ou predição de
  desfechos, salvo se a unidade de análise for comunicação/publicação científica;
- engenharia, indústria, agricultura e outros domínios em que “review” ou
  “paper” apareça apenas como método ou artefato periférico;
- ensino de língua/EFL e pedagogia escolar sem relação substantiva com escrita
  acadêmica, integridade ou ensino superior;
- registros sem título/resumo suficiente, duplicados, retratações e publicações
  fora do período.

### Regra operacional de inclusão

Criar uma tabela versionada, `screening_decisions.csv`, com `id`, título,
fonte, decisão, motivo e responsável pela decisão. Usar regras lexicais para
priorizar a triagem, nunca como substituto silencioso da decisão de escopo.

Fazer auditoria humana cega de uma amostra aleatória de incluídos e excluídos
(mínimo 50 de cada grupo). Se a precisão da inclusão for menor que 90% ou houver
erros repetidos de uma categoria, corrigir a regra e repetir a auditoria.

### Data freeze e proveniência

Congelar um diretório de execução específico para o artigo, incluindo:

- data/hora e expressão completa de cada consulta;
- fontes consultadas e número de registros por fonte;
- exportações brutas ou identificadores que permitam recuperá-las;
- regra de deduplicação e todos os motivos de exclusão;
- versão do código, ambiente Python e modelo `BAAI/bge-m3`;
- data de coleta das citações.

O fluxograma deve mostrar identificação, deduplicação, exclusões por escopo,
exclusões por ausência de resumo e corpus final. Relatar a automação de forma
transparente, seguindo PRISMA-ScR/PRISMA-S como guia de reporte; não chamar o
trabalho de revisão sistemática se não houver protocolo e triagem compatíveis.

## Perguntas e hipóteses

### RQ1 — Crescimento e composição

Como evoluiu, entre 2020 e 2026, a produção sobre IA em comunicação científica
e ensino superior?

**H1.** A participação de textos sobre IA generativa/modelos nomeados aumenta
substancialmente a partir de 2023.

### RQ2 — Enquadramento substantivo

Como se distribuem os trabalhos entre apoio a fluxos de trabalho e
governança/integridade?

**H2.** A pontuação de governança/integridade aumenta após 2023, acompanhando a
difusão pública de ChatGPT e de políticas institucionais.

### RQ3 — Relação entre tecnologia e enquadramento

Os artigos sobre modelos nomeados tendem a enfatizar mais a governança do que
os artigos sobre IA genérica?

**H3.** A especificidade a modelos nomeados tem associação positiva com a
dimensão governança/integridade, após controle por ano.

### RQ4 — Impacto, apenas como análise secundária

Há associação entre enquadramento e citações?

**H4 exploratória.** Trabalhos de governança/integridade recebem mais citações
do que trabalhos focados em fluxo de trabalho, condicionado ao ano de
publicação. Não formular uma hipótese causal.

## Análise semântica: desenho defensável

### Dimensões finais

Manter somente duas dimensões, definidas antes de olhar os resultados:

| Código | Polo 1 | Polo 5 | Uso no artigo |
|---|---|---|---|
| T — especificidade tecnológica | IA genérica / não nomeada | ChatGPT, GPT-4, Claude ou outro modelo/GenAI nomeado | mede a mudança tecnológica |
| G — orientação do trabalho | apoio a busca, escrita, revisão e síntese | integridade, autoria, disclosure, detecção, políticas e salvaguardas | mede o enquadramento substantivo |

Não usar no argumento principal os eixos atuais de domínio clínico nem de
oportunidade versus risco. O primeiro desaparece com o recorte correto; o
segundo se sobrepõe conceitualmente a G e teve estabilidade marginal.

### Cálculo automatizado

1. Codificar título + resumo com BGE-M3, com embeddings normalizados.
2. Para cada dimensão, definir conjuntos equilibrados de 4–6 protótipos por
   polo, todos documentados no apêndice.
3. Calcular o vetor de direção entre os centróides dos polos e centralizar o
   escore no ponto médio.
4. Padronizar o escore somente para apresentação (`z`), preservando também o
   valor bruto reprodutível.
5. Executar análise de sensibilidade leave-one-prototype-out e reportar a
   correlação de Spearman entre as ordenações. Meta: mínimo >= .80; abaixo disso
   o eixo deve ser revisado ou retirado.

### Rubrica humana Likert

Criar um formulário com título e resumo, sem score de IA, cluster, citações ou
ano visível. Cada avaliador responde duas escalas de 1–5:

**T — especificidade tecnológica**

1. IA/ML genérica, nenhum sistema/modelo generativo nomeado é central.  
2. GenAI/LLM aparece genericamente, sem modelo nomeado como objeto central.  
3. Caso misto ou menção incidental a produto/modelo.  
4. Um modelo/família nomeada é importante para o estudo.  
5. O estudo avalia, compara ou discute centralmente um ou mais modelos nomeados.

**G — orientação do trabalho**

1. Centralmente apoio a tarefas de pesquisa/escrita/revisão/síntese.  
2. Predominantemente apoio ao fluxo de trabalho, com menção secundária a regras.  
3. Equilíbrio ou foco indeterminado.  
4. Predominantemente integridade, autoria, disclosure, política ou salvaguardas.  
5. Centralmente governança/integridade/política; apoio à tarefa é secundário.

Incluir a opção `insufficient information`, analisada como dado ausente, não
forçada para o ponto médio.

### Amostragem de validação

- **Mínimo viável:** 200 artigos; **alvo:** 300.
- Seleção estratificada por ano (2020–22, 2023, 2024, 2025–26), fonte e
  quintil de cada score para não validar apenas casos fáceis.
- Os dois eixos podem ser avaliados na mesma amostra.
- Dois avaliadores independentes; se houver terceiro avaliador, usar apenas
  para desempate, preservando os dois julgamentos originais.
- Preparar uma rodada-piloto de 20 textos para esclarecer a rubrica. Não misturar
  o piloto com a amostra confirmatória sem reportá-lo.

### Critérios de validação

Reportar, com IC bootstrap de 95%:

- Krippendorff's alpha ordinal (preferencial) ou kappa ponderado entre avaliadores;
- correlação de Spearman entre score automático e média humana;
- erro absoluto médio após reescalar o score automático para 1–5;
- AUC para a classificação binária pré-definida (`1–2` versus `4–5`), excluindo
  o ponto 3 nessa análise;
- matriz/figura de calibração: média humana por quintil do score automático.

**Regra de decisão:** se a concordância humana for fraca ou a correlação for
baixa, o artigo reporta o resultado como limitação e reduz o peso inferencial do
eixo; não se ajusta a rubrica ou os protótipos repetidamente para maximizar o
resultado na mesma amostra. Se for necessário refinar os protótipos, separar um
conjunto de desenvolvimento e um holdout final.

## Plano estatístico

### Descritivos obrigatórios

- fluxograma de seleção e tabela de cobertura por fonte;
- produção anual e crescimento relativo;
- top fontes/periódicos, países e termos normalizados;
- distribuição dos dois scores por ano;
- 5 casos de cada extremo de cada dimensão, inspecionados manualmente.

### Testes principais

- **H1/H2:** regressão linear robusta dos scores por ano, e comparação de
  coortes pré-2023 versus 2023+; mostrar efeito e IC, não só valor-p.
- **H3:** regressão de G sobre T e ano; reportar coeficiente padronizado, IC e
  diagnóstico de colinearidade.
- **H4 exploratória:** modelo binomial negativo para citações, com `log(idade
  em meses)` como offset/exposição e, no mínimo, ano, fonte/base e T/G como
  covariáveis. Se o ajuste não for estável, limitar a análise a percentis de
  citação dentro de coorte anual e declarar a simplificação.

Não usar significância estatística como prova de validade semântica. Não
interpretar associação com citação como qualidade, utilidade ou causalidade.

### Clusters e redes

Clusters só entram como visualização auxiliar caso a qualidade seja aceitável.
Com silhouette próximo de .058, não apresentar os cinco clusters como “tópicos
descobertos” nem basear hipóteses neles. Para o artigo curto em espaço, priorizar
as duas dimensões validadas e rede de coocorrência de termos, se limpa e legível.

## Estrutura das 6–10 páginas

| Seção | Conteúdo | Orçamento |
|---|---|---:|
| Introdução | lacuna, objetivo, contribuições e hipóteses | 0,9 página |
| Trabalhos relacionados | bibliometria de GenAI + embeddings como medida, sem revisão enciclopédica | 0,8 |
| Método | fontes, critérios, seleção, embeddings, rubrica e plano estatístico | 2,1 |
| Resultados | corpus, validação humana, H1–H4 e figuras essenciais | 2,5 |
| Discussão | interpretação, implicações para ciência aberta/políticas, limites | 1,1 |
| Conclusão | resposta concisa às RQs e próximos passos | 0,4 |
| Referências / apêndice permitido | conforme template | — |

## Figuras e tabelas: pacote mínimo

1. **Figura 1:** fluxograma de seleção do corpus.
2. **Figura 2:** produção anual e distribuição dos dois eixos por coorte.
3. **Figura 3:** validação humana — score automático versus média Likert,
   separada para T e G, com IC/linha de tendência.
4. **Tabela 1:** fontes, período, critérios, tamanho final e cobertura de
   metadados.
5. **Tabela 2:** resultado de validação (IAA, Spearman, AUC, n).
6. **Tabela 3:** resultados das hipóteses (efeito, IC, p, interpretação).

Qualquer figura que não responda uma RQ ou demonstre validade metodológica sai.

## Roteiro de execução da semana

### Dia 1 — Protocolo e corpus

- [ ] Fixar título, pergunta, hipóteses e critérios deste documento.
- [ ] Criar run dedicado, congelar consultas/datas e gerar `screening_decisions.csv`.
- [ ] Aplicar recorte; revisar amostra de incluídos/excluídos; publicar contagens.
- [ ] Confirmar que não restaram clusters clínicos, industriais ou EFL como tema
  dominante.

### Dia 2 — Eixos antes dos resultados

- [ ] Implementar somente T e G, com protótipos em arquivo versionado.
- [ ] Produzir relatório de estabilidade e auditoria dos extremos.
- [ ] Sortear a amostra estratificada de validação e gerar formulário cego.
- [ ] Fazer piloto de 20 textos e congelar a rubrica.

### Dia 3 — Validação e análises

- [ ] Coletar duas avaliações independentes para 200–300 textos.
- [ ] Calcular IAA, validade convergente e calibração.
- [ ] Executar testes H1–H4 e análises de sensibilidade.
- [ ] Decidir, com base nos critérios, quais eixos/achados permanecem.

### Dia 4 — Primeira versão completa

- [ ] Escrever Método e Resultados primeiro, diretamente a partir das tabelas.
- [ ] Escrever Introdução com as hipóteses já fixadas.
- [ ] Gerar as seis peças visuais e inserir somente números reproduzíveis.

### Dia 5 — Revisão científica

- [ ] Conferir cada número contra o run congelado.
- [ ] Remover qualquer formulação causal ou generalização além do corpus.
- [ ] Revisar coerência entre título, escopo, RQs, método, resultados e conclusão.
- [ ] Garantir anonimização completa para blind review.

### Dia 6 — Formatação e submissão

- [ ] Ajustar ao template Latin.Science e limites de página.
- [ ] Compilar PDF e checar figuras, referências, tabelas e metadados do PDF.
- [ ] Fazer uma leitura de revisor: contribuição clara nos primeiros parágrafos,
  método replicável, achados não exagerados.
- [ ] Submeter com margem antes do hard deadline.

## Checklist de “pronto para submeter”

- [ ] O título e o corpus falam da mesma população.
- [ ] Critérios de inclusão/exclusão e consultas estão no artigo ou suplemento.
- [ ] Cada dimensão semântica tem definição, protótipos e evidência de validação.
- [ ] Há dois avaliadores, rubrica cega e IAA reportada.
- [ ] Todo resultado substantivo responde uma RQ/H; todo valor vem do run congelado.
- [ ] Citações são tratadas como medida temporalmente e disciplinarmente confundida.
- [ ] Clustering não é usado para alegar estrutura robusta sem qualidade suficiente.
- [ ] Código, configurações e dados permitidos para compartilhamento estão organizados
  para disponibilização após a revisão cega.
- [ ] O PDF não revela autores, afiliação, repositório identificável ou caminhos locais.

## Linguagem a usar e a evitar

Usar: “embedding-derived score”, “theory-guided prototype axis”, “human-validated
semantic dimension”, “association”, “within this corpus”, “exploratory”.

Evitar: “the embedding discovered”, “objective semantic truth”, “proved that”,
“caused citations”, “systematic review” (salvo se o protocolo realmente cumprir
essa modalidade), “topic cluster” para agrupamentos de baixa separação.

## Critério de sucesso

O artigo será bom se um revisor puder reproduzir a seleção, entender cada score,
ver que ele corresponde razoavelmente a julgamento humano independente e aceitar
que as conclusões respondem a uma pergunta pequena, clara e honesta. Um corpus
menor e coerente, com validação real, é mais publicável do que milhares de
registros heterogêneos com análises impressionantes mas desalinhadas.
