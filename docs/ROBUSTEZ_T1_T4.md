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

**Decisão de 14/10/2026 (amostra do piloto).** O piloto usa **todas** as sementes do
conjunto de 1.000 sorteadas por trabalho ≤ 2019, com a elegibilidade recalculada:
- **628 sementes e 246 elegíveis.** As "596" citadas antes vinham do inventário, que partia do
  corpus higienizado; 32 sementes não estão nele porque todas as suas autorias caíram na
  limpeza. A reconstrução parte do bruto.
- É uma **amostra retrospectiva condicionada ao mecanismo original de seleção**, sem afirmar
  representatividade histórica.
- **E3 não é relaxado.**
- A versão anterior com 500 sementes (189 elegíveis, 121 alvos) fica só como registro.

A precisão estatística dessa amostra é tratada em §4.1, não pela contagem de alvos.

### 3.5 Volume, custo e limite de gasto para a coleta do piloto (estimativa prévia; resultado em 3.5.1)

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

### 3.5.1 Resultado técnico do piloto Economia/2019 (14/10/2026) **[executado] [verificado]**

Parâmetros pré-registrados preservados (`configs/robustez.yaml › t4.piloto`; 628 sementes,
§3.4).

**Coleta (`scripts/coletor_t4.py`):**

| Item | Valor |
|---|---|
| Lotes de histórico | 280 de 280: 32 de candidatos novos (2015–2019) e 248 dos anos 2015–2016 dos já coletados |
| Trabalhos coletados | 32.404 distintos (43.343 linhas antes da deduplicação entre lotes) |
| Enriquecimento | trabalhos: 23.645 consultados, 8.759 já em cache; instituições: 198 consultadas, 5.097 em cache; ancestrais: 4 consultados, 24 em cache |
| ORCID | 168 leituras (gratuitas); 578 já em cache |
| **Gasto contado** | **818 créditos** (histórico 320, enriquecimento 498), de um teto de 2.600 |
| **Gasto informado pela API** (`/rate-limit`, antes e depois) | **818 créditos do dia**; pré-pago inalterado (76.872), porque o gasto coube na franquia diária gratuita. Valor nominal: US$ 0,08 |
| Estimativa prévia | ~1.255. O real foi menor: muitos candidatos não têm trabalho na área em 2015–2016 |

**Incidente registrado.** A primeira versão do enriquecimento relia o cache inteiro (3,5 GB) a
cada bloco de 1.000 trabalhos, o que levaria ~5 h. A coleta foi interrompida com segurança: a
contabilidade foi salva e a API confirmou 340 créditos, igual à contagem própria, sem consulta
fora dela. O enriquecimento foi substituído por uma rotina que lê só os IDs do cache e cobra cada
consulta antes de fazê-la (`enrich_lean`, testada). A retomada pulou os 280 lotes já feitos.

**Cobertura e lacunas restantes:**
- Todas as lacunas identificadas foram consultadas.
- Dos 1.560 candidatos novos, 1.107 têm ≥ 1 trabalho na área em 2015–2019. Dos 12.379 já
  coletados, 8.046 têm trabalho em 2015–2016. Os demais não têm trabalho na área nesses anos:
  isso é ausência na fonte, não falha de coleta.
- O enriquecimento ficou com 100% de cobertura (tópicos e instituições no cache).
- **Não há lacuna de coleta pendente** para o piloto.
- As limitações remanescentes são de **metadados atuais** (§3.5.3).

### 3.5.2 Reconciliação das contagens da amostra (`scripts/reconciliacao_piloto_t4.py`)

Fluxo por semente (`runs/robustez/t4/reconciliacao_economia_2019.{csv,json}`):

```
1.000 sementes brutas (seeds.csv)
 └─ 628 sorteadas por trabalho publicado ≤ 2019
     ├─ 596 presentes no corpus higienizado ATUAL  ← o "596" do inventário (que partia desse corpus)
     └─  32 ausentes dele:
           29 — todas as autorias removidas na limpeza (sem resumo/título/idioma)
            3 — autorias restantes rejeitadas na higienização (nível X)
 └─ elegibilidade E1–E8 com autorias ≤ 2019 (higienização refeita a partir do BRUTO):
       246 elegíveis
       353 inelegíveis com os dados disponíveis: E3 324, E5 70, E4 68, E7 14,
           sem publicação ≤ 2019: 9, E6 6, E8 4 (uma semente pode ter vários motivos)
        29 indeterminadas quanto ao ORCID (registro ausente do cache) — são exatamente as 29 sem
           nenhuma autoria após a limpeza: o ORCID não foi consultado porque não havia autoria;
           sem trabalho elegível, não poderiam ser alvo de qualquer forma
 └─ 159 alvos avaliáveis (≥ 1 coautoria nova em 2020–2022, após M9)
        87 elegíveis sem coautoria nova no horizonte
```

- **596 → 628:** o inventário (`inventario_t4.py`) contava só sementes presentes no corpus
  higienizado atual. A reconstrução parte do bruto (`seeds.csv`) e conta todas as sorteadas por
  trabalho ≤ 2019. As 32 a mais são as ausentes do corpus atual, com os motivos acima, e nenhuma
  delas é elegível.
- **189 → 246:** a versão anterior usava as **500 primeiras** pela ordem de sorteio (189
  elegíveis). A atual usa **todas as 628**: as 128 seguintes acrescentam 57 elegíveis. Não houve
  mudança de regra.
- **"Comprovada" com ressalva:** a inelegibilidade por E3, E4 e E7 usa o retrato **atual** do
  ORCID e do OpenAlex (§3.5.3). É inelegibilidade com os dados disponíveis, não comprovação
  histórica.

### 3.5.3 Higienização temporal: o que foi refeito e o que continua dependendo de metadados atuais

**Refeito.** A reconstrução parte das autorias e trabalhos **brutos** (antes da limpeza) e
reaplica limpeza, canonicalização, níveis e E1–E8:
- a elegibilidade é calculada só com autorias ≤ 2019;
- o KG usa só fatos ≤ 2019.

**Continua dependente de metadados atuais** (medido no corpus do piloto; registrado como
limitação, sem correção):

| Decisão | Depende de | Volume no T0 do piloto |
|---|---|---|
| Nível A (E3) | reivindicações no ORCID **atual** | 18.737 de 145.375 autorias |
| Vínculo I1 (E4) | afiliações no ORCID **atual** (com checagem de ano ±1) | 19.768 autorias |
| Nível X (E7, corpus) | nomes atuais (OpenAlex/ORCID) | 464 autorias |
| Canonicalização por ORCID | ligação autor–ORCID atual; 1.191 `author_id` têm ORCID só em trabalhos pós-corte | **0** autorias de T0 afetadas |
| Limpeza | resumo, idioma e campo atuais | não medido |
| Desambiguação de autores e tópicos | estado do OpenAlex em 09/10/2026 | não mensurável |

### 3.5.4 Especificação do treino e da avaliação do piloto

Gravada em `relatorio.json › modelo.especificacao_e_checagens`, com asserções que abortam a
execução se violadas.

| Elemento | Especificação |
|---|---|
| Rótulos de treino | coautorias novas em **2017–2019**, sobre o KG ≤ 2016 (consultas: sementes + candidatos do corte com coautoria nova; até 3.000, semente 42) |
| Rótulos de teste | coautorias novas em **2020–2022**, sobre o KG ≤ 2019 |
| Validação | **nenhuma**: sem parada antecipada nem busca de hiperparâmetros no piloto |
| Hiperparâmetros | **fixos** (`lgbm_params`, semente 42), os do modelo principal |
| Negativos | todos os candidatos do top-1000 da União RRF que não são coautores novos; consultas sem positivo saem do treino |
| TF-IDF | ajustado **separadamente** em cada KG, só com textos daquele passado: 24.634 trabalhos ≤ 2016 (treino) e 49.901 ≤ 2019 (teste) |
| Demais transformações | escores de meta-caminhos e atividade calculados em cada KG; anos relativos ao corte; sem padronização |
| Checagens automáticas | rótulos de treino em (2016, 2019]; rótulos de teste > 2019; KGs sem fatos posteriores aos cortes; datas máximas das autorias ≤ corte |
| Reprodutibilidade | duas execuções completas: métricas por alvo **idênticas** (681 linhas, diferença 0,0) |
| Métricas | gravadas (`metricas_por_alvo.parquet`), **não interpretadas** |

**Ressalva sobre os hiperparâmetros (corrigida em 14/10/2026).**
- Os hiperparâmetros fixos (`lgbm_params`) foram escolhidos **antes**, entre 4 variantes, na
  validação cruzada de Economia do protocolo **original**, cujos rótulos são de 2022 em diante.
- A janela de teste do piloto (2020–2022) **inclui 2022**. Na reprodução de 2021, os rótulos de
  teste são os **mesmos** usados naquela escolha.
- Portanto, os rótulos de teste **influenciaram** a configuração. A magnitude dessa influência
  **não foi medida**.

### 3.5.5 Reprodução, exploração e confirmação

| Modo | Configuração | Rótulos consultados para defini-la | Uso |
|---|---|---|---|
| **Reprodução** | a histórica (`lgbm_params`, semente 42), congelada | os de teste da referência (influência não medida) | comparar com a referência histórica; mostrar o efeito da correção da seleção. **Não** é confirmação |
| **Exploração** | qualquer outra escolha feita olhando resultados de teste (piloto, ablações, variantes) | os de teste | gerar hipóteses; reportada como exploratória |
| **Confirmação** | definida **sem consultar os rótulos de teste** daquela avaliação | só rótulos **anteriores** à janela de teste | sustentar as conclusões C1–C4 |

**Protocolo confirmatório proposto (pré-registrado aqui, antes de qualquer execução):**
1. **Espaço de busca fixo:** as mesmas 4 variantes avaliadas antes, sem acrescentar outras:
   padrão; regularizada lambdarank (a atual); regularizada binária; truncamento 1.000.
2. **Validação temporal anterior ao teste.** Para uma avaliação com corte c e teste em
   (c, c+H]:
   - **treino de seleção:** KG ≤ c−6 → rótulos em (c−6, c−3];
   - **validação:** KG ≤ c−3 → rótulos em (c−3, c].
   - Para c = 2021: treina em KG ≤ 2015 → 2016–2018 e valida em KG ≤ 2018 → 2019–2021.
   - Nenhum rótulo depois de c é consultado.
3. **Critério de escolha:** NDCG@10 médio na validação. Desempate: a variante mais regularizada.
   Escolha **por área**, registrada antes de abrir o teste.
4. **Treino final** com a variante escolhida: KG ≤ c−3 → (c−3, c], como no modelo principal.
   Depois, **uma única** avaliação no teste.
5. **Congelamento:** a configuração escolhida e o *hash* do código ficam gravados em
   `runs/robustez/confirmacao/<base>/config.json` **antes** de gerar o teste.

**Limitação de dados:** os candidatos têm histórico só em 2017–2021. Para c = 2021, o KG ≤ 2015
de seleção tem histórico de candidatos vazio (só as sementes), o que torna a validação mais pobre
que o treino final. Isso é declarado. Alternativa: validar só com o par 2018 → 2019–2021 e
selecionar por validação cruzada **temporal interna** às consultas de treino.

O T1 e o T4 confirmatórios usam a configuração assim definida. A reprodução histórica
continua disponível separadamente.

### 3.6 Auditoria dos sorteios 43–44 (ampliação posterior; decisão independente dos modelos)

`scripts/auditoria_sorteios.py` (dados locais; nenhum resultado de modelo consultado).
Saída em `runs/robustez/t4/auditoria_sorteios.json`.

| Aspecto | Economia | Matemática |
|---|---|---|
| Sorteios coletados | 42 (1.152 sementes), 43 (1.128), 44 (650) | 42 (1.415), 43 (1.350) |
| Usadas hoje | 1.000 primeiras do 42 | 1.000 primeiras do 42 |
| Quadro e regras | mesmo filtro e procedimento; `sample(2000, seed=s)` independentes | idem |
| Deduplicação | autores de um sorteio são excluídos dos seguintes: 43–44 são amostras **sem reposição de autores, condicionadas ao 42** | idem |
| Trabalhos sorteados repetidos entre sorteios | 1 | 1 |
| Autores repetidos | 0 | 0 |
| Sementes do 43 / 44 coautoras (≤ 2019) de sementes do 42 | 56 / 33 | 111 (43) |
| Sementes do 43 / 44 que já são candidatas atuais | 70 / 38 | 113 (43) |
| Cobertura ORCID no cache (≤ 2019), sorteio 43 | 667 de 698 | **129 de 786**: elegibilidade **indeterminada** sem ~650 leituras ORCID |
| Enriquecimento em cache | completo | faltam ~47 mil trabalhos (sorteio 43 e excedente do 42) |
| Elegíveis ≤ 2019, mesma regra (42 completo / 43 / 44) | 272 / 252 / 132 | 280 / (56, subestimado) |
| Com o teto de 15 mil, incluir 43–44 muda os candidatos | 8.734 novos candidatos (de 15 mil) | 8.442 |
| Créditos estimados (2019; inclui expansão e enriquecimento) | ~2,0 mil | ~3,7 mil |

**Viabilidade.**
- **Técnica:** sim. Mesmo quadro e regras, histórico das sementes já coletado.
- **Metodológica:**
  - 43–44 não são independentes do 42 (deduplicação de autores; 5–14% das sementes coautoras
    ou candidatas do 42);
  - com o teto fixo de 15 mil, mudam o universo de candidatos de **todos** os alvos, o que
    torna os resultados não comparáveis ao conjunto atual;
  - em Matemática, falta ORCID e enriquecimento.

**Ordem recomendada:** primeiro **completar o sorteio 42** (sementes além das 1.000 primeiras:
+152 em Economia, +415 em Matemática). É a mesma amostra, sem condicionamento entre sorteios.
Os sorteios 43–44 vêm só depois, com o teto de candidatos reavaliado e nova estimativa.

### 3.7 Horizonte e temporalidade do ORCID

- **Horizonte:**
  - avaliação principal corrigida de 2021: rótulos de 2022 até out/2026 (~4,8 anos; 2026
    incompleto), o mesmo da referência histórica;
  - piloto 2019 e T4: rótulos em (c, c+3], 3 anos;
  - comparações entre cortes usam a variante de 3 anos (2021: 2022–2024); a diferença de
    acompanhamento é declarada sempre que se compara com a avaliação principal
    (PROTOCOLO_CORRIGIDO_2021.md §3).
- **ORCID:**
  - o E3 do T4 é "trabalho publicado até o corte e reivindicado no ORCID **atual**": critério
    retrospectivo baseado no estado atual;
  - **não** é "reivindicação comprovadamente disponível no corte". A evidência histórica
    possível (data de criação de cada item do registro ORCID) está planejada em
    PROTOCOLO_CORRIGIDO_2021.md §4.

## 4. Critérios de estabilidade (fixados antes de rodar)

### 4.1 Precisão estatística

Detalhe em [PROTOCOLO_CORRIGIDO_2021.md](PROTOCOLO_CORRIGIDO_2021.md) §5
(`scripts/precisao_t4.py`):
- contraste principal: Δ R@50 (LambdaMART + KG − só coautoria), pareado;
- melhoria mínima relevante: δ = 10% relativo;
- precisão desejada: semiamplitude do IC 95% ≤ δ/2.

A dispersão de Δ é muito maior nas áreas esparsas. Com ~160 alvos, a semiamplitude esperada
é de ~1,9 pp em Economia, contra δ = 0,61 pp. Um corte isolado de uma base esparsa **estima**
efeitos do tamanho observado na referência (~+1 a +2 pp), mas **não** resolve δ de 10%. Daí a
proposta confirmatória: estimativa conjunta e estratificada entre bases (e entre cortes, no
T4), com estimativas por base interpretadas pelo intervalo.

### 4.2 Critérios

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
| N2a | **Controle sem convolução**: o mesmo encoder de tokens, os mesmos textos, a mesma tarefa de treinamento (pares alvo–candidato com rótulos temporais) e a mesma agregação por autor que N2b, com *mean pooling* + camada densa no lugar da convolução; escore do par como atributo do LambdaMART | isola o efeito da convolução | [planejado] |
| N2b | **Variante com CNN**: idêntica a N2a, com TextCNN (filtros 1D sobre os tokens) no lugar do *pooling* | se a convolução acrescenta, mantido tudo o mais | [planejado] (há uma TextCNN do ciclo anterior a adaptar) |
| N3 | **GNN: R-GCN heterogênea** sobre o KG tipado (um peso por relação), decodificador DistMult | relações aprendidas por propagação contra relações explícitas | [planejado] |
| N4 | **Fusão com GNN, texto sem convolução**: LambdaMART + KG + R-GCN + N2a | se a GNN acrescenta ao ranqueador | [planejado] |
| N5 | **Fusão com GNN, texto com CNN**: LambdaMART + KG + R-GCN + N2b | o contraste N2b × N2a repetido na presença da GNN | [planejado] |
| N6 | R-GCN + KG sozinha (sem LambdaMART) | a GNN como sistema completo | [planejado] |

**SPECTER2 (N1) permanece como comparador independente** de texto pré-treinado. O efeito da
CNN é medido **só** pelo contraste controlado N2b × N2a: mesmo encoder de tokens, mesmos
textos, mesma tarefa, mesma agregação por autor, mudando só a convolução. É repetido na fusão
com a GNN (N5 × N4).

Comparações centrais (pareadas, Bonferroni):
- N2b vs N2a (efeito da convolução);
- N2a e N2b vs N1 (contra o comparador pré-treinado);
- N3/N6 vs N0 (GNN contra atributos explícitos);
- N4 vs N0 (a GNN acrescenta?);
- N5 vs N4 (a convolução acrescenta na presença da GNN).

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
| 4 | Decidir o tamanho da amostra do T4 | 3 | — | **decidido** (14/10/2026): todas as sementes sorteadas ≤ corte; E3 sem relaxar |
| 5 | Coletor de lacunas com limite de gasto | 4 | — | [implementado] [testado] |
| 6 | Coleta paga do piloto T4 | 5 e autorização | **818 créditos** (teto 2.600) | [executado] [verificado contra a API] |
| 7 | Pipeline do corte reconstruído (higienização, enriquecimento, KG, treino temporal, avaliação) e piloto completo em Economia 2019 | 6 | local | [executado] [verificado: checagens e reprodutibilidade] |
| 8 | **Protocolo corrigido de 2021** (a mesma reconstrução com c = 2021) nas 4 bases | 7 | ~0,3 mil (Economia), ~0,5 mil (Matemática), ~2,6 mil (Computação), ~4,6 mil (Medicina) créditos (inventário; reestimar após 6) | [planejado] |
| 9 | T1 completo sobre o protocolo corrigido | 8 | local (~6–9 h) | [implementado o executor; execução bloqueada] |
| 10 | T4 completo (5 cortes × 4 bases) | 7, 8 | ~70 mil créditos no total (reestimar após 6) | [planejado] |
| 11 | Modelos neurais N2–N6 sobre a infraestrutura comum | 8 (protocolo); em paralelo a 9–10 | local; GPU opcional (Medicina) | [planejado] |
| 12 | Consolidação: estabilidade de C1–C4 e comparações neurais | 9, 10, 11 | local | [planejado] |
