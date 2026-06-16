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
