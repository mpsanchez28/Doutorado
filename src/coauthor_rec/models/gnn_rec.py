"""Recomendadores baseados nos embeddings da GNN heterogênea.

GNNRecommender: ranqueia TODOS os autores pelo produto interno (similaridade global).
GNNReranker: gera candidatos por vizinhança de 2 saltos (como o baseline/RF) e os
ranqueia pelo score da GNN, com fallback por popularidade — alinhando o espaço de
candidatos ao dos modelos topológicos (§4.5).
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .base import BaseRecommender


class GNNRecommender(BaseRecommender):
    def __init__(self, author_emb: np.ndarray, author_index: dict, name: str = "GNN (hetero)"):
        super().__init__(name)
        self.emb = np.asarray(author_emb, dtype=np.float32)
        self.author_index = author_index
        self.authors = np.array(list(author_index.keys()))

    def fit(self, train_df: pd.DataFrame) -> "GNNRecommender":
        return self  # embeddings já treinados

    def recommend(self, author_id, top_n: int = 10) -> list:
        idx = self.author_index.get(author_id)
        if idx is None:
            return []
        scores = self.emb @ self.emb[idx]
        scores[idx] = -np.inf
        k = min(top_n, len(scores) - 1)
        top = np.argpartition(-scores, k)[:k]
        top = top[np.argsort(-scores[top])]
        return self.authors[top].tolist()


class GNNReranker(BaseRecommender):
    """Gera candidatos por 2 saltos e os ranqueia pelo score (produto interno) da GNN."""

    def __init__(self, author_emb: np.ndarray, author_index: dict,
                 max_coauthors_per_work: int | None = None, name: str = "GNN reranker (2-hop)"):
        super().__init__(name)
        self.emb = np.asarray(author_emb, dtype=np.float32)
        self.author_index = author_index
        self.graph: dict = defaultdict(set)
        self.popular_authors: list = []
        self.max_coauthors_per_work = max_coauthors_per_work

    def fit(self, train_df: pd.DataFrame) -> "GNNReranker":
        cap = self.max_coauthors_per_work
        for _, group in train_df.groupby("work_id"):
            authors = group["author_id"].tolist()
            if len(authors) > 1 and not (cap is not None and len(authors) > cap):
                for a, b in itertools.combinations(authors, 2):
                    self.graph[a].add(b); self.graph[b].add(a)
        pop = Counter({a: len(n) for a, n in self.graph.items()})
        self.popular_authors = [a for a, _ in pop.most_common()]
        return self

    def _score(self, target_idx, cand_ids):
        idxs = [self.author_index.get(c) for c in cand_ids]
        valid = [(c, i) for c, i in zip(cand_ids, idxs) if i is not None]
        if not valid:
            return []
        cand, rows = zip(*valid)
        s = self.emb[list(rows)] @ self.emb[target_idx]
        order = np.argsort(-s)
        return [cand[i] for i in order]

    def recommend(self, author_id, top_n: int = 10) -> list:
        current = self.graph.get(author_id, set())
        idx = self.author_index.get(author_id)
        recs: list = []
        if idx is not None and author_id in self.graph:
            cands = {c for nb in current for c in self.graph.get(nb, set())
                     if c != author_id and c not in current}
            recs = self._score(idx, list(cands))
        if len(recs) < top_n:  # fallback: populares
            for pop in self.popular_authors:
                if pop != author_id and pop not in recs and pop not in current:
                    recs.append(pop)
                    if len(recs) >= top_n:
                        break
        return recs[:top_n]
