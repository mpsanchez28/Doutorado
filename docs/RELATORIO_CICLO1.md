# Relatório — Ciclo 1: Pipeline OpenAlex e Baselines Reprodutíveis

**Projeto:** Predição de coautorias utilizando Redes Neurais Convolucionais e Redes Neurais em Grafos
**Autor:** Marcos Paulo Sanchez · **Orientador:** Prof. Dr. Luciano Antonio Digiampietri
**Programa:** PPgSI — EACH/USP · **Data:** junho de 2026 (início do cronograma, 3T/2026)
**Repositório:** `coauthor-rec` (commit inicial `7879d4a`)

---

## 1. Objetivo do ciclo

Transformar o **Estudo Inicial** da qualificação (artigo SBBD / notebook do *case*) em uma
**aplicação modular, configurável, testada e reprodutível**, e construir o **pipeline de
coleta e preparação de dados do OpenAlex**. Esta etapa corresponde às primeiras atividades
do Plano de Trabalho (Cap. 6): refinamento do protocolo experimental, coleta/higienização/
versionamento da base e consolidação dos modelos de referência.

O ciclo **não** inclui ainda os módulos de aprendizado profundo (CNN textual e GNN
relacional), previstos para 2027; ele prepara a fundação estrutural para eles.

---

## 2. O que foi desenvolvido

Pacote Python (`coauthor_rec`) organizado por responsabilidade, no qual cada módulo
implementa uma seção da metodologia da qualificação:

| Módulo | Função | Referência |
|---|---|---|
| `collect/openalex.py` | Coleta do OpenAlex via API (pyalex), em 3 modos | §4.2, §5.1.1 |
| `data/clean.py` | Integração e limpeza; reconstrução de *abstract* | §5.1.1 |
| `data/gate.py` | *Gate* de qualidade do corpus (5 critérios) | §4.3.2 |
| `split/temporal.py` | Particionamento temporal T0→T1 e verdade fundamental | §5.1.3–5.1.4 |
| `graph/coauthor.py` | Rede de coautoria (simples e ponderada) | §5.1.2 |
| `graph/hetero.py` | **Esquema** do KG heterogêneo (*stub* para a fase GNN) | §4.3.1 (Tab. 8) |
| `models/` | Baseline, oráculo topológico e híbrido (Random Forest) | §5.1.5–5.1.8 |
| `eval/` | Métricas, regimes *warm/cool/cold*, análise estatística | §4.6, §5.1.6 |
| `cli.py` | Interface de linha de comando do pipeline | — |

Acompanha **suíte de 18 testes automatizados** (`pytest`), incluindo um teste que garante
**ausência de vazamento temporal** no split.

### 2.1 Estratégias de coleta

Em coerência com a §4.2.1 — que deixa a estratégia de coleta em aberto, mencionando tanto
"profundidade de expansão" quanto "critérios temáticos" —, o coletor suporta **três modos**,
selecionáveis por configuração:

- **`snowball`** — bola de neve a partir de um artigo/autor-semente (método do Estudo Inicial, Cap. 5);
- **`thematic`** — recorte por *Concept* do OpenAlex (cenário temático aberto da tese);
- **`hybrid`** — bola de neve a partir da semente, **restrita** aos *Concepts* temáticos.

Os três produzem os mesmos arquivos (`authorships.csv`, `works.csv`) e já capturam os
metadados adicionais do KG heterogêneo (instituições, *venue*/ISSN, *concepts*, citações),
para reuso direto nos módulos de 2027.

### 2.2 Protocolo experimental

- **Split temporal por artigo:** os 80% de *works* mais antigos formam o treino (T0); os 20%
  mais recentes, o teste (T1). A divisão por artigo impede que coautores do mesmo trabalho
  fiquem em lados opostos do corte.
- **Verdade fundamental:** `C_new(a) = C_future(a) \ C_past(a)` — apenas colaborações
  **inéditas** são instâncias positivas (Eq. 14). Só autores com ao menos uma nova coautoria
  são avaliados.
- **Gate de qualidade:** o corpus precisa satisfazer 5 critérios mínimos (§4.3.2) antes da
  modelagem; caso contrário, a coleta é recalibrada.
- **Regimes de avaliação:** cada autor-alvo é classificado em *warm* (≥5 coautores em T0),
  *cool* (1–4) ou *cold* (0), e as métricas são reportadas também por regime.
- **Métricas:** Precision@K, Recall@K, F1@K, NDCG@K, MRR@K e MAP, com `K ∈ {5,10,20,50,100,200}`.
- **Estatística:** Shapiro-Wilk → teste t pareado ou Wilcoxon; correção de Bonferroni;
  intervalos de confiança por *bootstrap*.

---

## 3. Validação de ponta a ponta (dados reais do OpenAlex)

O pipeline completo foi executado sobre dados reais, partindo da semente
`W1983561455` ("Predicting Co-Author Relationship in Medical Co-Authorship Networks"):

| Etapa | Resultado |
|---|---|
| Coleta (snowball, profundidade 2) | 9.095 *works* / 27.119 autores |
| Limpeza (inglês, ano ≥ 2004, dedup) | 5.878 *works* / 19.120 autores · 100% com *abstract* |
| **Gate de qualidade** | **APROVADO** (5/5 critérios; peso médio 1,387; 9.587 pares peso≥3) |
| Split temporal | treino 4.702 / teste 1.176 *works* · 5.894 autores-alvo |
| Regimes dos alvos | *warm* 979 · *cool* 78 · **cold 4.837** |

### 3.1 Resultados (geral)

Recall@K (%) — comparação dos três modelos:

| K | Baseline | Oráculo | Híbrido-RF |
|---:|---:|---:|---:|
| 5 | 2,91 | 19,27 | 3,42 |
| 10 | 5,01 | 20,29 | 4,96 |
| 20 | 7,55 | 20,46 | 7,82 |
| 50 | 9,83 | 20,47 | 10,52 |
| 100 | 10,58 | 20,47 | 12,31 |
| 200 | 11,85 | 20,47 | 12,81 |

Tabela completa (todos os modelos, todas as métricas) em `runs/baselines/report.txt`.

### 3.2 Leitura dos resultados

Os números **reproduzem o padrão descrito na qualificação** (§5.2–5.3):

1. **O oráculo é um teto claro** (~20,5% de Recall): há um limite superior imposto pelo
   espaço de candidatos topológico — a topologia, sozinha, restringe a predição.
2. **O híbrido supera o baseline em Recall** nos cortes maiores (12,81% vs 11,85% em K=200)
   e recupera **62,5% do oráculo** em K=200 — confirmando que parte do sinal estrutural é
   explorável por aprendizado supervisionado.
3. **O ganho é assimétrico:** a vantagem do híbrido concentra-se na cobertura (Recall em K
   alto), não no topo do *ranking* — coerente com a observação de que features topológicas
   não bastam para ordenar bem as primeiras posições.
4. **O regime *cold* domina** (4.837 de 5.894 alvos) e apresenta o pior desempenho relativo —
   evidência empírica direta do problema de *cold-start* que a tese se propõe a atacar com a
   fusão de semântica textual (CNN) e estrutura (GNN).

Em síntese: a aplicação não apenas funciona de ponta a ponta sobre dados reais, como
**sustenta empiricamente a motivação central da tese**.

---

## 4. Situação e próximos passos

**Concluído neste ciclo:** protocolo experimental, pipeline de dados OpenAlex (3 modos),
gate de qualidade, modelos de referência consolidados sob protocolo único com estratificação
por regime e base estatística — tudo testado e validado em corpus real aprovado no gate.

**Próximos ciclos (2027), já com fundação pronta:**
1. Materialização do **KG heterogêneo** → `HeteroData` (PyTorch Geometric); o esquema da
   Tabela 8 já está fixado em `graph/hetero.py`.
2. **Módulo textual** (BERT/SciBERT + CNN 1D) → *embedding* textual do autor.
3. **Módulo relacional** (GNN heterogênea, indutiva para *cold-start*).
4. **Fusão multimodal** (Eq. 10) e *re-ranking* supervisionado (Eq. 12); estudos de ablação.

---

*Resultados completos e configurações versionados no repositório (`runs/baselines/`,
`configs/`). Pipeline reproduzível via `coauthor-rec collect | clean | gate | run-baselines`.*
