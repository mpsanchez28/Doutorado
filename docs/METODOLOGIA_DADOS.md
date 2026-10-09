# Dados: coleta, seleção e higienização

> Texto-base para o capítulo de Materiais e Métodos da tese. Cada decisão é apresentada com
> sua **justificativa** e, quando aplicável, com a **evidência empírica** que a motivou e as
> **alternativas descartadas**. Os números finais das bases são gerados automaticamente em
> `docs/RESULTADOS_BASES.md` (`scripts/report_bases.py`). Implementação: repositório
> `github.com/mpsanchez28/Doutorado` (pacote `coauthor_rec`).

---

## 1. Visão geral

A tarefa da tese — recomendar coautores como **predição de links futuros** — exige dados com
três propriedades que não são garantidas pelas fontes bibliográficas abertas:

1. **Representatividade** — a amostra deve refletir a área de pesquisa, não um recorte
   enviesado (por exemplo, apenas os trabalhos mais citados).
2. **Estrutura preservada** — a rede de coautoria precisa conter as colaborações passadas
   e futuras dos autores avaliados; amostras que fragmentam a rede tornam a tarefa vazia.
3. **Identidade verificável** — cada aresta de coautoria precisa ligar a **pessoa certa** ao
   **trabalho certo**, na **instituição certa**; erros de identidade contaminam diretamente a
   verdade fundamental (seção 6.1).

O processo foi organizado em seis etapas, cada uma com critérios explícitos e versionados:

```
 OpenAlex ──► (1) definição da área ──► (2) amostragem por sementes aleatórias
                                              │ histórico completo das sementes
                                              ▼
              (3) critérios de inclusão de artigos (idioma, ano, abstract, campos)
                                              ▼
 ORCID ─────► (4) higienização de autores: pessoa canônica, níveis de evidência,
 ROR              vínculo institucional, coautoria validada, elegibilidade E1–E8
                                              ▼
              (5) controle de qualidade: gate de rede + auditoria + amostra manual
                                              ▼
              (6) corpus higienizado + autores-alvo  ──►  split temporal T0 → T1
```

### 1.1 Evolução do protocolo

O protocolo atual é resultado de três iterações; registrá-las justifica as escolhas finais.

| Iteração | Desenho | Limitação identificada |
|---|---|---|
| Estudo inicial (SBBD) | *Snowball* a partir de **um** artigo-semente (área médica) | Uma semente enviesa a amostra para a vizinhança de um grupo (crítica da banca) |
| Base temática de IA | Recorte por *Concepts* de IA, na **ordem padrão da API** | A ordem padrão é por citações (amostra = elite citada) e o filtro por *Concepts* aceita marcações irrelevantes (seções 3.2 e 4.1) |
| **Protocolo atual** | 4 áreas por **campo de *Topics***, **1.000 sementes aleatórias por área com histórico completo**, **histórico dos candidatos (2017–2021)**, **corte por ano civil** e **higienização com ORCID** | — |

Os experimentos anteriores (realizados sobre as duas primeiras bases) permanecem documentados
e reprodutíveis; as conclusões definitivas da tese são reavaliadas sobre as bases atuais.

---

## 2. Fontes de dados

### 2.1 OpenAlex
Índice bibliográfico aberto (licença CC0) que sucedeu o Microsoft Academic Graph (Priem;
Piwowar; Orr, 2022), com cobertura comparável às bases comerciais (Visser; van Eck; Waltman,
2021). **Por que foi escolhido:** acesso irrestrito via API (reprodutibilidade por terceiros),
identificadores persistentes para trabalhos, autores, instituições e fontes, e metadados de
afiliação, citação e classificação temática — os insumos do grafo de conhecimento.
**Entidades usadas:** *works* (trabalhos), *authorships* (autor × trabalho, com instituições e
ORCID), *topics* (classificação temática) e *institutions* (com ROR).
**Limitações relevantes:** a atribuição de autoria é automática (sujeita a fusão e
fragmentação de identidades), a classificação temática é automática, e os dados mudam com o
tempo — por isso a **data de coleta** é registrada e os dados brutos são preservados.

### 2.2 ORCID
Identificador persistente e **autodeclarado** de pesquisadores (Haak et al., 2012). **Por que
foi usado:** é a única fonte aberta em que a própria pessoa declara seus trabalhos e vínculos —
uma âncora de identidade independente do algoritmo de desambiguação do OpenAlex. Consultou-se
o registro público (API v3.0): nomes, DOIs dos trabalhos reivindicados e afiliações (com
identificador da organização e período). **Limitação:** a adoção é desigual entre áreas,
países e gerações, e muitos registros estão incompletos (seção 6.2).

### 2.3 ROR
*Research Organization Registry*, identificador aberto de instituições, presente nas
afiliações do OpenAlex. Usado para verificar o vínculo autor–instituição (seção 6.4, M5).

---

## 3. Desenho das bases

### 3.1 Quatro recortes num gradiente de densidade
A hipótese H3 afirma que *o ganho do sinal textual sobre o estrutural cresce com a
esparsidade da rede de coautoria*. Testá-la exige variar a densidade da rede mantendo o resto
constante. Foram definidas **quatro bases**, uma por área, posicionadas num gradiente de
densidade de colaboração conhecido na literatura cienciométrica (Newman, 2001; Wuchty; Jones;
Uzzi, 2007):

| Base | Área (campo do *primary topic*) | Densidade esperada |
|---|---|---|
| Medicina | `fields/27` Medicine | alta — equipes grandes, colaboração recorrente |
| Ciência da Computação | `fields/17` Computer Science | intermediária |
| Matemática | `fields/26` Mathematics | baixa — 1 a 3 autores por artigo |
| Economia | `fields/20` Economics, Econometrics and Finance | baixa |

**Por que dois polos esparsos:** Matemática e Economia têm densidades próximas; mantê-las
separadas dá robustez à extremidade do gradiente (n=4 em vez de 3) e permite estimar a
variabilidade da tendência entre áreas de densidade semelhante.

**Por que o mesmo protocolo e o mesmo número de sementes:** todas as bases usam a mesma
amostragem e param em **1.000 sementes**. A primeira versão parava em 60.000 autores distintos,
para igualar o catálogo de candidatos; mas, como as áreas de equipes grandes atingem esse número
com poucas sementes (Medicina: 250; Economia: 2.930), o número de **autores avaliados** ficava
até 10 vezes menor no polo denso do gradiente — justamente onde a H3 precisa de poder
estatístico. Fixar as sementes iguala as **unidades de avaliação** entre as áreas; trabalhos por
autor, densidade e tamanho do catálogo passam a ser propriedades da área. Economia e Matemática,
coletadas na versão anterior, foram reduzidas às 1.000 primeiras sementes — como as sementes
estão em ordem aleatória, é uma subamostra aleatória, idêntica a uma coleta que tivesse parado
em 1.000.

### 3.2 Por que campos de *Topics* e não *Concepts*
O OpenAlex oferece duas classificações temáticas: *Concepts* (multi-rótulo, com score por
conceito; descontinuada) e *Topics* (hierarquia domínio > campo > subcampo > tópico, em que
os campos seguem a classificação ASJC; cada trabalho tem **um** *primary topic*).

A primeira versão do protocolo usou *Concepts* de nível 0. Um piloto revelou que o filtro
`concepts.id` da API aceita **qualquer** marcação, **inclusive com score zero**: numa coleta de
"Economia", 20% dos trabalhos eram colaborações de física de partículas (marcadas com
*Economics* score 0,0 e *Physics* 0,92), concentrando 84% das autorias. Em amostras aleatórias
(n = 200 por área):

| Área | Trabalhos com score do *Concept* < 0,3 | com score = 0 | com campo principal ≠ área |
|---|---:|---:|---:|
| Medicina | 32% | 6% | 52% |
| Computação | 33% | 8% | 84% |
| Matemática | 68% | 21% | 90% |
| Economia | 72% | 34% | 86% |

**Decisão:** a área é definida pelo **campo do *primary topic***, filtrado no servidor
(`primary_topic.field.id`). Cada trabalho pertence a exatamente um campo — uma partição limpa
e reprodutível.

---

## 4. Estratégia de amostragem

### 4.1 O problema: a ordem da API vira a amostra
Cada campo tem milhões de trabalhos (Medicina ≈ 52 M; Economia ≈ 9 M) e coleta-se uma fração
ínfima. Constatou-se que a consulta temática devolve os trabalhos **ordenados por número de
citações**; coletar "os primeiros N" equivale a coletar a elite citada. Como trabalhos muito
citados tendem a ter equipes maiores (Wuchty; Jones; Uzzi, 2007), a densidade observada é
inflada — e de forma desigual entre áreas, o que **inverteria o gradiente da H3**:

| Área | Autores/artigo — mais citados (média · mediana) | — amostra aleatória | Inflação |
|---|---:|---:|---:|
| Medicina | 15,9 · 7 | 5,3 · 4 | 3,0× |
| Computação | 6,6 · 3 | 3,4 · 2 | 1,9× |
| Economia | 8,1 · 3 | 2,9 · 2 | 2,8× |
| Matemática | 5,4 · 3 | 3,1 · 2 | 1,7× |

Entre os mais citados, Economia pareceria mais densa que Computação. Com amostra aleatória e
filtro por campo, o gradiente esperado aparece: **Medicina 6,0 > Computação 2,9 > Matemática
2,2 ≈ Economia 2,1** autores por artigo (média; n = 200, semente 42).

### 4.2 Alternativas consideradas

| Estratégia | Representativa? | Preserva a rede? | Por que (não) foi adotada |
|---|:-:|:-:|---|
| Ordem padrão da API (mais citados) | ✗ | parcial | Enviesa a densidade e inverte o gradiente (4.1) |
| Amostra aleatória de trabalhos | ✓ | ✗ | Autores raramente reaparecem: sem colaborações futuras, a verdade fundamental fica quase vazia |
| *Snowball* de semente única | ✗ | ✓ | Amostra a vizinhança de um único grupo (crítica da banca) |
| **Sementes aleatórias + histórico completo** | ✓ | ✓ | **Adotada** — combina as vantagens (4.3) |

Amostrar grafos grandes preservando suas propriedades é um problema conhecido (Leskovec;
Faloutsos, 2006); a estratégia adotada é uma amostragem por nós aleatórios seguida da expansão
de 1 passo restrita à área.

### 4.3 Procedimento adotado (`seeded_collect`)
1. **Sorteio de trabalhos aleatórios** do campo (`sample` da API com sementes fixas —
   reprodutível), em lotes de 2.000 trabalhos.
2. **Um autor com ORCID por trabalho sorteado** vira candidato a semente. Tomar todos os autores
   de cada trabalho super-representaria quem publica em equipes grandes — um artigo de 8 autores
   renderia 8 candidatos (efeito análogo ao "paradoxo da amizade", Feld, 1991). No piloto, essa
   correção reduziu a densidade da amostra de 3,65 para 3,0 autores por artigo.
3. **Coleta do histórico completo** de cada semente no campo (2004 em diante), em lotes de 50
   autores por consulta. Os coautores das sementes entram no catálogo de candidatos.
4. **Parada** ao atingir **1.000 sementes** (3.1). Trabalhos com mais autores que o teto de
   coautores (seção 5) permanecem nos dados brutos, mas não geram arestas nem consultas ao ORCID.
5. Registro das sementes (`seeds.csv`) e dos parâmetros de cada sorteio.

### 4.4 Quem é avaliado: sementes elegíveis
Só as **sementes** têm o histórico completo na área; os coautores aparecem apenas nos trabalhos
compartilhados com alguma semente. Avaliar um coautor como alvo subestimaria seu passado (T0) e
seu futuro (T1). Por isso, os **autores-alvo** da avaliação são as **sementes que satisfazem os
critérios de elegibilidade** (seção 6.5); os demais autores participam do grafo e do catálogo de
candidatos.

### 4.5 Expansão: histórico dos candidatos
**Problema.** Com o histórico completo só das sementes, um coautor aparece com o único trabalho
feito junto à semente (mediana de 1 trabalho no piloto de Economia). Consequência medida: só
**12,9%** dos coautores novos das sementes em T1 estavam presentes em T0 — um teto de recall
de ~13% para qualquer modelo — e os perfis dos candidatos eram pobres. Uma verificação no
OpenAlex (200 casos) mostrou que **45%** desses ausentes já publicavam no campo antes do corte:
a ausência era, em boa parte, **artefato da coleta**, e não iniciantes reais.
**Procedimento.** Para cada **candidato** — coautor de alguma semente em trabalho de T0 —
coleta-se o histórico no campo nos **5 anos anteriores ao corte (2017–2021)**, em lotes de 50
autores por consulta, com checkpoint a cada 100 lotes.
**Sem vazamento.** Os candidatos são escolhidos **só entre coautores de T0**. Escolhê-los também
entre coautores de T1 colocaria no catálogo exatamente as pessoas que vão colaborar com as
sementes no futuro, porque colaboraram — o universo de candidatos ficaria enviesado a favor dos
positivos e inflaria qualquer avaliação. Coautores que só aparecem em T1 continuam na verdade
fundamental, mas não ajudam a montar a base.
**Por que só 5 anos.** Em áreas de equipes grandes cada semente traz ~200 candidatos (Medicina),
contra ~14 em Economia; o histórico completo tornaria a base de Medicina inviável. A mesma janela
é usada em todas as áreas, e os 5 anos anteriores ao corte concentram a atividade relevante
para prever colaborações seguintes.

### 4.6 Corte temporal
T0 = trabalhos publicados até **31/12/2021**; T1 = de 2022 em diante — o **mesmo ano civil nas
quatro bases**. O protocolo da qualificação (80% dos trabalhos mais antigos em T0) dava um ano
de corte diferente por base e mudava com o volume coletado (inclusive com a expansão); o corte
por ano civil torna a comparação entre áreas limpa e alinha-se ao pedido da banca de testar
cortes por ano (T4). A divisão é por trabalho: coautores de um mesmo artigo ficam do mesmo lado.

---

## 5. Critérios de inclusão e exclusão de artigos
Definidos numa fonte única (`configs/filters.yaml`) e aplicados na coleta e na limpeza:

| Critério | Valor | Justificativa |
|---|---|---|
| Idioma | inglês | Os modelos textuais (SciBERT) são treinados em inglês |
| Ano | ≥ 2004 | Profundidade temporal para o particionamento T0 → T1 |
| Campos obrigatórios | autor, data, título, **abstract**, idioma | A vertente textual depende do abstract |
| Teto de coautores | 50 por trabalho | Trabalhos com mais autores não geram arestas de coautoria (consórcios: autoria nominal, sem colaboração direta entre todos os pares) |

O teto foi submetido a teste de sensibilidade (10, 20, 50, ∞): a ordem dos modelos se mantém em
todos os valores (`docs/SENSIBILIDADE_TETO.md`).

---

## 6. Higienização de autores

### 6.1 Por que higienizar: erros de identidade viram erros de rótulo
A desambiguação de nomes de autores é um problema aberto em bibliotecas digitais (Ferreira;
Gonçalves; Laender, 2012) e afeta análises baseadas em autores (Strotmann; Zhao, 2012). Na
predição de coautoria, os dois tipos de erro têm efeito direto:

- **Fragmentação** (uma pessoa dividida em vários identificadores): se a pessoa usa um
  identificador em T0 e outro em T1, uma colaboração antiga aparece como **coautoria nova** —
  um falso positivo na verdade fundamental.
- **Fusão** (pessoas distintas sob um identificador): cria arestas entre quem nunca colaborou e
  mistura perfis textuais de pesquisadores diferentes.

### 6.2 Evidência empírica (amostras aleatórias, outubro de 2026)

| Área | Autorias com ORCID | com instituição (ROR) | Trabalhos com DOI | Trabalhos com **todos** os autores com ORCID |
|---|---:|---:|---:|---:|
| Medicina | 62% | 76% | 80% | 26% |
| Computação | 65% | 71% | 79% | 36% |
| Economia | 58% | 55% | 72% | 34% |
| Matemática | 64% | 76% | 80% | 38% |

Verificação contra o registro ORCID (n = 15 autorias por área, indicativo): o DOI do trabalho
consta entre os trabalhos **reivindicados** pela pessoa em 20–47% dos casos; 7–33% dos ORCIDs
não têm trabalhos públicos; e a instituição da autoria raramente casa por ROR, porque o ORCID
identifica organizações majoritariamente por RINGGOLD/GRID. Além disso, **5,5%** das autorias não
têm autor resolvido e **16%** dos ORCIDs aparecem em mais de um identificador de autor do
OpenAlex (n = 80); quando ambos existem, o autor da autoria é sempre o dono do ORCID (0% de
divergência).

**Consequências para o desenho:**
1. Exigir ORCID de **todos** os autores eliminaria 62–74% dos trabalhos e destruiria a rede →
   o ORCID entra **em camadas**: obrigatório para quem é avaliado e como nível de confiança para
   os demais vínculos.
2. O ORCID declarado na publicação e o trabalho reivindicado no registro são evidências de força
   diferente → níveis distintos (A e B).
3. O vínculo institucional usa ROR **ou** nome normalizado + país + período.
4. A fragmentação é corrigida tomando o **ORCID como chave canônica da pessoa**.

### 6.3 Cadeia de verificação
```
 PESSOA ──(ORCID)──► identificador(es) OpenAlex ──► AUTORIA ──► TRABALHO (DOI)
    │                     ▲ funde fragmentos            │             │
    │                     └ rejeita conflitos            ▼             ▼
    └──── afiliações declaradas no ORCID ──────────► INSTITUIÇÃO (ROR / nome+país+ano)
                                                        │
          AUTORIA válida ◄──────── mesmo trabalho ──────► AUTORIA válida
                       └──────────── ARESTA DE COAUTORIA ─────────┘
```

### 6.4 Métodos
- **M1 — Autorias não resolvidas** (sem identificador de autor) são excluídas.
- **M2 — Pessoa canônica:** identificadores com o mesmo ORCID são fundidos numa só pessoa;
  identificador com mais de um ORCID é tratado como identidade fundida (conflito).
- **M3 — Nível de evidência de cada autoria:** **A** — ORCID e DOI reivindicado no registro;
  **B** — ORCID declarado na publicação; **C** — sem ORCID, identidade consistente;
  **X** — rejeitada (conflito ou nome incompatível). Um ORCID cujo registro só traz nomes
  incompatíveis com o autor rebaixa a autoria para C.
- **M4 — Consistência de nome:** nomes normalizados (sem acentos, sem pontuação) são compatíveis
  se compartilham ao menos um termo significativo (≥ 2 letras, exceto partículas como *de*,
  *da*, *van*) — tolera iniciais, ordem invertida e transliterações simples.
- **M5 — Vínculo autor–instituição:** **I1** — confirmado no ORCID (ROR, ou nome + país) com o
  ano do trabalho dentro do período do vínculo (± 1 ano); **I2** — instituição identificada por
  ROR apenas no OpenAlex; **I3** — sem instituição.
- **M6 — Coautoria validada:** aresta só entre autorias não rejeitadas, no mesmo trabalho, dentro
  do teto de coautores e entre pessoas canônicas distintas; a confiança da aresta é o menor nível
  das duas pontas.
- **M7 — Elegibilidade** (6.5) e **M8 — Relatório** com funil de atrito e amostra para
  verificação manual (seção 7).

### 6.5 Critérios de elegibilidade dos autores-alvo

| Critério | Regra | Por quê |
|---|---|---|
| E1 Identidade | possui ORCID | identidade verificável externamente |
| E2 Unicidade | sem ORCIDs conflitantes | evita pessoas fundidas |
| E3 Âncora de autoria | ≥ 1 trabalho com DOI reivindicado no ORCID | prova que o ORCID pertence a quem escreveu |
| E4 Vínculo institucional | ≥ 1 autoria com instituição identificada | liga pessoa a instituição |
| E5 Atividade | ≥ 2 trabalhos no campo | perfil mínimo para recomendar |
| E6 Plausibilidade | ≤ 30 trabalhos/ano e ≤ 3 grupos de afiliação desconexos no mesmo ano | produtividade ou afiliações implausíveis indicam identidade fundida |
| E7 Nome | nenhuma autoria com nome incompatível | consistência da atribuição |
| E8 Equipe | ≥ 1 trabalho dentro do teto de coautores | sem isso o autor não gera arestas |

### 6.6 Calibração dos critérios
- **E6 por grupos de afiliação.** Contar instituições avulsas reprovava 6,5% dos autores de um
  piloto, porque um mesmo artigo pode listar universidade, hospital e instituto. Instituições
  co-listadas numa autoria passaram a formar **um grupo**; só grupos desconexos no mesmo ano
  indicam identidade fundida. Reprovações indevidas: 6,5% → 0%.
- **E3 estrito com análise de sensibilidade.** No piloto com sementes (Economia), 46% das
  sementes têm ao menos um trabalho reivindicado no ORCID — é o critério mais restritivo (42% das
  sementes se tornam alvos). Mantém-se E3 estrito, por ser a garantia de identidade mais forte, e
  repete-se a avaliação com E3 relaxado (identidade pelo nível B): se as conclusões se mantêm, o
  viés de quem mantém o registro ORCID não as explica.

---

## 7. Controle de qualidade

1. **Gate de rede** (`configs/corpus_gate.yaml`): ≥ 5.000 trabalhos; ≥ 2.000 autores; peso
   médio de coautoria ≥ 1,3 (colaborações recorrentes); ≥ 30 pares com 3 ou mais coautorias
   (grupos estabelecidos); cobertura de abstract ≥ 70%.
2. **Auditoria de identidade** (`scripts/audit_authors.py`) sobre os dados brutos: cobertura de
   ORCID, homônimos, candidatos a fusão (mesmo nome com coautor ou instituição em comum),
   divergência de nome, multiafiliação e produtividade implausível.
3. **Verificação manual**: 200 autores sorteados por base, com links para OpenAlex e ORCID;
   autores brasileiros conferidos no Lattes/BRCris. A proporção de erros encontrados estima a
   **taxa de erro residual** da higienização.

---

## 8. Engenharia e reprodutibilidade
- **Configuração versionada e centralizada:** áreas e amostragem em `configs/bases.yaml`;
  critérios de artigo e de autor em `configs/filters.yaml` — uma única fonte de verdade.
- **Determinismo:** sementes fixas nos sorteios da API e no embaralhamento; `PYTHONHASHSEED=0`.
- **Retomada e eficiência:** cache em disco das respostas do ORCID (uma consulta por pessoa,
  reaproveitável); consultas em paralelo sob limite global de 15 requisições/s (o sequencial
  rendia 3,8/s); consultas em lote ao OpenAlex (50 autores por requisição).
- **Proteção contra erros de configuração:** antes de coletar, os identificadores das áreas são
  conferidos na API, e a coleta é abortada se o nome não corresponder ao esperado.
- **Testes automatizados** (pytest) para métricas, split temporal anti-vazamento, coleta,
  higienização e elegibilidade.
- **Ambiente:** Python 3.11; pyalex 0.21; pandas 2.0; PyTorch 2.8; PyTorch Geometric 2.8. Coleta
  realizada em outubro de 2026; os dados brutos são preservados para reprocessamento.
- **Orçamento das APIs (condição de reprodutibilidade):** desde fevereiro de 2026 o OpenAlex mede
  o uso em créditos diários (1.000/dia sem chave; 10× com chave gratuita; 1 crédito por consulta
  de lista/filtro); o ORCID limita o acesso anônimo a 25 mil leituras/dia por IP (100 mil/dia com
  credencial gratuita de cliente público). Cada base consome ~1 mil créditos de coleta + ~2 mil de
  enriquecimento no OpenAlex e ~30 mil leituras no ORCID. O código usa as credenciais quando
  presentes (`OPENALEX_API_KEY`, `ORCID_TOKEN`), interrompe com mensagem explícita quando a cota
  acaba — nunca pula lotes em silêncio — e retoma do cache (`docs/ENRIQUECIMENTO.md`, diário).

---

## 9. Resultados da coleta
As tabelas por base — trabalhos, autores, sementes, densidade, distribuição dos níveis A/B/C/X,
vínculo institucional, funil de elegibilidade E1–E8, autores-alvo e gate de rede — são geradas a
partir dos relatórios de execução em **`docs/RESULTADOS_BASES.md`**.

---

## 10. Limitações e ameaças à validade
1. **Viés de adoção do ORCID** — exigir ORCID e trabalho reivindicado dos autores-alvo pode
   favorecer países, áreas e gerações com maior adoção. Mitigação: comparar elegíveis e não
   elegíveis (país, produtividade, ano do primeiro trabalho) e a análise de sensibilidade do E3.
2. **Classificação temática automática** — o campo do *primary topic* é atribuído por modelo do
   OpenAlex; trabalhos interdisciplinares ficam num único campo.
3. **Amostragem por autor** — a probabilidade de um autor virar semente cresce com sua
   produtividade no campo; a correção de um autor por trabalho remove o viés de tamanho de
   equipe, mas não o de produtividade.
4. **Dados vivos** — o OpenAlex é atualizado continuamente; reproduzir a coleta em outra data
   pode produzir amostras diferentes. Mitigação: data de coleta registrada e dados brutos
   preservados.
5. **Regra de nome tolerante** — prioriza não rejeitar transliterações; homônimos com sobrenome
   comum só são separados pelo ORCID.
6. **Erros de afiliação** — falhas de interpretação das afiliações no OpenAlex permanecem nos
   níveis I2/I3.

---

## 11. Síntese das técnicas utilizadas

| Técnica | Onde | Para quê |
|---|---|---|
| Classificação por campo de *Topics* (ASJC) | Definição da área | Partição temática limpa, sem marcações irrelevantes |
| Amostragem aleatória reprodutível (`sample` + sementes) | Sorteio de candidatos | Representatividade |
| Correção de viés de tamanho (1 autor por trabalho) | Escolha das sementes | Evitar super-representação de equipes grandes |
| Expansão de 1 passo restrita à área (histórico completo das sementes) | Coleta | Preservar a estrutura da rede |
| Parada por número de sementes (1.000) | Coleta | Mesmo nº de unidades de avaliação entre áreas |
| Histórico dos candidatos escolhidos só em T0 (janela 2017–2021) | Expansão | Alcance dos coautores futuros sem vazamento |
| Corte temporal por ano civil comum | Avaliação | Comparação entre áreas independente do volume |
| Normalização de nomes e casamento por termos | Higienização | Consistência de identidade |
| Resolução de entidades por identificador persistente (ORCID) | Higienização | Pessoa canônica: fundir fragmentos, rejeitar fusões |
| Níveis de evidência (A/B/C/X; I1/I2/I3) | Higienização | Graduar a confiança em vez de excluir em bloco |
| Componentes conexos (*union-find*) de afiliações | Critério E6 | Distinguir multiafiliação de identidade fundida |
| Funil de atrito por critério | Relatórios | Transparência sobre o que cada critério remove |
| Gate de qualidade de rede | Controle | Garantir colaborações recorrentes e textos |
| Amostra para verificação manual | Controle | Estimar a taxa de erro residual |
| Cache em disco, consultas em lote e paralelas com limite de taxa | Engenharia | Retomada, eficiência e respeito às APIs |

---

## Referências
- FELD, S. L. Why your friends have more friends than you do. *American Journal of Sociology*,
  v. 96, n. 6, p. 1464–1477, 1991.
- FERREIRA, A. A.; GONÇALVES, M. A.; LAENDER, A. H. F. A brief survey of automatic methods for
  author name disambiguation. *ACM SIGMOD Record*, v. 41, n. 2, p. 15–26, 2012.
- HAAK, L. L. et al. ORCID: a system to uniquely identify researchers. *Learned Publishing*,
  v. 25, n. 4, p. 259–264, 2012.
- LESKOVEC, J.; FALOUTSOS, C. Sampling from large graphs. In: *Proceedings of the 12th ACM
  SIGKDD*, 2006. p. 631–636.
- LIBEN-NOWELL, D.; KLEINBERG, J. The link-prediction problem for social networks. *JASIST*,
  v. 58, n. 7, p. 1019–1031, 2007.
- NEWMAN, M. E. J. The structure of scientific collaboration networks. *PNAS*, v. 98, n. 2,
  p. 404–409, 2001.
- PRIEM, J.; PIWOWAR, H.; ORR, R. OpenAlex: a fully-open index of scholarly works, authors,
  venues, institutions, and concepts. *arXiv:2205.01833*, 2022.
- STROTMANN, A.; ZHAO, D. Author name disambiguation: what difference does it make in
  author-based citation analysis? *JASIST*, v. 63, n. 9, p. 1820–1833, 2012.
- VISSER, M.; VAN ECK, N. J.; WALTMAN, L. Large-scale comparison of bibliographic data sources.
  *Quantitative Science Studies*, v. 2, n. 1, p. 20–41, 2021.
- WUCHTY, S.; JONES, B. F.; UZZI, B. The increasing dominance of teams in production of
  knowledge. *Science*, v. 316, n. 5827, p. 1036–1039, 2007.

> Conferir paginação e dados completos das referências antes da versão final.
