# Resultados — ablação das relações do KG

> Gerado por `scripts/report_ablacao_kg.py` a partir de `runs/ablacao_kg/`. Método e leitura em
> [ABLACAO_KG.md](ABLACAO_KG.md). Valores em %, média por alvo, gabarito com M9. `*` = diferença
> significativa no teste pareado com correção de Bonferroni.

## 1. Ordenação — modelos sobre o mesmo conjunto de candidatos (top-1000 da União)

### R@10

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 1,20 | 3,41 | 4,15 | 3,25 |
| LTR só coautoria | 1,20 | 2,88 | 3,59 | 2,73 |
| LTR completo | 1,33 | 3,41 | 4,83 | 3,63 |

### R@50

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 3,32 | 5,84 | 11,36 | 6,08 |
| LTR só coautoria | 3,46 | 5,58 | 9,22 | 6,20 |
| LTR completo | 3,78* | 6,16* | 11,16* | 6,93 |

### NDCG@10

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 7,83 | 5,37 | 4,99 | 3,71 |
| LTR só coautoria | 8,00 | 3,71 | 4,49 | 3,05 |
| LTR completo | 8,21 | 5,10* | 5,21 | 4,02 |

`*` no LTR completo: diferença significativa contra o LTR só coautoria.

## 2. Ganho de cada relação — leave-one-out (Δ do NDCG@10 ao retirar o grupo)

Negativo = a relação ajudava (retirá-la piora). Base de comparação: LTR completo.

| Grupo retirado | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | -2,83* | -0,69 | -0,67 | -0,67 |
| Instituição | -0,12 | -0,64 | -0,10 | -0,45 |
| Tópicos | +0,38 | -0,08 | +0,00 | +0,10 |
| Periódico | +0,25 | -0,13 | +0,11 | -0,21 |
| Citação/acoplamento | +0,38 | -0,45 | -0,25 | +0,14 |
| Ex-colegas ORCID | +0,35 | +0,04 | -0,11 | -0,29 |
| Texto TF-IDF | +0,34 | +0,20 | -0,23 | -0,15 |
| Atividade (grau, produção, anos) | -0,41 | -0,32 | +0,00 | -0,33 |

## 3. Ganho de cada relação — add-one (Δ do NDCG@10 ao somar o grupo à coautoria)

| Grupo somado | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Instituição | +0,15 | +0,12 | -0,29 | +0,43 |
| Tópicos | +0,08 | +0,02 | +0,50 | -0,41 |
| Periódico | +0,08 | +0,13 | -0,14 | +0,13 |
| Citação/acoplamento | +0,15 | +0,83 | +0,65 | +0,11 |
| Ex-colegas ORCID | +0,35 | +0,01 | +0,04 | -0,21 |
| Texto TF-IDF | +0,39 | +0,45 | +0,40 | +0,22 |

## 4. Peso de cada relação no modelo completo (|SHAP| médio, % do total)

| Grupo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | 31,08 | 33,64 | 20,87 | 16,85 |
| Instituição | 19,91 | 15,85 | 8,13 | 13,06 |
| Tópicos | 4,46 | 7,55 | 17,29 | 10,80 |
| Periódico | 5,16 | 5,84 | 6,87 | 4,74 |
| Citação/acoplamento | 7,33 | 9,41 | 16,86 | 13,41 |
| Ex-colegas ORCID | 0,00 | 0,00 | 0,00 | 0,06 |
| Texto TF-IDF | 11,24 | 8,65 | 15,59 | 19,09 |
| Atividade (grau, produção, anos) | 20,81 | 19,06 | 14,39 | 21,98 |

## 5. Geração — Alcance@1000 da União sem cada relação (soma de pares)

| Conjunto | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Todos os meta-caminhos | 12,91 | 10,76 | 21,46 | 15,43 |
| sem Coautoria | 7,87 (-5,04) | 8,77 (-1,99) | 19,83 (-1,63) | 12,86 (-2,57) |
| sem Instituição | 12,72 (-0,19) | 10,32 (-0,44) | 21,31 (-0,15) | 14,62 (-0,81) |
| sem Tópicos | 13,16 (+0,25) | 10,79 (+0,03) | 21,05 (-0,41) | 15,55 (+0,12) |
| sem Periódico | 12,91 (+0,00) | 10,69 (-0,07) | 21,46 (+0,00) | 15,01 (-0,42) |
| sem Citação/acoplamento | 12,78 (-0,13) | 10,41 (-0,35) | 20,63 (-0,83) | 14,92 (-0,51) |
| sem Ex-colegas ORCID | 12,91 (+0,00) | 10,73 (-0,03) | 21,49 (+0,03) | 15,40 (-0,03) |
| sem Texto TF-IDF | 13,16 (+0,25) | 10,88 (+0,12) | 21,23 (-0,23) | 15,49 (+0,06) |

## 6. Por regime — NDCG@10 (LTR só coautoria → LTR completo)

**Medicina**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 8,63 | 8,86 | 8,44 |
| cool | 0,00 | 0,00 | 0,00 |
| cold | 0,00 | 0,00 | 0,00 |
| newcomer | 0,00 | 0,00 | 0,00 |

**Ciência da Computação**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 3,99 | 5,50 | 5,77 |
| cool | 3,77 | 5,23 | 5,54 |
| cold | 5,45 | 6,13 | 7,71 |
| newcomer | 0,00 | 0,00 | 0,00 |

**Matemática**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 5,19 | 5,34 | 5,13 |
| cool | 3,16 | 5,23 | 4,57 |
| cold | 0,00 | 13,38 | 15,36 |
| newcomer | 0,00 | 0,00 | 0,00 |

**Economia**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 4,03 | 4,98 | 4,77 |
| cool | 1,26 | 2,90 | 1,98 |
| cold | 0,00 | 0,00 | 0,00 |
| newcomer | 0,00 | 0,00 | 0,00 |

## 7. Tamanho do problema de aprendizado

| Base | Alvos | Pares (alvo, candidato) | Positivos no conjunto | Coautorias novas | α Bonferroni |
|---|---:|---:|---:|---:|---:|
| Medicina | 466 | 451.000 | 3.964 | 30.706 | 0.0031 |
| Ciência da Computação | 449 | 417.000 | 993 | 9.232 | 0.0031 |
| Matemática | 414 | 392.000 | 827 | 3.853 | 0.0031 |
| Economia | 337 | 309.000 | 517 | 3.351 | 0.0031 |
