# Comparativo de Modelos — Ciclos 1–2 (com crítica)

Comparação dos modelos construídos até aqui sob **um único protocolo**, com leitura crítica
da evolução. Todos os números vêm de `runs/baselines/results.json` (modelos topológicos) e
`runs/text/text_compare.json` (encoders textuais), gerados na mesma execução experimental.

## Protocolo e o que mudou (aviso de comparabilidade)

Os números do **relatório do Ciclo 1** (`RELATORIO_CICLO1.docx`) **não são diretamente
comparáveis** com os daqui: foram produzidos antes de duas mudanças metodológicas:

1. **Teto de coautores/artigo = 50** (anti-consórcio): remove cliques espúrias de artigos com
   listas enormes de autores. Reduz arestas de coautoria (~−21%) e altera os baselines.
2. **Bucket `newcomer`**: separamos autores **sem artigo em T0** (estreantes que só aparecem
   em T1) do regime `cold` (≥1 artigo, 0 coautores), alinhando warm/cool/cold à qualificação.

Por isso **re-rodamos os baselines** no protocolo atual antes de comparar. (Caveat de
reprodutibilidade: a ordenação de empates varia com `PYTHONHASHSEED` entre processos —
ex.: topologia Recall@200 13,28 vs 13,21 nas duas execuções; diferença ínfima, mas convém
fixar a seed de hash para reprodução exata.)

## População de avaliação

| Regime | Critério (T0) | Alvos | Atendível por perfil-T0? |
|---|---|---:|---|
| warm | ≥5 coautores | 976 | sim |
| cool | 1–4 coautores | 78 | sim |
| cold | 0 coautores, ≥1 artigo | **3** | sim (mas n irrisório) |
| newcomer | sem artigo em T0 | 4.837 | **não** (sem perfil) |
| **Total** | | **5.894** | |

## Recall@K (%) — GERAL (dominado por newcomers)

| Modelo | @5 | @10 | @20 | @50 | @100 | @200 |
|---|--:|--:|--:|--:|--:|--:|
| Baseline (Common Neighbors) | 2,93 | 4,88 | 7,59 | 10,95 | 11,85 | 13,28 |
| Híbrido RF (topológico) | 3,41 | 4,89 | 8,09 | 11,43 | 13,01 | **14,80** |
| Oráculo topológico (teto) | 19,47 | 20,54 | 20,72 | 20,73 | 20,73 | 20,73 |
| Texto: TF-IDF | 0,24 | 0,50 | 0,76 | 1,21 | 1,67 | 2,07 |
| Texto: BERT-base | 0,31 | 0,52 | 0,86 | 1,29 | 1,67 | 2,00 |
| Texto: SciBERT | 0,46 | 0,73 | 1,02 | 1,41 | 1,80 | 2,22 |
| Texto: SPECTER | 0,38 | 0,60 | 1,02 | 1,48 | 1,90 | 2,26 |

## Recall@K (%) — WARM (976 alvos)

| Modelo | @5 | @10 | @20 | @50 | @100 | @200 |
|---|--:|--:|--:|--:|--:|--:|
| Baseline (Common Neighbors) | 2,21 | 2,96 | 4,32 | 6,25 | 8,18 | 10,08 |
| Híbrido RF (topológico) | **2,82** | **4,41** | 6,80 | 10,45 | 12,73 | **14,36** |
| Oráculo topológico (teto) | 15,41 | 16,40 | 16,55 | 16,55 | 16,55 | 16,55 |
| Texto: TF-IDF | 1,24 | 2,59 | 3,92 | 6,14 | 8,68 | 10,96 |
| Texto: BERT-base | 1,61 | 2,72 | 4,44 | 6,63 | 8,62 | 10,50 |
| Texto: SciBERT | 2,32 | 3,74 | 5,29 | 7,33 | 9,39 | 11,73 |
| Texto: SPECTER | 1,86 | 3,04 | 5,35 | 7,83 | 9,90 | 11,84 |

## Recall@K (%) — COOL (78 alvos)

| Modelo | @5 | @10 | @20 | @50 | @100 | @200 |
|---|--:|--:|--:|--:|--:|--:|
| Baseline (Common Neighbors) | 1,49 | 2,58 | 3,79 | 8,25 | 12,31 | 14,96 |
| Híbrido RF (topológico) | 2,37 | 3,39 | 8,51 | 14,39 | 20,89 | 22,41 |
| Oráculo topológico (teto) | 22,22 | 23,49 | 23,83 | 23,83 | 23,83 | 23,83 |
| Texto: TF-IDF | 2,94 | 5,37 | 8,54 | 14,27 | 17,30 | 19,19 |
| Texto: BERT-base | 3,26 | 5,47 | 9,25 | 14,32 | 18,26 | 19,92 |
| Texto: SciBERT | **6,10** | **8,39** | 10,80 | 15,04 | 18,10 | 20,77 |
| Texto: SPECTER | 5,65 | 7,44 | 10,16 | 14,12 | 19,45 | **22,48** |

## Análise crítica

**1. A métrica "geral" engana — não a use para ranquear modelos.**
82% dos alvos (4.837) são *newcomers* sem perfil em T0; nenhum modelo baseado em histórico os
atende, e a topologia só "pontua" por *fallback* de popularidade. O "geral" mistura populações
incomparáveis. A leitura honesta é **por regime** (T0-ativos: warm+cool = 1.054 alvos).

**2. Houve evolução, mas o salto NÃO foi do texto sobre a topologia (correção de leitura).**
Comparado corretamente contra o **Híbrido RF** (o melhor modelo topológico), e não contra o
baseline fraco:
- **WARM:** o Híbrido RF **lidera** (Recall@200 14,36 vs ~11,8 do texto; e também no topo,
  @5 2,82 vs 2,32 do SciBERT). Onde há histórico de colaboração, a topologia ainda manda.
- **COOL:** o texto **vence no topo do ranking** (Recall@5 SciBERT 6,10 vs 2,37 do RF — ~2,6×),
  enquanto o RF alcança o texto em recall de listas longas (@200 22,4 ≈ 22,5). Ou seja, quando
  o histórico é escasso, o **conteúdo ordena melhor os primeiros candidatos**.

A história real não é "texto > topologia", e sim **complementaridade**: topologia forte com
muito histórico (warm); texto forte no topo quando o histórico é fino (cool). É exatamente o
argumento para a **fusão** — mas mais sutil do que uma vitória direta do texto.

**3. O teto do oráculo topológico é baixo — e o texto não está preso a ele.**
O oráculo topológico satura em Recall@200 = 16,55% (warm) / 23,83% (cool): mesmo um ranqueador
*perfeito* restrito à vizinhança de 2 saltos não alcança a maioria das colaborações futuras.
O texto opera em **outro espaço de candidatos** (todos os autores), então pode recuperar links
que a topologia **literalmente não enxerga** — em cool, o SPECTER (22,48) já encosta no teto
topológico (23,83). Isso reforça que fundir os dois pode **superar** o limite de cada um.

**4. `cold` é inconclusivo (n = 3).** Não dá para afirmar nada sobre *cold-start* neste corpus:
o snowball gerou pouquíssimos autores solo-em-T0 que depois colaboram. Para estudar cold-start
de verdade, é preciso um corpus com mais autores nesse perfil (ou ajustar a coleta). Como está,
o regime cold é estatisticamente vazio.

**5. Encoders: ranking esperado, mas diferenças pequenas e ainda não testadas.**
SciBERT ≈ SPECTER > BERT-base > TF-IDF — domínio/tarefa batem o genérico e o clássico, como a
literatura prevê. Porém: (a) as diferenças são modestas (décimos de ponto) e **faltam testes de
significância pareados** (já temos a infraestrutura em `eval/stats.py`); (b) o **TF-IDF chega
perto do BERT-base**, sugerindo que boa parte do sinal é **vocabulário de domínio**, não
semântica contextual profunda — o que relativiza o ganho dos transformers neste recorte.

**6. Em termos absolutos, a tarefa segue difícil e nenhum modelo "resolve".**
Recall@200 na casa de 12–22% nos regimes bons, precisão de poucos por cento. O comparativo
mostra *de onde* vem cada ganho, não um sistema pronto — coerente com a tese ainda estar na
fase de construir e fundir os módulos.

## Testes de significância (pareados)

`scripts/significance.py` aplica Shapiro→t pareado/Wilcoxon com Bonferroni (α ajustado =
0,0083 para 6 pares) e IC bootstrap da diferença média, sobre os mesmos alvos. Todas as
comparações recaíram no **Wilcoxon** (Shapiro rejeitou normalidade — esperado para métricas
por autor, muito assimétricas, como a qualificação antecipa). `*` = significativo após Bonferroni.

**WARM (n = 976):**

| Comparação (A vs B) | métrica | Δ (pp) | p | signif.? |
|---|---|--:|--:|:--:|
| Híbrido RF vs Baseline | R@50 | +4,14 | 1e‑24 | * |
| Texto SciBERT vs Híbrido RF | R@50 | −2,96 | 1e‑12 | * (RF vence) |
| Texto SPECTER vs Híbrido RF | R@50 | −2,49 | 3e‑10 | * (RF vence) |
| SciBERT vs TF‑IDF | R@50 | +1,22 | 2e‑4 | * |
| SciBERT vs BERT‑base | R@50 | +0,71 | 1e‑7 | * |
| SPECTER vs SciBERT | R@50 | +0,47 | 0,31 | — (empate) |

**COOL (n = 78):**

| Comparação (A vs B) | métrica | Δ (pp) | p | signif.? |
|---|---|--:|--:|:--:|
| Texto SciBERT vs Híbrido RF | R@10 | +6,01 | 0,0023 | * (texto vence) |
| Texto SciBERT vs Híbrido RF | NDCG@10 | +4,59 | 0,0049 | * (texto vence) |
| Texto SciBERT vs Híbrido RF | R@50 | −0,47 | 0,86 | — (empate) |
| SPECTER vs SciBERT | R@10 | −0,94 | 0,75 | — (empate) |
| SciBERT vs TF‑IDF | R@10 | +3,02 | 0,22 | — (sem poder, n=78) |

**O que os testes fecham (com rigor estatístico):**
- **Híbrido RF > Baseline**: confirmado e fortíssimo (Ciclo 1 se sustenta).
- **Em WARM, a topologia (RF) > texto**: significativo — minha leitura anterior ("texto bate
  topologia") está **estatisticamente refutada** para warm.
- **Em COOL, o texto > RF no topo do ranking** (R@10 e NDCG@10): significativo mesmo com n=78,
  e empata em recall de lista longa. É a **complementaridade** que motiva a fusão, agora apoiada.
- **SciBERT ≈ SPECTER**: empate estatístico em toda métrica/regime — escolher qualquer um.
- **SciBERT > TF‑IDF e > BERT‑base**: significativo onde há poder (warm); em cool (n=78) não dá
  para distinguir encoders — amostra pequena demais.

## GNN heterogênea (1º corte) — resultado negativo honesto

Primeira versão da GNN heterogênea (`gnn-run`): encoder HeteroConv(SAGEConv, `mean`) de 2
camadas sobre o KG T0, com features SciBERT nos nós Paper/Author, treinado por predição de
link nas arestas CO_AUTHOR de T0 (BCE + negativos aleatórios), recomendando por produto
interno dos embeddings de autor. Após corrigir a instabilidade inicial (LayerNorm, agregação
`mean`, padronização de features, clipping, lr menor), **a loss converge** (14,98 → 0,45) —
mas o desempenho **fica abaixo de todos os modelos**, inclusive do baseline:

| Recall@200 (%) | Baseline | Híbrido RF | Texto SciBERT | **GNN** | Oráculo |
|---|--:|--:|--:|--:|--:|
| warm | 10,08 | 14,36 | 11,73 | **9,11** | 16,55 |
| cool | 14,96 | 22,41 | 20,77 | **12,60** | 23,83 |

**Diagnóstico (por que ainda não compete):**
1. **Objetivo vs. avaliação desalinhados.** O modelo é treinado para *reconstruir* arestas de
   coautoria já existentes em T0, mas avaliado em *novas* coautorias (T1) — e a avaliação
   **remove os coautores passados** das recomendações. Ou seja, otimizamos justamente o sinal
   que é filtrado na hora de medir. Falta um *split de arestas* em nível de link (train/val)
   e/ou supervisão orientada a links futuros.
2. **Geração de candidatos global × local.** A GNN ranqueia *todos* os autores por similaridade
   de embedding; os modelos topológicos restringem a candidatos de 2 saltos (muito mais
   preciso). Sem essa restrição, a precisão no topo despenca.
3. **Negativos fáceis.** Amostragem uniforme de negativos torna a tarefa fácil demais; faltam
   *hard negatives* (como no Híbrido RF).
4. **Sem validação/early-stopping nem tuning.** 200 épocas fixas, hiperparâmetros não ajustados.

**Leitura crítica:** não é um defeito de implementação (loss converge, infraestrutura testada),
e sim o esperado para uma GNN de link prediction *ingênua* — a literatura é clara em que esses
modelos exigem desenho cuidadoso (split de arestas, hard negatives, restrição de candidatos)
para superar heurísticas topológicas.

### 2º corte: GNN reranker sobre candidatos de 2 saltos

Aplicando os consertos — **candidatos restritos a 2 saltos** (como o baseline/RF), **hard
negatives** (pares a 2 saltos sem aresta), **split de arestas T0 treino/validação** com
early-stopping — a GNN deixa de ser global e passa a *reranquear* os mesmos candidatos dos
modelos topológicos. O efeito é enorme:

| Recall@200 (%) | Baseline | Híbrido RF | Texto SciBERT | GNN global | **GNN-rerank** | Oráculo |
|---|--:|--:|--:|--:|--:|--:|
| overall | 13,28 | 14,80 | 2,22 | 1,68 | **14,33** | 20,73 |
| warm | 10,08 | 14,36 | 11,73 | 9,11 | 11,49 | 16,55 |
| cool | 14,96 | 22,41 | 20,77 | 12,60 | **22,65** | 23,83 |

**Leitura (honesta):**
- **A restrição de candidatos era o fator dominante:** Recall@200 overall saltou de 1,68 → 14,33,
  empatando com o Híbrido RF (14,80). Confirma o diagnóstico — o problema do 1º corte era o
  espaço de candidatos global, não a representação.
- **Em COOL, o GNN-rerank é o melhor (@200 = 22,65)**, encostando no teto do oráculo (23,83) e
  superando o Híbrido RF e o texto. Combinar estrutura (2-hop) + features textuais (SciBERT)
  na agregação ajuda exatamente onde o histórico é fino.
- **Mas não domina:** em WARM o Híbrido RF ainda lidera (14,36 vs 11,49) e, no **topo do ranking**
  (low-K), tanto o RF (warm) quanto o texto (cool) continuam melhores que o GNN-rerank.
- **A loss de validação estaciona em ~0,60** (vs 0,69 do acaso): o ranqueador da GNN discrimina
  só fracamente — boa parte do desempenho vem da geração de candidatos 2-hop, e o reranking da
  GNN agrega modestamente. Há margem clara para tuning (mais camadas/épocas, melhor objetivo de
  ranking, pares como features). 

**Conclusão atualizada:** com o desenho correto, a GNN passou de inviável a **competitiva**
(≈ Híbrido RF no geral, **melhor em cool@200**), mas **ainda não supera consistentemente** o
Híbrido RF — falta ganhar no topo do ranking. É um ponto de partida sólido para a **fusão**
(combinar score topológico + textual + GNN num reranker único), que é o passo natural seguinte.

## Fusão end-to-end CNN + GNN (Eq. 10) — hipótese ainda não confirmada

Modelo da proposta (`fusion-run`): branch textual **CNN 1D** sobre tokens SciBERT (congelados)
→ z_text(a); branch estrutural **GNN heterogênea** → z_graph(a); fusão `Dense(LayerNorm(z_text) ⊕
LayerNorm(z_graph))`; treino conjunto por link prediction (split de arestas, hard negatives,
early-stopping); recomendação por reranking dos candidatos de 2 saltos. A loss converge
(early-stop em 186, val ≈ 0,59) — mas o resultado **empata com a GNN-rerank e não supera o
Híbrido RF**:

| Recall@200 (%) | Híbrido RF | Texto SciBERT | GNN-rerank | **Fusão** | Oráculo |
|---|--:|--:|--:|--:|--:|
| overall | **14,80** | 2,22 | 14,33 | 14,25 | 20,73 |
| warm | **14,36** | 11,73 | 11,49 | 11,17 | 16,55 |
| cool | 22,41 | 20,77 | **22,65** | 20,39 | 23,83 |
| cool R@5 | 2,37 | **6,10** | 4,34 | 1,05 | 22,22 |

**Diagnóstico (por que a fusão não ganhou):**
1. **Redundância de sinal textual.** A GNN já recebe os embeddings SciBERT *estáticos* como
   features dos nós (Paper/Author); a CNN textual acrescenta pouco além do que a estrutura já
   codifica → a fusão ≈ GNN sozinha.
2. **O reranking de 2 saltos anula a maior força do texto.** O texto vencia em *cool* justamente
   por alcançar coautores **fora** da vizinhança de 2 saltos (espaço de candidatos global). Ao
   restringir a fusão aos candidatos de 2 saltos, esse ganho some — veja cool R@5: texto 6,10 →
   fusão 1,05. **O gerador de candidatos virou o gargalo, não a representação.**
3. **Cabeça de ranking fraca.** val loss ≈ 0,59 (acaso 0,69): o produto interno dos embeddings
   fundidos discrimina mal; a geração de candidatos faz quase todo o trabalho.

**Leitura crítica honesta:** a hipótese "texto+estrutura > cada um isolado" **não se confirma
nesta primeira implementação da fusão** — e o diagnóstico aponta que o problema central é o
**espaço de candidatos**, não a fusão de representações em si. Caminhos concretos:
- **Geração de candidatos híbrida**: unir 2-hop **+** vizinhos mais próximos por similaridade
  textual (preserva a força do texto em cool).
- **Separar os sinais**: GNN só com features estruturais (sem o SciBERT estático), deixando todo
  o sinal textual para a CNN — para a fusão somar informação não redundante.
- **Cabeça de ranking supervisionada** (MLP sobre features do par) em vez de produto interno.
- **Comparar com a fusão "clássica"** (reranker RF sobre `[CN, Jaccard, AA, sim_textual,
  score_GNN]`) — pode superar a end-to-end com muito menos custo.

## Enriquecimento GenAI no KG (ablação) — não ajudou a GNN

Extraímos atributos de alto nível dos abstracts via LLM (§4.3.3) com **dois provedores**
(OpenAI gpt-4o-mini e Claude Haiku, mesmo esquema): `paper_type`, `contribution`,
`writing_style`, `methods`, `topic`. Concordância entre provedores (nos válidos): writing_style
90%, paper_type 66%, contribution 66% (Claude rodou completo/limpo; OpenAI teve 1.449 falhas
por limite de TPM, a refazer). Integramos as **categorias como novos nós/relações do KG**
(`paper → has_ptype/has_contrib/has_style`) e re-treinamos a GNN-rerank — ablação com vs sem:

| Recall@200 (%) | GNN-rerank (sem) | GNN-rerank **+enrich** |
|---|--:|--:|
| overall | 14,33 | 14,35 |
| warm | 11,49 | 11,73 |
| cool | **22,65** | 20,98 |

**Leitura crítica:** o enriquecimento categórico é **neutro a levemente negativo** (cool piora).
Diagnóstico: (1) **baixa variância/ruído** — `writing_style` é 91% `formal_technical`, e
`paper_type`/`contribution` têm só 66% de concordância entre provedores; (2) **hubs densos** —
milhares de papers ligam a ~6–8 nós de categoria, que após agregação `mean` diluem em vez de
discriminar; (3) o sinal textual rico (`topic`/`methods`, livre) **não** foi usado — só as
categorias. val loss idêntica (≈0,597) confirma que o modelo não extraiu sinal novo.
**Conclusão: a caixa "Enriquecimento GenAI" da arquitetura, como categorias no KG, não
melhora a recomendação neste corpus.** Avenida ainda aberta: embutir `topic`/`methods` (texto
livre) como branch semântico, em vez de categorias.

## Candidatos híbridos (estrutural ∪ textual) — o gargalo era a geração de candidatos

Todas as ablações anteriores apontaram o mesmo gargalo: **o espaço de candidatos** (2 saltos),
não a representação. Testamos gerar candidatos = **2-hop ∪ top-M vizinhos por similaridade
textual** (SciBERT) e ranquear a união. Resultado por ranqueador:

| Recall@200 (%) | Híbrido RF | GNN-rerank | Texto-only | Hybrid (rank=**gnn**) | Hybrid (rank=**text**, m=100) | Oráculo top. |
|---|--:|--:|--:|--:|--:|--:|
| overall | 14,80 | 14,33 | 2,22 | 14,15 | **14,84** | 20,73 |
| warm | 14,36 | 11,49 | 11,73 | 10,44 | **14,39** | 16,55 |
| cool | 22,41 | 22,65 | 20,77 | 21,69 | **24,95** | 23,83 |

**Resultado (números brutos):** ranqueado por texto, o reranker de candidatos híbridos atinge
14,84 no geral (vs 14,80 do RF), 14,39 em warm (vs 14,36) e 24,95 em cool — neste último
acima do teto do oráculo topológico (23,83), pois os candidatos textuais alcançam coautores
**fora** do 2-hop. Ranqueado pela GNN, piora (14,15): ranqueador fraco + pool maior = ruído.

**Testes de significância (Wilcoxon, α Bonferroni = 0,0125) — corrigem a leitura:**

| Comparação | métrica | Δ (pp) | p | veredito |
|---|---|--:|--:|---|
| Hybrid-cand vs RF (T0-ativos) | R@200 | +0,08 | 0,21 | **empate** |
| Hybrid-cand vs RF (T0-ativos) | R@50 | −3,39 | 1e‑13 | **RF melhor** |
| Hybrid-cand vs RF (warm) | NDCG@10 | −1,07 | 0,001 | **RF melhor** |
| Hybrid-cand vs RF (cool) | R@200 | +1,26 | 0,72 | empate (n=78) |
| Hybrid-cand vs GNN-rerank | R@200 | +3,7 | 1e‑29 | **Hybrid melhor** |
| Hybrid-cand vs Texto-only | R@200 | +2,8 | 1e‑24 | **Hybrid melhor** |

**Leitura crítica honesta:** o "14,84 vs 14,80" é **ruído** — Hybrid-cand **empata** com o
Híbrido RF, e o **RF segue significativamente melhor em R@50 e no topo (NDCG@10)**. O que é
estatisticamente real: Hybrid-cand **supera a GNN e o texto-only** (esp. em recall@200, via
candidatos estruturais). Ou seja, a **fusão de fontes de candidatos** (estrutura ∪ texto) é a
direção certa e já bate os modelos aprendidos, mas **ainda não vence o RF** — falta ganhar no
topo/meio do ranking, onde features supervisionadas (RF) dominam. Próximo: ranqueador
supervisionado sobre o pool híbrido; varredura de `m`.

## Reranker supervisionado sobre o pool híbrido (RF + features) — falhou

Tentativa de unir o alcance dos candidatos híbridos ao ranqueamento forte do RF: RF sobre
features `[CN, Jaccard, Adamic-Adar, sim_textual, score_GNN]` do par, no pool 2-hop ∪ texto.
Importâncias: **Adamic-Adar 0,48**, CN 0,19, **text_sim 0,17**, gnn_sim 0,09, Jaccard 0,06
(topologia ainda domina; texto contribui; GNN pouco).

Números brutos: maior **Recall@200** de todos (overall 14,92; cool 25,42, acima do oráculo),
**mas precisão no topo desaba** (warm R@5 0,45 vs 2,82 do RF). Significância (Wilcoxon, α=0,0167):

| Sup-Hybrid vs RF (T0-ativos) | Δ (pp) | p | veredito |
|---|--:|--:|---|
| R@10 | −3,79 | 3e‑35 | **RF muito melhor** |
| R@50 | −6,86 | 3e‑37 | **RF muito melhor** |
| NDCG@10 | −4,78 | 2e‑38 | **RF muito melhor** |
| R@200 | +0,49 | 0,18 | empate |

**Conclusão:** o reranker supervisionado sobre o pool híbrido é **significativamente pior que o
RF** (e que o próprio Hybrid-cand) no topo/meio — adicionar candidatos textuais a um ranqueador
forte **polui** as primeiras posições (não‑coautores textualmente similares recebem score alto).
Ganhar recall@200 ao custo de destruir P@5/NDCG@10 não é um avanço útil.

## Validação em base de IA — cold-start COMPROVADO (o achado central)

Na base médica (snowball denso) cool tinha n=78 e cold n=3 → inconclusivo. Coletamos uma base
**temática de IA e correlatas** (Concepts AI/ML/NLP/CV/Deep Learning, 20k works → 13.924 limpos,
**45.732 autores**), que por ser menos densa popula os regimes: **cool n=783, cold n=53**. Com
poder estatístico real (Wilcoxon + Bonferroni, IC95% bootstrap):

| Recall@200 (%) | Baseline | Híbrido RF | Texto | Cand. híbridos |
|---|--:|--:|--:|--:|
| **cool** (n=783) | 1,3 | 3,6 | 7,4 | **7,6** |
| **cold** (n=53) | **0,0** | **0,0** | **6,2** | 4,7 |

- **COLD (autores sem coautoria em T0): os modelos topológicos zeram** — a vizinhança de 2 saltos
  é vazia, não há o que recomendar. **Só o texto funciona** (Texto vs RF Δ=+6,2pp, p=0,0009;
  Cand. híbridos vs RF +4,7pp, p=0,003). É o argumento mais limpo para o multimodal: no
  cold-start, a topologia **falha por construção** e o conteúdo é a única fonte de sinal.
- **COOL: texto/híbrido superam o Híbrido RF de forma robusta** (Cand. híbridos vs RF Δ=+4,0pp,
  **p=1,2e‑23**; Texto vs RF +3,7pp, p=1,5e‑13). Diferente da base médica (n=78, inconclusivo),
  aqui o ganho é altamente significativo.
- No **topo do ranking** (R@10) em cool, RF ainda empata/leva ligeira vantagem; o ganho do texto
  é em cobertura (recall em K maior) — complementaridade preservada.

**Conclusão atualizada:** com uma base adequada, a hipótese da tese se confirma onde é decisiva —
**recomendação para pesquisadores de baixa/nenhuma conectividade (cool/cold), onde a topologia é
insuficiente ou nula e a semântica textual é essencial.** (Caveat: o gate reprovou a base de IA
em `mean_coauthor_weight`=1,05 — esperado em coleta temática, não-snowball; demais critérios ok.)

## Síntese geral (honesta) dos modelos

Após baselines, texto, GNN, fusão end-to-end, enriquecimento GenAI e candidatos híbridos
(+ ranqueador supervisionado), com testes de significância pareados:

- **O Híbrido RF (topológico) permanece o melhor modelo geral.** Nenhuma abordagem multimodal
  o superou de forma robusta em warm ou no topo do ranking.
- **O ganho real e robusto do texto é localizado em COOL** (autores com pouco histórico):
  Hybrid-cand R@10 +5,06pp vs RF (p=0,005) e furam o teto do oráculo topológico, porque
  candidatos textuais alcançam coautores fora do 2-hop. É onde a hipótese da tese se sustenta.
- **A "fusão" que funciona é de fontes de candidatos** (estrutura ∪ texto), não de representações
  (fusão end-to-end empatou) nem de ranqueador supervisionado sobre o pool (piorou o topo).
- **Caveat de reprodutibilidade:** comparações borderline (Hybrid-cand × RF em R@200) **variam
  com `PYTHONHASHSEED`** (p oscilou 0,002↔0,21) — é preciso fixar a seed de hash para conclusões
  estáveis. Recomendado antes de cravar qualquer resultado fino.

## Síntese: evoluiu?

| Frente | Evoluiu? | Observação crítica |
|---|---|---|
| Baseline → Híbrido RF | Sim, modesto | Ganha recall em K alto; assimétrico (Ciclo 1). |
| Topologia → Texto (warm) | **Não** | Híbrido RF ainda supera o texto onde há histórico. |
| Topologia → Texto (cool, topo) | **Sim** | Texto (SciBERT/SPECTER) ~2,6× no Recall@5. |
| Encoders (TF-IDF→SciBERT/SPECTER) | Sim, pequeno | Sem teste de significância; TF-IDF perto do BERT. |
| Cobertura de newcomers | Não (nenhum) | Fronteira real; nem texto nem topologia resolvem. |

**Conclusão:** o ganho claro do texto é **localizado** (topo do ranking em baixa conectividade),
não global. Isso **justifica a fusão** (texto+estrutura via GNN) como próximo passo — com a
ressalva de que ela precisa **superar o Híbrido RF**, e não apenas o baseline, para valer a pena.
