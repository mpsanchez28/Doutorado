# Resultados da coleta e higienização das bases

> Gerado por `scripts/report_bases.py` em 10/10/2026 01:17. Métodos: `docs/METODOLOGIA_DADOS.md`.

## 1. Total de registros coletados

| Base | Status | Coletada em | Sementes | Candidatos expandidos | Trabalhos | (dos quais, só dos candidatos) | Autorias | Autores distintos | Autorias sem autor identificado |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Medicina | higienizada | 2026-10-09 | 1.000 | 15.000 | 597.149 | 502.727 | 6.322.476 | 1.166.030 | 121.451 (1.9%) |
| Ciência da Computação | higienizada | 2026-10-09 | 1.000 | 15.000 | 300.527 | 244.650 | 1.353.785 | 299.012 | 32.412 (2.4%) |
| Matemática | higienizada | 2026-10-09 | 1.000 | 15.000 | 146.979 | 107.596 | 405.706 | 82.239 | 9.414 (2.3%) |
| Economia | higienizada | 2026-10-09 | 1.000 | 15.000 | 103.545 | 74.916 | 321.584 | 82.487 | 7.983 (2.5%) |
| **Total** | | | 4.000 | 60.000 | 1.148.200 | 929.889 | 8.403.551 | 1.629.768 | 171.260 |

### 1.1 Funil dos critérios de inclusão de artigos (bruto → corpus limpo)

Aplicação sequencial dos critérios de `configs/filters.yaml`; entre parênteses, quantos trabalhos cada critério removeria isoladamente.

| Etapa | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| trabalhos coletados (bruto) | 597.149 (100.0%) | 300.527 (100.0%) | 146.979 (100.0%) | 103.545 (100.0%) |
| idioma = en | 597.149 (100.0%) · −0 isol. | 300.527 (100.0%) · −0 isol. | 146.979 (100.0%) · −0 isol. | 103.545 (100.0%) · −0 isol. |
| ano ≥ 2004 | 597.149 (100.0%) · −0 isol. | 300.527 (100.0%) · −0 isol. | 146.979 (100.0%) · −0 isol. | 103.545 (100.0%) · −0 isol. |
| com título | 597.117 (100.0%) · −32 isol. | 300.526 (100.0%) · −1 isol. | 146.963 (100.0%) · −16 isol. | 103.545 (100.0%) · −0 isol. |
| com abstract | 392.904 (65.8%) · −204.232 isol. | 221.192 (73.6%) · −79.334 isol. | 102.112 (69.5%) · −44.851 isol. | 60.926 (58.8%) · −42.619 isol. |
| com ≥1 autor identificado | 392.903 (65.8%) · −1 isol. | 221.192 (73.6%) · −0 isol. | 102.112 (69.5%) · −0 isol. | 60.926 (58.8%) · −0 isol. |

## 2. Corpus higienizado e densidade

| Base | Trabalhos | Pessoas | Autores/trabalho (média · mediana) | Trabalhos de 1 autor | Trabalhos > 50 autores | Período |
|---|---:|---:|---:|---:|---:|---|
| Medicina | 392.861 | 951.376 | 10.66 · 8 | 2.5% | 4256 | 2004–2026 |
| Ciência da Computação | 221.157 | 251.757 | 4.49 · 4 | 4.4% | 140 | 2004–2026 |
| Matemática | 101.887 | 69.339 | 2.75 · 2 | 18.0% | 40 | 2004–2026 |
| Economia | 60.882 | 62.493 | 3.10 · 3 | 19.0% | 25 | 2004–2026 |

**Gradiente de densidade (por polo):** medicina 10.66 (alto), computacao 4.49 (intermediario), economia 3.10 (baixo), matematica 2.75 (baixo) → **confirmado** — a ordem entre polos se mantém.

## 3. Identidade: níveis de evidência e vínculo institucional

| Base | A (reivindicada) | B (ORCID declarado) | C (sem ORCID) | X (rejeitada) | I1 (confirmado no ORCID) | I2 (ROR) | I3 (sem inst.) | ORCIDs fragmentados fundidos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Medicina | 5.2% | 76.0% | 18.4% | 0.3% | 5.8% | 78.7% | 15.5% | 5.538 (11.382 ids) |
| Ciência da Computação | 8.7% | 77.5% | 13.6% | 0.2% | 11.5% | 72.5% | 15.9% | 934 (1.890 ids) |
| Matemática | 15.3% | 70.0% | 14.0% | 0.8% | 15.5% | 58.9% | 25.6% | 162 (328 ids) |
| Economia | 12.4% | 65.2% | 22.0% | 0.4% | 13.0% | 53.0% | 34.0% | 118 (239 ids) |

## 4. Elegibilidade das sementes (E1–E8) e autores-alvo

| Base | Sementes (pessoas) | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | **Alvos** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Medicina | 988 | 100% | 100% | 64% | 99% | 98% | 85% | 95% | 100% | **487** (49.3%) |
| Ciência da Computação | 986 | 100% | 100% | 61% | 96% | 94% | 92% | 97% | 100% | **507** (51.4%) |
| Matemática | 968 | 100% | 100% | 61% | 95% | 92% | 98% | 95% | 100% | **535** (55.3%) |
| Economia | 947 | 100% | 100% | 54% | 90% | 88% | 99% | 97% | 99% | **465** (49.1%) |

Critérios: E1 ORCID · E2 sem conflito · E3 trabalho reivindicado · E4 instituição · E5 ≥2 trabalhos · E6 plausibilidade · E7 nome · E8 equipe ≤ teto.

## 5. Funil de elegibilidade (todas as pessoas)

**Medicina**

| Etapa | Restantes | Reprovam isolado |
|---|---:|---:|
| pessoas canônicas | 953.606 | — |
| E1_orcid — possui ORCID (identidade verificável) | 574.501 | 379.105 |
| E2_sem_conflito — sem ORCIDs conflitantes no mesmo author_id | 574.501 | 0 |
| E3_reivindicado — ≥ min_claimed_works trabalhos reivindicados no ORCID | 8.317 | 945.289 |
| E4_instituicao — ≥ min_works_with_ror autorias com instituição identificada | 8.307 | 119.921 |
| E5_atividade — ≥ min_works trabalhos na área | 8.296 | 495.254 |
| E6_plausivel — produtividade e multiafiliação plausíveis por ano | 6.695 | 3.557 |
| E7_nome — nome consistente entre artigo, OpenAlex e ORCID | 6.455 | 6.189 |
| E8_equipe — ≥1 trabalho dentro do teto de coautores (gera aresta) | 6.455 | 73.418 |

**Ciência da Computação**

| Etapa | Restantes | Reprovam isolado |
|---|---:|---:|
| pessoas canônicas | 252.103 | — |
| E1_orcid — possui ORCID (identidade verificável) | 179.448 | 72.655 |
| E2_sem_conflito — sem ORCIDs conflitantes no mesmo author_id | 179.448 | 0 |
| E3_reivindicado — ≥ min_claimed_works trabalhos reivindicados no ORCID | 6.744 | 245.359 |
| E4_instituicao — ≥ min_works_with_ror autorias com instituição identificada | 6.711 | 32.090 |
| E5_atividade — ≥ min_works trabalhos na área | 6.655 | 134.677 |
| E6_plausivel — produtividade e multiafiliação plausíveis por ano | 6.066 | 1.185 |
| E7_nome — nome consistente entre artigo, OpenAlex e ORCID | 6.002 | 706 |
| E8_equipe — ≥1 trabalho dentro do teto de coautores (gera aresta) | 6.002 | 5.469 |

**Matemática**

| Etapa | Restantes | Reprovam isolado |
|---|---:|---:|
| pessoas canônicas | 69.641 | — |
| E1_orcid — possui ORCID (identidade verificável) | 50.357 | 19.284 |
| E2_sem_conflito — sem ORCIDs conflitantes no mesmo author_id | 50.357 | 0 |
| E3_reivindicado — ≥ min_claimed_works trabalhos reivindicados no ORCID | 5.837 | 63.804 |
| E4_instituicao — ≥ min_works_with_ror autorias com instituição identificada | 5.777 | 10.704 |
| E5_atividade — ≥ min_works trabalhos na área | 5.469 | 36.087 |
| E6_plausivel — produtividade e multiafiliação plausíveis por ano | 5.399 | 119 |
| E7_nome — nome consistente entre artigo, OpenAlex e ORCID | 5.273 | 708 |
| E8_equipe — ≥1 trabalho dentro do teto de coautores (gera aresta) | 5.273 | 1.266 |

**Economia**

| Etapa | Restantes | Reprovam isolado |
|---|---:|---:|
| pessoas canônicas | 62.757 | — |
| E1_orcid — possui ORCID (identidade verificável) | 40.897 | 21.860 |
| E2_sem_conflito — sem ORCIDs conflitantes no mesmo author_id | 40.897 | 0 |
| E3_reivindicado — ≥ min_claimed_works trabalhos reivindicados no ORCID | 4.650 | 58.107 |
| E4_instituicao — ≥ min_works_with_ror autorias com instituição identificada | 4.548 | 15.393 |
| E5_atividade — ≥ min_works trabalhos na área | 4.221 | 36.932 |
| E6_plausivel — produtividade e multiafiliação plausíveis por ano | 4.200 | 33 |
| E7_nome — nome consistente entre artigo, OpenAlex e ORCID | 4.169 | 405 |
| E8_equipe — ≥1 trabalho dentro do teto de coautores (gera aresta) | 4.169 | 1.275 |

## 6. Gate de rede e auditoria

| Base | Gate | Trabalhos | Autores | Peso médio coautoria | Pares peso ≥3 | Abstract | Auditoria |
|---|---|---:|---:|---:|---:|---:|---|
| Medicina | aprovado | 392.861 | 951.376 | 1.732 | 2.742.960 | 1.0 | reprovada |
| Ciência da Computação | aprovado | 221.157 | 251.757 | 1.582 | 174.839 | 1.0 | reprovada |
| Matemática | aprovado | 101.887 | 69.339 | 1.698 | 39.799 | 1.0 | reprovada |
| Economia | aprovado | 60.882 | 62.493 | 1.411 | 24.265 | 1.0 | reprovada |

## 7. Enriquecimento (camadas 1–3)

| Base | Corpus | Trabalhos com tópico | Tópicos/trabalho | Tópico principal no campo da base | Instituições | com ROR | com ancestral | Pessoas ORCID com vínculo | com emprego datado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Medicina | higienizado | 100.0% | 3.0 | 100.0% | 31.454 | 100.0% | 25.2% | 2.0% | 1.4% |
| Ciência da Computação | higienizado | 100.0% | 3.0 | 100.0% | 15.084 | 100.0% | 26.8% | 4.9% | 3.4% |
| Matemática | higienizado | 100.0% | 3.0 | 100.0% | 9.857 | 100.0% | 25.4% | 14.8% | 10.1% |
| Economia | higienizado | 100.0% | 3.0 | 100.0% | 10.219 | 100.0% | 23.7% | 29.4% | 20.9% |

**Diagnóstico de sinal** — lift = P(relação | coautoria nova em T1) ÷ P(relação | par aleatório), relações calculadas só com T0 (`docs/ENRIQUECIMENTO.md` §5):

| Relação | Medicina | Ciência da Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| ex_colegas_orcid | 4.26× (3% vs 1%; cob. 1%) | 3.51× (3% vs 1%; cob. 1%) | ∞ (5.4% vs 0%; cob. 3%) | ∞ (5.9% vs 0%; cob. 25%) |
| mesma_instituicao | 19.62× (37% vs 2%; cob. 40%) | 24.59× (24% vs 1%; cob. 25%) | 20.7× (21% vs 1%; cob. 28%) | 24.6× (24% vs 1%; cob. 23%) |
| mesma_org_mae | 16.29× (38% vs 2%; cob. 40%) | 20.87× (25% vs 1%; cob. 25%) | 19.17× (21% vs 1%; cob. 28%) | 20.85× (25% vs 1%; cob. 23%) |
| mesmo_pais | 3.44× (78% vs 23%; cob. 40%) | 3.11× (66% vs 21%; cob. 25%) | 3.02× (56% vs 19%; cob. 28%) | 3.22× (46% vs 14%; cob. 23%) |
| mesmo_subcampo_principal | 5.49× (31% vs 6%; cob. 42%) | 2.39× (46% vs 19%; cob. 27%) | 3.91× (73% vs 19%; cob. 31%) | 1.56× (73% vs 47%; cob. 25%) |
| similaridade_subcampos>0,5 | 5.43× (42% vs 8%; cob. 42%) | 2.35× (60% vs 26%; cob. 27%) | 3.8× (80% vs 21%; cob. 31%) | 1.54× (86% vs 56%; cob. 25%) |
