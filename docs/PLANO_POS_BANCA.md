# Plano pós-banca — o que ajustar para re-rodar os testes

Cruzamento dos pareceres da banca de qualificação (Profs. Thiago Magela, José Pérez e
Rodrigo Rocha — `Pareceres_Banca_Qualificacao_Doutorado.docx` + `ComentariosMarcos.txt`)
com o estado atual do repositório `coauthor-rec` (commit `e1f8252`). Gerado em 31/08/2026.

Legenda de status: ✅ já atendido pelo repo · 🟡 parcialmente atendido · ❌ não atendido ·
📝 é ajuste de texto (não exige experimento).

---

## 0. Leitura geral

A banca pediu, em essência, seis coisas: (1) defender um **método indutivo-temporal-semântico**,
não "CNN+GNN"; (2) **hipótese e protocolo explícitos** antes dos resultados; (3) um **KG de
verdade** (tipagem/ontologia), distinto de rede heterogênea; (4) **corpus auditável** e
justificado; (5) **baselines fortes**; (6) **escopo controlado** (generativo → secundário).

O repositório já cobre bem (1), (2) e (6) em substância — mas com evidências que ainda não
estão organizadas como a banca pediu. Onde ele está **mais exposto** é em (3) e (5): o KG é
hoje uma `HeteroData` sem ontologia, e o único baseline topológico não supervisionado é
Common Neighbors. É aí que os novos testes devem se concentrar.

As cinco "lacunas da qualificação" que o repo já fechou (fusão por atenção/α, GAT vs SAGE,
explicabilidade sistemática, avaliação indutiva, beyond-accuracy) respondem a pedidos de
Rodrigo e José, mas **não cobrem** os pedidos experimentais mais concretos da banca. A tabela
abaixo mostra o que falta.

---

## 1. Matriz comentário → estado → ajuste

### A. Hipótese, contribuição e protocolo (José, Rodrigo)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| Reposicionar a contribuição como **método indutivo-temporal (e multimodal)**, não CNN+GNN | 🟡 A evidência já é essa (2 etapas vence; CNN e GNN não são decisivas), mas o README/título ainda dizem "CNN+GNN" | Reescrever README, ROADMAP e título de trabalho; nomear o método (ex.: *recomendação de coautoria por candidatos multimodais com ordenação estrutural*). Nenhum experimento novo. | P0 📝 |
| **Hipótese explícita e destacada**, ligada às ablações e testes estatísticos | 🟡 A hipótese está implícita ("texto+estrutura > isolado") e espalhada nos .md | Criar `docs/HIPOTESES.md` com H1–H4 formais e a tabela *hipótese → experimento → métrica → teste → veredito* (ver §2.1). Todos os testes já existem; falta o mapeamento. | P0 📝 |
| **Protocolo experimental formal** com parametrização: hiperparâmetros, seeds, janelas, negative sampling, early stopping, recursos; *repetir execuções* | 🟡 `configs/eval.yaml` fixa split/K/regimes/bootstrap e `seed: 42`; resultados finais com `PYTHONHASHSEED=0`; GNN/fusão rodaram com **1 seed**, 60 épocas, hidden 64, CPU ("comparação relativa, não busca do melhor número") | **Re-rodar tudo com 5 seeds** (média ± dp), fixar `PYTHONHASHSEED` dentro dos scripts (não só no shell), gerar `docs/PROTOCOLO.md` com tabela de hiperparâmetros + hardware + tempo. Persistir a significância do 2 etapas e do estudo cool/cold em JSON (hoje só impressa). | **P0** |
| **Explicar métricas antes de usar**; banca cita MRR, **Hits@K**, P@K, R@K, MAP, nDCG | 🟡 Todas existem em `eval/metrics.py`, exceto **Hits@K** | Adicionar `hits_at_k` (=1 se ≥1 acerto no top-K) e reportar junto às demais. Trivial. | P1 |
| A forma de testar é limitada (só automática) | ❌ Só avaliação offline | Estudo qualitativo pequeno: 5–10 pesquisadores da EACH avaliam top-10 do 2 etapas vs RF com as explicações (estrutural/temática) — `scripts/pick_example.py` já gera os casos. | P2 |

### B. Baselines (José, Rodrigo)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| **Baselines mais fortes**: GraphSAGE, modelos temporais/indutivos, GCN, GAT, LightGCN | 🟡 Baseline = Common Neighbors; RF sobre [CN, Jaccard, AA]; GNN-SAGE e GAT existem, mas como *modelos próprios*, não como baselines de referência | (1) **Heurísticas clássicas completas**: Adamic-Adar, Jaccard, Preferential Attachment, Resource Allocation e **Katz** isoladas (Katz já existe em `_case_repo/link_prediction_model_katz.ipynb`); (2) **Embeddings de grafo**: node2vec/DeepWalk + produto interno; (3) **LightGCN** sobre bipartido autor–artigo (ou autor–autor); (4) **GCN** homogêneo; (5) **1 modelo temporal** (TGN, EvolveGCN ou DySAT — o mais simples que rodar em CPU); (6) **1 método publicado de recomendação de coautoria** (ex.: baseado em random walk com restart / SimRank) para posicionar frente à literatura. Todos avaliados como reranker do mesmo pool 2-hop **e** como ranqueador global, para isolar o efeito do pool. | **P0** |
| Rodrigo: "Como combinar? Explorar mais a arquitetura" | ✅ Fusão por portão α; 2 etapas; ablação de componentes | Acrescentar **ablação formal do 2 etapas**: (a) tamanho da cauda textual *m* ∈ {25, 50, 100, 200}; (b) estágio 1 = RF vs GNN-rerank vs AA; (c) ordem invertida (texto→RF) para mostrar que a ordem importa. | P1 |
| Rodrigo: alta dimensionalidade | ❌ SciBERT 768-d usado direto | Teste de sensibilidade: PCA/UMAP para 64/128/256 dims na similaridade textual; se não degradar, reduz custo e vira nota de generalização. | P2 |

### C. Knowledge Graph, semântica e ontologia (José, Rodrigo)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| **KG ≠ rede heterogênea**: tipagem, relações semanticamente definidas, **ontologia mínima**, alinhamento externo | ❌ `graph/hetero.py` materializa 5 entidades/6 relações em `HeteroData` (é uma HIN). Não há ontologia nem alinhamento | Definir ontologia mínima (Autor, Artigo, Instituição, Venue, Conceito; relações `writes`, `coAuthorWith`, `cites`, `affiliatedWith`, `publishedIn`, `hasTopic`) **alinhada a vocabulários existentes**: FOAF/Schema.org (Person, Organization), FaBiO/CiTO (obra, citação), VIVO-ISF; conceitos OpenAlex já trazem **Wikidata IDs** → alinhamento imediato. Documentar em `docs/ONTOLOGIA.md` + exportar amostra em RDF/Turtle. Não muda os números; muda a defesa. | **P0** 📝 |
| Mostrar **quais relações o modelo usa** e quais ficam para extensão | 🟡 Ablação mostrou: KG completa ≈ só coautoria **para a GNN** (4,01 vs 4,00) | O teste que falta: **relações do KG como features do ranqueador** (não da GNN). Adicionar ao RF/2 etapas: `mesma_instituicao`, `mesmo_venue`, `n_conceitos_comuns`, `cita_ou_citado`, `distancia_temporal`. Se ajudarem no topo, o KG passa a ter papel mensurável além da explicabilidade; se não, é resultado negativo limpo. | **P0** |
| Rodrigo: prever ontologia como gancho; André Regino como referência de KG | ❌ | Citar/alinhar com o trabalho de KG acadêmico do grupo (Regino); prever no texto a extensão para ontologias externas. | P1 📝 |
| **Conceitos como 3ª fonte de candidatos** (decorre dos dois itens acima) | ❌ Candidatos hoje = 2-hop ∪ vizinhos SciBERT | Testar pool = 2-hop ∪ texto ∪ **autores com ≥k conceitos OpenAlex em comum** (semântica explícita do KG). Compara "semântica simbólica" (KG) vs "semântica latente" (SciBERT) como gerador de candidatos — resposta direta a "você terá de fato um KG?". | P1 |

### D. Dados e corpus (Thiago)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| **Uma semente gera viés** | 🟡 Existem 3 modos (snowball/thematic/hybrid) e duas bases (médica snowball, IA temática) | **Sensibilidade à semente**: re-coletar snowball a partir de 2 sementes alternativas (outra área médica; outra área de CS) e mostrar que o padrão RF-domina-em-denso / texto-domina-em-esparso se mantém. | P1 |
| **Teto de coautores: 20 em vez de 50?** | 🟡 `max_coauthors_per_work: 50` fixo; nenhum teste de sensibilidade | Re-rodar baselines + 2 etapas com teto ∈ {10, 20, 50, ∞} na base IA. Reportar nº de arestas removidas e efeito nas métricas. Provavelmente muda pouco (base IA tem `authors_per_paper` ≈ 6,6), o que já é o argumento. | **P0** (barato) |
| **Dados ruidosos do OpenAlex**: desambiguação, atribuição, qualidade; citar BRCris; informar limitações | ❌ Há `gate` (5 critérios de rede), mas nenhuma auditoria de identidade de autor | **Auditoria amostral**: 200 autores aleatórios → % com ORCID, % com ≥2 instituições incompatíveis no mesmo ano, % de nomes duplicados (mesmo `display_name`, IDs diferentes) no corpus; estimar taxa de erro e discutir impacto no grafo. Registrar em `docs/QUALIDADE_DADOS.md`. Opcional: cruzar 30 autores brasileiros com BRCris/Lattes. | **P0** |
| **Critério de exclusão rigoroso demais**; sustentar escolhas | 🟡 `filters.yaml` centraliza (inglês, ≥2004, abstract obrigatório, 5 conceitos de IA) e `CRITERIOS_INCLUSAO_EXCLUSAO.md` documenta, mas sem **funil por filtro** | Gerar tabela de atrito por filtro (quantos works cada critério remove, isoladamente e em cascata) para as duas bases. Teste de sensibilidade: relaxar `language` (incluir pt/es) e `min_year` (2000) e ver se o veredito muda. | P1 |
| **Exemplo concreto metadado → grafo** | 🟡 Há `diagrama_fluxo.png` e `diagrama_candidatos.png`, mas não um registro real | Escolher 1 work da base e mostrar o JSON do OpenAlex → nós/arestas/atributos gerados (figura + tabela). `scripts/pick_example.py` é ponto de partida. | P1 📝 |
| Rodrigo: "quem não tem nenhuma publicação?" | ✅ Declarado fora do escopo (newcomers = 82% dos alvos na base médica; sem perfil em T0) | Manter como limitação explícita + trabalho futuro (perfil externo: Lattes/ORCID/homepage). Citar o artigo de Rodrigo sobre formação de times (IEEE 10041131) como caminho. | 📝 |

### E. Temporalidade, indução e generalização (José, Rodrigo)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| Método **temporal**: partição cronológica T0→T1 | 🟡 Um único corte (80/20 por work). Robustez temporal não testada | **Múltiplos cortes**: `train_fraction` ∈ {0,6, 0,7, 0,8, 0,9} e/ou cortes por ano civil (ex.: T0 ≤ 2019, 2020, 2021). Se o 2 etapas vence em todos, a afirmação "temporal" fica sólida. | **P0** |
| Método **indutivo**: generaliza para não vistos | ✅ `inductive_eval.py` (400 alvos held-out) — indutivo > transdutivo em R@10/R@50 | Estender: (a) 5 seeds; (b) regime **cold como teste indutivo natural** (nós sem arestas de coautoria em T0) — já existe, só falta enquadrar; (c) avaliar 2 etapas em held-out, não só o encoder. | P1 |
| **Generalizar a arquitetura** (versão geral × instanciada; outros domínios/fontes) | 🟡 Dois domínios (médico denso, IA esparso) sustentam "valor do texto cresce com esparsidade" — n=2 é pouco | **Terceiro domínio** com esparsidade intermediária (ex.: Ciências Sociais ou Engenharia via `thematic`) para virar tendência, não anedota. Documentar a arquitetura em camadas (dados → semântica → grafo → aprendizado → ranking) e o que é específico do OpenAlex. | P1 |
| Rodrigo: **LLMs** em testes comparativos/exploratórios | 🟡 LLM usado só para *enriquecimento categórico* (negativo). Nenhum **embedding de LLM** como encoder, nenhum reranker LLM | (1) Adicionar encoders de embedding modernos em `text/encoders.py`: `bge-m3`/`e5-large` (abertos, CPU ok) e SPECTER2; opcional `text-embedding-3-large`. Comparar com SciBERT no texto-only e no 2 etapas. (2) **Reranker LLM** exploratório: LLM reordena o top-20 do 2 etapas com o abstract do alvo — só em 200 alvos, para custo controlado. Enquadrar como comparação, não dependência. | P1 |

### F. Escopo (José, Thiago)

| Comentário da banca | Estado no repo | Ajuste / novo teste | Prior. |
|---|---|---|:--:|
| **Reduzir escopo; generativo → trabalho futuro** ou experimento secundário | ✅ O enriquecimento GenAI foi testado e deu neutro/negativo | Mover para apêndice ("experimento secundário: resultado negativo"). **Não** investir mais em `topic/methods` livre antes de fechar B, C e D. | 📝 |
| Só 13 artigos na revisão; revisar critérios; incluir "coauthor/collaborator recommendation", redes de colaboração, temporal link prediction | ❌ (fora do repo) | Revisão complementar exploratória — necessária também para escolher os baselines publicados do item B. | P1 📝 |

### G. Texto (Rodrigo, Thiago, José) — sem experimento

Introdução com referências e ganchos para os capítulos 2–3; redes de colaboração antes de KG na
fundamentação; lacunas ao **final** da revisão; métricas definidas antes dos resultados;
parágrafos de 5–6 linhas; menos adjetivos; figuras de processo; trabalhos seminais.

---

## 2. Novos testes — especificação

### 2.1 Hipóteses formais (para `docs/HIPOTESES.md`)

| Hipótese | Enunciado testável | Experimento | Métrica / teste | Estado atual |
|---|---|---|---|---|
| **H1 — Complementaridade** | Combinar fontes de candidatos textual e estrutural supera cada fonte isolada em todos os regimes | 2 etapas vs RF vs Texto | R@K, NDCG@10, MRR; Wilcoxon + Bonferroni; IC95% bootstrap | Confirmada (base IA, 1 seed) → **re-rodar 5 seeds, 4 cortes temporais** |
| **H2 — Cold-start** | Para autores sem coautoria em T0, métodos topológicos têm recall nulo e a semântica textual é a única fonte de sinal | cold n=53; α do portão | R@200; Δ vs RF; α por regime | Confirmada → **ampliar n com 3º domínio** |
| **H3 — Esparsidade** | O ganho relativo do texto cresce com a esparsidade da rede de coautoria | médico (denso) vs IA (esparso) | Δ(texto−RF) × densidade | Sugerida com n=2 → **3º domínio** |
| **H4 — Indução** | O método produz recomendações úteis para autores fora da supervisão | held-out 400 | R@K indutivo vs transdutivo | Confirmada (modesta) → **5 seeds; avaliar 2 etapas** |
| **H0-KG (nova)** | Relações tipadas do KG (instituição, venue, conceito, citação) melhoram a ordenação no topo além da coautoria | RF ± features de KG | NDCG@10, R@10 | **Não testada** |

### 2.2 Lista de execução (scripts a criar/alterar)

> **Progresso (S1):** ✅ T15 (Hits@K em `eval/metrics.py`), ✅ T2 (significância persistida em
> `runs/two_stage/significance.json` e `runs/cool_cold_frac0.8.json`), ✅ T3 (`scripts/sens_cap.py`
> + `docs/SENSIBILIDADE_TETO.md`). Pendentes de S1: T1 e T4 (multi-seed / multi-corte — 1–2 dias CPU).
> **Dados (S3, adiantado):** 🟡 T11 — higienização implementada e documentada
> (`docs/HIGIENIZACAO.md`: ORCID como pessoa canônica, níveis A/B/C/X, vínculo I1–I3, critérios
> E1–E8, funil); falta rodar nas bases definitivas e a verificação manual dos 200 autores.
> Bases do gradiente redefinidas: 4 áreas no nível de campo (`docs/SELECAO_BASES.md`).

| # | Teste | Script | Mudança | Saída | Esforço |
|---|---|---|---|---|---|
| T1 | Multi-seed de todos os modelos | `scripts/final_comparison.py` | loop `--seeds 0 1 2 3 4`; `os.environ["PYTHONHASHSEED"]` + `random/numpy/torch.manual_seed` dentro do script | `runs/final_comparison_seeds.json` (média±dp) | 1–2 dias CPU |
| T2 ✅ | Persistir significância | `scripts/two_stage_eval.py`, `scripts/cool_cold_study.py` | `json.dump` dos testes | `runs/two_stage/significance.json`, `runs/cool_cold/significance.json` | horas |
| T3 ✅ | Sensibilidade ao teto de coautores | `coauthor-rec build-graph` + `run-baselines` | `max_coauthors_per_work` ∈ {10, 20, 50, ∞} | `runs/sens_cap/*.json` | 1 dia |
| T4 | Múltiplos cortes temporais | `configs/eval.yaml` | `train_fraction` ∈ {0,6, 0,7, 0,8, 0,9}; variante por ano | `runs/sens_split/*.json` | 1–2 dias |
| T5 | Baselines fortes | novo `scripts/baselines_strong.py` | AA, Jaccard, PA, RA, Katz; node2vec; LightGCN; GCN; 1 temporal; 1 publicado — como reranker 2-hop **e** global | `runs/baselines_strong/*.json` | 1–2 semanas |
| T6 | Features de KG no ranqueador | `models/hybrid_rf.py`, `models/two_stage.py` | +`same_inst`, `same_venue`, `n_shared_concepts`, `citation_link`, `year_gap`; importâncias | `runs/kg_features/*.json` | 2–3 dias |
| T7 | Conceitos como 3ª fonte de candidatos | `models/hybrid_cand.py` | pool ∪ autores com ≥k conceitos comuns; varrer k | `runs/cand_concepts/*.json` | 2 dias |
| T8 | Ablação do 2 etapas | novo `scripts/two_stage_ablation.py` | *m* ∈ {25,50,100,200}; estágio 1 ∈ {RF, GNN, AA}; ordem invertida | `runs/two_stage/ablation.json` | 2 dias |
| T9 | Encoders LLM | `text/encoders.py` | +`bge-m3`, `e5-large-v2`, `specter2`; opcional OpenAI | `runs/text/text_compare_llm.json` | 2–3 dias (embeddings) |
| T10 | Reranker LLM exploratório | novo `scripts/llm_rerank.py` | 200 alvos; top-20 → LLM ordena com abstracts | `runs/llm_rerank.json` | 2 dias + custo API |
| T11 🟡 | Auditoria de qualidade dos dados | novo `scripts/audit_authors.py` | 200 autores: ORCID, afiliações conflitantes, homônimos | `docs/QUALIDADE_DADOS.md` | 2 dias |
| T12 | Funil de filtros | `data/clean.py` | contar remoções por critério | `docs/CRITERIOS_INCLUSAO_EXCLUSAO.md` (tabela) | 1 dia |
| T13 | Sensibilidade à semente (snowball) | `configs/collect.yaml` | 2 sementes alternativas | `runs/sens_seed/*.json` | 3–4 dias (coleta) |
| T14 | Terceiro domínio | `configs/filters.yaml` | conceitos de outra área (esparsidade intermediária) | `runs/domain3/*.json` | 1 semana |
| T15 ✅ | Hits@K | `eval/metrics.py` | `hits_at_k` | todas as tabelas | horas |
| T16 | Ontologia mínima + export RDF | novo `graph/ontology.py` | mapeamento FOAF/Schema/FaBiO/Wikidata; amostra Turtle | `docs/ONTOLOGIA.md`, `data/processed/kg_sample.ttl` | 2–3 dias |

### 2.3 O que **não** precisa re-rodar

- Fusão end-to-end CNN+GNN, Sup-Hybrid, enriquecimento GenAI categórico, 3 saltos, KG vs
  só-coautoria **na GNN**: resultados negativos com diagnóstico consistente. Basta repeti-los
  dentro do T1 (multi-seed) para ter dp; não vale redesenhar.
- Explicabilidade sistemática e beyond-accuracy: apenas re-executar sobre o modelo final após T5–T8.

---

## 3. Ordem sugerida (sprints de ~2 semanas)

| Sprint | Foco | Testes | Por quê primeiro |
|---|---|---|---|
| **S1 — Blindar o que já existe** | Protocolo | T1, T2, T3, T4, T15 | Barato; transforma resultados de 1 seed/1 corte em evidência robusta antes de qualquer coisa nova. Se algo cair aqui, muda tudo o que vem depois. |
| **S2 — Baselines e KG** | Pontos mais expostos da banca | T5, T6, T7, T8 | Responde diretamente a José ("baselines fortes") e a José/Rodrigo ("é KG de verdade?"). T6 pode dar ao KG um papel mensurável. |
| **S3 — Dados** | Thiago | T11, T12, T13, T16 | Corpus auditável e ontologia documentada; T13 pode rodar em paralelo (coleta). |
| **S4 — Generalização e LLMs** | Rodrigo/José | T9, T10, T14 | Fecha H3 com 3º domínio e posiciona frente a LLMs sem mover o núcleo. |
| **S5 — Consolidação** | Escrita | HIPOTESES.md, PROTOCOLO.md, README/ROADMAP, apêndice de negativos | Só depois de S1–S4 para os números serem finais. |

---

## 4. Riscos que os novos testes podem expor

1. **Multi-seed pode reduzir a margem do 2 etapas no topo** (R@10 +0,48pp é pequeno). Se o IC
   cruzar zero em algum K, a narrativa vira "domina em alcance, empata no topo" — ainda
   defensável, mas exige ajuste do texto.
2. **LightGCN/node2vec podem bater o RF como ranqueador do 2-hop**. Não ameaça a tese (o
   estágio 1 é plugável); ao contrário, fortalece o protocolo. Mas exige re-rodar T8 com o novo
   estágio 1.
3. **Features de KG podem não ajudar (T6)**. Aí o KG fica com papel de explicabilidade e
   candidatos por conceito (T7). É preciso ter a resposta pronta: "tipagem serve para explicar e
   para gerar candidatos, não para ranquear".
4. **Terceiro domínio pode não seguir a curva de esparsidade**. H3 vira "observado em 2 de 3" —
   melhor descobrir agora do que na defesa.
