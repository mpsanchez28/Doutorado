# Linha de base e oráculos por meta-caminho do KG

Este documento registra o **primeiro passo da fase de modelagem pós-banca**: materializar o
grafo de conhecimento (KG) de cada base, fixar o protocolo de avaliação e medir, para cada
relação do KG, (i) quanto ela acerta sozinha (**baseline**) e (ii) até onde ela poderia chegar
com uma ordenação perfeita (**oráculo**). Os números estão em
[RESULTADOS_LINHA_BASE.md](RESULTADOS_LINHA_BASE.md), gerado automaticamente.

Código: `graph/kg.py` (KG T0), `eval/protocol.py` (protocolo e M9),
`models/kg_generators.py` (geradores), `scripts/baseline_oracle.py` (execução por base),
`scripts/report_linha_base.py` (relatório). Testes: `tests/test_kg_baseline.py`.

## 1. Por que começar por aqui

Na qualificação, o oráculo topológico mostrou que um ranqueador **perfeito** restrito à
vizinhança de 2 saltos chegava a só 16,5% de Recall@200 (warm). Ou seja, grande parte do erro
não estava em *ordenar mal*: as colaborações futuras nem entravam na lista de candidatos.
Antes de propor técnicas para aumentar a acurácia, é preciso saber **onde** o erro está. A
família de oráculos decompõe o erro em parcelas, e cada técnica candidata ataca uma delas:

```
coautoria nova em T1
 ├─ coautor sem nenhum trabalho no corpus até 2021  → inalcançável por qualquer modelo histórico
 ├─ em T0, mas nenhum meta-caminho o liga ao alvo    → falta RELAÇÃO (enriquecer o KG)
 ├─ ligado, mas fora dos 1.000 primeiros candidatos  → falta GERAÇÃO de candidatos
 ├─ entre os 1.000, mas fora do top-K                → falta ORDENAÇÃO (re-ranqueador)
 └─ no top-K                                         → acerto
```

Isso também responde, com números, à pergunta da banca sobre o papel do KG: cada relação da
ontologia é testada como **gerador de candidatos**, que é onde ela tem mais chance de pesar
(nas tentativas anteriores, o KG só tinha sido testado como estrutura para a GNN, com efeito
nulo).

## 2. Protocolo de avaliação (`eval/protocol.py`)

| Elemento | Definição | Por quê |
|---|---|---|
| Corte | T0 = publicações até 31/12/2021; T1 = 2022 em diante (`bases.yaml: split`) | Mesmo ano civil em todas as áreas (comparação limpa da H3) |
| Teto de coautores | Artigos com > 50 autores não geram pares de coautoria (nem no grafo nem no gabarito) | Consórcios formariam cliques espúrias (`filters.yaml`) |
| Gabarito | C_new(a) = coautores de *a* em T1 que não eram coautores em T0 | Predição de colaborações **novas** |
| Alvos | Sementes elegíveis (E1–E8, coluna `alvo`) com ≥1 coautoria nova | Unidade de avaliação com identidade verificada |
| M9 | Remove do gabarito o par (*a*, *b*) se *b* tem o mesmo nome normalizado de um coautor de T0 de *a* | Identidade fragmentada no OpenAlex: colaboração antiga que parece nova ([HIGIENIZACAO.md](HIGIENIZACAO.md)) |
| Regimes | warm ≥ 5 coautores em T0; cool 1–4; cold 0 com ≥1 trabalho; newcomer sem trabalho em T0 | Leitura por quantidade de histórico (`eval.yaml`) |
| Candidatos | Pessoas com ≥1 trabalho em T0, exceto o próprio alvo e seus coautores de T0 | Só se recomenda quem existe no passado e ainda não colaborou |

O resultado oficial é **com M9**; a versão sem a regra é calculada sobre os mesmos rankings
(análise de sensibilidade).

## 3. KG T0 materializado (`graph/kg.py`)

Até aqui o KG existia como esquema (TBox, [ONTOLOGIA.md](ONTOLOGIA.md)) e como uma amostra RDF
por base. Os modelos liam tabelas soltas do enriquecimento. Agora o grafo **inteiro** de cada
base é materializado em `data/processed/kg_<base>/`: uma tabela parquet por propriedade da
ontologia (`wrote`, `atInstitution`, `partOf`, `relatedInstitution`, `locatedIn`, `hasTopic`,
`broader`, `publishedIn`, `cites`, `hasEmployment`), cada fato com o ano em que passou a valer.

**Corte temporal no próprio KG.** Só entram fatos conhecidos até o fim de T0: autorias,
afiliações, tópicos, periódicos e citações de trabalhos até 2021; vínculos ORCID iniciados até
2021, com término posterior tratado como "em aberto" (no corte, o vínculo estava vigente). O
KG é uma fotografia do mundo em 31/12/2021; nenhum gerador ou modelo enxerga o futuro.

**Validação** (`validate_kg`, gravada em `manifest.json`): nenhum fato posterior ao corte;
domínio das relações respeitado (todo fato de trabalho aponta para um trabalho de T0, todo
vínculo institucional para um autor de T0); tópicos dentro da taxonomia (`broader`); nenhuma
instituição parte de si mesma. Também registra contagens de entidades e a **cobertura** de
cada relação (fração de trabalhos com tópico, periódico, referências; de autores com
instituição e com vínculo ORCID).

**Formato.** As tabelas são a forma de trabalho dos modelos (álgebra esparsa); a exportação
RDF continua disponível como visão validável do mesmo grafo. Montar um *triple store* completo
de Medicina (≈1 milhão de pessoas) no rdflib seria lento e não traria ganho aos modelos; a
ontologia segue como a regra que define e valida o grafo.

## 4. Geradores por meta-caminho (`models/kg_generators.py`)

Cada gerador é um **meta-caminho** da ontologia que liga o alvo a outras pessoas, com um
escore. A = autor, W = trabalho, I = instituição, T = tópico, V = periódico, O = organização.

| Gerador | Meta-caminho | Escore | Fundamento |
|---|---|---|---|
| Coautoria: vizinhos comuns | A–W–A–W–A | nº de coautores em comum | fechamento triádico (Newman, 2001) |
| Coautoria: Adamic-Adar | idem | Σ 1/log(grau do intermediário) | intermediários menos conectados valem mais (Adamic; Adar, 2003) |
| Coautoria: Resource Allocation | idem | Σ 1/grau | variante mais punitiva (Zhou; Lü; Zhang, 2009) |
| PageRank personalizado | passeio A–W–A com reinício (α = 0,15, 20 iterações) | probabilidade estacionária | alcança além de 2 saltos (Haveliwala, 2002) |
| Mesma instituição | A–atInstitution–I–A | Σ 1/log(tamanho de I) | proximidade física; lift 20–25× no diagnóstico |
| Mesma organização-mãe | A–I–partOf*–I_raiz–I–A | idem na raiz | une hospitais/institutos à universidade |
| Tópicos | A–W–hasTopic–T–W–A | cosseno dos perfis de tópico | homofilia temática |
| Mesmo periódico | A–W–publishedIn–V–W–A | Σ 1/log(tamanho de V) | mesma comunidade de publicação |
| Citação direta | A–W–cites–W–A (os dois sentidos) | nº de citações | quem cita alguém conhece seu trabalho |
| Acoplamento bibliográfico | A–W–cites–R–cites–W–A | referências em comum, ponderadas por 1/log(popularidade de R), normalizadas | base de conhecimento compartilhada (Kessler, 1963) |
| Ex-colegas (ORCID) | A–hasEmployment–O–A com períodos sobrepostos | nº de organizações em comum | vínculo declarado pela própria pessoa |
| Texto: TF-IDF | A–W ~ W–A | cosseno médio entre resumos | referência textual barata (SPECTER/SciBERT entram depois) |
| Popularidade | — | grau em T0 | referência ingênua (igual para todos os alvos) |
| **União (RRF)** | todos os acima, exceto popularidade | Σ 1/(60 + posição) | fusão sem parâmetros aprendidos (Cormack et al., 2009) |

Decisões de implementação:

- Coautoria e PageRank usam só trabalhos dentro do teto de coautores (o mesmo grafo do
  gabarito). As relações semânticas usam **todos** os trabalhos de T0: um consórcio não gera
  coautoria par a par, mas ainda informa tema, periódico e instituição.
- O PageRank caminha no grafo bipartido autor–trabalho, sem materializar a matriz
  autor × autor (que em Medicina teria centenas de milhões de entradas).
- Todos os escores são calculados por lotes de 32 alvos com álgebra esparsa; Economia roda em
  ≈15 s.
- Empates são desfeitos pelo grau em T0 (determinístico).

## 5. Baseline e oráculo

Para cada gerador e alvo, guarda-se o ranking dos 1.000 primeiros candidatos e o conjunto
completo de candidatos com escore > 0.

- **Baseline**: métricas do ranking na ordem do próprio escore — Recall@K, Hits@K, NDCG@10 e
  MRR (K ∈ {5, 10, 20, 50, 100, 200}).
- **Oráculo**: o que um ranqueador perfeito obteria reordenando os candidatos do gerador.
  - *Alcance@P* = fração dos coautores novos entre os P primeiros candidatos (P ∈ {200, 1.000}).
    É o teto de um re-ranqueador que receba esse top-P — o cenário realista de um sistema em
    duas etapas.
  - *Alcance total* = fração dentro de todo o conjunto com escore > 0. Para geradores densos
    (tópico, texto, popularidade), o conjunto é quase todo o corpus e o alcance total é
    trivial; o número relevante é o Alcance@1000.

Generaliza o oráculo da qualificação (`models/oracle.py`), que era um único caso: vizinhos
comuns com P = 5.000.

## 6. Como reproduzir

```bash
PYTHONHASHSEED=0 python scripts/baseline_oracle.py economia
python scripts/report_linha_base.py
```

Saídas: `data/processed/kg_<base>/` (KG + `manifest.json`), `runs/linha_base/<base>.json`
(agregados por gerador, regime e variante M9) e `runs/linha_base/<base>.parquet` (métricas por
alvo, para os testes de significância pareados).

## 7. Resultados e leitura (10/10/2026)

Tabelas completas em [RESULTADOS_LINHA_BASE.md](RESULTADOS_LINHA_BASE.md). Os principais achados:

**1. A maior perda está antes de qualquer modelo.** De 58% (Medicina) a 73% (Economia) dos
coautores novos de T1 **não têm nenhum trabalho no corpus até 2021**. Nenhum recomendador
baseado em histórico pode acertá-los, e o teto absoluto de recall fica entre 27% e 42%. Isso
mistura dois fenômenos:
- estreantes reais (doutorandos que começam a publicar);
- pessoas com histórico fora da coleta. A coleta é egocêntrica: histórico das sementes e dos
  seus coautores de T0.

Separar os dois exige um diagnóstico à parte: consultar no OpenAlex se esses coautores tinham
publicações até 2021. Isso só mede o fenômeno, sem usar a informação no modelo, para não vazar
o futuro.

**2. Entre os alcançáveis, quase todo coautor novo está ligado ao alvo por algum
meta-caminho** (só 0,5% a 1,3% dos pares ficam fora de todos). O gargalo seguinte muda com a
área (decomposição, §5 dos resultados):

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Ligado, mas fora do top-1000 (falta **geração/priorização**) | **29,0** | 16,0 | 10,2 | 10,1 |
| No top-1000, fora do top-50 (falta **ordenação**) | 9,5 | 6,8 | **12,5** | 10,0 |
| Acerto no top-50 | 3,4 | 3,9 | 9,0 | 5,4 |

Na área densa, os candidatos certos se perdem numa vizinhança enorme (mediana de 1.144
candidatos a 2 saltos em Medicina contra 62 em Matemática). Nas áreas esparsas, eles já estão
na lista e falta ordená-los. É um resultado direto para a H3: **a técnica que mais ajuda
depende da densidade da área**.

**3. As relações do KG são complementares à coautoria, mesmo sem aprendizado.** A União RRF
supera o melhor gerador de coautoria (Adamic-Adar) em R@50 em todas as bases:

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Adamic-Adar | 2,68 | 4,57 | 7,29 | 4,41 |
| União RRF | 3,32 | 5,84 | 11,36 | 6,08 |
| Ganho relativo | +24% | +28% | +56% | +38% |

**4. Lift não é poder de ordenação.** "Mesma instituição" tinha lift de 20–25× no diagnóstico
de sinal, mas sozinha ordena mal (R@50 de 0,8% a 3,2%). Instituições grandes empatam milhares
de candidatos. Ela informa mais como atributo combinado do que como ranking. O acoplamento
bibliográfico é o meta-caminho do KG mais forte em Matemática (Alcance@1000 18,6%), coerente
com uma área em que a colaboração segue a base de conhecimento compartilhada.

**5. Ir além de 2 saltos ajuda em toda parte.** O PageRank personalizado é o melhor gerador
isolado em R@50 nas 4 bases e amplia o Alcance@1000 em relação aos 2 saltos (Matemática: 11,9
→ 19,1).

**6. O gradiente não é monótono na densidade.** Matemática tem o melhor recall; Medicina, o
pior. Medicina, porém, tem o maior Hits@10 (36% dos alvos com ao menos um acerto no top-10) e
NDCG@10. Cada alvo de Medicina tem em média 66 coautores novos, o que derruba o recall sem
indicar ranking ruim. Para a H3, as métricas precisam ser lidas juntas.

**7. A M9 muda pouco os resultados** (≤ 0,16 ponto de R@50). A avaliação é robusta à
fragmentação de identidades.

**8. Regimes.** Com histórico fino (cool, cold), as relações de conteúdo (acoplamento, tópicos,
texto) alcançam e acertam o que a coautoria não alcança (Matemática cold: acoplamento R@50 18,2
contra 0 da coautoria). Repete-se, nas bases novas, o padrão da qualificação. Os números de
cold são pequenos (2 a 11 alvos por base).
