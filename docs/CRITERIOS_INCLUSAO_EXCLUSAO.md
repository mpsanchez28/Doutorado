# Critérios de inclusão e exclusão de artigos

Todos os filtros do trabalho são centralizados em **`configs/filters.yaml`** (fonte única de
verdade); o código os lê de lá (`config.load_filters` / `load_config`). Esta seção documenta,
em padrão científico, cada critério, onde é aplicado e sua justificativa.

## Critérios de inclusão
| Critério | Valor | Onde é aplicado | Mecanismo |
|---|---|---|---|
| Área temática | Concepts de IA (AI, ML, NLP, CV, Deep Learning) | Coleta (API OpenAlex) | `Works().filter(concepts={"id": "C…|C…"})` (OR) |
| Idioma | inglês | Coleta + limpeza | `filter(language=...)` e `df[language=="en"]` |
| Ano de publicação | ≥ 2004 | Coleta + limpeza | `from_publication_date` e `dt.year >= 2004` |
| Tamanho-alvo | 20.000 works | Coleta | paginação até o alvo |

## Critérios de exclusão
| Critério | Regra | Onde é aplicado | Mecanismo |
|---|---|---|---|
| Campos obrigatórios | exclui se faltar `author_id`, `publication_date`, `title`, **`abstract`**, `language` | Limpeza | `dropna(subset=require_fields)` |
| Duplicatas | um registro por `work_id` / `(work_id, author_id)` | Coleta | `drop_duplicates` |

## Critérios de construção (não excluem o artigo, restringem relações)
| Critério | Valor | Efeito |
|---|---|---|
| Teto de coautores/artigo | 50 | artigos com >50 autores **não geram clique de coautoria** (permanecem para WRITES/HAS_TOPIC/PUBLISHED_IN) |
| HAS_TOPIC (artigo→conceito) | score ≥ 0,3; ≤ 5 conceitos | só conceitos relevantes entram no KG |

## Critérios de avaliação (sobre autores-alvo, não artigos)
- Apenas autores com **nova coautoria** em T1 (`C_new ≠ ∅`) são avaliados.
- Nas tabelas finais, restringe-se a **autores ativos em T0** (warm/cool/cold), reportando os
  *newcomers* (sem perfil em T0) à parte.

## Efeito quantitativo
Base de IA: **20.000 coletados → 13.924 após limpeza** (~6 mil excluídos, sobretudo por falta de
abstract, idioma ou ano), **45.732 autores**.

## Implicações (a declarar na tese)
1. **Abstract obrigatório** é o filtro mais consequente: como a vertente textual depende do
   abstract, artigos sem ele são excluídos — favorece levemente os modelos textuais e enviesa o
   corpus para publicações com abstract indexado.
2. **Idioma (inglês) e recorte de IA** limitam a generalização (domínio/idioma) — escopo do estudo.
3. **Ano ≥ 2004** garante profundidade temporal para o particionamento T0→T1.

> Para alterar qualquer critério, edite **apenas** `configs/filters.yaml` — todo o pipeline passa
> a usá-lo automaticamente.
