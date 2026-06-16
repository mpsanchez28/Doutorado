"""Particionamento temporal e definição da verdade fundamental (Seção 5.1.3-5.1.4).

A tarefa é formulada como predição de links futuros: o grafo de treino usa apenas
publicações até o corte T0; novas coautorias observadas em T1 formam o ground truth.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from ..graph.coauthor import build_coauthor_adjacency


def chronological_split(
    merged_df: pd.DataFrame,
    train_fraction: float = 0.80,
    work_col: str = "work_id",
    date_col: str = "publication_date",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide as autorias em treino/teste por corte cronológico no nível de works.

    Os ``train_fraction`` works mais antigos vão para treino; o restante para teste.
    A divisão é feita por work (não por linha de autoria) para que todos os coautores
    de um mesmo artigo fiquem do mesmo lado do corte — prevenindo vazamento temporal.
    """
    unique_works = (
        merged_df[[work_col, date_col]]
        .drop_duplicates()
        .sort_values(date_col)
        .reset_index(drop=True)
    )
    total = len(unique_works)
    split_at = int(total * train_fraction)

    train_ids = set(unique_works.iloc[:split_at][work_col])
    test_ids = set(unique_works.iloc[split_at:][work_col])

    train_df = merged_df[merged_df[work_col].isin(train_ids)]
    test_df = merged_df[merged_df[work_col].isin(test_ids)]
    return train_df, test_df


def build_ground_truth(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    max_coauthors_per_work: int | None = None,
) -> tuple[dict, dict]:
    """Constrói (train_graph, ground_truth).

    ``train_graph``: adjacência de coautoria observada em T0 (C_past).
    ``ground_truth[a]``: C_new(a) = C_future(a) \\ C_past(a) — apenas autores com
    pelo menos uma nova coautoria são incluídos (Eq. 14).

    ``max_coauthors_per_work`` aplica o mesmo teto de coautores em T0 e T1, para que
    consórcios não contem como colaborações pareadas (no grafo nem no ground truth).
    """
    train_graph = build_coauthor_adjacency(
        train_df, directed=False, max_coauthors_per_work=max_coauthors_per_work)
    test_graph = build_coauthor_adjacency(
        test_df, directed=False, max_coauthors_per_work=max_coauthors_per_work)

    ground_truth: dict = defaultdict(set)
    for author, future_coauthors in test_graph.items():
        past = train_graph.get(author, set())
        new_links = future_coauthors - past
        if new_links:
            ground_truth[author] = new_links
    return train_graph, dict(ground_truth)
