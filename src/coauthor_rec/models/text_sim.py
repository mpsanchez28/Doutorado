"""Recomendador text-only por similaridade de embeddings (§4.5, Eq. 11).

Dado o embedding final de cada autor, recomenda candidatos pela similaridade do cosseno.
Serve para (a) avaliar isoladamente a contribuição textual e (b) comparar encoders.
Diferente dos modelos topológicos, consegue pontuar autores sem coautoria observada
(regime cold) — desde que tenham ao menos um artigo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender


class TextSimilarityRecommender(BaseRecommender):
    def __init__(self, author_emb: np.ndarray, author_index: dict, name: str = "Text (cosine)"):
        super().__init__(name)
        # normaliza para que produto interno = similaridade do cosseno
        norms = np.linalg.norm(author_emb, axis=1, keepdims=True)
        self.emb = (author_emb / np.clip(norms, 1e-9, None)).astype(np.float32)
        self.author_index = author_index
        self.authors = np.array(list(author_index.keys()))

    def fit(self, train_df: pd.DataFrame) -> "TextSimilarityRecommender":
        return self  # embeddings já calculados

    def recommend(self, author_id, top_n: int = 10) -> list:
        idx = self.author_index.get(author_id)
        if idx is None:
            return []
        sims = self.emb @ self.emb[idx]   # [n_autores]
        sims[idx] = -np.inf               # exclui o próprio autor
        k = min(top_n, len(sims) - 1)
        top = np.argpartition(-sims, k)[:k]
        top = top[np.argsort(-sims[top])]
        return self.authors[top].tolist()
