# Resultados da coleta e higienização das bases

> Gerado por `scripts/report_bases.py` em 09/10/2026 11:16. Métodos: `docs/METODOLOGIA_DADOS.md`.

## 1. Total de registros coletados

| Base | Status | Coletada em | Sementes | Trabalhos | Autorias | Autores distintos | Autorias sem autor identificado |
|---|---|---|---:|---:|---:|---:|---:|
| Medicina | não coletada | — | — | — | — | — | — |
| Ciência da Computação | não coletada | — | — | — | — | — | — |
| Matemática | coletada — higienização pendente | 2026-10-09 | 2.765 | 130.515 | 345.942 | 61.937 | 7.592 (2.2%) |
| Economia | higienizada | 2026-10-09 | 2.930 | 99.383 | 278.926 | 62.303 | 6.906 (2.5%) |
| **Total** | | | 5.695 | 229.898 | 624.868 | 124.240 | 14.498 |

### 1.1 Funil dos critérios de inclusão de artigos (bruto → corpus limpo)

Aplicação sequencial dos critérios de `configs/filters.yaml`; entre parênteses, quantos trabalhos cada critério removeria isoladamente.

| Etapa | Matemática | Economia |
|---|---:|---:|
| trabalhos coletados (bruto) | 130.515 (100.0%) | 99.383 (100.0%) |
| idioma = en | 130.515 (100.0%) · −0 isol. | 99.383 (100.0%) · −0 isol. |
| ano ≥ 2004 | 130.515 (100.0%) · −0 isol. | 99.383 (100.0%) · −0 isol. |
| com título | 130.478 (100.0%) · −37 isol. | 99.382 (100.0%) · −1 isol. |
| com abstract | 88.535 (67.8%) · −41.943 isol. | 58.222 (58.6%) · −41.161 isol. |
| com ≥1 autor identificado | 88.535 (67.8%) · −0 isol. | 58.222 (58.6%) · −0 isol. |

**Higienização ainda não concluída:** Medicina, Ciência da Computação, Matemática — as seções 2 a 6 aparecem quando a base for higienizada.


## 2. Corpus higienizado e densidade

| Base | Trabalhos | Pessoas | Autores/trabalho (média · mediana) | Trabalhos de 1 autor | Trabalhos > 50 autores | Período |
|---|---:|---:|---:|---:|---:|---|
| Economia | 58.157 | 47.431 | 2.78 · 2 | 23.5% | 22 | 2004–2026 |

## 3. Identidade: níveis de evidência e vínculo institucional

| Base | A (reivindicada) | B (ORCID declarado) | C (sem ORCID) | X (rejeitada) | I1 (confirmado no ORCID) | I2 (ROR) | I3 (sem inst.) | ORCIDs fragmentados fundidos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Economia | 20.8% | 58.9% | 19.9% | 0.4% | 21.7% | 43.4% | 34.9% | 151 (306 ids) |

## 4. Elegibilidade das sementes (E1–E8) e autores-alvo

| Base | Sementes (pessoas) | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | **Alvos** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Economia | 2.775 | 100% | 100% | 53% | 90% | 88% | 99% | 97% | 99% | **1.343** (48.4%) |

Critérios: E1 ORCID · E2 sem conflito · E3 trabalho reivindicado · E4 instituição · E5 ≥2 trabalhos · E6 plausibilidade · E7 nome · E8 equipe ≤ teto.

## 5. Funil de elegibilidade (todas as pessoas)

**Economia**

| Etapa | Restantes | Reprovam isolado |
|---|---:|---:|
| pessoas canônicas | 47.694 | — |
| E1_orcid — possui ORCID (identidade verificável) | 30.203 | 17.491 |
| E2_sem_conflito — sem ORCIDs conflitantes no mesmo author_id | 30.203 | 0 |
| E3_reivindicado — ≥ min_claimed_works trabalhos reivindicados no ORCID | 11.912 | 35.782 |
| E4_instituicao — ≥ min_works_with_ror autorias com instituição identificada | 11.282 | 12.568 |
| E5_atividade — ≥ min_works trabalhos na área | 7.056 | 28.477 |
| E6_plausivel — produtividade e multiafiliação plausíveis por ano | 7.039 | 29 |
| E7_nome — nome consistente entre artigo, OpenAlex e ORCID | 7.005 | 590 |
| E8_equipe — ≥1 trabalho dentro do teto de coautores (gera aresta) | 7.005 | 1.464 |

## 6. Gate de rede e auditoria

| Base | Gate | Trabalhos | Autores | Peso médio coautoria | Pares peso ≥3 | Abstract | Auditoria |
|---|---|---:|---:|---:|---:|---:|---|
| Economia | aprovado | 58.157 | 47.431 | 1.486 | 19.737 | 1.0 | reprovada |

## 7. Enriquecimento (camadas 1–3)

| Base | Corpus | Trabalhos com tópico | Tópicos/trabalho | Tópico principal no campo da base | Instituições | com ROR | com ancestral | Pessoas ORCID com vínculo | com emprego datado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Economia | higienizado | 100.0% | 3.0 | 100.0% | 8.899 | 100.0% | 22.5% | 65.6% | 46.1% |

**Diagnóstico de sinal** — lift = P(relação | coautoria nova em T1) ÷ P(relação | par aleatório), relações calculadas só com T0 (`docs/ENRIQUECIMENTO.md` §5):

| Relação | Economia |
|---|---:|
| ex_colegas_orcid | 101.99× (6% vs 0%; cob. 24%) |
| mesma_instituicao | 22.88× (25% vs 1%; cob. 11%) |
| mesma_org_mae | 18.24× (27% vs 1%; cob. 11%) |
| mesmo_pais | 3.42× (54% vs 16%; cob. 11%) |
| mesmo_subcampo_principal | 1.47× (71% vs 48%; cob. 12%) |
| similaridade_subcampos>0,5 | 1.46× (83% vs 56%; cob. 12%) |
