"""Baseline topológico: Common Neighbors / vizinhança de 2ª ordem (Seção 5.1.5).

Porta fiel do TopologyRecommender do estudo inicial. O grafo é armazenado de forma
assimétrica (u->v para i<j) e a vizinhança de 2ª ordem gera os candidatos, ranqueados
por frequência de vizinhos em comum, com fallback por popularidade (grau).
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict

import pandas as pd

from .base import BaseRecommender


class TopologyRecommender(BaseRecommender):
    def __init__(self, max_coauthors_per_work: int | None = None):
        super().__init__("Topology (Graph Coauthor)")
        self.graph: dict = defaultdict(set)
        self.popular_authors: list = []
        self.max_coauthors_per_work = max_coauthors_per_work

    def fit(self, train_df: pd.DataFrame) -> "TopologyRecommender":
        self.train_df = train_df
        cap = self.max_coauthors_per_work
        for _, group in train_df.groupby("work_id"):
            authors = group["author_id"].tolist()
            if len(authors) > 1 and not (cap is not None and len(authors) > cap):
                for u, v in itertools.combinations(authors, 2):
                    self.graph[u].add(v)
        popularity = Counter({a: len(n) for a, n in self.graph.items()})
        self.popular_authors = [a for a, _ in popularity.most_common()]
        return self

    def recommend(self, author_id, top_n: int = 10) -> list:
        recommendations: list = []
        current = self.graph.get(author_id, set())

        if author_id in self.graph:
            candidates = []
            for neighbor in current:
                for candidate in self.graph.get(neighbor, set()):
                    if candidate != author_id and candidate not in current:
                        candidates.append(candidate)
            recommendations = [c for c, _ in Counter(candidates).most_common(top_n)]

        if len(recommendations) < top_n:  # fallback: populares
            for pop in self.popular_authors:
                if pop != author_id and pop not in recommendations and pop not in current:
                    recommendations.append(pop)
                    if len(recommendations) >= top_n:
                        break
        return recommendations
