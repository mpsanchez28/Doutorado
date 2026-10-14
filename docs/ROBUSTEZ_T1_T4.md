# Robustez científica — T1 (robustez a sementes) e T4 (generalização temporal), e plano integrado

Itens T1 e T4 do [plano pós-banca](PLANO_POS_BANCA.md), aplicados ao **modelo principal**
(LambdaMART + KG, treino temporal) e às 4 bases.

- Branch: `research/t1-t4-robustez`. Referência histórica preservada em `477dcd1`.
- Configuração própria: `configs/robustez.yaml`. Resultados: `runs/robustez/`.
- Auditoria da seleção: [AUDITORIA_SELECAO.md](AUDITORIA_SELECAO.md).

**Legenda de estado:**
- **[implementado]**: código existe;
- **[executado]**: rodou;
- **[verificado]**: tem checagem independente;
- **[planejado]**: ainda não implementado.

## 0. Correções em relação à versão anterior deste documento (14/10/2026)

Três afirmações da versão anterior **foram retiradas**, porque os diagnósticos não as
sustentam:

1. *"A seleção por atividade futura torna os resultados conservadores."* O alvo sorteado
   depois de 2021 ter desempenho menor é uma diferença **descritiva** entre subconjuntos de um
   modelo treinado no protocolo original. Ela se confunde com a quantidade de histórico dos
   alvos e não estima o desempenho de um protocolo corrigido. A direção do viés **não está
   determinada** (AUDITORIA_SELECAO.md §5).
2. *"Filtrar as sementes pelo ano do trabalho sorteado dá uma amostra histórica válida."*
   Dá uma subamostra uniforme entre os trabalhos **do quadro atual** do OpenAlex publicados até
   c. O quadro atual não é o que existia em c: indexação posterior, tópicos atuais e ORCID
   atual. Também não resolve a elegibilidade nem os candidatos (AUDITORIA_SELECAO.md §2, §6).
3. *"Os metadados atuais não podem afetar a predição / o resíduo é pequeno e não direcionado."*
   O efeito não foi medido e não pode ser presumido.

A reconstrução do T4 passa a ser descrita como **retrospectiva pela data dos fatos, com
metadados atuais** (§3).

## 1. Conclusões a proteger

| # | Conclusão | Evidência atual (semente 42, corte 2021, protocolo original) |
|---|---|---|
| C1 | O KG melhora além da coautoria (H0-KG) | LTR completo > só coautoria em R@50, significativo nas 4 bases |
| C2 | O aprendizado supera a fusão sem aprendizado | LTR completo > União RRF; significativo em Medicina e Economia |
| C3 | O peso do conteúdo cresce do polo denso ao esparso (H3) | \|SHAP\| do conteúdo 18% → 29% → 36–45% |
| C4 | Supera os baselines clássicos | +36% a +91% sobre vizinhos comuns e Adamic-Adar |

A auditoria (AUDITORIA_SELECAO.md) mostrou que esse protocolo original usa informação
posterior a 2021 na **seleção** das sementes, na **elegibilidade** e nos **metadados**. Por
isso, a confirmação final de C1–C4 exige o protocolo corrigido (§3.3), não só T1 e T4 sobre o
protocolo original.

## 2. T1 — o que efetivamente varia

| Tipo de variação | Pergunta que responde | Implementado? |
|---|---|---|
| **Sementes do algoritmo** (LightGBM `random_state`: subamostragem de linhas e colunas) | o resultado depende do acaso do ajuste do modelo? | **sim** (modo `lightgbm`) |
| **Novas amostras de treinamento** (re-sorteio das consultas de treino entre sementes e candidatos com coautoria nova em 2019–2021) | depende de quais exemplos de treino foram usados? | **sim** (modo `consultas`) |
| Ambos juntos | variabilidade total do treino | **sim** (modo `ambos`) |
| **Novas amostras de autores** (outro sorteio de sementes da área) | depende de quais pesquisadores entraram na base? | **não**: exige nova coleta (outro sorteio, histórico, expansão, higienização). Aproximação parcial: bootstrap sobre os alvos, que mede a incerteza de amostrar alvos, mas não refaz o corpus. Sorteios 43 e 44 já coletados em Economia e Matemática (`seeds_full.csv`) poderiam servir, mas exigiriam expansão e enriquecimento próprios **[planejado, não orçado]** |

O executor `scripts/robustez_t1.py` **[implementado] [verificado em Economia]** implementa as
duas primeiras. Ele responde: *"dado este corpus, as conclusões dependem do acaso do treino?"*.
Ele **não** responde se dependem da amostra de autores.

Verificações do executor, piloto técnico em Economia, sem interpretação de desempenho:
- **fidelidade:** a rodada de referência (42, 42) reproduz exatamente
  `runs/ltr_temporal/economia.json`;
- **reprodutibilidade:** duas execuções idênticas bit a bit;
- **vazamento:** valida os KGs de 2018 e de 2021 e os intervalos de rótulos, e aborta se
  houver violação.

**A bateria completa do T1 não será executada** antes de resolver a dependência temporal da
seleção. Rodá-la sobre o protocolo original mediria só a estabilidade de um protocolo que a
auditoria mostrou ser dependente de informação posterior ao corte. O T1 completo roda sobre o
**protocolo corrigido de 2021** (§3.3), quando ele existir.

## 3. T4 — generalização temporal

### 3.1 Por que o corpus atual não serve para outros cortes

Detalhado em AUDITORIA_SELECAO.md §2:
- o quadro de sorteio inclui trabalhos até 2026;
- os candidatos foram escolhidos por laços até 2021, com expansão em 2017–2021;
- a elegibilidade usa todos os anos;
- os metadados são atuais.

O diagnóstico em Economia (`scripts/diagnostico_t4.py`) mostrou o efeito da seleção dos
candidatos: no corpus completo, o alcance dos cortes antigos fica inflado (39,9% em 2018
contra 29,3% em 2021).

### 3.2 Análises complementares condicionadas ao corpus (não substituem a reconstrução)

| Desenho | O que faz | Limitação |
|---|---|---|
| Só sementes | KG só com os trabalhos das sementes atuais | sementes selecionadas com informação até 2026; alcance de 8–10% (Economia) |
| Laço até o corte | candidatos atuais com laço ≤ c | candidatos escolhidos e priorizados por laços até 2021; histórico encurtado |

### 3.3 Protocolo preferencial: reconstrução retrospectiva pela data dos fatos

Para um corte c, cada etapa da construção é refeita usando apenas **fatos datados até c**. Os
**metadados** (desambiguação, tópicos, afiliações, ORCID, resumos) **são os de hoje**: não há
versões históricas disponíveis nas APIs. Etapas:

1. **Sementes:** as do sorteio original cujo trabalho sorteado tem ano ≤ c, as primeiras N pela
   ordem de sorteio.
2. **Elegibilidade:** E1–E8 recalculados com autorias ≤ c. E1/E3 seguem dependentes do ORCID
   atual.
3. **Candidatos:** `select_candidates`, a mesma função da expansão original, com essas
   sementes, laços ≤ c e teto de 15 mil.
4. **Expansão:** histórico de c−4 a c de cada candidato. Reaproveita o já coletado e coleta só
   as lacunas.
5. **Limpeza, higienização, enriquecimento e KG:** refeitos sobre esse corpus, com KG ≤ c
   validado.
6. **Treino temporal:** KG em c−3 e rótulos em (c−3, c]. **Teste:** coautorias novas em
   (c, c+3], com M9, nas avaliações estrita e padrão.

**Limitações:**
- metadados atuais (AUDITORIA_SELECAO.md §2);
- quadro de sorteio atual (§0, correção 2);
- E1/E3 com o ORCID atual;
- a subamostra de sementes por corte é menor que 1.000.

### 3.4 Etapa 1 do T4: piloto local em Economia, corte 2019 **[implementado] [executado] [verificado]**

Pré-registrado em `configs/robustez.yaml › t4.piloto`, antes de qualquer resultado:
- corte 2019 e rótulos 2020–2022;
- 500 sementes sorteadas por trabalho ≤ 2019;
- elegibilidade ≤ 2019;
- candidatos com laços ≤ 2019 e histórico 2015–2019;
- treino KG 2016 → 2017–2019;
- métricas R@10, R@50, NDCG@10 e Hits@10, estrita e padrão;
- comparações pareadas com Bonferroni: LTR completo contra só coautoria, União RRF,
  Adamic-Adar e vizinhos comuns.

`scripts/reconstrucao_t4.py` rodou só com dados locais, em 16 s, sem chamadas.

| Verificação | Resultado |
|---|---|
| A função de candidatos reproduz o original (1.000 sementes, laços ≤ 2021) | **sim**: 15.000 de 15.000, diferença 0 |
| Sementes do corte | 596 sorteadas por trabalho ≤ 2019; usadas 500 |
| Elegíveis com autorias ≤ 2019 | **189 de 500** |
| Alvos avaliáveis (com coautoria nova em 2020–2022) | **121** |
| Candidatos no corte | 14.067 (abaixo do teto: a priorização não corta ninguém) |
| Já coletados / novos | 12.379 / 1.688 |
| Lacunas | 1.688 candidatos sem histórico; anos 2015–2016 para os 12.379 já coletados |
| Corpus local parcial → KG | KG **válido**: fatos até 2019; rótulos em 2020–2022 |

**Achado que afeta o desenho:** só 189 das 500 sementes são elegíveis com dados até 2019,
gerando 121 alvos. O gargalo é E3 (reivindicação no ORCID de algum trabalho ≤ c). Com tão
poucos alvos, o poder estatístico por corte é baixo. Opções a decidir antes da coleta paga:
- **(a)** usar todas as sementes sorteadas ≤ c (596), o que dá ~140 alvos;
- **(b)** incluir os sorteios 43–44 já coletados em Economia (`seeds_full.csv`, 2.930
  sementes), o que exige enriquecimento dos trabalhos extras;
- **(c)** relaxar E3 no T4 e reportar a sensibilidade.

### 3.5 Volume, custo e limite de gasto para a coleta do piloto **[planejado; nenhuma chamada feita]**

Com base em `runs/robustez/t4/reconstrucao_economia_2019/relatorio.json`, usando a média de
trabalhos por candidato e ano da expansão original (±50% de incerteza):

| Item | Volume estimado |
|---|---|
| Candidatos novos (janela 2015–2019 inteira) | 1.688 |
| Candidatos já coletados (anos 2015–2016) | 12.379 |
| Trabalhos a coletar | ~22 mil |
| Consultas de lista (lotes de 50 autores + páginas de 200) | ~400 |
| Consultas de enriquecimento (tópicos e instituições; 50 IDs por consulta) | ~880 |
| **Créditos OpenAlex** | **~1.275 (≈ US$ 0,13)** |
| Leituras ORCID (candidatos novos sem cache) | 215 (gratuitas; cota de 100 mil/dia) |

**Limite de gasto proposto para o piloto: 2.600 créditos (≈ US$ 0,26)**, o dobro da
estimativa. O coletor do piloto **[planejado]** deve:
- contar os créditos consumidos a cada consulta;
- abortar ao atingir o limite, com o progresso salvo;
- registrar o gasto real contra o estimado.

**Ampliação, depois do piloto validado** (estimativa do inventário, `scripts/inventario_t4.py`,
5 cortes):
- Economia ~3 mil créditos;
- Matemática ~4,6 mil;
- Computação ~22 mil;
- Medicina ~40 mil;
- total ~70 mil (≈ US$ 7) e ~44 mil leituras ORCID.

A estimativa da ampliação será refeita com o gasto real do piloto.

**Nota sobre as duas estimativas.** O inventário (`inventario_t4.py`) é uma aproximação feita
sobre o corpus **higienizado**. A reconstrução (`reconstrucao_t4.py`) usa a mesma função e as
mesmas autorias **brutas** da expansão original, e por isso prevalece. Em Economia 2019, o
inventário previa 664 candidatos novos; a reconstrução encontrou 1.688. Os valores da
ampliação acima são do inventário e tendem a estar **subestimados**. A cobertura local do
piloto é de 52,8% dos pares (candidato, ano) da janela.

## 4. Critérios de estabilidade (fixados antes de rodar)

- **Variação:** coeficiente de variação entre sementes ≤ 10% em R@50 e NDCG@10 (T1).
- **Conclusões:** C1, C2 e C3 em ≥ 80% das sementes (T1) e dos cortes (T4).
- **Leitura:** uma conclusão que falhe vira ressalva explícita.

## 5. Plano integrado: modelos neurais (texto com e sem CNN, GNN, fusões)

A confirmação final (T1/T4 sobre o protocolo corrigido) deve abranger também as comparações
neurais centrais da tese. Todos os modelos compartilham a mesma infraestrutura:
- protocolo corrigido;
- pares (alvo, candidato) do top-1000 da União RRF;
- treino temporal;
- avaliações estrita e padrão;
- testes pareados.

| # | Modelo | O que testa | Estado |
|---|---|---|---|
| N0 | **LambdaMART + KG, texto TF-IDF** (modelo principal) | referência | [implementado] [executado] |
| N1 | **Controle textual sem CNN**: LambdaMART + KG + similaridade de embeddings pré-treinados (SPECTER2) | texto forte sem rede treinável | [implementado] [executado]: empate com N0 (TEXTO_SPECTER2.md) |
| N2 | **Variante com CNN**: TextCNN treinada sobre tokens dos resumos (como `gnn/fusion.py`), escore do par como atributo do LambdaMART | se uma cabeça convolucional treinável acrescenta ao texto pré-treinado | [planejado] (existe uma TextCNN do ciclo anterior a adaptar) |
| N3 | **GNN: R-GCN heterogênea** sobre o KG tipado (um peso por relação), decodificador DistMult | relações aprendidas por propagação contra relações explícitas | [planejado] |
| N4 | **Fusão sem CNN**: LambdaMART + KG + escore/embeddings da R-GCN | se a GNN acrescenta ao ranqueador | [planejado] |
| N5 | **Fusão com CNN**: LambdaMART + KG + R-GCN + CNN | contribuição marginal da CNN na presença da GNN | [planejado] |
| N6 | R-GCN + KG sozinha (sem LambdaMART) | a GNN como sistema completo | [planejado] |

Comparações centrais (pareadas, Bonferroni):
- N2 vs N1 (efeito da CNN no texto);
- N3/N6 vs N0 (GNN vs atributos explícitos);
- N4 vs N0 (GNN acrescenta?);
- N5 vs N4 (CNN acrescenta na presença da GNN).

Requisitos comuns:
- treino temporal;
- negativos difíceis do conjunto de candidatos;
- amostragem de vizinhança escalável para Medicina;
- mesmos alvos e conjunto de candidatos do modelo principal.

O histórico do projeto (GNN e GAT empatando com a coautoria; CNN sem ganho na fusão,
ABLACAO_CAMADAS.md) torna plausíveis resultados negativos, igualmente informativos.

**Paralelismo:** depois de validar o protocolo corrigido e a infraestrutura comum (pares,
avaliação, testes), o desenvolvimento neural (N2–N6) pode avançar em paralelo à preparação do
T1/T4. A confirmação final roda tudo sob os mesmos T1/T4.

## 6. Plano de execução, dependências e custos

| # | Etapa | Depende de | Custo | Estado |
|---|---|---|---|---|
| 1 | Auditoria da seleção e elegibilidade ≤ 2021 | — | local | [implementado] [executado 4 bases] [verificado] |
| 2 | Diagnóstico descritivo por subconjunto | 1 | local | [implementado] [executado 4 bases] |
| 3 | Reconstrução local do piloto T4 (Economia, 2019) e lacunas | — | local | [implementado] [executado] [verificado] |
| 4 | Decidir o tamanho da amostra do T4 (§3.4: a, b ou c) | 3 | — | **decisão pendente** |
| 5 | Coletor de lacunas com limite de gasto | 4 | — | [planejado] |
| 6 | Coleta paga do piloto T4 | 5 e autorização | ≤ 2.600 créditos | [planejado; não iniciado] |
| 7 | Pipeline do corte reconstruído (higienização, enriquecimento, KG, treino temporal, avaliação) e piloto completo em Economia 2019 | 6 | local + enriquecimento (incluído em 6) | [planejado] |
| 8 | **Protocolo corrigido de 2021** (a mesma reconstrução com c = 2021) nas 4 bases | 7 | ~0,3 mil (Economia), ~0,5 mil (Matemática), ~2,6 mil (Computação), ~4,6 mil (Medicina) créditos (inventário; reestimar após 6) | [planejado] |
| 9 | T1 completo sobre o protocolo corrigido | 8 | local (~6–9 h) | [implementado o executor; execução bloqueada] |
| 10 | T4 completo (5 cortes × 4 bases) | 7, 8 | ~70 mil créditos no total (reestimar após 6) | [planejado] |
| 11 | Modelos neurais N2–N6 sobre a infraestrutura comum | 8 (protocolo); em paralelo a 9–10 | local; GPU opcional (Medicina) | [planejado] |
| 12 | Consolidação: estabilidade de C1–C4 e comparações neurais | 9, 10, 11 | local | [planejado] |
