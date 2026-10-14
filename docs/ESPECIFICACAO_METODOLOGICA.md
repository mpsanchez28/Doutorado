# Especificação metodológica única — reanálise retrospectiva temporal (protocolo corrigido)

**Versão:** 14/10/2026, 17h, universo de candidatos **v2**, emendas E1–E5 (abaixo).

**O que este documento faz:** reúne num só lugar as decisões que ficam **congeladas antes das
próximas execuções**. Em caso de conflito, prevalece sobre ROBUSTEZ_T1_T4.md e
PROTOCOLO_CORRIGIDO_2021.md, que apontam para cá.

**O que continua fora deste documento:**
- O protocolo histórico (`main @ 477dcd1`) não muda; é a referência.
- O T1 completo continua **suspenso** até a validação do pipeline corrigido.
- Decisões ainda pendentes de aprovação estão marcadas **[pendente]** ou **[dependente de decisão]**.

**Legenda de estado** (usada em todos os documentos da frente de robustez):

| Estado | Significado |
|---|---|
| relatado | número ou fato informado anteriormente, ainda não conferido nesta versão |
| inspecionado | conferido por leitura de código, configuração ou artefato |
| implementado | código existe |
| executado | rodou, com artefato identificado |
| verificado | tem checagem independente (teste, asserção, recontagem ou API) |
| proposto | redação ou regra sugerida, não adotada |
| incompleto | executado em parte; o que falta está listado |
| dependente de decisão | não pode avançar sem escolha registrada do usuário |

Testes de software passando **não** constituem validação científica do protocolo.

**Histórico de emendas:**

| Emenda | Data | Conteúdo | Seções |
|---|---|---|---|
| E0 | 14/10, 15:40 (`a827a18`) | versão inicial: classificação, universo v2, fase de treino no próprio corte, estatística, neurais | todas |
| **E1** | 14/10, tarde | **revogada** a substituição da validação temporal por validação cruzada por pessoa (§3.2 de E0). A estratégia temporal volta a **[dependente de decisão]**, com as alternativas executáveis A e B e a matriz de cobertura | §3 |
| E2 | 14/10, tarde | entradas congeladas (cópia S1, manifesto, leitura exclusiva, falha explícita); recálculo e comparação com a v2 | §2.4, §7 |
| E3 | 14/10, tarde | regra entre sementes rastreada da coleta ao ranking; histórico de candidatos que são sementes lido do bruto | §2.2–2.3 |
| E4 | 14/10, tarde | memória do cálculo de poder; calibração do IC percentil | §4.5 |
| E5 | 14/10, tarde | espaço de modelos fixado antes da busca; cronologia das duas etapas, inclusive a seleção da integração; registro de escores | §5 |

---

## 1. Classificação da avaliação: reanálise retrospectiva temporal

O teste de 2022 em diante **já foi consultado**. Por isso a avaliação sobre o protocolo
corrigido é uma **reanálise retrospectiva temporal**:
- "retrospectiva": reconstrói, com restrição temporal dos dados, um corte passado;
- "temporal": treino e teste separados no tempo.

Não é uma confirmação independente. "Pré-especificado", aqui, quer dizer apenas que as escolhas
abaixo foram congeladas **antes das próximas execuções**. Não quer dizer que o teste esteja
intocado.

**O que já foi consultado e o que se decidiu depois:**

| Data | Consulta aos rótulos de teste (2022+) | Decisões tomadas depois |
|---|---|---|
| 10/10 | Validação cruzada de Economia entre 4 variantes do LightGBM (rótulos 2022+) | hiperparâmetros `lgbm_params` fixados para todas as bases |
| 10–11/10 | Ablação do KG, LTR temporal (inclusive com parâmetros padrão), avaliação padrão, cascata e SPECTER2, nas 4 bases; R@K, NDCG, SHAP | treino temporal adotado no modelo principal; avaliação padrão (`gt_t0`) como leitura complementar; SPECTER2 mantido como comparador (N1); cascata não adotada |
| 14/10 | Piloto T1 (Economia) e diagnóstico por subconjunto (R@50, NDCG@10, diferenças pareadas) | T1 completo suspenso; seleção corrigida (protocolo de 2021) |
| 14/10 | — (piloto T4 2019: só contagens) | amostra 500 → todas as sorteadas ≤ corte (decidido sobre contagens de elegíveis, não desempenho) |
| 14/10 | — | horizonte de 3 anos (2022–2024) como principal; δ, famílias, análise por área, bootstrap de Poisson e esta especificação. **Todos fixados depois** de os resultados históricos terem sido vistos |

As métricas das reconstruções (piloto 2019 e 2021, v1 e v2) foram gravadas e **não foram
examinadas**. Nesta revisão (E1–E5) nenhuma busca de hiperparâmetros, seleção de modelo, treino
neural ou bateria de avaliação foi iniciada; as reconstruções feitas com a cópia congelada só
montaram conjuntos (sem treinar modelo).

**Confirmação independente:** exige dados reservados, que não tenham influenciado o
desenvolvimento. Pode ser feita com acompanhamento futuro: coautorias publicadas depois de
2026-10-08, coletadas numa data a fixar, com esta especificação congelada. Fica como etapa
posterior e **não bloqueia** a reanálise.

## 2. Populações, conjuntos e entradas (um corte c)

### 2.1 Cinco conjuntos distintos

| Conjunto | Definição | Onde no código | Estado |
|---|---|---|---|
| **Sementes permitidas pelo corte** | as do sorteio 42 cujo trabalho sorteado é ≤ c, todas | `reconstrucao_t4.py` etapa 1 | implementado, executado |
| **Sementes que satisfazem os critérios de alvo** | sementes permitidas com E1–E8 ≤ c (ORCID: retrato atual; E3 sem relaxar) e ≥ 1 coautoria nova no horizonte (após M9) | etapa 2; `eval/protocol.build_protocol` | implementado, executado |
| **Autores selecionados para coleta complementar** (universo) | coautores das sementes permitidas, em trabalhos ≤ c com equipe ≤ teto; exclui só as sementes permitidas, **porque o histórico delas já está no bruto**; até 15 mil por laço | `collect/openalex.candidate_universe_at_cut` | implementado, verificado |
| **Pessoas representadas no corpus e no KG** | todos os autores dos trabalhos das sementes permitidas (todos os anos até o fim dos rótulos) e dos trabalhos dos candidatos na janela [c−W+1, c]; candidatos que são sementes de outro corte/sorteio usam o histórico do bruto (E3) | `reconstrucao_t4.compose_corpus` | implementado, executado |
| **Candidatos recomendáveis para cada consulta** | **todo** autor do KG ≤ c com escore > 0 em algum gerador, **exceto** a própria consulta (identidade canônica) e seus coautores anteriores (`train_graph`); top-1000 da União RRF (k = 60) | `models/kg_ltr.ranking_exclusions`, `kg_generators.rank_candidates` | implementado, verificado (testes) |

### 2.2 Regra do universo (coleta)

- Gerado **só** pelos trabalhos das sementes permitidas (`candidate_universe_at_cut`); verificação
  automática aborta se um candidato não tiver laço ≤ c, com equipe ≤ teto, com semente permitida,
  ou se for semente permitida.
- Uma semente **fora do corte** pode ser candidata se tiver esse laço (14–26 por base). Não é
  proibida por ter sido excluída como alvo; isso também não autoriza usar os trabalhos dela para
  gerar o universo.
- Sementes permitidas inelegíveis geram o universo, como no protocolo original.
- **Correção de cobertura (E3, local, sem coleta):** um candidato que é semente (de outro corte)
  nunca entra na fila de coleta (o original excluía as 1.000 sementes), e por isso ficava sem
  histórico além dos trabalhos com sementes permitidas. Agora o histórico dele na janela vem do
  bruto. Efeito medido: +2 a +5 trabalhos no corpus de teste; 12–27 membros dos universos das
  fases de treino passam a ter histórico (`comparacao_S1_v2.json`).
- A reprodução do universo histórico (todas as sementes, T0 = 2021) é teste separado
  (`tests/test_universo_candidatos.py`, diferença 0).

### 2.3 Regra entre sementes no ranking (E3) — rastreada da coleta ao top-1000

| Etapa | Há exclusão de sementes? | Evidência |
|---|---|---|
| Fila de coleta (`select_candidates` / `candidate_universe_at_cut`) | sim, só das sementes **permitidas**: o histórico delas já está no bruto | código; inspecionado |
| Corpus e KG | não: sementes permitidas entram com todos os trabalhos | `compose_corpus`; inspecionado |
| Gabarito (`split/temporal.build_ground_truth`, `eval/protocol`) | não: coautor novo = futuro − passado, sem filtro de sementes; M9 é por nome, não por papel | código; teste `test_ground_truth_keeps_other_targets_as_new_coauthors` |
| Recuperação e top-1000 (`build_pairs`, `cascade_pairs`) | **não**: excluem só a consulta e os coautores anteriores (`ranking_exclusions`, extraída sem mudar o comportamento) | testes `test_regra_sementes.py` (5) |
| Ranking final (LambdaMART) | não: reordena os pares do top-1000 | código; inspecionado |

**Conclusão (verificada):** **não há bloqueio de recomendações entre alvos.** Positivos cujo
coautor novo é outra semente permitida ou outro alvo **estão no gabarito e são recuperáveis**
(`runs/robustez/t4/positivos_entre_sementes.json`, cópia S1):

| Base, horizonte | Positivos (dirigidos) | Coautor é semente permitida: dirigidos / pares únicos / alcançáveis | Coautor é alvo: dirigidos / pares únicos | Retirados do gabarito / bloqueados no ranking |
|---|---:|---:|---:|---:|
| Economia 2019, 3 anos | 1.542 | 7 / 6 / 7 | 2 / 1 | 0 / 0 |
| Economia 2021, 3 anos | 1.434 | 6 / 5 / 6 | 2 / 1 | 0 / 0 |
| Economia 2021, até 2026-10-08 | 2.079 | 7 / 6 / 7 | 2 / 1 | 0 / 0 |
| Matemática 2021, 3 anos | 1.774 | 7 / 5 / 7 | 4 / 2 | 0 / 0 |
| Matemática 2021, até 2026-10-08 | 2.410 | 9 / 7 / 9 | 5 / 3 | 0 / 0 |

Os "0 / 0" decorrem da inspeção do código (não há filtro), não de uma recontagem independente.
**Nenhuma alteração proposta** para o ranking. Identidade da consulta: a exclusão usa o ID
canônico após a higienização; uma pessoa partida em dois IDs (fusão não feita) poderia ser
recomendada a si mesma — limitação da desambiguação, não da regra.

### 2.4 Entradas congeladas (E2)

- **Cópia S1** (`data/snapshots/S1_20261014_econ_mat/`, fora do Git; manifesto compacto em
  `docs/manifestos/S1_20261014_econ_mat.json`, versionado; S2 em `docs/manifestos/S2_20261014_comp_med.json`): bruto de Economia e Matemática, dados do
  T4 (2019 e 2021, com `estado.json` e lacunas v1), 33.525 registros ORCID (87.599 ORCIDs dos
  dados sem registro no cache: listados como ausentes, nunca buscados), 286.879 registros de
  trabalhos e 16.137 de instituições (com ancestrais), configurações e ontologia. 764 arquivos;
  SHA-256 por arquivo e combinado.
- **Garantias implementadas** (`data/snapshot.py`; testes em `tests/test_snapshot.py`): cópia
  física (sem links), hash da origem antes e depois de cada cópia (falha se a origem mudar),
  linha incompleta em jsonl (gravação concorrente) → falha, árvore somente leitura, cópia selada
  não é sobrescrita. `--snapshot` faz a reconstrução ler **só** da cópia, verificar todos os
  hashes antes e falhar se as configurações do repositório diferirem das seladas.
- **Isolamento testado** com diretórios temporários (o cache de produção não foi tocado): mudar o
  cache global depois do congelamento não altera o que a execução congelada lê.
- **Demonstração em produção:** o recálculo com S1 rodou **durante** a coleta de Computação e
  Medicina, que gravava nos caches globais; os conjuntos de Matemática têm a mesma impressão
  digital ORCID da v2.
- Coletas novas ficam fora de S1 e entram numa **nova versão selada** (S2: Computação e
  Medicina, §7). Congelar uma base incompleta não a torna completa.
- **Comparação S1 × v2** (`runs/robustez/t4/comparacao_S1_v2.json`), Economia (2019; 2021 nos dois
  horizontes) e Matemática (2021 nos dois horizontes):

| Item | Resultado |
|---|---|
| Elegíveis; pessoas que entram/saem | idênticos (246, 313, 344); 0 entram, 0 saem |
| Identidade canônica das sementes | 0 mudanças |
| Universo de candidatos | idêntico |
| Alvos e nº de coautores novos por alvo | idênticos; protocolo (pares novos, M9, alcançáveis, avaliação padrão) idêntico |
| Corpus | +2 a +5 trabalhos (histórico do bruto de candidatos que são sementes; E3) |
| Fase de treino | sementes, universo e composição das consultas idênticos; 12–27 membros do universo passam a ter histórico do bruto |
| Impressão digital ORCID (Matemática) | idêntica |

  **Execuções a repetir:** os treinos técnicos da v2 (métricas não examinadas) mudam por causa
  dos +2–5 trabalhos e do histórico do bruto nas fases de treino; qualquer execução de modelo
  passa a usar a cópia selada. **Permanecem reproduzíveis com entradas identificadas:** os
  conjuntos de teste (elegibilidade, universo, alvos, gabarito) da v2 de Economia e Matemática,
  agora reproduzidos a partir de S1.

### 2.5 Denominadores

- **Alvos estritos:** sementes que satisfazem os critérios de alvo. Denominador por alvo:
  **todos** os coautores novos, presentes ou não no corpus.
- **Alvos da avaliação padrão:** alvos estritos com ≥ 1 coautor novo presente em T0.
  Denominador: só esses. É leitura complementar.
- **Elegíveis sem coautoria nova:** contados à parte, fora das métricas condicionais.
- **Newcomers:** com E5 (≥ 2 trabalhos) calculado até c, o grupo é **vazio** por construção
  (confirmado: 0); só existe no protocolo histórico.
- **P@K com lista < K:** denominador K; o número de listas curtas é reportado.

## 3. Desenho temporal [dependente de decisão] (E1)

**A emenda E1 revoga** a substituição da validação temporal por validação cruzada por pessoa
(E0 §3.2). Separar pessoas no mesmo intervalo pode ser uma restrição adicional, mas não substitui a
separação temporal. Nenhuma busca começa antes de a escolha ser registrada em
`configs/desenho_temporal.yaml` (`escolha`) e numa emenda.

### 3.1 Cronologia (princípios)

- Um exemplo histórico tem features no **instante t** (fatos ≤ t, inclusive grafo e candidatos) e
  rótulos em (t, t+L]. Ele pode treinar um modelo usado **depois**, quando esses rótulos já são
  conhecidos (instante ≥ t+L).
- Nenhum rótulo posterior ao instante de previsão influencia o modelo usado nesse instante:
  pesos, hiperparâmetros, transformações, geração de candidatos, escolha de consultas.
- Decisões de ajuste tomadas com a validação orientam avaliações **posteriores**, nunca as
  previsões que geraram os próprios resultados de validação.
- Participantes também precisam respeitar o instante: cortar arestas ou textos não basta se as
  consultas ou os candidatos forem escolhidos por laços futuros. Por isso cada fase tem
  sementes sorteadas ≤ t e universo com laços ≤ t (`training_phase`, com asserções).
- Restringir a data dos fatos **não** comprova que desambiguação, tópicos ou registros ORCID
  fossem iguais no passado (metadados atuais).

### 3.2 O que os dados permitem (inspecionado e medido)

- **Sementes:** histórico na área 2004–2026 no bruto → completo para features, rótulos e
  reconhecimento de colaborações anteriores.
- **Candidatos:** histórico na área só **2017–2021** (expansão original + T4 2021). Economia tem
  ainda 2015–2016 para parte do universo (coleta do piloto 2019; reaproveitável). Trabalhos de
  candidatos depois de 2021: não coletados (desnecessários: os alvos de teste são sementes).
- **Matriz de cobertura** por base e etapa (`runs/robustez/t4/cobertura_historica.{json,csv}`;
  "não consultado" ≠ zero publicações): ver §7.3.
- **Reconhecimento de colaborações anteriores com janela curta** (proxy medido só com os
  trabalhos das sementes, cujo histórico é completo): a fração de pares "novos" que na verdade
  são colaborações antigas.

| Base | Instante 2018, janela de reconhecimento 2017–2018, rótulos 2019–2021 | Instante 2021, janela 2017–2021, rótulos 2022–2024 |
|---|---:|---:|
| Economia | **13,8%** (469 de 3.396) | 5,4% (174 de 3.238) |
| Matemática | **16,9%** (480 de 2.848) | 6,1% (206 de 3.390) |

  Para as **consultas-candidato** (≈ 90% das 3.000 consultas de treino da fase 2018), o
  reconhecimento hoje só usa 2017–2018 (+ trabalhos com sementes): parte relevante dos rótulos de
  treino delas pode ser colaboração antiga. Para os **alvos de teste** (sementes), o
  reconhecimento é completo. O efeito sobre os rótulos de consultas-candidato **não é nulo** e
  não está corrigido em nenhuma execução até aqui.

### 3.3 Fases exigidas pelo desenho registrado (W = 5, defasagem 3) × disponibilidade

| Fase | Instante | Fatos/grafo | Rótulos de treino | Rótulos de validação | Sementes / consultas / candidatos | Histórico de candidatos exigido | Disponível | Transformações ajustadas (dados) |
|---|---|---|---|---|---|---|---|---|
| Treino de seleção | 2015 | ≤ 2015 | 2016–2018 | — | sorteio ≤ 2015 / da fase / laços ≤ 2015 | 2011–2015 (+2016–2018 para rótulos de consultas-candidato) | **nenhum** ≤ 2015 (Economia: 2015 parcial); 2016 ausente | TF-IDF, PPR, graus, enriquecimento: corpus da fase ≤ 2015; LightGBM: pares da fase |
| Validação | 2018 | ≤ 2018 | — | 2019–2021 | sorteio ≤ 2018 / sementes elegíveis ≤ 2018 com positivo / laços ≤ 2018 | 2014–2018 | 2017–2018 | idem, ≤ 2018 |
| Treino final | 2018 | ≤ 2018 | 2019–2021 | — | sorteio ≤ 2018 / da fase / laços ≤ 2018 | 2014–2018 | 2017–2018 | idem, ≤ 2018 |
| Teste | 2021 | ≤ 2021 | — | teste 2022–2024 | sorteio ≤ 2021 / alvos / laços ≤ 2021 | 2017–2021 | **completo** em Economia, Matemática e Computação; **incompleto** em Medicina (§7) | idem, ≤ 2021 |

Versão das entradas: S1 (Economia, Matemática); S2 (Computação, Medicina — Medicina incompleta).
**Conclusão:** o desenho registrado **não é executável** com os dados atuais: a fase de treino de
seleção não tem histórico de candidatos, e as fases de 2018 têm 2 de 5 anos.

### 3.4 Alternativa A — completar o histórico (coleta NÃO autorizada)

- **Mantém** a pergunta: W = 5 em todas as fases, defasagem 3, teste 2022–2024.
- **Coleta necessária:** universo da fase 2018, anos 2014–2016; universo da fase 2015, anos
  2011–2016 (2016 também como rótulo). Autores, autor-anos e custo por base em §7.3
  (`cobertura_historica.json`). Reaproveitáveis: 2015–2016 de Economia (piloto 2019).
- **Reconhecimento:** pares candidato–candidato com a mesma janela de 5 anos em todas as fases
  (proxy ≈ 5–6% de falsos novos, comparável entre fases); sementes completas.
- **Efeito:** seleção 2015 → 2018 viável com cobertura comparável; treino final e teste com a
  mesma janela. A seleção da integração neural continua inviável (exigiria a fase 2012; §5.3).

### 3.5 Alternativa B — janela comum mais curta (sem coleta)

- **Histórico de features dos candidatos: W = 2 anos em todas as fases, inclusive o teste**
  (no teste, 2017–2019 dos candidatos são descartados de propósito, para a cobertura ser
  comparável).
- **Fases:** treino de seleção t = 2018 (rótulos 2019); validação t = 2020 (rótulos 2021); treino
  final t = 2020 (rótulos 2021); teste t = 2021 (rótulos 2022–2024, inalterados).
- **Separado do histórico de features: o horizonte dos rótulos de treino muda** de 3 anos para
  1 ano. A pergunta experimental passa a ser "um ranqueador treinado para prever coautorias
  novas no ano seguinte, avaliado em 3 anos".
- **Reconhecimento de colaborações anteriores (especificado à parte):** sementes completas;
  pares candidato–candidato só na janela de 2 anos (proxy ≈ 14–17% de falsos novos entre os
  rótulos de consultas-candidato). "Nova coautoria" **não** é redefinida: é "não observada no
  passado disponível", e a limitação é declarada.
- **Executável agora:** `--janela-hist 2 --defasagem 1` (implementado). Teste técnico com S1 em
  Economia (sem modelo): alvos 184 e gabarito inalterados; consultas da fase 2020: 199 sementes
  + 2.801 candidatos; **pares alcançáveis em T0 no teste 426 → 348** e alvos da avaliação padrão
  110 → 95, porque o histórico curto tira do corpus futuros coautores.
- **Inviabilidades demonstradas:** (i) B com rótulos de 3 anos na seleção exigiria validação com
  rótulos ≥ 2022 (= teste); (ii) B com W = 5 exigiria histórico desde 2013 para t = 2018;
  (iii) seleção da integração neural exigiria t = 2016 com W = 2 (2015–2016 indisponíveis).

### 3.6 Variante comum às duas (proposta)

- **Consultas de validação = sementes da fase que satisfazem os critérios de alvo** (reconhecimento
  completo), como no teste. Consultas-candidato só no treino.
- Restringir também as consultas de **treino** às sementes eliminaria a contaminação de rótulos,
  mas reduz as consultas de ~3.000 para ~200–320 por fase: é mudança de população de treino,
  dependente de decisão.

### 3.7 Recomendação

- **A** em Economia e Matemática, se a coleta for autorizada: preserva a pergunta, o horizonte e
  a cobertura comparável. **B** como alternativa sem custo, aceitando a mudança do horizonte de
  treino e a contaminação de rótulos medida.
- Em ambas: validação só com sementes (§3.6) e LambdaMART como única seleção (§5.1).
- Nenhuma alternativa foi escolhida pelo desempenho de 2022+, e nenhuma busca foi executada.

## 4. Análise estatística (fixada antes da execução)

### 4.1 Unidade, estimando e horizonte

- **Unidade:** a pessoa-alvo (identidade canônica).
- **Estimando principal, por área:** Δ = média por alvo de [R@50(LambdaMART + KG) −
  R@50(LambdaMART só coautoria)], avaliação estrita, no **horizonte de 3 anos** (2022–2024 para
  c = 2021).
- **Leituras descritivas, sem teste:** o horizonte completo (até 2026-10-08) e a avaliação
  padrão.

### 4.2 Por área (principal) e agregado (complementar)

- A análise **principal é por área**.
- O agregado das 4 áreas, com pesos fixos de **1/4**, é **complementar**. Responde a "o efeito
  médio entre áreas, com cada área pesando igual".
  - Não entra nas famílias de testes.
  - Não é usado para afirmar efeito numa área.
  - Não é apresentado como prova de generalidade.

### 4.3 Melhoria mínima relevante δ (unidades absolutas de R@50)

δ_área = 10% do R@50 médio do **controle** (LambdaMART só coautoria) no **protocolo histórico**
(LTR temporal, corte 2021, todos os alvos; `runs/robustez/precisao.json`). Fica fixado como
constante:

| Área | Controle histórico R@50 (proporção) | **δ (proporção de R@50)** | δ (pp) | Arredondamentos registrados antes |
|---|---:|---:|---:|---|
| Medicina | 0,034718 | **0,003472** | 0,3472 | 0,35 |
| Computação | 0,055476 | **0,005548** | 0,5548 | **0,55 (E0) × 0,56 (PROTOCOLO, `precisao_t4`)** |
| Matemática | 0,093901 | **0,009390** | 0,9390 | 0,94 |
| Economia | 0,060621 | **0,006062** | 0,6062 | 0,61 |

**Constante adotada: o valor não arredondado** (coluna em negrito), recalculado de forma
reproduzível em `scripts/memoria_poder.py`. A divergência 0,55 × 0,56 em Computação é só de
arredondamento (0,5548 pp); não muda nenhuma decisão. Escala: R@50 vai de 0 a 1; "0,61 pp" =
0,0061 de R@50 — não é 0,61 de R@50 nem 0,61% de melhoria relativa (é 10% relativos ao controle).

**Justificativa:**
- Escolha *a priori*: um acerto a mais a cada dez que o controle já obtém, a menor melhoria de
  interesse prático para um ranqueador.
- Ancorada no histórico porque é um valor **anterior** à reanálise. Ancorar no controle
  reconstruído faria δ depender do resultado.
- O controle histórico usa outro horizonte (2022–2026) e outra seleção. Por isso δ é uma
  constante em pp, não uma proporção re-derivada.

### 4.4 Teste, nível e famílias

- **Teste:** H0: Δ = 0, bilateral. Rejeita se o intervalo bootstrap (Poisson por pessoa, §4.6,
  percentil) no nível 1 − α/m excluir 0. α = 0,05; Bonferroni dentro de cada família.

| Família | Comparações | m | Nível do IC |
|---|---|---:|---|
| **F1 (principal)** | Δ R@50 LambdaMART + KG × só coautoria, uma por área (4 áreas) | 4 | 98,75% |
| **F2_área (secundária, uma família por área)** | Δ NDCG@10 do mesmo contraste; Δ R@50 LambdaMART + KG × União RRF; × Adamic-Adar; × vizinhos comuns | 4 | 98,75% |
| Descritivas (sem teste) | agregado 1/4 (IC 95%); horizonte completo; avaliação padrão; P@K incondicional; regimes; C3 (participação do conteúdo no SHAP) | — | 95% |
| F3 (neural, §5; só quando executada) | N2b × N2a; N3 × N0; N4 × N2a; N5 × N2b; N5 × N4; N6 × N0; N2a × N1; N2b × N1, por área | 8 | 99,375% |

- Uma área não executada é reportada como "não executada"; m continua 4. Não se acrescentam
  alvos, cortes ou sementes para obter significância.

### 4.5 Poder, precisão e calibração (E4: memória reproduzível)

**Script:** `scripts/memoria_poder.py` → `runs/robustez/memoria_poder.json` (e
`memoria_poder_calibracao.json`). Semente 20261014; R = 1.000 amostras simuladas, bootstrap
interno B = 1.000 (calibração com B = 10.000).

| Item | Especificação |
|---|---|
| Unidade | pessoa-alvo; Δ_i = R@50(LambdaMART + KG)_i − R@50(só coautoria)_i, avaliação estrita |
| H0 / alternativa | E[Δ] = 0 / **bilateral** |
| Teste | IC percentil do bootstrap; rejeita se excluir 0. Aproximação analítica: z |
| Nível | α nominal 0,05; família F1 com **m = 4**; Bonferroni → **α efetivo 0,0125 por teste** (IC 98,75%; z = 2,4977) |
| δ | 10% do controle histórico (§4.3), em proporção |
| Dispersão | σ de Δ por alvo no **protocolo histórico** (`runs/ltr_temporal/<base>.parquet`; teste já consultado). **Métricas da v2 não foram lidas**; da v2 só as contagens de alvos (n) |
| Forma | muitos zeros (71–81%), assimetria (Medicina +6,2; Computação +3,3; Matemática +2,3; Economia −1,0) |
| Dependência | alvos independentes (sem repetição de pessoa num corte) |
| Fórmula analítica | poder = Φ(δ√n/σ − z) + Φ(−δ√n/σ − z); n80 = ((z + 0,8416)·σ/δ)²; semiamplitude = z·σ/√n |
| Simulação | diferenças históricas reamostradas e **deslocadas** para média δ (poder), 0 (tamanho sob H0) ou a média histórica (efeito observado); efeito aditivo constante suposto |

**Conferência dos números relatados** (3% / 7% de poder; ~4.900 / ~2.500 alvos):

| Base, n (conjuntos congelados, 3 anos) | σ (proporção) | δ√n/σ | Poder analítico, α_ef = 0,0125 | Sem multiplicidade (α = 0,05) | n para 80% (F1) | Semiamplitude 98,75% |
|---|---:|---:|---:|---:|---:|---:|
| Economia, 184 | 0,1268 | 0,649 | **0,033** | 0,099 | **4.877** | 2,33 pp |
| Matemática, 221 | 0,1405 | 0,993 | **0,067** | 0,168 | **2.498** | 2,36 pp |
| Computação, 234 | 0,0436 | 1,946 | 0,291 | 0,495 | 689 | 0,71 pp |
| Medicina, 286 | 0,0219 | 2,676 | 0,571 | 0,763 | 446 | 0,32 pp |

- **Confirmados:** são poderes para δ com α efetivo de 1,25% bilateral (não 5%). Sob H0 a
  frequência nominal de rejeição é 1,25%; 3% e 7% estão acima dela, como devem.
- **Calibração do procedimento (achado novo):** o tamanho empírico do IC percentil sob H0
  ficou acima do nominal: com B = 10.000, Economia 1,9% ± 0,4, Matemática 1,4% ± 0,4,
  Computação 2,0% ± 0,4 e **Medicina 3,4% ± 0,6** (nominal 1,25%). Com B = 1.000: 1,7–5,3%. O IC
  percentil é **anticonservador** para essas distribuições com cauda pesada, sobretudo em
  Medicina. Por isso o poder simulado (Economia 9%, Matemática 7–11%) supera o analítico.
  **[dependente de decisão]:** manter o percentil com essa calibração reportada, ou adotar um
  IC mais bem calibrado (BCa ou bootstrap-t por pessoa), decidido antes da análise e sem olhar
  resultados.
- **Frequência de rejeição sob o efeito observado no histórico** (não é poder; o efeito vem do
  teste consultado): Economia 25%, Matemática 63% com o n da v2.
- **Medicina e Computação** (n dos conjuntos congelados S2, 3 anos): Medicina n = 286 → poder
  analítico **57%** (simulado 76%, com tamanho sob H0 de 3,2%); Computação n = 234 → **29%**
  (simulado 38%). n80 = 446 e 689. Medicina está INCOMPLETA no enriquecimento (o n não depende
  dele).
- **Precisão:** semiamplitude esperada contra δ/2 (Economia 0,30 pp; Matemática 0,47 pp): meta
  descritiva, não regra de parada; inatingível com os n disponíveis.
- **"80% de poder" ≠ "efeito positivo em 80% das execuções"** (critério de estabilidade do T1,
  suspenso: "≥ 4 de 5 execuções"). Não se intercambiam.
- Projeções de n dependem das premissas acima; **não** ampliam coleta nem autorizam alvos.

### 4.6 Bootstrap de Poisson por pessoa e dependência

**Implementação:** `coauthor_rec.eval.bootstrap.poisson_bootstrap`, com B = 10.000 réplicas. (A
simulação de poder usa reamostragem multinomial de alvos independentes; com uma observação por
pessoa, é assintoticamente equivalente.)
- Cada pessoa canônica recebe, por réplica, **um** peso ~ Poisson(1), derivado de um *hash*
  estável da identidade.
- A **mesma identidade tem o mesmo peso em todas as áreas, cortes, horizontes e modelos**, mesmo
  processados separadamente (testado); comparações entre modelos usam as mesmas réplicas.
- Estimativa por área: média ponderada pelos pesos. Agregado: 1/4 por área.

**Limites:**
- Trata a **repetição de pessoas**.
- **Não** resolve automaticamente a dependência entre pessoas diferentes: coautores em comum,
  instituições, candidatos compartilhados, redes.
- A ligação entre áreas depende de identificadores canônicos coincidentes (ORCID ou o mesmo ID
  de autor).

**Reportados junto:**
- pessoas em mais de uma área;
- componentes do grafo alvo–alvo (coautoria ≤ c ou coautor novo em comum): número, tamanhos e
  maior componente;
- sobreposição de janelas, por tipo:
  1. mesmo primeiro evento em dois cortes;
  2. histórico incompleto;
  3. mudança de identidade ou corpus;
  4. "colaboração recorrente" — não pode ocorrer com passado cumulativo; se ocorrer, é defeito.

## 5. Espaço de modelos e treinamento em duas etapas (E5; nada executado)

### 5.1 Ranqueador: variantes e regras fixadas antes da busca

| Variante | Família / algoritmo | Objetivo | Entradas | Configuração | Estado da definição |
|---|---|---|---|---|---|
| V1 padrão | LambdaMART (LightGBM `LGBMRanker`) | `lambdarank` | pares do top-1000 da União RRF; todos os grupos de atributos + atividade | parâmetros padrão do LightGBM, com 400 árvores de 31 folhas e 20 amostras por folha (relatado em `lgbm_params.__doc__`) | **proposto**: reconstruído da docstring; o script de 10/10 não está no repositório |
| V2 regularizada | LambdaMART | `lambdarank` | idem | `models/kg_ltr.lgbm_params`: 200 árvores, lr 0,05, 7 folhas, ≥ 200 por folha, L2 = 5, subamostra 0,8/0,8, truncamento 100, semente 42 | **inspecionado** (exato no código) |
| V3 binária | **classificador pontual** (LightGBM `LGBMClassifier`) — **não é LambdaMART** | `binary` | idem | = V2 com `objective="binary"` e sem truncamento | **proposto** (o original não está no repositório) |
| V4 truncamento 1.000 | LambdaMART | `lambdarank` | idem | = V2 com `lambdarank_truncation_level=1000` | **proposto** |

**Regras fixadas antes da busca:**
- **Critério:** NDCG@10 médio, avaliação estrita, nas consultas de validação (sementes que
  satisfazem os critérios de alvo na fase de validação; §3.6).
- **Métricas registradas:** NDCG@10 (critério), R@50, R@10, Hits@10.
- **Desempate:** se a diferença para V2 for menor que 1 erro-padrão (bootstrap de Poisson por
  pessoa na validação), fica **V2**.
- **Orçamento:** exatamente 4 ajustes por área (sem busca adicional, sem *early stopping*;
  número de árvores fixo); semente 42; uma única rodada.
- **Condições comparáveis:** mesmos pares, atributos, candidatos e consultas para as 4
  variantes; diferenças intencionais apenas no objetivo e nos parâmetros listados.
- **Se V3 vencer** numa área, o modelo dessa área é reportado como classificador pontual.
- Seleção **por área**, gravada (variante, *hash* do código, cópia selada) **antes** do teste.
- Nenhuma escolha usa o desempenho de 2022+.

### 5.2 Contrastes neurais (inalterados; não ampliados)

Base comum: alvos, candidatos (top-1000 da União RRF) e rótulos do protocolo corrigido; desenho
temporal escolhido em §3; avaliações estrita e padrão; testes de F3. O TF-IDF é mantido em todas
as variantes com LambdaMART: os escores neurais **somam** atributos. A variante do LambdaMART
selecionada em §5.1 para N0 é usada igualmente em N1–N5.

| Var. | Arquitetura | Entradas | Treinamento | Comparação que permite |
|---|---|---|---|---|
| N0 | LambdaMART + KG (atributos explícitos, TF-IDF) | atributos dos grupos | fase c−3 | referência |
| N1 | N0 + cosseno SPECTER2 (congelado) | + 1 atributo | igual a N0 (sem parte treinável) | comparador de texto pré-treinado |
| N2a | N0 + escore de um módulo textual **sem convolução**: encoder de tokens + *mean pooling* + camada densa; perfis por autor; escore do par | + 1 atributo (escore fora da amostra) | módulo em duas etapas (§5.3); LambdaMART como N0 | controle da convolução |
| N2b | idêntica a N2a, com **TextCNN** (filtros 1D) no lugar do *pooling* | idem | idem | **N2b × N2a**: efeito da convolução, tudo o mais igual |
| N3 | N0 + escore de uma **R-GCN** (KG tipado ≤ c', um peso por relação, decodificador DistMult) | + 1 atributo | módulo em duas etapas | **N3 × N0**: GNN, dado o ranqueador e o texto TF-IDF |
| N4 | N2a + escore R-GCN | + 2 atributos | idem | **N4 × N2a**: GNN, dado o braço textual sem convolução |
| N5 | N2b + escore R-GCN | + 2 atributos | idem | **N5 × N2b**: GNN, dado o braço com CNN; **N5 × N4**: convolução na presença da GNN |
| N6 | a mesma R-GCN de N3 como **ranqueador único** sobre o top-1000 compartilhado, sem LambdaMART | KG ≤ c' | fase c−3 | **N6 × N0**: sistemas completos; **não** isola componente |

- **Duplicidade eliminada:** N3 é a GNN como atributo do LambdaMART; N6 é a GNN como ranqueador.
- **"LambdaMART só coautoria":** é um controle de **ranqueamento sobre candidatos gerados com o
  KG**, não um pipeline sem KG.

### 5.3 Cronologia das duas etapas (módulo neural → LambdaMART)

**Janelas por arquitetura** (todas leem só fatos ≤ instante, da cópia selada):

| Arquitetura | Histórico exigido no instante t | Sensibilidade ao histórico truncado de candidatos |
|---|---|---|
| N1 SPECTER2 (congelado) | textos dos trabalhos ≤ t na janela W (perfis por autor) | perfis de candidatos com menos trabalhos |
| N2a / N2b (texto treinável) | idem; treino do módulo com rótulos da fase | idem + menos exemplos positivos limpos |
| N3–N6 R-GCN | KG ≤ t inteiro (propagação de 2 saltos) | maior: vizinhanças de candidatos incompletas afetam também os vizinhos |

**Alternativa A (W = 5):**

| Uso | Módulo treinado em (instante → rótulos) | Pontua (instante; janela prevista) | Rótulos vistos pelo módulo |
|---|---|---|---|
| Atributo do treino do LambdaMART | t = 2015 → 2016–2018 | pares da fase 2018 (2019–2021) | ≤ 2018 |
| Atributo do teste | t = 2018 → 2019–2021 | pares do teste 2021 (2022–2024) | ≤ 2021 |

**Alternativa B (W = 2):**

| Uso | Módulo treinado em | Pontua | Rótulos vistos |
|---|---|---|---|
| Atributo do treino do LambdaMART | t = 2018 → 2019 | pares da fase 2020 (2021) | ≤ 2019 |
| Atributo do teste | t = 2020 → 2021 | pares do teste 2021 (2022–2024) | ≤ 2021 |

**Seleção da configuração da integração:**
- Selecionar temporalmente a configuração do módulo e da integração exigiria **uma fase anterior
  à do módulo da 1ª etapa** (t = 2012 em A; t = 2016 com W = 2 em B), sem histórico de candidatos.
- Usar os rótulos da fase de treino do LambdaMART (2019–2021 em A) para escolher hiperparâmetros
  do módulo faria a 2ª etapa aprender sobre previsões de um módulo **ajustado** com os mesmos
  rótulos. Isso é vedado.
- **Portanto:** arquitetura, hiperparâmetros e tratamento de cada módulo são **fixados a
  priori**, registrados antes de qualquer treino neural (proposta a apresentar antes de N2–N6);
  a única seleção é a do LambdaMART (§5.1), aplicada igualmente a N0–N5.
- **Sensibilidade:** módulo único congelado (o da 1ª etapa) pontuando treino e teste.
- Separar pessoas no mesmo intervalo (*cross-fitting*) **não** substitui a exigência temporal e
  não é adotado (o par simétrico vaza).

**Registro de escores** (`coauthor_rec.eval.score_registry`; testado): cada escore registra
consulta, candidato, instante, janela prevista, período dos rótulos de ajuste do módulo, versão do
módulo e uso. Checagem por par/evento/janela:
1. rótulos de ajuste ∩ janela prevista = ∅;
2. rótulos de ajuste ≤ instante;
3. instante < início da janela.

Um par pode aparecer em janelas diferentes; isso não autoriza usar o desfecho futuro dele.

## 6. Comparação histórica × reconstruída

Entre as versões mudam **ao mesmo tempo**:
- sementes (~30% saem);
- elegibilidade (≤ 2021);
- universo de candidatos;
- expansão e KG;
- portanto, gabarito e alvos.

A diferença entre médias de populações diferentes **não é atribuível a um fator**.

- **Comparação principal:** entre modelos, **dentro** de cada versão (mesmos alvos, candidatos e
  gabarito).
- **Complementar:** os alvos comuns às duas versões, informando se os gabaritos coincidem (podem
  diferir pelo corpus, por identidades e pela M9).

## 7. Estado de execução, gasto, cobertura e custo (14/10/2026, 17h30)

### 7.1 Execuções com o universo v2 (técnicas; métricas gravadas e não examinadas) — estado de 15:40, mantido como registro

| | Economia 2019 (piloto) | Economia 2021 | Matemática 2021 |
|---|---:|---:|---:|
| Sementes do corte / elegíveis | 628 / 246 | 739 / 313 | 741 / 344 |
| Universo v2 (v1) | 11.499 (13.939) | 14.472 (15.000) | 14.062 (15.000) |
| Sementes fora do corte no universo: v2 (v1) | 14 (221) | 14 (161) | 26 (196) |
| Verificação do universo (violações) | 0 | 0 | 0 |
| Candidatos novos / ainda não consultados | 1.158 / 0 | 1.539 / 0 | 1.979 / 0 |
| … com ≥ 1 trabalho na área na janela | 785 | 1.011 | 1.377 |
| Alvos, horizonte de 3 anos | 159 (2020–2022) | **184** (2022–2024) | **221** (2022–2024) |
| Alvos, horizonte completo (até 2026-10-08) | — | 204 | 245 |
| Newcomers | 0 | 0 | 0 |
| Pares alcançáveis em T0, 3 anos: v2 (v1) | 507 (532) | 426 (433) | 584 (575) |
| Fase de treino: sementes / universo | 467 / 7.445 (≤ 2016) | 562 / 10.012 (≤ 2018) | 547 / 8.630 (≤ 2018) |
| Anos da janela de treino sem histórico de candidatos | 2012–2014 | 2014–2016 | 2014–2016 |
| Consultas de treino: sementes / candidatos | 224 / 2.776 | 278 / 2.722 | 317 / 2.683 |
| KG de treino e de teste válidos; rótulos dentro das janelas | sim | sim | sim |

**Notas:**
- Pastas: `runs/robustez/t4/reconstrucao_<base>_<c>_v2_coletado_{h3,ate2026-10-08}/`.
- Reprodutibilidade do piloto v2: métricas por alvo idênticas em duas execuções.
- Em Matemática, as execuções gravam a impressão digital dos registros ORCID usados. As de
  Economia foram feitas antes desse registro. O cache ORCID é compartilhado e cresceu durante a
  coleta (§2).

**Conjuntos com as cópias congeladas** (sem modelo; `…_v2_<S>_coletado_{h3,ate2026-10-08}/`):

| | Economia (S1) | Matemática (S1) | Computação (S2) | Medicina (S2, **INCOMPLETA**) |
|---|---:|---:|---:|---:|
| Sementes do corte / elegíveis | 739 / 313 | 741 / 344 | 696 / 297 | 692 / 310 |
| Universo (verificação: violações) | 14.472 (0) | 14.062 (0) | 15.000 (0) | 15.000 (0) |
| Alvos 3 anos / completo | 184 / 204 | 221 / 245 | 234 / 248 | 286 / 291 |
| Consultas de treino (fase 2018): sementes / candidatos | 278 / 2.722 | 317 / 2.683 | 381 / 2.619 | 463 / 2.537 |
| Universo da fase 2018 fora do universo de teste (sem nenhum histórico coletado) | 10 | 12 | 4.378 | 5.614 |

### 7.2 Gasto acumulado (contagem própria, conferida no `/rate-limit` a cada execução)

| Coleta | Créditos | API (créditos do dia) |
|---|---:|---|
| **Piloto 2019** (teto próprio de 2.600; separado) | 818 | 818 |
| 2021, rodada 1 (lacunas v1) | 1.021 (Economia 91, Matemática 198, Computação 321, Medicina 411) | confere |
| 2021, rodada 2 (lacunas v2, Economia e Matemática) | 71 (18 + 53) | 18 + 53 |
| 2021, rodada 3 (lacunas v2, Computação e Medicina; margem global de 100) | **1.208** (Computação 595, Medicina 613) | 595 + 613 |
| **Total de 2021** | **2.300 de 2.400** (saldo 100 = margem) | antes da rodada 3 a API informava 1.910 no dia = 818 + 1.092: nenhum consumo externo |

- Universo usado em cada solicitação: registrado em `coleta_<base>_2021/gasto.json › conferencia_api.universo`
  (caminho e SHA-256 de `candidatos.csv` e `lacunas.csv` v2). A coleta cobre o **universo v2**; não
  é cobertura garantida de um eventual universo novo.
- **Medicina INCOMPLETA:** listas de histórico completas (42 lotes); enriquecimento de trabalhos
  interrompido no teto; ORCID (gratuito) feito depois, sem custo (1.468 leituras).
  - **Pendente:** 26.139 trabalhos e 470 instituições sem enriquecimento → **~533 créditos**
    (`pendencias_enriquecimento_2021.json`), retomável com o mesmo coletor (lotes pulados, cache
    consultado).
  - Efeito: tópicos ausentes em parte do corpus de Medicina (KG `hasTopic` e gerador de tópico).
    Elegibilidade, universo, alvos e gabarito não dependem do enriquecimento.
- Computação: completa (2.521 novos consultados; 19.916 trabalhos e 209 instituições
  enriquecidos; 1.544 leituras ORCID).

### 7.3 Matriz de cobertura histórica (`runs/robustez/t4/cobertura_historica.{json,csv}`)

"Não consultado" ≠ zero publicações. Situação por autor do universo da etapa:

| Base | Etapa (features; rótulos de consultas-candidato) | Universo | Cobertura completa | Situação | Autor-anos não consultados | Custo incremental (créditos) | Componentes |
|---|---|---:|---:|---|---:|---:|---|
| Economia | teste 2021 (2017–2021) | 14.472 | 100% | com registros 9.467; sem registros 3.732; registros todos excluídos na limpeza 1.259; sementes 14 | 0 | 0 | teste |
| Economia | fase 2018 (2014–2018; 2019–2021) | 10.012 | 0,1% | parcial 9.997 (2017–2018; 2015–2016 do piloto, **não integrados** à reconstrução de 2021); sementes 15 | 9.997 | ~120–250 | treino final; validação; módulo da 2ª etapa |
| Economia | fase 2015 (2011–2015; 2016–2018) | 6.188 | 0,2% | parcial 6.175 | 24.700 | ~290–620 | treino de seleção; módulo da 1ª etapa |
| Matemática | teste 2021 | 14.062 | 100% | 10.231 / 2.966 / 839 / 26 | 0 | 0 | teste |
| Matemática | fase 2018 | 8.630 | 0,3% | parcial 8.603; sementes 27 | 25.809 | ~520–650 | idem |
| Matemática | fase 2015 | 5.172 | 0,5% | parcial 5.148 | 30.888 | ~620–770 | idem |
| Computação | teste 2021 | 15.000 | 100% | 12.219 / 2.276 / 493 / 12 | 0 | 0 | teste |
| Computação | fase 2018 | 15.000 | 0,1% | **não consultado 3.542**; parcial 11.443 | 62.665 | ~1,6–2,9 mil | idem |
| Computação | fase 2015 | 15.000 | 0,2% | **não consultado 7.241**; parcial 7.735 | 104.338 | ~2,6–4,8 mil | idem |
| Medicina | teste 2021 (listas) | 15.000 | 100% das listas; **enriquecimento incompleto** | 14.193 / 627 / 178 / 2 | 0 | ~533 (enriquecimento) | teste |
| Medicina | fase 2018 | 15.000 | 0,05% | **não consultado 5.458**; parcial 9.535 | 72.269 | ~1,8–5,3 mil | idem |
| Medicina | fase 2015 | 15.000 | 0,1% | **não consultado 8.354**; parcial 6.634 | 106.636 | ~2,7–7,8 mil | idem |
| Economia | piloto: teste 2019 / fase 2016 | 11.499 / 7.445 | 100% / 0,2% | — | 0 / 22.299 | 0 / ~260–560 | piloto |

- **Custos:** faixa entre a taxa por autor-ano da coleta de 2021 da base (Economia 0,012;
  Matemática 0,020; Computação 0,046; Medicina 0,073) e a do piloto (0,025). Os custos das fases
  2018 e 2015 **não se somam** (os anos 2014–2016 se sobrepõem). São estimativas, não autorizações.
- **Efeitos potenciais** (não presumidos nulos):
  - **features:** graus, atividade, perfis textuais e vizinhanças de candidatos truncados nas
    fases 2018/2015; em Computação e Medicina, um terço a mais da metade do universo da fase não
    tem nenhum histórico coletado;
  - **elegibilidade:** sem efeito, porque usa só sementes (bruto completo);
  - **geração de candidatos:** o universo é escolhido pelos trabalhos das sementes (completo); a
    pontuação dos geradores usa o histórico truncado;
  - **reconhecimento de colaborações anteriores:** proxy de falsos novos com janela curta (§3.2):
    Economia 13,8%, Matemática 16,9%, Computação 7,6%, Medicina 11,5% (instante 2018, janela de
    2 anos); 2,3–6,1% com 5 anos;
  - **rótulos:** os das sementes estão completos; os das consultas-candidato são afetados pelo
    reconhecimento truncado.
- **Comparação principal:** só em condições comparáveis de cobertura (alternativa A, ou B com a
  janela comum). Análises com cobertura assimétrica (o desenho atual, com W = 5 no teste e 2 no
  treino) ficam identificadas como tais. Restringir a população à interseção de casos completos
  **não** é proposto: em Computação e Medicina eliminaria a maior parte do universo das fases.

### 7.4 Poder e precisão com os n atuais

Ver §4.5 (memória completa em `runs/robustez/memoria_poder.json`).
