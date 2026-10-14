# Especificação metodológica única — reanálise retrospectiva temporal (protocolo corrigido)

**Versão:** 14/10/2026, universo de candidatos **v2**.

**O que este documento faz:** reúne num só lugar as decisões que ficam **congeladas antes das
próximas execuções**. Em caso de conflito, prevalece sobre ROBUSTEZ_T1_T4.md e
PROTOCOLO_CORRIGIDO_2021.md, que apontam para cá.

**O que continua fora deste documento:**
- O protocolo histórico (`main @ 477dcd1`) não muda; é a referência.
- O T1 completo continua **suspenso** até a validação do pipeline corrigido.
- Decisões ainda pendentes de aprovação estão marcadas **[pendente]**.

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
examinadas**.

**Confirmação independente:** exige dados reservados, que não tenham influenciado o
desenvolvimento. Pode ser feita com acompanhamento futuro: coautorias publicadas depois de
2026-10-08, coletadas numa data a fixar, com esta especificação congelada. Fica como etapa
posterior e **não bloqueia** a reanálise.

## 2. Populações e conjuntos (um corte c)

| Conjunto | Definição | Papel |
|---|---|---|
| Sementes do corte | as do sorteio 42 cujo trabalho sorteado é ≤ c, todas (sem subamostra) | geram o universo de candidatos e o corpus |
| Sementes elegíveis (alvos potenciais) | sementes do corte que cumprem E1–E8 com autorias ≤ c (ORCID: retrato atual; E3 sem relaxar) | só elas são alvos |
| Universo de candidatos | coautores das **sementes do corte**, em trabalhos ≤ c com equipe ≤ teto. Exclui só as sementes do corte. Até 15 mil, priorizados pelo laço (nº de trabalhos ≤ c em comum), desempate com semente fixa | autores cujo histórico entra no corpus |
| Corpus | todos os trabalhos das sementes do corte (bruto) + trabalhos dos candidatos na janela [c−4, c] (expansão original e coleta do T4). Nada depois do fim dos rótulos | KG ≤ c; rótulos em (c, fim] |

**Regras do universo:**
- O universo é gerado **só** pelos trabalhos das sementes do corte (`candidate_universe_at_cut`).
- Uma semente **fora do corte** (sorteada por trabalho posterior) **pode ser candidata**, se for
  coautora até c de uma semente do corte. Ela não é proibida só por ter sido excluída como alvo.
- Como no protocolo original (em que as 1.000 sementes geram o universo e só as elegíveis são
  alvos), sementes do corte inelegíveis geram o universo, mas não são alvos nem candidatas.

**Verificações automáticas** (abortam a execução):
- todo candidato tem um trabalho ≤ c, com equipe ≤ teto, junto a uma semente do corte;
- nenhuma semente do corte é candidata.

A reprodução do universo **histórico** (todas as sementes, T0 = 2021, `candidates.csv`) é um
teste separado e continua passando (diferença 0).

**Cache ORCID:** é compartilhado e cresce com as coletas. Entre duas execuções do piloto, 19
registros novos mudaram 2 autorias de nível A, sem mudar as métricas. Em Matemática, as
elegibilidades da auditoria dos sorteios mudaram (280 → 282).
- Cada reconstrução grava a impressão digital (contagem e SHA-256) dos registros usados na
  elegibilidade e na higienização.
- A avaliação final usa um **instantâneo congelado** do cache, registrado antes da execução.

**Denominadores:**
- **Alvos estritos:** elegíveis com ≥ 1 coautoria nova no horizonte, após M9. Denominador por
  alvo: **todos** os coautores novos, presentes ou não no corpus.
- **Alvos da avaliação padrão:** alvos estritos com ≥ 1 coautor novo presente em T0.
  Denominador: só esses. É leitura complementar.
- **Elegíveis sem coautoria nova:** contados à parte, fora das métricas condicionais.
- **Newcomers:** com E5 (≥ 2 trabalhos) calculado até c, não há elegíveis sem trabalho em T0. O
  grupo é **vazio** por construção no protocolo corrigido; só existe no histórico.
- **P@K com lista < K:** denominador K. As listas têm 1.000 candidatos; o número de listas
  curtas é reportado.

## 3. Estratégia temporal (fechada antes de treinar)

**Decisão tomada agora**, com dados restritos temporalmente. **Não** é apresentada como escolha
feita em 2021.

### 3.1 Construção de cada fase: cada exemplo respeita o próprio corte

Uma fase com corte c' (treino do modelo, ou treino de módulo neural) é construída como um corte
reconstruído (`scripts/reconstrucao_t4.py › training_phase`):

| Elemento | Regra na fase c' |
|---|---|
| Sementes | as do corte c **sorteadas por trabalho ≤ c'**. As sorteadas em (c', c] foram escolhidas por atividade posterior a c' e ficam fora |
| Universo | `candidate_universe_at_cut` com essas sementes e laços ≤ c' (mesma regra e teto) |
| Consultas de treino | sementes e candidatos **da fase** com coautoria nova em (c', c] (até 3.000, semente 42) |
| Corpus | trabalhos das sementes da fase + trabalhos dos candidatos da fase na janela [c'−4, c'] e em (c', c] (rótulos) |
| KG, TF-IDF, meta-caminhos, atributos, enriquecimento | recalculados no corpus da fase, só com fatos ≤ c' (tabelas de enriquecimento próprias, `enrich_treino/`) |
| Rótulos | coautorias novas em (c', c] |

Nenhum laço posterior a c' escolhe consultas, candidatos ou exemplos de treino. Antes da
correção, o treino em c−3 usava o corpus do teste: candidatos escolhidos por laços em
(c−3, c], ou seja, pelos próprios rótulos de treino.

**Limitação que permanece (declarada, não corrigida):** os candidatos só têm histórico coletado
a partir de 2017 (2015 no piloto de 2019). Na fase 2018 (teste de 2021), a janela de histórico
dos candidatos tem 2 dos 5 anos (2017–2018). Isso cria uma diferença de cobertura entre os
atributos de treino e de teste. Completar a janela exige coleta (custo em §7), que não está
autorizada.

### 3.2 Treino do modelo e seleção de hiperparâmetros

- **Treino final:** fase c−3 (KG ≤ c−3 → rótulos (c−3, c]); aplicação ao teste KG ≤ c →
  rótulos (c, c+H].
- **Espaço de busca:** fixo, as 4 variantes já avaliadas, sem acrescentar outras:
  1. padrão (`lambdarank`, parâmetros do LightGBM);
  2. regularizada `lambdarank` (a atual, `lgbm_params`);
  3. regularizada **binária**: objetivo `binary`, **classificador pontual, não LambdaMART**. Se
     for escolhida numa área, o modelo dessa área é um classificador pontual, e isso é reportado;
  4. truncamento 1.000.
- **Estratégia única de seleção:** validação cruzada em 5 dobras **por pessoa**, dentro da fase
  c−3 (rótulos (c−3, c] ≤ 2021).
  - Nas dobras de treino, removem-se os pares cujo candidato é consulta da dobra de validação.
    Isso evita aprender o par simétrico (B, A) e avaliá-lo como (A, B).
  - Critério: NDCG@10 médio na validação (já registrado). Desempate (diferença < 1 erro-padrão
    entre dobras): a variante mais regularizada.
  - Escolha **por área**, gravada em `runs/robustez/confirmacao/<base>/config.json` (variante,
    *hash* do código) **antes** de gerar o teste.
- **Por que não a validação temporal 2015 → 2018** (antes em ROBUSTEZ §3.5.5): a fase 2015, com
  a construção de §3.1, não tem histórico de candidatos na janela 2011–2015, nem os trabalhos
  dos candidatos de 2016 (rótulos). A validação seria feita num regime de dados degenerado.
  - Fica registrada como alternativa que exige coleta (§7).
  - **[pendente: confirmação do usuário]** — muda o desenho registrado em 3.5.5 pelo motivo
    acima; nenhuma seleção foi executada.
- **Reprodução histórica:** `lgbm_params` congelados, rodados também, como reprodução (não como
  confirmação).

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

| Área | Controle histórico R@50 | **δ (pp de R@50)** |
|---|---:|---:|
| Medicina | 3,47 | **0,35** |
| Computação | 5,55 | **0,55** |
| Matemática | 9,39 | **0,94** |
| Economia | 6,06 | **0,61** |

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

### 4.5 Poder e precisão (separados)

**Poder de detecção:** probabilidade de o IC de F1 (nível 98,75%) excluir 0 se Δ = δ.
- Aproximação normal: poder ≈ Φ(δ·√n/σ − z_{1−0,05/8}), com z = 2,50.
- **Premissas:** σ = desvio-padrão por alvo de Δ no protocolo histórico (outra seleção e outro
  horizonte); alvos independentes, exceto a repetição de pessoas; distribuição com muitos zeros
  (a aproximação é otimista).
- Valores para o n de cada área em §7.

**Precisão do intervalo:** semiamplitude esperada z·σ/√n, comparada com δ/2. É uma **meta
descritiva**, não uma regra de parada.

**O "80%" dos documentos anteriores tem dois sentidos, agora separados:**
1. **"n para 80% de poder"** em `precisao_t4.py`: teste z bilateral, α = 0,05 sem Bonferroni,
   efeito δ, σ histórico. É planejamento aproximado, não critério.
2. **"≥ 80% das execuções"** (ROBUSTEZ §4.2): critério de **estabilidade** do T1/T4, não poder.
   - Passa a ser "≥ 4 de 5 execuções": C1/C2 com o IC de F1/F2 excluindo 0, mesmo sinal, por
     área.
   - C3: em cada execução, a participação média do conteúdo (|SHAP| de tópicos + citação + texto)
     no polo esparso (média de Matemática e Economia) é maior que no polo denso (média de
     Medicina e Computação).
   - O T1 continua suspenso.

### 4.6 Bootstrap de Poisson por pessoa e dependência

**Implementação:** `coauthor_rec.eval.bootstrap.poisson_bootstrap`, com B = 10.000 réplicas.
- Cada pessoa canônica recebe, por réplica, **um** peso ~ Poisson(1), derivado de um *hash*
  estável da identidade.
- A **mesma identidade tem o mesmo peso em todas as áreas, cortes e horizontes**, mesmo
  processados separadamente (testado).
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

## 5. Contrastes neurais (fechados; nada implementado nesta etapa)

Base comum a todas as variantes:
- alvos, candidatos (top-1000 da União RRF) e rótulos do protocolo corrigido;
- treino temporal (§3);
- avaliações estrita e padrão;
- testes de F3.

O TF-IDF é **mantido** em todas as variantes com LambdaMART: os escores neurais **somam**
atributos, não substituem.

| Var. | Arquitetura | Entradas | Treinamento | Comparação que permite |
|---|---|---|---|---|
| N0 | LambdaMART + KG (atributos explícitos, TF-IDF) | atributos dos grupos | fase c−3 | referência |
| N1 | N0 + cosseno SPECTER2 (congelado) | + 1 atributo | igual a N0 (sem parte treinável) | comparador de texto pré-treinado |
| N2a | N0 + escore de um módulo textual **sem convolução**: encoder de tokens + *mean pooling* + camada densa; perfis por autor; escore do par | + 1 atributo (escore fora da amostra) | módulo em duas etapas (§5.1); LambdaMART como N0 | controle da convolução |
| N2b | idêntica a N2a, com **TextCNN** (filtros 1D) no lugar do *pooling* | idem | idem | **N2b × N2a**: efeito da convolução, tudo o mais igual |
| N3 | N0 + escore de uma **R-GCN** (KG tipado ≤ c', um peso por relação, decodificador DistMult) | + 1 atributo | módulo em duas etapas | **N3 × N0**: GNN, dado o ranqueador e o texto TF-IDF |
| N4 | N2a + escore R-GCN | + 2 atributos | idem | **N4 × N2a**: GNN, dado o braço textual sem convolução |
| N5 | N2b + escore R-GCN | + 2 atributos | idem | **N5 × N2b**: GNN, dado o braço com CNN; **N5 × N4**: convolução na presença da GNN |
| N6 | a mesma R-GCN de N3 como **ranqueador único** sobre o top-1000 compartilhado, sem LambdaMART | KG ≤ c' | fase c−3 | **N6 × N0**: sistemas completos; **não** isola componente |

- **Duplicidade eliminada:** N3 é a GNN como atributo do LambdaMART; N6 é a GNN como ranqueador.
- **"LambdaMART só coautoria":** é um controle de **ranqueamento sobre candidatos gerados com o
  KG**, não um pipeline sem KG.

### 5.1 Treino em duas etapas com previsões fora da amostra produzidas temporalmente

Cada módulo neural é treinado numa fase anterior ao conjunto que pontua. As fases seguem §3.1.

| Etapa | Módulo treinado em | Pontua | Rótulos vistos pelo módulo |
|---|---|---|---|
| Atributo do **treino** do LambdaMART | fase c−6: KG ≤ c−6 → rótulos (c−6, c−3] | pares da fase c−3 (entradas ≤ c−3) | só ≤ c−3 |
| Atributo do **teste** | fase c−3: KG ≤ c−3 → rótulos (c−3, c] | pares do teste (entradas ≤ c) | só ≤ c |

- O LambdaMART (2ª etapa) é ajustado com rótulos (c−3, c]. Os escores que recebe vêm de um
  módulo que **nunca viu** esses rótulos.
- No teste, o módulo viu rótulos ≤ c, nunca os de teste.
- Cada módulo prevê "os 3 anos seguintes aos seus rótulos", a mesma relação no treino e no
  teste.

**Registrados por módulo:**
- fase;
- períodos de entrada e de rótulo;
- *hash* do código e dos pesos;
- distribuição dos escores nos dois usos (compatibilidade).

**Sensibilidade:** módulo único congelado (fase c−6) pontuando treino e teste.

**Limitação de dados:** para c = 2021, a fase c−6 = 2015 não tem histórico de candidatos (§3.1).
O módulo da 1ª etapa seria treinado num grafo degenerado. Opções, a decidir antes de executar
N2–N6:
- **[pendente]** coletar o histórico 2011–2016 do universo da fase 2015 (custo em §7);
- ou declarar a assimetria e reportar a compatibilidade.

Fazer *cross-fitting* por pessoa no mesmo período **não** é adotado: o par simétrico vaza entre
as dobras.

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

## 7. Estado de execução, gasto e custo restante (14/10/2026, 15:40)

### 7.1 Execuções com o universo v2 (técnicas; métricas gravadas e não examinadas)

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

### 7.2 Gasto acumulado (contagem própria, conferida no `/rate-limit` a cada execução)

| Coleta | Créditos |
|---|---:|
| Piloto 2019 (teto próprio de 2.600) | 818 |
| 2021 até a revisão (lacunas v1) | 1.021 (Economia 91, Matemática 198, Computação 321, Medicina 411) |
| 2021, lacunas v2 de Economia e Matemática (autorizadas nesta etapa) | **71** (Economia 18, Matemática 53; API: 18 e 53 créditos do dia; pré-pago intocado) |
| **Total de 2021** | **1.092 de 2.400**; saldo **1.308** |

### 7.3 Custo restante (estimativas; nada autorizado além do teto atual)

**Computação e Medicina (lacunas v2, já descontado o que foi consultado):**
- Computação: 2.521 candidatos novos não consultados. Custo **~530–560 créditos**.
- Medicina: 2.062 candidatos novos não consultados. Custo **~510–1.140 créditos**.
- O intervalo vai do estimador do script (média de trabalhos por candidato-ano; enriquecimento
  sem desconto de cache) ao custo real médio por candidato da coleta anterior da mesma base
  (que já embute o aproveitamento de cache: 47% em Computação, 61% em Medicina).
- **Total: ~1,0–1,7 mil**, contra um saldo de 1.308. Pode não caber; não amplio o teto.

**Janelas completas nas fases de treino** (opcional; `runs/robustez/t4/custo_janelas_fases_treino.json`):

| Fase | Economia | Matemática | Computação | Medicina |
|---|---:|---:|---:|---:|
| 2018: anos 2014–2016 do universo da fase | ~350–750 | ~520–650 | ~1,1–2,0 mil | ~1,1–5,0 mil |
| 2015 (1ª etapa neural / validação temporal): anos 2011–2016 | ~430–930 | ~620–780 | ~2,3–4,0 mil | ~2,3–9,9 mil |

As faixas vão da taxa por candidato-ano da coleta de 2021 da base à do piloto (0,025).

### 7.4 Poder e precisão com os n atuais (F1, aproximação normal; §4.5)

| | Economia, 3 anos (n = 184) | Matemática, 3 anos (n = 221) |
|---|---:|---:|
| δ (pp) | 0,61 | 0,94 |
| σ histórico de Δ (pp) | 12,7 | 14,1 |
| **Poder para δ** (IC 98,75%) | **~3%** | **~7%** |
| n para 80% de poder em F1 | ~4.900 | ~2.500 |
| Semiamplitude esperada do IC 98,75% / 95% (pp) | 2,3 / 1,8 | 2,4 / 1,9 |
| Meta de precisão δ/2 (pp) | 0,30 | 0,47 |

**Consequência, declarada antes de qualquer resultado:**
- Em Economia e Matemática, o teste F1 **não tem poder** para detectar um efeito do tamanho de
  δ.
- Um IC que inclua 0 **não** é evidência de ausência de efeito. Esses resultados são
  interpretados pela estimativa e pelo intervalo.
- Um IC que exclua 0 só ocorrerá para efeitos muito maiores que δ. O efeito da referência
  histórica foi de +1,3 a +2,5 pp, mas foi observado no mesmo teste já consultado e não pode
  justificar nada aqui.
- Não se ampliam alvos para obter significância (§4.4).
