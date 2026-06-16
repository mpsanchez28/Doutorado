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
