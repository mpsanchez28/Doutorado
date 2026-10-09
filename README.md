# Doutorado — Recomendação de coautoria científica (coauthor-rec)

Recomendação de coautoria por **predição de links futuros** em redes acadêmicas do
**OpenAlex** — sistema híbrido **texto (SciBERT/CNN) + estrutura (GNN)** sobre um Grafo de
Conhecimento heterogêneo, avaliado sob split temporal (T0→T1) nos regimes *warm/cool/cold*.

> **Projeto de Doutorado** · PPgSI — EACH/USP
> Pesquisador: **Marcos Paulo Sanchez** · Orientador: **Prof. Dr. Luciano Antonio Digiampietri**

## Estado atual

Pipeline completo e reprodutível, do OpenAlex à avaliação, com **49 testes**. A hipótese
central foi testada com rigor: a fusão de representações CNN+GNN **não** superou o melhor
modelo topológico, mas o diagnóstico levou a um achado mais forte — **o gargalo é a geração
de candidatos, não a representação**. O modelo vencedor é o **reranker de 2 etapas
(RF→texto)**, o primeiro a vencer todos os demais em todas as faixas de K e regimes (com
significância) e a ultrapassar o teto do oráculo topológico. No **cold-start**, onde a
topologia zera, só o texto funciona.

### Documentação
| Tema | Documento |
|---|---|
| Comparativo crítico dos modelos | [docs/COMPARATIVO_MODELOS.md](docs/COMPARATIVO_MODELOS.md) |
| Critérios de inclusão/exclusão | [docs/CRITERIOS_INCLUSAO_EXCLUSAO.md](docs/CRITERIOS_INCLUSAO_EXCLUSAO.md) |
| Avaliação multidimensional (diversidade/novidade) + explicabilidade | [docs/AVALIACAO_MULTIDIMENSIONAL.md](docs/AVALIACAO_MULTIDIMENSIONAL.md) |
| Ablação de camadas (GAT, fusão por atenção, indutivo) | [docs/ABLACAO_CAMADAS.md](docs/ABLACAO_CAMADAS.md) |
| Plano pós-banca de qualificação | [docs/PLANO_POS_BANCA.md](docs/PLANO_POS_BANCA.md) |
| Seleção das bases (4 áreas, gradiente da H3, viés de amostragem) | [docs/SELECAO_BASES.md](docs/SELECAO_BASES.md) |
| Higienização de autores (ORCID, pessoa canônica, critérios E1–E8) | [docs/HIGIENIZACAO.md](docs/HIGIENIZACAO.md) |
| Relatório do Ciclo 1 · Roadmap | [docs/RELATORIO_CICLO1.md](docs/RELATORIO_CICLO1.md) · [docs/ROADMAP.md](docs/ROADMAP.md) |

> Dados (`data/`), resultados (`runs/`) e segredos (`.env`) **não** são versionados.
> Reproduza os artefatos com os comandos abaixo.

## Instalação

```bash
cd coauthor-rec
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# módulos de 2027 (opcional, pesado): pip install -e ".[deep]"
```

## Uso (pipeline)

```bash
# 1. Coleta do OpenAlex — três modos (configs/collect.yaml: campo `mode`):
#    snowball: a partir de semente (Cap. 5)      -> defina seed.id
#    thematic: recorte por Concept (Cap. 4.2.1)  -> defina thematic.concept_ids
#    hybrid:   snowball restrito ao tema         -> defina seed.id E thematic.concept_ids
coauthor-rec collect                 # usa o modo do YAML
coauthor-rec collect --mode hybrid   # sobrepõe o modo na linha de comando

# 2. Integra e limpa o corpus -> data/processed/corpus.parquet
coauthor-rec clean

# 3. Gate de qualidade (configs/corpus_gate.yaml)
coauthor-rec gate

# 4. Treina e avalia baseline / oráculo / Random Forest -> runs/baselines/
coauthor-rec run-baselines

# 5. Materializa o KG heterogêneo T0 (HeteroData/PyG) -> data/processed/hetero_T0.pt
coauthor-rec build-graph              # só T0 (predição de links futuros)
coauthor-rec build-graph --split all  # corpus inteiro

# 6. Métricas estruturais do KG (grau, densidade, componentes, cobertura) -> runs/
coauthor-rec graph-stats
```

## Estrutura

```
configs/        collect.yaml · corpus_gate.yaml · eval.yaml
src/coauthor_rec/
  collect/      coletor OpenAlex (snowball via pyalex)
  data/         limpeza, gate de qualidade
  graph/        rede de coautoria · STUB do KG heterogêneo (Tabela 8)
  split/        particionamento temporal + ground truth
  models/       baseline · oráculo · híbrido Random Forest
  eval/         métricas · regimes · estatística · harness
notebooks/      notebook original do case (referência)
tests/          métricas · split (anti-vazamento) · gate · pipeline
```

## Filtros (critérios de inclusão/exclusão)

Todos os filtros de artigo são centralizados em **`configs/filters.yaml`** (idioma, ano mínimo,
Concepts de área, campos obrigatórios incl. abstract, teto de coautores/artigo, HAS_TOPIC). O
pipeline inteiro lê de lá. Para mudar qualquer critério, edite só esse arquivo. Documentação:
[docs/CRITERIOS_INCLUSAO_EXCLUSAO.md](docs/CRITERIOS_INCLUSAO_EXCLUSAO.md).

## Protocolo

- **Split temporal** por work (80% mais antigos = T0): previne vazamento.
- **Ground truth**: `C_new(a) = C_future(a) \ C_past(a)` (apenas autores com novos links).
- **Métricas**: Precision@K, Recall@K, F1@K, NDCG@K, MRR@K, MAP — `K ∈ {5,10,20,50,100,200}`.
- **Regimes**: warm (≥5 coautores em T0), cool (1–4), cold (0).
- **Estatística**: Shapiro→t pareado/Wilcoxon, Bonferroni, IC por bootstrap.
- **Multidimensional**: diversidade (ILD), novidade e cobertura + explicabilidade
  sistemática — [docs/AVALIACAO_MULTIDIMENSIONAL.md](docs/AVALIACAO_MULTIDIMENSIONAL.md)
  (`scripts/beyond_accuracy.py`, `scripts/explain_systematic.py`).
- **Ablação de camadas**: GAT vs SAGE, fusão por atenção (peso α de cada modalidade) e
  avaliação indutiva — [docs/ABLACAO_CAMADAS.md](docs/ABLACAO_CAMADAS.md)
  (`scripts/ablation_layers.py`, `scripts/inductive_eval.py`).
- **Robustez (pós-banca)**: sensibilidade ao teto de coautores {10,20,50,∞} —
  [docs/SENSIBILIDADE_TETO.md](docs/SENSIBILIDADE_TETO.md) (`scripts/sens_cap.py`);
  Hits@K adicionado; significância persistida em `runs/`. Plano completo em
  [docs/PLANO_POS_BANCA.md](docs/PLANO_POS_BANCA.md).

## Testes

```bash
pytest
```
