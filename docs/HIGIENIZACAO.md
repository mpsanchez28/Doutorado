# Higienização de autores — métodos, critérios e evidências

Responde aos pareceres da banca (Thiago Magela: *dados ruidosos do OpenAlex, desambiguação,
atribuição, citar BRCris, informar limitações*). Objetivo: garantir, **antes de qualquer
modelagem**, que cada coautoria usada no grafo e na verdade fundamental liga **a pessoa
certa, ao trabalho certo, na instituição certa** — usando o **ORCID** como âncora de
identidade — e que todo autor avaliado satisfaz critérios explícitos de elegibilidade.

Implementação: `src/coauthor_rec/data/hygiene.py` (regras), `src/coauthor_rec/data/orcid.py`
(API pública do ORCID), `scripts/hygiene.py` (orquestração, chamado por `build_base.py`).
Parâmetros: `configs/filters.yaml › hygiene` (fonte única). Testes: `tests/test_hygiene.py`.

---

## 1. A cadeia que precisa ser garantida

```
 PESSOA ──(ORCID)──► author_id(s) do OpenAlex ──► AUTORIA ──► TRABALHO (DOI)
    │                       ▲ funde fragmentos        │             │
    │                       └ rejeita conflitos        ▼             ▼
    └──── afiliações declaradas ────────────► INSTITUIÇÃO (ROR / nome+país+ano)
                                                       │
            AUTORIA válida ◄──── mesmo trabalho ────► AUTORIA válida
                         └────────── ARESTA DE COAUTORIA ──────────┘
```

Um erro em qualquer elo contamina a tarefa: um autor **fragmentado** em dois ids faz uma
colaboração antiga parecer **nova** em T1 (falso positivo na verdade fundamental); dois
homônimos **fundidos** num id criam arestas entre pessoas que nunca colaboraram; uma
autoria **mal atribuída** liga o nome errado ao trabalho e, por consequência, ao coautor.

## 2. Evidência empírica que fundamentou o desenho (OpenAlex/ORCID, 09/10/2026)

Amostras aleatórias da API (`sample`, ≥2004, inglês, com abstract), nas 4 áreas do gradiente:

| Área | Autorias c/ ORCID | c/ instituição (ROR) | Works c/ DOI | Works c/ **todos** autores ORCID |
|---|---:|---:|---:|---:|
| Medicina | 62% | 76% | 80% | 26% |
| Computação | 65% | 71% | 79% | 36% |
| Economia | 58% | 55% | 72% | 34% |
| Matemática | 64% | 76% | 80% | 38% |

Verificação contra o registro ORCID (n=15 por área, indicativo):

| Área | DOI do trabalho **reivindicado** no ORCID | ORCID sem trabalhos públicos | ROR da autoria no ORCID |
|---|---:|---:|---:|
| Computação | 40% | 20% | 1/6 |
| Medicina | 47% | 20% | 2/12 |
| Economia | 33% | 33% | 3/12 |
| Matemática | 20% | 7% | 2/12 |

Outros achados: **5,5%** das autorias não têm `author_id` (autor não resolvido); **16%** dos
ORCIDs estão ligados a **mais de um** `author_id` no OpenAlex (pessoa fragmentada); **0%**
de divergência entre o `author_id` da autoria e o dono do ORCID quando ambos existem.

**Consequências de desenho:**
1. Exigir ORCID de **todos** os autores eliminaria 62–74% dos trabalhos e destruiria a rede →
   o ORCID entra em **camadas**: obrigatório para quem é **avaliado** (alvo/semente) e como
   **nível de confiança** para os demais vínculos.
2. O ORCID anexado pelo OpenAlex vem, em geral, da metadata do editor (autor declara na
   submissão) — evidência forte, mas distinta de a pessoa **reivindicar** o trabalho no próprio
   registro (20–47%). Daí dois níveis distintos (A e B).
3. Afiliações no ORCID são desambiguadas majoritariamente por **RINGGOLD/GRID**, não ROR →
   casar instituição só por ROR subestima muito; usa-se ROR **ou** nome normalizado + país,
   com compatibilidade de ano.
4. A fragmentação (16%) é corrigida tomando o **ORCID como chave canônica da pessoa**.

## 3. Métodos

### M1 — Exclusão de autorias não resolvidas
Autoria sem `author_id` não pode ser ligada a pessoa alguma → excluída (`require_fields`),
contabilizada no relatório (`autorias_sem_author_id`).

### M2 — Pessoa canônica por ORCID
- `canonical_id = "orcid:<ORCID>"` se o `author_id` tem exatamente um ORCID; senão o `author_id`.
- **Fusão de fragmentos:** todos os `author_id` com o mesmo ORCID viram a mesma pessoa; o
  corpus higienizado usa `canonical_id` como `author_id` (original em `author_id_openalex`)
  e deduplica (trabalho, pessoa).
- **Conflito:** `author_id` com >1 ORCID = identidade fundida → todas as suas autorias X.

### M3 — Nível de evidência de cada autoria (autor × trabalho)
Regras na ordem:
| Nível | Regra | Significado |
|---|---|---|
| **X** | conflito de identidade **ou** nome no artigo incompatível com o nome canônico | rejeitada (não entra no grafo) |
| **A** | ORCID + DOI do trabalho listado nos trabalhos do registro ORCID | autoria **reivindicada pela própria pessoa** |
| **B** | ORCID declarado na publicação, DOI não reivindicado | autoria **declarada** (metadata do editor) |
| **C** | sem ORCID (ou ORCID cujo registro traz nomes incompatíveis com o autor) | identidade só do OpenAlex, consistente |

Um ORCID cujo registro lista apenas nomes incompatíveis com o autor **rebaixa A/B → C**
(o ORCID anexado não confirma a pessoa).

### M4 — Consistência de nome
Nomes normalizados (sem acento, *casefold*, pontuação de nome → espaço). Dois nomes são
compatíveis se compartilham ao menos um token significativo (≥2 letras, exceto partículas
*de, da, van, von…*) — tolera iniciais, ordem invertida e acentos. Comparações: nome no
artigo (`raw_author_name`) × nome canônico (OpenAlex) × nomes do registro ORCID.

### M5 — Vínculo autor–instituição
| Nível | Regra |
|---|---|
| **I1** | instituição da autoria confirmada no ORCID: mesmo **ROR**, ou mesmo **nome normalizado + país**, com o ano do trabalho dentro do período do vínculo (±1 ano) |
| **I2** | instituição identificada por ROR no OpenAlex, não confirmada no ORCID |
| **I3** | sem instituição identificada (não invalida a autoria) |

### M6 — Coautoria validada
Aresta (a, b) existe se a e b têm autorias **não rejeitadas** no mesmo trabalho, o trabalho
respeita o teto de coautores (50) e a ≠ b **após a canonicalização** (evita auto-laço de
fragmentos). Confiança da aresta = menor nível das duas pontas. `min_edge_level` define o
mínimo aceito no corpus (padrão `C`; análise de sensibilidade com `B` = só pessoas com ORCID).

### M7 — Elegibilidade do autor como alvo/semente (todos obrigatórios)
| Critério | Regra (parâmetro em `filters.yaml`) | Por quê |
|---|---|---|
| **E1** Identidade | possui ORCID | identidade verificável externamente |
| **E2** Unicidade | sem ORCIDs conflitantes no mesmo `author_id` | evita pessoas fundidas |
| **E3** Âncora de autoria | ≥1 trabalho com DOI **reivindicado** no ORCID | prova que o ORCID é de quem escreveu |
| **E4** Vínculo institucional | ≥1 autoria com instituição identificada (I1/I2) | liga pessoa a instituição |
| **E5** Atividade | ≥2 trabalhos na área no período | perfil mínimo para recomendar |
| **E6** Plausibilidade | ≤30 trabalhos/ano e ≤3 **grupos de afiliação desconexos** no mesmo ano | produtividade/afiliações implausíveis indicam identidade fundida |
| **E7** Nome | nenhuma autoria com nome incompatível (artigo/OpenAlex/ORCID) | consistência da atribuição |
| **E8** Equipe | ≥1 trabalho dentro do teto de coautores | sem isso o autor não gera arestas |

**Sobre o E6:** instituições co-listadas numa mesma autoria (universidade + hospital +
instituto) formam **um** grupo — multiafiliação legítima. No piloto, contar instituições
avulsas reprovava 6,5% dos autores indevidamente; com grupos, 0%.

**Uso:** alvos de avaliação e sementes de coleta = autores **elegíveis**. O catálogo de
candidatos e as arestas usam todas as pessoas com autorias não rejeitadas (A/B/C) — coautores
sem ORCID continuam sendo pessoas reais, com confiança menor e explicitada.

### M8 — Relatório, funil e auditoria manual
Cada base gera `runs/<base>/hygiene.json` (níveis, fusões, vínculos, **funil de atrito E1→E8**
com reprovação sequencial e isolada) e `data/processed/autores_<base>.csv` (critérios por
pessoa). Complementarmente, `scripts/audit_authors.py` diagnostica o bruto (homônimos,
fragmentação por nome, produtividade) e sorteia **200 autores** para verificação humana
(`audit_sample.csv`, com links OpenAlex/ORCID; autores brasileiros cruzados com
**Lattes/BRCris**) — estimativa da taxa de erro residual a reportar na tese.

## 4. Piloto (Computação, 151 works reais, 09/10/2026)

| Etapa | Resultado |
|---|---|
| Autorias brutas / sem `author_id` | 1.194 / 42 (3,5%) |
| `author_id` → pessoas canônicas | 744 → 743 (1 ORCID fragmentado fundido) |
| Níveis A / B / C / X | 315 / 320 / 218 / 2 (37% / 37% / 25% / 0,2%) |
| Vínculo I1 / I2 / I3 | 231 / 565 / 57 — **27% confirmado no ORCID** |
| Funil E1→E8 | 743 → 553 (E1) → 277 (E3) → 269 (E4) → 33 (E5) → **33 elegíveis** |

O corte em **E5** é artefato do piloto (amostra de trabalhos: cada autor aparece ~1 vez).

### Piloto 2 — coleta `seeded` (Economia, 100 sementes com histórico completo)

| Etapa | Resultado |
|---|---|
| Pessoas / ORCIDs / fragmentados fundidos | 2.231 / 1.361 / 5 ORCIDs (10 author_ids) |
| Níveis A / B / C / X (todas as autorias) | 1.237 / 3.885 / 1.844 / 25 (18% / 56% / 26% / 0,4%) |
| Vínculo I1 / I2 / I3 | 1.668 / 2.511 / 2.787 (24% confirmado no ORCID) |
| Aprovação das **sementes** por critério | E1 100% · E2 100% · **E3 46%** · E4 91% · E5 91% · E6 99% · E7 98% · E8 100% |
| **Alvos** (semente ∩ elegível) | **39 de 93 (42%)** |

Com o histórico completo, E5 deixa de ser problema (91%). O critério que define o tamanho
da amostra de alvos é o **E3** (trabalho reivindicado no próprio ORCID): é a garantia mais
forte de identidade, mas depende de a pessoa manter o registro. Decisão de protocolo:
manter **E3 estrito para os alvos** e rodar uma **análise de sensibilidade com E3 relaxado**
(`min_claimed_works: 0`, identidade pelo nível B) — se as conclusões se mantêm, o viés de
manutenção do ORCID não as explica. Para ter N alvos, coletam-se ~2,4·N sementes.

## 5. Limitações e vieses a declarar

1. **Viés de adoção do ORCID** — a adoção varia por país, área e geração; exigir ORCID dos
   alvos pode enviesar a amostra. Mitigação: reportar a distribuição (país, nº de trabalhos,
   ano do 1º trabalho) de elegíveis × não elegíveis.
2. **E3 depende de a pessoa manter o ORCID** — autores legítimos com registro vazio (7–33%)
   são excluídos dos alvos (não do grafo).
3. **Regra de nome tolerante** — prioriza não rejeitar transliterações; homônimos com
   sobrenome comum só são separados pelo ORCID.
4. **Instituições** — erros de parsing de afiliação do OpenAlex persistem em I2/I3.
5. **Bases antigas** — a base IA atual (e todos os resultados até out/2026) é **anterior** à
   higienização (coleta sem ORCID/DOI/ROR); re-coletar com `build_base.py ia --recollect`
   para comparar antes × depois.

## 6. Integração com a amostragem (aprovada — modo `seeded`; alvos = sementes ∩ elegíveis)

A ordem padrão da API é por citações — os mais citados têm equipes 1,7–3× maiores e
invertem o gradiente da H3; e o filtro por Concepts aceita marcações com score 0 (física de
partículas dentro de "Economia"). Por isso a área é o **campo do primary topic** e as
**sementes são aleatórias** (um autor com ORCID por artigo sorteado), com o **histórico
completo** coletado (`docs/SELECAO_BASES.md`). Isso (i) torna a amostra representativa,
(ii) responde à crítica de "uma semente gera viés" com milhares de sementes e (iii) faz E3/E5
serem avaliados sobre o histórico completo. Autores que só aparecem em consórcios (acima do
teto de coautores) não contam para a parada da coleta nem recebem consulta ORCID.

## 7. Reprodução

```bash
PYTHONHASHSEED=0 python scripts/build_base.py computacao          # coleta + higieniza + gate + auditoria
PYTHONHASHSEED=0 python scripts/hygiene.py computacao --offline   # só re-higieniza (cache ORCID)
pytest tests/test_hygiene.py
```
