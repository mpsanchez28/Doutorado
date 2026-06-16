"""Oráculo topológico (Seção 5.1.7).

Ranqueador ideal restrito ao mesmo espaço de candidatos do baseline: reordena os
candidatos colocando os verdadeiros colaboradores futuros no topo. Define o limite
superior empírico de desempenho dado o espaço de candidatos topológico.
"""
from __future__ import annotations

import pandas as pd

from .base import BaseRecommender


class IdealTopologyRecommender(BaseRecommender):
    def __init__(self, base_topology_model: BaseRecommender, ground_truth: dict,
                 candidate_pool: int = 5000):
        super().__init__("Ideal Topology (Oracle)")
        self.base_model = base_topology_model
        self.ground_truth = ground_truth
        self.candidate_pool = candidate_pool

    def fit(self, train_df: pd.DataFrame) -> "IdealTopologyRecommender":
        return self

    def recommend(self, author_id, top_n: int = 10) -> list:
        all_candidates = self.base_model.recommend(author_id, top_n=self.candidate_pool)
        future = self.ground_truth.get(author_id, set())
        hits = [c for c in all_candidates if c in future]
        rest = [c for c in all_candidates if c not in future]
        return (hits + rest)[:top_n]
