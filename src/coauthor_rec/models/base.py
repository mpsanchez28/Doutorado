"""Interface comum dos recomendadores (porta de BaseRecommender do estudo inicial)."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseRecommender(ABC):
    def __init__(self, name: str):
        self.name = name
        self.train_df: pd.DataFrame | None = None

    @abstractmethod
    def fit(self, train_df: pd.DataFrame) -> "BaseRecommender":
        """Treina o modelo com os dados de treino (T0)."""

    @abstractmethod
    def recommend(self, author_id, top_n: int = 10) -> list:
        """Retorna lista ordenada de author_ids recomendados."""
