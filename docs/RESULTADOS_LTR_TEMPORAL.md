# Resultados — treino temporal do re-ranqueador

> Gerado por `scripts/report_ltr_temporal.py` a partir de `runs/ltr_temporal/`. Método em
> [ABLACAO_KG.md](ABLACAO_KG.md) §7. Treino: KG até 2018 → coautorias novas de 2019–2021 (sementes e
> candidatos como consultas). Teste: KG até 2021 → T1, mesmos alvos e candidatos da ablação. Valores em %,
> média por alvo, com M9. `*` = significativo (teste pareado, Bonferroni).

## 1. Tamanho do treino

| Base | Consultas (sementes + candidatos) | Pares de treino | Positivos de treino | dos quais de sementes | Positivos no teste |
|---|---:|---:|---:|---:|---:|
| Medicina | 856 + 2144 | 2.882.000 | 60.172 | 7.593 | 3.964 |
| Ciência da Computação | 695 + 2305 | 2.707.000 | 10.402 | 1.786 | 993 |
| Matemática | 607 + 2393 | 2.356.000 | 5.303 | 1.231 | 827 |
| Economia | 507 + 2493 | 2.205.000 | 5.509 | 880 | 517 |

## 2. R@10

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 1,20 | 3,41 | 4,15 | 3,25 |
| LTR completo (validação cruzada) | 1,33 | 3,41 | 4,83 | 3,63 |
| LTR temporal só coautoria | 1,32 | 2,57 | 4,19 | 2,73 |
| **LTR temporal completo** | 1,46 | 3,64 | 5,49 | 3,95 |
| LTR temporal completo, só sementes | 1,32 | 3,60 | 4,56 | 3,57 |
| LTR temporal completo, parâmetros padrão | 1,40 | 3,61 | 4,40 | 3,40 |

## 3. R@50

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 3,32 | 5,84 | 11,36 | 6,08 |
| LTR completo (validação cruzada) | 3,78 | 6,16 | 11,16 | 6,93 |
| LTR temporal só coautoria | 3,47 | 5,55 | 9,39 | 6,06 |
| **LTR temporal completo** | 3,84ᴿᶜ | 6,21ᶜ | 11,85ᶜ | 7,37ᴿᶜ |
| LTR temporal completo, só sementes | 3,66 | 6,05 | 11,34 | 7,18 |
| LTR temporal completo, parâmetros padrão | 3,86 | 5,93 | 12,32 | 7,77 |

## 4. NDCG@10

| Modelo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF (sem aprendizado) | 7,83 | 5,37 | 4,99 | 3,71 |
| LTR completo (validação cruzada) | 8,21 | 5,10 | 5,21 | 4,02 |
| LTR temporal só coautoria | 8,73 | 3,94 | 4,70 | 3,16 |
| **LTR temporal completo** | 9,30ᴿⱽ | 5,41ᶜ | 5,96 | 4,25ᶜ |
| LTR temporal completo, só sementes | 8,47 | 5,42 | 5,12 | 4,07 |
| LTR temporal completo, parâmetros padrão | 8,99 | 5,05 | 5,13 | 3,60 |

Marcas no LTR temporal completo: diferença significativa contra ᴿ a União RRF, ᶜ o LTR temporal só coautoria, ⱽ o LTR por validação cruzada.

## 5. Leave-one-out — Δ ao retirar cada grupo (R@50 / NDCG@10)

| Grupo retirado | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | -1,19* / -2,87* | -1,29* / -1,01* | -1,73* / -0,62 | -1,71* / -0,68 |
| Instituição | -0,16 / -0,14 | -0,74* / -0,60 | -0,02 / +0,20 | -0,65 / -0,64 |
| Tópicos | -0,10 / +0,06 | -0,01 / +0,10 | +0,27 / +0,10 | +0,35 / +0,04 |
| Periódico | -0,10 / +0,02 | -0,04 / -0,06 | +0,13 / +0,04 | +0,38 / -0,03 |
| Citação/acoplamento | -0,09 / +0,01 | -0,09 / -0,29 | -0,39 / -0,23 | -0,37 / +0,02 |
| Ex-colegas ORCID | -0,02 / -0,03 | -0,01 / -0,15 | +0,21 / +0,18 | -0,36 / -0,34 |
| Texto TF-IDF | -0,09 / -0,17 | +0,01 / -0,23 | -0,15 / +0,12 | -0,28 / +0,00 |
| Atividade | -0,27* / -0,66* | -0,03 / -0,46 | -0,23 / -0,28 | +0,02 / -0,01 |

## 6. Add-one — Δ ao somar cada grupo à coautoria (R@50 / NDCG@10)

| Grupo somado | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Instituição | +0,08 / +0,07 | +0,39* / +0,79* | +0,09 / +0,04 | +1,21* / +0,92* |
| Tópicos | +0,09 / +0,19 | +0,17 / +0,08 | +1,31* / +0,58 | +0,23 / +0,11 |
| Periódico | +0,06 / +0,11 | -0,26 / +0,16 | +0,58 / +0,26 | +0,29 / +0,05 |
| Citação/acoplamento | +0,04 / +0,39 | -0,10 / +0,34 | +2,36* / +1,41* | +0,45 / +0,50 |
| Ex-colegas ORCID | +0,02 / +0,04 | -0,03 / -0,04 | +0,10 / +0,09 | +0,39 / +0,10 |
| Texto TF-IDF | +0,16 / +0,39 | +0,07 / +0,77* | +2,21* / +0,85 | +0,55 / +0,45 |

## 7. Peso de cada grupo no LTR temporal completo (|SHAP| médio, % do total)

| Grupo | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | 41,32 | 23,55 | 11,93 | 13,27 |
| Instituição | 20,03 | 18,93 | 12,15 | 14,37 |
| Tópicos | 5,22 | 9,91 | 19,39 | 11,05 |
| Periódico | 6,65 | 11,33 | 6,64 | 8,12 |
| Citação/acoplamento | 4,15 | 7,85 | 12,18 | 6,81 |
| Ex-colegas ORCID | 0,11 | 0,07 | 0,13 | 0,15 |
| Texto TF-IDF | 8,21 | 10,94 | 13,13 | 17,76 |
| Atividade | 14,31 | 17,41 | 24,46 | 28,46 |
| *Conteúdo (tópicos + citação + texto)* | *17,58* | *28,70* | *44,70* | *35,62* |

## 8. Por regime — NDCG@10 (só coautoria → completo, treino temporal)

**Medicina**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 9,42 | 10,03 | 8,44 |
| cool | 0,00 | 0,00 | 0,00 |
| cold | 0,00 | 0,00 | 0,00 |

**Ciência da Computação**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 4,40 | 5,84 | 5,77 |
| cool | 3,36 | 5,22 | 5,54 |
| cold | 0,00 | 7,92 | 7,71 |

**Matemática**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 5,57 | 6,39 | 5,13 |
| cool | 2,57 | 4,92 | 4,57 |
| cold | 0,00 | 12,50 | 15,36 |

**Economia**

| Regime | Só coautoria | Completo | União RRF |
|---|---:|---:|---:|
| warm | 4,14 | 5,29 | 4,77 |
| cool | 1,41 | 2,96 | 1,98 |
| cold | 0,00 | 0,00 | 0,00 |

## 9. Avaliação padrão — só coautorias novas com pessoas presentes em T0

Mesmos modelos e rankings; o gabarito exclui coautores sem trabalho em T0. Marcas no LTR completo: ᴿ contra a União RRF, ᶜ contra o só coautoria (Bonferroni próprio).

| Base | Alvos | Modelo | R@10 | R@50 | NDCG@10 | Hits@10 |
|---|---:|---|---:|---:|---:|---:|
| Medicina | 405 | União RRF (sem aprendizado) | 4,25 | 10,35 | 9,91 | 41,98 |
| Medicina | 405 | LTR temporal só coautoria | 4,76 | 10,78 | 11,14 | 42,47 |
| Medicina | 405 | **LTR temporal completo** | 5,26 | 12,06ᴿᶜ | 11,95ᴿ | 43,95 |
| Ciência da Computação | 333 | União RRF (sem aprendizado) | 11,86 | 21,78 | 10,90 | 31,83 |
| Ciência da Computação | 333 | LTR temporal só coautoria | 9,43 | 20,34 | 8,10 | 27,03 |
| Ciência da Computação | 333 | **LTR temporal completo** | 13,65 | 23,78ᶜ | 11,38ᶜ | 36,04 |
| Matemática | 283 | União RRF (sem aprendizado) | 15,46 | 36,42 | 11,72 | 34,63 |
| Matemática | 283 | LTR temporal só coautoria | 14,67 | 30,65 | 10,68 | 34,63 |
| Matemática | 283 | **LTR temporal completo** | 19,06 | 37,23ᶜ | 13,80ᶜ | 40,64 |
| Economia | 204 | União RRF (sem aprendizado) | 14,89 | 28,87 | 10,16 | 29,90 |
| Economia | 204 | LTR temporal só coautoria | 11,28 | 24,93 | 8,31 | 24,51 |
| Economia | 204 | **LTR temporal completo** | 17,55 | 33,55ᴿᶜ | 11,99ᶜ | 35,78 |
