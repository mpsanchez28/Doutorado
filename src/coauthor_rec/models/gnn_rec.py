"""Recomendador baseado nos embeddings da GNN heterogênea.

Ranqueia candidatos pelo produto interno dos embeddings de autor — a mesma função de
score otimizada no treino (§4.5). Diferente do text-sim (cosseno), usa produto interno cru.
"""
from __future__ import annotations

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
