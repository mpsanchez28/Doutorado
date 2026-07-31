# coauthor-rec

Recomendação de coautoria por **predição de links** em redes acadêmicas do **OpenAlex**.
Projeto de doutorado (PPgSI/EACH-USP) — sistema híbrido **CNN (texto) + GNN (estrutura)**
sobre um Grafo de Conhecimento heterogêneo, avaliado sob split temporal (T0→T1) nos
regimes *warm/cool/cold*.

Este repositório parte do **estudo inicial** (artigo SBBD / notebook do case) e o
transforma num projeto modular e reprodutível. **Ciclo atual:** pipeline de dados
OpenAlex + baselines reprodutíveis. Os módulos textual (CNN/BERT) e relacional (GNN/PyG)
entram nos ciclos seguintes.

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

## Testes

```bash
pytest
```
