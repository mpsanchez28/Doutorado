# Seleção das bases (recortes por área) — H3

**Decisão (09/10/2026):** 4 recortes no **nível de campo**, formando um gradiente de
densidade de coautoria para testar a **H3** ("o ganho do texto cresce com a esparsidade da
rede"). Configuração: `configs/bases.yaml`.

| Ordem | Base | Área (campo do *primary topic*, OpenAlex Topics) | Works no OpenAlex | Densidade esperada |
|---:|---|---|---:|---|
| 1 | Medicina | `fields/27` Medicine (Health Sciences) | ~52M | alta |
| 2 | Ciência da Computação | `fields/17` Computer Science (Physical Sciences) | ~18M | intermediária |
| 3 | Matemática | `fields/26` Mathematics (Physical Sciences) | ~5,7M | baixa |
| 4 | Economia | `fields/20` Economics, Econometrics and Finance (Social Sciences) | ~9M | baixa |

IDs conferidos na API; `build_base.py` aborta a coleta se o nome não bater.

## Justificativas
- **Gradiente:** a variável da H3 é a densidade da rede de coautoria; os 4 campos vão do polo
  denso (Medicina) ao esparso (Matemática e Economia).
- **Dois polos baixos:** dão robustez à extremidade esparsa (n=4) — divergências entre
  Matemática e Economia medem a variância da própria tendência.
- **Mesmo nível e mesmo protocolo para todas:** campo × campo, coleta `seeded`, parada por
  **autores distintos** (`target_authors: 60000`) — densidade é propriedade da área, não da coleta.
- **Base IA (5 sub-conceitos)** = legado fora do gradiente, mantida para reprodutibilidade.

## Por que campos de *Topics* e não *Concepts* (correção em 09/10/2026)

A primeira versão usava Concepts nível 0. O piloto real mostrou contaminação grave: o filtro
`concepts.id` da API casa **qualquer** marcação, **inclusive com score 0** — numa coleta de
"Economia", 20% dos trabalhos eram colaborações de **física de partículas** (Economics com
score 0,0; Physics 0,92) e concentravam 84% das autorias. Amostra aleatória (n=200):

| Área | Concept com score < 0,3 | Concept com score 0 | Campo principal ≠ área |
|---|---:|---:|---:|
| Medicina | 32% | 6% | 52% |
| Computação | 33% | 8% | 84% |
| Matemática | 68% | 21% | 90% |
| Economia | 72% | 34% | 86% |

Os **Topics** (domínio > campo > subcampo > tópico; campos = classificação ASJC) são a
classificação atual do OpenAlex — os Concepts estão descontinuados. Cada trabalho tem **um**
*primary topic* e, portanto, **um** campo: partição limpa, filtrável no servidor.

**Implicação para resultados anteriores:** a base IA legada foi filtrada por Concepts e pelos
mais citados — pode conter trabalhos fora da IA. Declarar como limitação; a re-coleta permite
quantificar.

## A ordem padrão da API enviesa a densidade

A consulta devolve os trabalhos **ordenados por citações (decrescente)**; como coletamos uma
fração ínfima de cada campo, a ordem **vira a amostra**. Os mais citados têm equipes 1,7–3×
maiores e **invertem o gradiente** (Economia pareceria mais densa que Computação: 8,1 × 6,6
autores/artigo). Com amostra **aleatória** e filtro por campo (n=200, seed 42, ≥2004, inglês,
com abstract), o gradiente esperado aparece:

| Área | Autores/artigo (média · mediana) | Artigos > 50 autores |
|---|---:|---:|
| Medicina | 6,0 · 4 | 1 |
| Computação | 2,9 · 2 | 0 |
| Matemática | 2,2 · 2 | 0 |
| Economia | 2,1 · 1 | 0 |

## Amostragem `seeded` (aprovada e implementada)
`collect/openalex.py › seeded_collect`; parâmetros em `configs/bases.yaml › coleta`.

1. Sortear trabalhos aleatórios do campo (`sample` + várias `seed`, reprodutível).
2. De cada trabalho, sortear **um** autor com ORCID como candidato a semente. Tomar todos os
   autores super-representaria quem publica em equipes grandes (um artigo de 8 autores
   renderia 8 candidatos); no piloto, isso inflava a densidade de 3,0 para 3,65.
3. Coletar o **histórico completo** das sementes no campo (lotes de 50 autores por consulta).
4. Parar em `target_authors` pessoas distintas, **contando só autores de trabalhos dentro do
   teto de coautores** (consórcios ficam no bruto, mas não inflam a contagem).
5. Gravar `seeds.csv`. **Alvos de avaliação = sementes ∩ elegíveis (E1–E8).** Só as sementes
   têm histórico completo; os coautores entram no catálogo e no grafo, com histórico parcial.

Responde também à crítica "uma semente gera viés": são milhares de sementes aleatórias.

## Piloto real (Economia, 100 sementes, 09/10/2026)

| Medida | Resultado |
|---|---|
| Coleta | 4.148 trabalhos · 2.822 autores · 40 s |
| Densidade | 3,0 autores/artigo (mediana 2) · 1 artigo > 50 autores |
| Histórico por semente | mediana de 7 trabalhos no campo |
| Alvos (semente ∩ elegível) | 39 de 93 = **42%** (critério que mais restringe: E3, 46%) |
| Tempo total com higienização | 105 s (ORCID em paralelo, 15 req/s) |

**Estimativa para as bases definitivas:** ~2 mil sementes e ~29 mil ORCIDs por base →
~1 h por base (coleta + ORCID), ~4 h para as quatro.

## Revisão de 09/10/2026 — número de sementes, expansão e corte

| Base | Sementes na 1ª coleta (parada por 60 mil autores) | Decisão |
|---|---:|---|
| Economia | 2.930 | reduzida às 1.000 primeiras (`scripts/subset_seeds.py`) |
| Matemática | 2.765 | reduzida às 1.000 primeiras |
| Computação | 800 | re-coletada até 1.000 |
| Medicina | 250 | re-coletada até 1.000 |

Motivos e procedimento da expansão dos candidatos e do corte por ano civil:
`docs/METODOLOGIA_DADOS.md` §3.1, §4.5 e §4.6. Números finais: `docs/RESULTADOS_BASES.md`.
