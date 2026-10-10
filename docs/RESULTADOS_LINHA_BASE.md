# Resultados — linha de base e oráculos por meta-caminho do KG

> Gerado por `scripts/report_linha_base.py` a partir de `runs/linha_base/`. Método e leitura em
> [LINHA_BASE.md](LINHA_BASE.md). Valores em %, média por alvo (macro), gabarito **com M9**,
> salvo indicação.

## 1. Protocolo por base

| Base | Alvos | warm | cool | cold | newcomer | Pares novos | Removidos M9 | Coautor novo fora de T0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Medicina | 466 | 432 | 17 | 2 | 15 | 30.706 | 476 | 57,62 |
| Ciência da Computação | 449 | 377 | 33 | 7 | 32 | 9.232 | 174 | 72,27 |
| Matemática | 414 | 320 | 63 | 9 | 22 | 3.853 | 75 | 67,35 |
| Economia | 337 | 236 | 62 | 11 | 28 | 3.351 | 38 | 73,17 |

*Coautor novo fora de T0*: o coautor de T1 não tem nenhum trabalho no corpus até 2021 — nenhum modelo baseado no histórico pode recomendá-lo (teto absoluto = 100 − esse valor).

## 2. KG T0 materializado

| Base | Válido | Autores | Trabalhos | Instituições | Periódicos | Tópicos | Org. ORCID | wrote | cites | Trab. c/ tópico | c/ periódico | c/ refs | Refs no corpus | Autores c/ vínculo ORCID |
|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Medicina | sim | 893.851 | 366.585 | 27.753 | 10.285 | 2.249 | 7.842 | 3.807.489 | 10.226.137 | 100,00 | 97,70 | 70,75 | 6,98 | 0,53 |
| Ciência da Computação | sim | 235.538 | 207.495 | 12.405 | 8.681 | 2.196 | 6.495 | 924.885 | 6.106.863 | 100,00 | 90,75 | 85,67 | 10,63 | 2,00 |
| Matemática | sim | 65.049 | 93.230 | 8.035 | 4.341 | 1.252 | 5.977 | 255.025 | 1.883.101 | 100,00 | 97,02 | 78,81 | 6,89 | 6,53 |
| Economia | sim | 58.624 | 56.714 | 7.765 | 5.546 | 1.601 | 6.749 | 174.667 | 1.393.060 | 100,00 | 92,65 | 61,14 | 4,11 | 6,89 |

## 3. Geradores por base (baseline e oráculo)

Baseline = ordenar pelo escore do próprio meta-caminho. Oráculo = reordenar perfeitamente o conjunto do gerador. *Alcance@1000*: fração dos coautores novos entre os 1.000 primeiros candidatos (teto de um re-ranqueador sobre esse top-1000). *Alcance total*: dentro de todo o conjunto com escore > 0. *Conjunto*: mediana de candidatos por alvo.

### Medicina (466 alvos)

| Gerador | R@10 | R@50 | NDCG@10 | Hits@10 | MRR | Alcance@200 | Alcance@1000 | Alcance total | Conjunto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Coautoria: vizinhos comuns | 1,01 | 2,60 | 7,64 | 33,05 | 18,03 | 5,33 | 8,81 | 12,99 | 1.144 |
| Coautoria: Adamic-Adar | 1,07 | 2,68 | 7,62 | 33,48 | 17,88 | 5,57 | 9,11 | 12,99 | 1.144 |
| Coautoria: Resource Allocation | 0,99 | 2,66 | 6,55 | 32,83 | 16,78 | 5,18 | 8,88 | 12,99 | 1.144 |
| PageRank personalizado | 1,03 | 2,89 | 6,69 | 32,19 | 16,77 | 5,62 | 10,05 | 29,04 | 833.054 |
| KG: mesma instituição | 0,25 | 0,76 | 1,67 | 10,09 | 4,93 | 2,11 | 4,57 | 10,82 | 3.228 |
| KG: mesma organização-mãe | 0,19 | 0,63 | 1,17 | 7,08 | 3,59 | 1,79 | 4,09 | 11,38 | 3.804 |
| KG: tópicos (cosseno) | 0,06 | 0,18 | 0,59 | 3,65 | 2,16 | 0,55 | 1,79 | 21,48 | 128.466 |
| KG: mesmo periódico | 0,17 | 0,53 | 1,83 | 11,80 | 6,19 | 1,34 | 3,09 | 14,04 | 44.366 |
| KG: citação direta | 0,42 | 0,97 | 2,89 | 15,02 | 7,65 | 1,92 | 3,20 | 3,84 | 117 |
| KG: acoplamento bibliográfico | 0,27 | 0,77 | 2,12 | 11,59 | 5,64 | 2,01 | 4,55 | 14,88 | 61.854 |
| KG: ex-colegas (ORCID) | 0,01 | 0,01 | 0,18 | 1,29 | 0,65 | 0,01 | 0,01 | 0,01 | 0 |
| Texto: TF-IDF | 0,05 | 0,25 | 0,25 | 2,15 | 1,19 | 0,71 | 2,00 | 30,47 | 893.266 |
| Popularidade (grau) | 0,01 | 0,03 | 0,33 | 1,72 | 1,55 | 0,07 | 0,34 | 29,78 | 834.154 |
| **União (RRF)** | 1,20 | 3,32 | 7,83 | 36,48 | 17,81 | 5,79 | 9,81 | 30,47 | 893.618 |

### Ciência da Computação (449 alvos)

| Gerador | R@10 | R@50 | NDCG@10 | Hits@10 | MRR | Alcance@200 | Alcance@1000 | Alcance total | Conjunto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Coautoria: vizinhos comuns | 1,96 | 4,34 | 3,19 | 17,59 | 8,87 | 6,55 | 8,53 | 9,49 | 147 |
| Coautoria: Adamic-Adar | 2,35 | 4,57 | 3,33 | 18,49 | 8,80 | 6,82 | 8,93 | 9,49 | 147 |
| Coautoria: Resource Allocation | 2,44 | 4,30 | 2,94 | 17,15 | 7,69 | 6,70 | 8,90 | 9,49 | 147 |
| PageRank personalizado | 2,43 | 5,13 | 3,54 | 19,82 | 9,86 | 7,64 | 10,77 | 22,03 | 229.475 |
| KG: mesma instituição | 0,90 | 2,59 | 1,40 | 9,80 | 4,50 | 3,88 | 5,39 | 6,48 | 346 |
| KG: mesma organização-mãe | 0,77 | 2,24 | 1,13 | 7,35 | 3,83 | 3,64 | 5,41 | 6,74 | 411 |
| KG: tópicos (cosseno) | 0,22 | 0,55 | 0,38 | 2,45 | 1,09 | 1,33 | 4,85 | 18,25 | 46.583 |
| KG: mesmo periódico | 0,35 | 1,00 | 0,79 | 6,01 | 2,80 | 1,92 | 3,77 | 11,42 | 14.802 |
| KG: citação direta | 0,80 | 2,20 | 2,20 | 11,80 | 6,36 | 3,12 | 3,61 | 3,63 | 46 |
| KG: acoplamento bibliográfico | 1,62 | 2,68 | 2,07 | 11,58 | 5,48 | 4,10 | 6,00 | 12,91 | 27.948 |
| KG: ex-colegas (ORCID) | 0,01 | 0,01 | 0,06 | 0,45 | 0,19 | 0,01 | 0,01 | 0,01 | 0 |
| Texto: TF-IDF | 0,48 | 1,36 | 0,65 | 3,79 | 1,88 | 2,49 | 5,12 | 23,46 | 235.220 |
| Popularidade (grau) | 0,05 | 0,13 | 0,12 | 0,89 | 0,51 | 0,38 | 1,06 | 23,40 | 231.548 |
| **União (RRF)** | 3,41 | 5,84 | 5,37 | 23,61 | 13,59 | 8,01 | 11,43 | 23,46 | 235.434 |

### Matemática (414 alvos)

| Gerador | R@10 | R@50 | NDCG@10 | Hits@10 | MRR | Alcance@200 | Alcance@1000 | Alcance total | Conjunto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Coautoria: vizinhos comuns | 2,93 | 6,22 | 3,50 | 18,36 | 8,50 | 10,65 | 11,87 | 11,97 | 62 |
| Coautoria: Adamic-Adar | 3,07 | 7,29 | 3,74 | 18,84 | 9,46 | 11,30 | 11,94 | 11,97 | 62 |
| Coautoria: Resource Allocation | 3,05 | 7,12 | 3,37 | 17,39 | 7,90 | 11,34 | 11,94 | 11,97 | 62 |
| PageRank personalizado | 4,06 | 9,56 | 4,82 | 22,46 | 11,11 | 14,32 | 19,06 | 27,50 | 61.540 |
| KG: mesma instituição | 0,63 | 2,13 | 1,15 | 6,28 | 3,05 | 4,02 | 5,20 | 5,32 | 170 |
| KG: mesma organização-mãe | 0,87 | 1,97 | 1,26 | 6,76 | 3,08 | 4,09 | 5,21 | 5,39 | 197 |
| KG: tópicos (cosseno) | 0,85 | 2,41 | 0,94 | 5,31 | 2,64 | 7,03 | 16,70 | 28,69 | 13.393 |
| KG: mesmo periódico | 0,70 | 2,40 | 1,07 | 7,00 | 3,07 | 5,09 | 8,51 | 22,07 | 21.656 |
| KG: citação direta | 2,53 | 4,42 | 3,21 | 17,63 | 8,13 | 5,23 | 5,43 | 5,43 | 15 |
| KG: acoplamento bibliográfico | 4,00 | 7,93 | 4,17 | 19,08 | 9,71 | 13,40 | 18,63 | 21,88 | 6.232 |
| KG: ex-colegas (ORCID) | 0,09 | 0,09 | 0,30 | 1,45 | 1,24 | 0,09 | 0,09 | 0,09 | 0 |
| Texto: TF-IDF | 1,74 | 4,13 | 1,67 | 8,70 | 3,95 | 7,92 | 15,30 | 30,46 | 64.774 |
| Popularidade (grau) | 0,05 | 0,16 | 0,12 | 0,72 | 0,48 | 0,41 | 1,30 | 30,16 | 64.010 |
| **União (RRF)** | 4,15 | 11,36 | 4,99 | 23,67 | 12,19 | 16,87 | 23,05 | 30,46 | 64.998 |

### Economia (337 alvos)

| Gerador | R@10 | R@50 | NDCG@10 | Hits@10 | MRR | Alcance@200 | Alcance@1000 | Alcance total | Conjunto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Coautoria: vizinhos comuns | 1,61 | 4,69 | 2,30 | 12,46 | 6,06 | 6,55 | 7,16 | 7,24 | 36 |
| Coautoria: Adamic-Adar | 1,85 | 4,41 | 2,31 | 12,76 | 5,41 | 6,40 | 7,18 | 7,24 | 36 |
| Coautoria: Resource Allocation | 1,46 | 4,34 | 1,59 | 9,50 | 4,20 | 6,26 | 7,18 | 7,24 | 36 |
| PageRank personalizado | 2,93 | 5,64 | 3,00 | 14,54 | 6,57 | 8,57 | 11,57 | 19,00 | 53.259 |
| KG: mesma instituição | 1,71 | 3,19 | 1,99 | 10,68 | 4,68 | 4,86 | 6,24 | 6,39 | 76 |
| KG: mesma organização-mãe | 1,74 | 2,90 | 2,12 | 10,98 | 5,28 | 4,18 | 5,59 | 6,64 | 84 |
| KG: tópicos (cosseno) | 0,10 | 1,02 | 0,07 | 0,89 | 0,43 | 2,12 | 5,78 | 19,61 | 14.726 |
| KG: mesmo periódico | 0,59 | 1,65 | 0,85 | 6,23 | 2,37 | 3,59 | 6,26 | 11,15 | 2.324 |
| KG: citação direta | 0,70 | 1,86 | 1,09 | 5,93 | 3,32 | 2,38 | 2,48 | 2,48 | 14 |
| KG: acoplamento bibliográfico | 1,14 | 2,20 | 1,15 | 6,53 | 2,92 | 4,76 | 8,48 | 12,75 | 4.825 |
| KG: ex-colegas (ORCID) | 0,40 | 0,40 | 0,39 | 1,48 | 0,81 | 0,40 | 0,40 | 0,40 | 0 |
| Texto: TF-IDF | 0,90 | 1,30 | 0,56 | 2,37 | 1,29 | 2,74 | 5,96 | 22,19 | 58.263 |
| Popularidade (grau) | 0,03 | 0,17 | 0,12 | 0,30 | 0,27 | 0,47 | 1,15 | 21,64 | 57.387 |
| **União (RRF)** | 3,25 | 6,08 | 3,71 | 18,10 | 8,42 | 10,00 | 13,56 | 22,19 | 58.415 |

## 4a. Gradiente — R@50 (baseline)

| Gerador | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 2,68 | 4,57 | 7,29 | 4,41 |
| PageRank personalizado | 2,89 | 5,13 | 9,56 | 5,64 |
| KG: mesma instituição | 0,76 | 2,59 | 2,13 | 3,19 |
| KG: tópicos (cosseno) | 0,18 | 0,55 | 2,41 | 1,02 |
| KG: acoplamento bibliográfico | 0,77 | 2,68 | 7,93 | 2,20 |
| Texto: TF-IDF | 0,25 | 1,36 | 4,13 | 1,30 |
| **União (RRF)** | 3,32 | 5,84 | 11,36 | 6,08 |

## 4b. Gradiente — Alcance@1000 (oráculo)

| Gerador | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 9,11 | 8,93 | 11,94 | 7,18 |
| PageRank personalizado | 10,05 | 10,77 | 19,06 | 11,57 |
| KG: mesma instituição | 4,57 | 5,39 | 5,20 | 6,24 |
| KG: tópicos (cosseno) | 1,79 | 4,85 | 16,70 | 5,78 |
| KG: acoplamento bibliográfico | 4,55 | 6,00 | 18,63 | 8,48 |
| Texto: TF-IDF | 2,00 | 5,12 | 15,30 | 5,96 |
| **União (RRF)** | 9,81 | 11,43 | 23,05 | 13,56 |

## 5. Onde se perde cada coautoria nova (União RRF, soma de pares)

| Base | Fora de T0 | Em T0, fora do conjunto | No conjunto, fora do top-1000 | Top-1000, fora do top-50 | Acerto no top-50 |
|---|---:|---:|---:|---:|---:|
| Medicina | 57,62 | 0,52 | 28,95 | 9,50 | 3,41 |
| Ciência da Computação | 72,27 | 0,95 | 16,02 | 6,83 | 3,92 |
| Matemática | 67,35 | 1,04 | 10,15 | 12,46 | 9,01 |
| Economia | 73,17 | 1,34 | 10,06 | 10,00 | 5,43 |

## 6. Por regime — R@50 / Alcance@1000

**Medicina** — warm: n=432, cool: n=17, cold: n=2, newcomer: n=15

| Gerador | warm | cool | cold | newcomer |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 2,89 / 9,82 | 0,00 / 0,00 | 0,00 / 0,00 | 0,00 / 0,00 |
| PageRank personalizado | 3,12 / 10,85 | 0,00 / 0,00 | 0,00 / 0,00 | 0,00 / 0,00 |
| KG: mesma instituição | 0,82 / 4,91 | 0,00 / 0,53 | 0,00 / 0,96 | 0,00 / 0,00 |
| KG: tópicos (cosseno) | 0,19 / 1,91 | 0,00 / 0,00 | 0,00 / 2,88 | 0,00 / 0,00 |
| KG: acoplamento bibliográfico | 0,82 / 4,90 | 0,00 / 0,00 | 0,96 / 2,88 | 0,00 / 0,00 |
| Texto: TF-IDF | 0,27 / 2,14 | 0,00 / 0,05 | 0,96 / 2,88 | 0,00 / 0,00 |
| **União (RRF)** | 3,58 / 10,56 | 0,00 / 0,27 | 0,00 / 2,88 | 0,00 / 0,00 |

**Ciência da Computação** — warm: n=377, cool: n=33, cold: n=7, newcomer: n=32

| Gerador | warm | cool | cold | newcomer |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 5,02 / 10,21 | 4,86 / 4,86 | 0,00 / 0,00 | 0,00 / 0,00 |
| PageRank personalizado | 5,73 / 12,02 | 4,36 / 9,14 | 0,00 / 0,00 | 0,00 / 0,00 |
| KG: mesma instituição | 2,75 / 5,83 | 2,61 / 5,40 | 6,12 / 6,12 | 0,00 / 0,00 |
| KG: tópicos (cosseno) | 0,42 / 5,15 | 2,63 / 6,77 | 0,00 / 2,04 | 0,00 / 0,00 |
| KG: acoplamento bibliográfico | 2,86 / 6,72 | 2,99 / 3,92 | 4,08 / 4,08 | 0,00 / 0,00 |
| Texto: TF-IDF | 1,33 / 5,50 | 2,53 / 5,56 | 4,08 / 6,12 | 0,00 / 0,00 |
| **União (RRF)** | 6,23 / 12,57 | 6,93 / 10,67 | 6,12 / 6,12 | 0,00 / 0,00 |

**Matemática** — warm: n=320, cool: n=63, cold: n=9, newcomer: n=22

| Gerador | warm | cool | cold | newcomer |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 8,51 / 14,48 | 4,68 / 4,95 | 0,00 / 0,00 | 0,00 / 0,00 |
| PageRank personalizado | 10,61 / 20,97 | 8,92 / 18,73 | 0,00 / 0,00 | 0,00 / 0,00 |
| KG: mesma instituição | 2,42 / 6,19 | 1,38 / 2,10 | 2,22 / 4,44 | 0,00 / 0,00 |
| KG: tópicos (cosseno) | 2,49 / 16,96 | 2,25 / 20,42 | 6,67 / 22,22 | 0,00 / 0,00 |
| KG: acoplamento bibliográfico | 7,57 / 19,78 | 11,04 / 19,37 | 18,15 / 18,15 | 0,00 / 0,00 |
| Texto: TF-IDF | 3,87 / 15,94 | 5,89 / 17,00 | 11,11 / 17,78 | 0,00 / 0,00 |
| **União (RRF)** | 11,75 / 24,49 | 12,69 / 23,61 | 15,93 / 24,44 | 0,00 / 0,00 |

**Economia** — warm: n=236, cool: n=62, cold: n=11, newcomer: n=28

| Gerador | warm | cool | cold | newcomer |
|---|---:|---:|---:|---:|
| Coautoria: Adamic-Adar | 5,62 / 9,44 | 2,59 / 3,13 | 0,00 / 0,00 | 0,00 / 0,00 |
| PageRank personalizado | 7,01 / 14,63 | 3,97 / 7,18 | 0,00 / 0,00 | 0,00 / 0,00 |
| KG: mesma instituição | 3,43 / 7,71 | 4,31 / 4,54 | 0,00 / 0,00 | 0,00 / 0,00 |
| KG: tópicos (cosseno) | 1,17 / 7,37 | 1,13 / 3,19 | 0,00 / 0,97 | 0,00 / 0,00 |
| KG: acoplamento bibliográfico | 3,08 / 10,47 | 0,12 / 5,99 | 0,53 / 1,40 | 0,00 / 0,00 |
| Texto: TF-IDF | 1,56 / 7,47 | 1,13 / 3,75 | 0,00 / 0,97 | 0,00 / 0,00 |
| **União (RRF)** | 7,70 / 16,14 | 3,72 / 12,01 | 0,00 / 1,40 | 0,00 / 0,00 |

## 7. Sensibilidade à M9 — R@50 da União (com / sem a regra)

| Base | Com M9 | Sem M9 | Δ (pp) |
|---|---:|---:|---:|
| Medicina | 3,32 | 3,32 | 0,00 |
| Ciência da Computação | 5,84 | 5,85 | -0,01 |
| Matemática | 11,36 | 11,20 | 0,16 |
| Economia | 6,08 | 6,04 | 0,04 |
