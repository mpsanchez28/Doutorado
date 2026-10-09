# Plano de enriquecimento da base — próximo passo

Pré-requisito: as 4 bases do gradiente coletadas, higienizadas e validadas
(`docs/RESULTADOS_BASES.md`). Métodos de coleta: `docs/METODOLOGIA_DADOS.md`.

## 1. Por que enriquecer — e o que NÃO repetir

**Objetivo:** transformar a rede heterogênea atual num **grafo de conhecimento**, com relações
tipadas, semanticamente definidas e alinhadas a vocabulários externos. É a crítica mais forte da
banca (*"KG ≠ rede heterogênea"*) e abre três usos mensuráveis:
1. **Fonte de candidatos** — semântica explícita (tópico, instituição) como gerador de
   candidatos ao lado da estrutura (2-hop) e do texto (SciBERT) — teste T7;
2. **Atributos do ranqueador** — relações do KG como features do RF/2 etapas — teste T6;
3. **Explicação** — justificativas tipadas ("mesmo subcampo", "mesma instituição em 2015").

**O que não repetir como eixo principal:** o enriquecimento **generativo** (LLM extraindo tipo de
artigo, contribuição e estilo) já foi testado e teve efeito nulo; a banca recomendou tratá-lo
como secundário. Ele fica como experimento de apêndice.

**Princípio de avaliação:** cada camada só permanece no modelo se (a) melhorar significativamente
o ranqueamento (Wilcoxon + Bonferroni, IC95% bootstrap) ou (b) aumentar a cobertura de
explicações. Resultado nulo é registrado como tal — o KG mantém valor de explicação e de
documentação semântica.

## 2. Camadas de enriquecimento (por prioridade)

Viabilidade medida em amostra aleatória de Economia (n = 200, outubro de 2026).

| # | Camada | Fonte | Cobertura | Relações / atributos novos | Uso previsto |
|---|---|---|---:|---|---|
| **1** | **Semântica temática** | OpenAlex *Topics* | 100% (≈3 tópicos/trabalho) | `HAS_TOPIC` (score) → tópico → subcampo → campo → domínio; perfil temático do autor | substitui os *Concepts* ruidosos; 3ª fonte de candidatos (T7); feature `n_subcampos_comuns` (T6); explicação |
| **2** | **Instituições** | OpenAlex *Institutions* + ROR | tipo 100%, país 98%, hierarquia 100% (das afiliações) | `AFFILIATED_WITH` com ano; `PART_OF` (organização-mãe); `LOCATED_IN` (país); tipo (universidade, hospital, empresa, governo) | features `mesma_instituicao`, `mesma_org_mae`, `mesmo_pais`, `par_de_tipos` (T6); explicação |
| **3** | **Trajetória de carreira** | ORCID (**já em cache**) | 67% com emprego/formação; 32% com ano de conclusão | histórico de vínculos; estágio de carreira (anos desde a formação); mobilidade | feature `ja_foram_colegas_de_instituicao` (preditor clássico de colaboração); análise por estágio de carreira |
| **4** | **Veículos** | OpenAlex *Sources* | 95% | `PUBLISHED_IN` tipado (periódico, conferência, repositório); editora | feature `mesmo_veiculo`; explicação |
| **5** | **Ontologia e alinhamento externo** | FOAF, Schema.org, FaBiO/CiTO, Wikidata | — | mapeamento de classes e relações; exportação RDF/Turtle de amostra | resposta direta à banca (T16); não altera números |
| 6 | Citações | OpenAlex `referenced_works` | 44% (Economia) | `CITES`, co-citação, acoplamento bibliográfico | feature `cita_ou_citado`; cobertura parcial |
| 7 | Representações textuais modernas | bge-m3, e5, SPECTER2 | 100% (abstract) | embeddings como atributo de nó | T9 — exige GPU (créditos de nuvem) |
| 8 | Financiamento e ODS | OpenAlex `funders`/`awards`, SDGs | 12% / 52% | `FUNDED_BY`, `ADDRESSES_SDG` | secundário (cobertura baixa) |
| 9 | Generativo (LLM) | — | — | categorias extraídas do texto | apêndice; já testado (nulo) |

## 3. Arquitetura

O enriquecimento é uma **etapa separada**, posterior à higienização. A coleta trata de
identidade e estrutura; o enriquecimento, de semântica e atributos:

```
corpus higienizado ──► scripts/enrich_base.py <base>
                          ├─ busca em lote por ID no OpenAlex (50 trabalhos/consulta, cache)
                          ├─ instituições e veículos por ID; ROR para tipos e hierarquia
                          └─ trajetórias a partir do cache ORCID (sem rede)
                       ──► data/processed/enrich_<base>/
                              work_topics · institutions · author_careers · sources · citations
                       ──► graph/hetero.py (KG v2, tipado)  ──► ontologia + export RDF
```

**Custo estimado:** ~30 min por base em consultas sequenciais ao OpenAlex (~100 mil trabalhos),
menos com paralelismo; as trajetórias vêm do cache ORCID já existente. Rodar **depois** que a
coleta terminar, para não disputar o limite de requisições da API.

## 4. Avaliação

| Teste | Pergunta | Métrica |
|---|---|---|
| T6 — relações do KG como features | As relações tipadas melhoram o topo do ranking? | NDCG@10, R@10 por base e regime |
| T7 — tópicos/instituições como fonte de candidatos | A semântica explícita amplia o alcance como o texto amplia? | R@200, cobertura do oráculo, regime cold |
| Explicabilidade por camada | Que fração das recomendações ganha justificativa tipada? | % explicável por camada |
| Gradiente (H3) | O valor de cada camada varia com a densidade da área? | Δ por base × densidade |

Todas as comparações com Wilcoxon pareado + Bonferroni e IC95% bootstrap, nas 4 bases.

## 5. Ordem proposta
1. Camadas **1, 2 e 3** — maior cobertura, menor custo, respostas diretas à banca.
2. Camada **5** (ontologia) — documentação semântica do KG v2.
3. Testes **T6 e T7** com as camadas 1–3.
4. Camadas **4 e 6**; depois **7** (GPU); **8 e 9** como secundárias.

## 6. Riscos
- **As relações podem não melhorar o ranking.** A ablação anterior mostrou que, na GNN, só a
  coautoria carregava sinal. Diferenças agora: as relações entram como **features do
  ranqueador** e **fontes de candidatos**, não como mensagens da GNN; e os dados são mais limpos
  (Topics em vez de Concepts). Se ainda assim forem nulas, o KG fica justificado pela explicação
  e pela semântica — resposta pronta para a banca.
- **Cobertura desigual entre áreas** (ex.: referências e financiamento) — reportar a cobertura por
  base e não comparar camadas incompletas entre áreas sem ajuste.
