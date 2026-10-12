# Resultados — TF-IDF × SPECTER2

> Gerado por `scripts/report_texto.py`. Método em [TEXTO_SPECTER2.md](TEXTO_SPECTER2.md). Valores em %.
> `*` = diferença significativa contra a variante TF-IDF (teste pareado por alvo, Bonferroni).

## 1. Gerador textual isolado (mesmo protocolo da linha de base)

| Gerador | Métrica | Medicina | Ciência da Computação | Matemática | Economia |
|---|---|---:|---:|---:|---:|
| TF-IDF | R@50 estrita | 0,25 | 1,36 | 4,13 | 1,30 |
| TF-IDF | NDCG@10 estrita | 0,25 | 0,65 | 1,67 | 0,56 |
| TF-IDF | Alcance@1000 estrita | 2,00 | 5,12 | 15,30 | 5,96 |
| TF-IDF | R@50 padrão | 0,83 | 4,94 | 14,04 | 4,61 |
| TF-IDF | Alcance@1000 padrão | 6,72 | 16,65 | 47,62 | 29,33 |
| SPECTER2 | R@50 estrita | 0,89 | 1,72 | 5,24 | 2,34 |
| SPECTER2 | NDCG@10 estrita | 3,02 | 1,54 | 3,24 | 1,08 |
| SPECTER2 | Alcance@1000 estrita | 4,70 | 6,60 | 15,47 | 8,94 |
| SPECTER2 | R@50 padrão | 2,64 | 5,84 | 14,98 | 11,54 |
| SPECTER2 | Alcance@1000 padrão | 12,48 | 22,68 | 45,30 | 37,64 |
| União RRF (com os dois) | R@50 estrita | 3,32 | 5,84 | 11,70 | 5,95 |
| União RRF (com os dois) | NDCG@10 estrita | 7,83 | 5,41 | 5,10 | 3,82 |
| União RRF (com os dois) | Alcance@1000 estrita | 9,87 | 11,56 | 23,20 | 13,88 |
| União RRF (com os dois) | R@50 padrão | 10,32 | 22,09 | 37,25 | 29,52 |
| União RRF (com os dois) | Alcance@1000 padrão | 28,66 | 43,88 | 71,44 | 61,71 |

## LTR temporal — R@50, avaliação estrita

| Modelo | Texto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---|---:|---:|---:|---:|
| LTR só coautoria | — | 3,47 | 5,55 | 9,39 | 6,06 |
| coautoria + texto | TF-IDF | 3,63 | 5,62 | 11,60 | 6,61 |
| coautoria + texto | SPECTER2 | 3,63 | 5,60 | 10,92 | 6,29 |
| coautoria + texto | TF-IDF + SPECTER2 | 3,64 | 5,53 | 11,96 | 6,60 |
| LTR completo | TF-IDF | 3,84 | 6,21 | 11,85 | 7,37 |
| LTR completo | SPECTER2 | 3,85 | 6,25 | 12,44 | 6,95 |
| LTR completo | TF-IDF + SPECTER2 | 3,83 | 6,27 | 12,31 | 7,06 |

## LTR temporal — NDCG@10, avaliação estrita

| Modelo | Texto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---|---:|---:|---:|---:|
| LTR só coautoria | — | 8,73 | 3,94 | 4,70 | 3,16 |
| coautoria + texto | TF-IDF | 9,12 | 4,71 | 5,55 | 3,61 |
| coautoria + texto | SPECTER2 | 9,00 | 4,23 | 5,31 | 3,18 |
| coautoria + texto | TF-IDF + SPECTER2 | 9,15 | 4,59 | 5,76 | 3,38 |
| LTR completo | TF-IDF | 9,30 | 5,41 | 5,96 | 4,25 |
| LTR completo | SPECTER2 | 9,18 | 5,13 | 5,99 | 4,08 |
| LTR completo | TF-IDF + SPECTER2 | 9,33 | 5,32 | 6,07 | 4,14 |

## LTR temporal — R@50, avaliação padrão

| Modelo | Texto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---|---:|---:|---:|---:|
| LTR só coautoria | — | 10,78 | 20,34 | 30,65 | 24,93 |
| coautoria + texto | TF-IDF | 11,29 | 20,18 | 36,07 | 26,90 |
| coautoria + texto | SPECTER2 | 11,34 | 20,58 | 34,57 | 26,57 |
| coautoria + texto | TF-IDF + SPECTER2 | 11,34 | 20,10 | 37,35 | 28,36 |
| LTR completo | TF-IDF | 12,06 | 23,78 | 37,23 | 33,55 |
| LTR completo | SPECTER2 | 11,95 | 24,10 | 38,16 | 31,71 |
| LTR completo | TF-IDF + SPECTER2 | 12,02 | 24,05 | 37,86 | 33,05 |

## LTR temporal — NDCG@10, avaliação padrão

| Modelo | Texto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---|---:|---:|---:|---:|
| LTR só coautoria | — | 11,14 | 8,10 | 10,68 | 8,31 |
| coautoria + texto | TF-IDF | 11,73 | 9,55 | 12,95 | 9,24 |
| coautoria + texto | SPECTER2 | 11,40 | 8,83 | 12,10 | 8,43 |
| coautoria + texto | TF-IDF + SPECTER2 | 11,75 | 9,37 | 13,37 | 8,96 |
| LTR completo | TF-IDF | 11,95 | 11,38 | 13,80 | 11,99 |
| LTR completo | SPECTER2 | 11,73 | 10,52 | 13,84 | 11,15 |
| LTR completo | TF-IDF + SPECTER2 | 11,85 | 11,14 | 14,01 | 11,45 |

## Peso do grupo texto no LTR temporal completo (|SHAP|, % do total)

| Texto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| TF-IDF | 8,21 | 10,94 | 13,13 | 17,76 |
| SPECTER2 | 17,28 | 21,70 | 20,24 | 26,79 |
| TF-IDF + SPECTER2 | 20,12 | 25,05 | 26,17 | 35,69 |

α de Bonferroni: 0.0008.
