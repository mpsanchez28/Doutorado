"""Modelo híbrido: gera candidatos por topologia e re-ranqueia com Random Forest
sobre features topológicas (Seção 5.1.8). Porta fiel do estudo inicial.

Features por par (u, v): Common Neighbors, Jaccard, Adamic-Adar. Treino balanceado com
positivos = arestas observadas e negativos difíceis = pares a 2 saltos sem aresta direta.
"""
from __future__ import annotations

import itertools
import math
import random
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from .base import BaseRecommender


class HybridCoauthorRecommender(BaseRecommender):
    def __init__(self, candidate_pool_size: int = 100, n_estimators: int = 100,
                 max_positive_samples: int = 100_000, random_state: int = 42):
        super().__init__("Hybrid (Graph + RandomForest)")
        self.graph: dict = defaultdict(set)
        self.popular_authors: list = []
        self.candidate_pool_size = candidate_pool_size
        self.max_positive_samples = max_positive_samples
        self.random_state = random_state
        self.rf_model = RandomForestClassifier(
            n_estimators=n_estimators, random_state=random_state
        )

    def _build_graph(self, train_df: pd.DataFrame) -> None:
        for _, group in train_df.groupby("work_id"):
            authors = group["author_id"].tolist()
            if len(authors) > 1:
                for a, b in itertools.combinations(authors, 2):
                    self.graph[a].add(b)
                    self.graph[b].add(a)  # bidirecional
        popularity = Counter({a: len(n) for a, n in self.graph.items()})
        self.popular_authors = [a for a, _ in popularity.most_common()]

    def _extract_features(self, u, v) -> list[float]:
        nu, nv = self.graph.get(u, set()), self.graph.get(v, set())
        common = nu & nv
        union = nu | nv
        cn = len(common)
        jaccard = cn / len(union) if union else 0.0
        aa = 0.0
        for z in common:
            dz = len(self.graph.get(z, set()))
            if dz > 1:
                aa += 1.0 / math.log(dz)
        return [cn, jaccard, aa]

    def _generate_training_data(self) -> tuple[np.ndarray, np.ndarray]:
        rng = random.Random(self.random_state)
        X, y = [], []

        positive_edges = {
            (u, v) for u, neighbors in self.graph.items() for v in neighbors if u < v
        }
        positive_edges = list(positive_edges)
        max_samples = min(len(positive_edges), self.max_positive_samples)
        sampled_positives = rng.sample(positive_edges, max_samples)
        for u, v in sampled_positives:
            X.append(self._extract_features(u, v))
            y.append(1)

        # Negativos difíceis: pares a 2 saltos sem aresta direta.
        author_keys = list(self.graph.keys())
        negatives = 0
        while negatives < max_samples:
            u = rng.choice(author_keys)
            nu = self.graph.get(u, set())
            if not nu:
                continue
            neighbor = rng.choice(list(nu))
            nn = self.graph.get(neighbor, set())
            if not nn:
                continue
            v = rng.choice(list(nn))
            if u != v and v not in nu:
                X.append(self._extract_features(u, v))
                y.append(0)
                negatives += 1
        return np.array(X), np.array(y)

    def fit(self, train_df: pd.DataFrame) -> "HybridCoauthorRecommender":
        self.train_df = train_df
        self._build_graph(train_df)
        X, y = self._generate_training_data()
        self.rf_model.fit(X, y)
        return self

    def recommend(self, author_id, top_n: int = 10) -> list:
        current = self.graph.get(author_id, set())
        scores: Counter = Counter()
        for neighbor in current:
            for candidate in self.graph.get(neighbor, set()):
                if candidate != author_id and candidate not in current:
                    scores[candidate] += 1

        top_candidates = [c for c, _ in scores.most_common(self.candidate_pool_size)]
        if top_candidates:
            X = [self._extract_features(author_id, c) for c in top_candidates]
            probs = self.rf_model.predict_proba(X)[:, 1]
            ranked = sorted(zip(top_candidates, probs), key=lambda x: x[1], reverse=True)
            recommendations = [c for c, _ in ranked]
        else:
            recommendations = []

        if len(recommendations) < top_n:  # fallback: populares
            for pop in self.popular_authors:
                if pop != author_id and pop not in recommendations and pop not in current:
                    recommendations.append(pop)
                    if len(recommendations) >= top_n:
                        break
        return recommendations[:top_n]
