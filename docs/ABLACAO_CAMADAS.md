# Ablação das camadas e peso de uso de cada modalidade

Fecha os três gaps restantes da qualificação e responde "quanto o modelo usa cada camada".
Base IA, KG T0 (`data/processed/hetero_T0_ai.pt`: 32.835 autores, 11.139 artigos), 2.003
autores-alvo T0-ativos. Avaliação por Recall@K com `GNNReranker` (ranqueia candidatos 2-hop).
Reprodução:

```bash
PYTHONHASHSEED=0 python scripts/ablation_layers.py    # SAGE vs GAT · componentes · gate α
PYTHONHASHSEED=0 python scripts/inductive_eval.py     # indutivo vs transdutivo (held-out)
```

> Nota de escala: encoders treinados a 60 épocas, hidden 64, CPU, negativos aleatórios — a
> ablação é uma **comparação relativa controlada**, não a busca do melhor número absoluto.

---

## Gap #2 — GAT vs GraphSAGE no encoder estrutural
Adicionado `conv_type` ao `HeteroEncoder` (`GATConv`, atenção por vizinho; `add_self_loops=False`
nas arestas heterogêneas). Só-grafo:

| Encoder | R@10 | R@50 | R@200 |
|---|---:|---:|---:|
| GNN-SAGE | 1,73 | 3,26 | 3,78 |
| GNN-GAT | **1,87** | 3,21 | 3,78 |

Por regime (R@10): warm SAGE 1,39 → **GAT 1,64**; cool empate (2,36 / 2,34); cold ambos 0,0.
**Leitura:** a atenção do GAT dá um ganho pequeno no topo em warm e empata no resto — coerente
com o achado de que, no grafo, só a coautoria carrega sinal; ponderar vizinhos por atenção não
cria informação nova. GAT fica disponível como opção (`--conv gat`), sem ser decisivo.

---

## Gap #1 — Fusão por atenção e o PESO de cada camada
Adicionada `AttentionFusionModel` (portão α por autor: `z = α·texto + (1−α)·grafo`,
α = σ(gate)). Na ablação, um portão leve funde a camada textual (SciBERT) e a estrutural
(GNN-SAGE), treinado por link-prediction. α é interpretável = **peso do ramo textual**.

### Componentes (Recall)
| Modelo | R@10 | R@50 | R@200 |
|---|---:|---:|---:|
| Só-grafo (SAGE) | 1,73 | 3,26 | 3,78 |
| Só-texto (SciBERT) | 1,94 | 3,28 | 3,78 |
| **Fusão por portão** | **2,01** | **3,33** | 3,78 |

### Peso de uso de cada camada (α do portão)
| Regime | peso texto (α) | peso grafo (1−α) |
|---|---:|---:|
| geral | 0,094 | 0,906 |
| warm | 0,074 | 0,926 |
| cool | 0,103 | 0,897 |
| **cold** | **0,397** | 0,603 |

**Leitura (quantifica a tese):** a fusão por portão supera cada componente isolado no topo
(R@10 2,01 vs 1,94/1,73). E o peso do texto **cresce monotonicamente do warm ao cold**
(0,074 → 0,103 → **0,397**): quando o autor tem estrutura, o modelo se apoia no grafo; quando
não tem (cold-start), o peso do texto **quintuplica**. É a leitura direta e mensurável de
"quanto cada camada é usada" — e confirma que o texto é o mecanismo de resgate no cold-start.

---

## Gap #4 — Aprendizado indutivo (generaliza para não-vistos?)
Protocolo: 400 alvos (H) têm **todas as suas arestas de coautoria removidas da supervisão**
(3.490 de 109.338). Os nós de H seguem no grafo (chegam com a vizinhança, como recém-chegados).
Dois encoders sobre as mesmas arestas, avaliados **só em H**:

| Encoder | R@10 | R@50 | R@200 |
|---|---:|---:|---:|
| Indutivo (features SciBERT) | **1,56** | **3,18** | 3,98 |
| Transdutivo (tabela de embeddings) | 1,46 | 3,13 | 3,98 |

**Leitura:** nos autores fora da supervisão, o encoder **com features** generaliza melhor
(+0,10pp R@10, consistente em R@10/R@50). O ganho é modesto porque a própria agregação de
vizinhança da GNN já confere alguma capacidade indutiva ao transdutivo — mas a direção confirma
o requisito da qualificação: o modelo **produz embeddings úteis para autores nunca supervisionados**,
e as features textuais ajudam. (Um transdutor raso puro — só a linha da tabela, sem convolução —
falharia por completo em nós novos.)

---

## Teto recorrente e conclusão
Em **todos** os experimentos o R@200 empata (~3,78–3,98): é o teto de cobertura do pool **2-hop**
que o `GNNReranker` ranqueia — a qualidade do embedding move o **topo** do ranking, não o alcance.
Reafirma o achado central da tese: **o gargalo é a geração de candidatos**, e é por isso que o
modelo operacional vencedor (2 etapas) acrescenta a cauda textual *fora* do 2-hop. As três
extensões enriquecem a análise (atenção mensura o uso das camadas; GAT e indutivo são positivos
mas não decisivos), sem mudar o veredito: o valor multimodal está em **ampliar e explicar** o
espaço de candidatos. Artefatos: `runs/ablation/ablation.json`, `runs/ablation/inductive.json`.
