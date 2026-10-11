# Resultados — geração seletiva em cascata

> Gerado por `scripts/report_cascata.py` a partir de `runs/cascata/`. Método em
> [GERACAO_SELETIVA.md](GERACAO_SELETIVA.md). Treino temporal (KG 2018 → 2019–2021); teste no KG 2021 → T1.
> Valores em %. `*` = significativo contra o LTR temporal sobre a União RRF (teste pareado, Bonferroni).

## 1. Geração — alcance do conjunto que a etapa 2 recebe (soma de pares)

### Avaliação estrita (todas as coautorias novas)

| | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Top-1000 da União RRF (atual) | 12,91 | 10,76 | 21,46 | 15,43 |
| **Top-1000 da etapa 1** | 15,90 | 11,83 | 22,92 | 16,86 |
| Conjunto ampliado inteiro (teto) | 21,03 | 15,78 | 26,32 | 20,35 |
| Ganho relativo da etapa 1 | +23,2% | +9,9% | +6,8% | +9,3% |

### Avaliação padrão (só coautores presentes em T0)

| | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Top-1000 da União RRF (atual) | 30,46 | 38,79 | 65,74 | 57,51 |
| **Top-1000 da etapa 1** | 37,51 | 42,66 | 70,19 | 62,85 |
| Conjunto ampliado inteiro (teto) | 49,61 | 56,91 | 80,60 | 75,86 |
| Ganho relativo da etapa 1 | +23,1% | +10,0% | +6,8% | +9,3% |

Conjunto ampliado (mediana de candidatos por alvo): Medicina 6.417, Ciência da Computação 5.443, Matemática 4.623, Economia 4.642.

## Resultado final — R@50, avaliação estrita

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 3,32 | 5,84 | 11,36 | 6,08 |
| LTR temporal (União RRF → LTR) | 3,84 | 6,21 | 11,85 | 7,37 |
| Cascata: etapa 1 apenas | 3,62 | 5,93 | 11,40 | 7,52 |
| Cascata: etapa 1 → LTR | 3,85 | 6,16 | 11,72 | 7,26 |
| Cascata: etapa 1 → LTR (+ nota da etapa 1) | 3,90 | 6,18 | 12,01 | 7,40 |

## Resultado final — NDCG@10, avaliação estrita

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 7,83 | 5,37 | 4,99 | 3,71 |
| LTR temporal (União RRF → LTR) | 9,30 | 5,41 | 5,96 | 4,25 |
| Cascata: etapa 1 apenas | 9,29 | 5,28 | 5,61 | 3,79 |
| Cascata: etapa 1 → LTR | 9,20 | 5,19 | 5,46 | 4,24 |
| Cascata: etapa 1 → LTR (+ nota da etapa 1) | 9,32 | 4,98 | 5,68 | 3,75 |

## Resultado final — R@50, avaliação padrão

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 10,35 | 21,78 | 36,42 | 28,87 |
| LTR temporal (União RRF → LTR) | 12,06 | 23,78 | 37,23 | 33,55 |
| Cascata: etapa 1 apenas | 11,48 | 22,72 | 35,98 | 32,96 |
| Cascata: etapa 1 → LTR | 12,07 | 23,54 | 36,25 | 33,54 |
| Cascata: etapa 1 → LTR (+ nota da etapa 1) | 12,16 | 23,29 | 37,39 | 32,41 |

## Resultado final — NDCG@10, avaliação padrão

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 9,91 | 10,90 | 11,72 | 10,16 |
| LTR temporal (União RRF → LTR) | 11,95 | 11,38 | 13,80 | 11,99 |
| Cascata: etapa 1 apenas | 11,70 | 10,87 | 12,91 | 10,72 |
| Cascata: etapa 1 → LTR | 11,83 | 10,77 | 12,80 | 12,36 |
| Cascata: etapa 1 → LTR (+ nota da etapa 1) | 11,94 | 10,58 | 12,92 | 10,57 |

## Etapa 1 — atributos mais usados (ganho, % do total)

- **Medicina**: `coautoria_aa` 42,57; `ppr` 21,03; `coautoria_ra` 7,72; `acoplamento` 3,74; `grau_alvo` 3,07; `rrf` 3,06
- **Ciência da Computação**: `rrf` 30,19; `ppr` 16,32; `coautoria_aa` 11,16; `acoplamento` 7,45; `topico` 6,54; `grau_alvo` 5,44
- **Matemática**: `rrf` 41,14; `acoplamento` 10,46; `rrf_pos` 8,81; `ppr` 8,22; `topico` 5,88; `texto_tfidf` 4,41
- **Economia**: `rrf` 37,80; `coautoria_aa` 8,92; `ppr` 8,87; `rrf_pos` 6,54; `topico` 6,29; `texto_tfidf` 6,27
