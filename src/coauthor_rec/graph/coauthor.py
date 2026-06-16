"""Construção da rede de coautoria (Seção 5.1.2).

Uma aresta liga dois autores que publicaram juntos pelo menos um trabalho. A relação
é não direcionada; também expomos uma versão ponderada (peso = nº de artigos em comum,
ano = colaboração mais recente) que alimentará a aresta CO_AUTHOR do KG heterogêneo.
"""
from __future__ import annotations

import itertools
from collections import defaultdict

import pandas as pd


def build_coauthor_adjacency(
    df: pd.DataFrame,
    directed: bool = False,
    work_col: str = "work_id",
    author_col: str = "author_id",
    max_coauthors_per_work: int | None = None,
) -> dict[str, set]:
    """Constrói a adjacência de coautoria como dict[author] -> set(coautores).

    ``directed=False`` adiciona ambos os sentidos (u<->v); ``directed=True`` mantém
    apenas u->v para i<j (compatível com o ``TopologyRecommender`` do estudo inicial,
    cuja vizinhança de 2ª ordem assume armazenamento assimétrico).

    ``max_coauthors_per_work``: se definido, artigos com mais autores que o teto não
    geram arestas de coautoria (evita que consórcios formem cliques gigantes). O artigo
    permanece no corpus para as demais relações; apenas a clique de coautoria é omitida.
    """
    graph: dict[str, set] = defaultdict(set)
    for _, group in df.groupby(work_col):
        authors = group[author_col].tolist()
        if len(authors) <= 1:
            continue
        if max_coauthors_per_work is not None and len(authors) > max_coauthors_per_work:
            continue
        for u, v in itertools.combinations(authors, 2):
            graph[u].add(v)
            if not directed:
                graph[v].add(u)
    return graph


def build_weighted_coauthor_edges(
    df: pd.DataFrame,
    work_col: str = "work_id",
    author_col: str = "author_id",
    date_col: str = "publication_date",
    max_coauthors_per_work: int | None = None,
) -> dict[tuple, dict]:
    """Arestas CO_AUTHOR deduplicadas e ponderadas.

    Retorna dict[(a, b)] -> {"weight": nº de artigos em comum, "year": ano mais recente},
    com ``a < b`` para evitar duplicidade. Base para a relação central do KG (Tabela 8).

    ``max_coauthors_per_work``: artigos acima do teto não contribuem arestas (ver
    ``build_coauthor_adjacency``).
    """
    edges: dict[tuple, dict] = defaultdict(lambda: {"weight": 0, "year": None})
    has_date = date_col in df.columns
    for _, group in df.groupby(work_col):
        authors = sorted(group[author_col].tolist())
        year = None
        if has_date:
            ts = pd.to_datetime(group[date_col].iloc[0], errors="coerce")
            year = None if pd.isna(ts) else int(ts.year)
        if len(authors) <= 1:
            continue
        if max_coauthors_per_work is not None and len(set(authors)) > max_coauthors_per_work:
            continue
        for a, b in itertools.combinations(set(authors), 2):
            key = (a, b) if a < b else (b, a)
            edges[key]["weight"] += 1
            if year is not None:
                cur = edges[key]["year"]
                edges[key]["year"] = year if cur is None else max(cur, year)
    return dict(edges)
