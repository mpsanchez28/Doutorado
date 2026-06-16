"""Reranker supervisionado sobre o pool de candidatos HÍBRIDO (§4.5, Eq. 12).

Une as duas forças que os experimentos isolaram: (a) o ALCANCE dos candidatos híbridos
(2-hop ∪ vizinhos textuais), que fura o teto topológico; e (b) o RANQUEAMENTO supervisionado
forte do Random Forest, que domina o topo/meio do ranking. Para cada par (autor-alvo,
candidato) usa o vetor de features [Common Neighbors, Jaccard, Adamic-Adar, sim_textual,
score_GNN] e treina um RF (positivos = coautorias T0; negativos difíceis = pares a 2 saltos).
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
from .hybrid_cand import _l2norm

FEATURES = ["common_neighbors", "jaccard", "adamic_adar", "text_sim", "gnn_sim"]


class SupervisedHybridReranker(BaseRecommender):
    def __init__(self, author_index: dict, text_emb, gnn_emb=None, m_text: int = 50,
                 candidate_pool_size: int = 200, n_estimators: int = 200,
                 max_positive_samples: int = 100_000, max_coauthors_per_work: int | None = None,
                 random_state: int = 42, name: str = "Sup-Hybrid (RF sobre pool híbrido)"):
        super().__init__(name)
        self.author_index = author_index
        self.authors = np.array(list(author_index.keys()))
        self.text = _l2norm(text_emb)
        self.gnn = _l2norm(gnn_emb) if gnn_emb is not None else None
        self.m_text = m_text
        self.candidate_pool_size = candidate_pool_size
        self.max_positive_samples = max_positive_samples
        self.cap = max_coauthors_per_work
        self.random_state = random_state
        self.rf = RandomForestClassifier(n_estimators=n_estimators, random_state=random_state, n_jobs=-1)
        self.graph: dict = defaultdict(set)
        self.popular_authors: list = []

    def _build_graph(self, train_df):
        cap = self.cap
        for _, g in train_df.groupby("work_id"):
            a = g["author_id"].tolist()
            if len(a) > 1 and not (cap is not None and len(a) > cap):
                for x, y in itertools.combinations(a, 2):
                    self.graph[x].add(y); self.graph[y].add(x)
        pop = Counter({a: len(n) for a, n in self.graph.items()})
        self.popular_authors = [a for a, _ in pop.most_common()]

    def _feats(self, u, v):
        nu, nv = self.graph.get(u, set()), self.graph.get(v, set())
        common = nu & nv
        union = nu | nv
        cn = len(common)
        jac = cn / len(union) if union else 0.0
        aa = sum(1.0 / math.log(len(self.graph.get(z, set())))
                 for z in common if len(self.graph.get(z, set())) > 1)
        iu, iv = self.author_index.get(u), self.author_index.get(v)
        tsim = float(self.text[iu] @ self.text[iv]) if iu is not None and iv is not None else 0.0
        gsim = (float(self.gnn[iu] @ self.gnn[iv])
                if self.gnn is not None and iu is not None and iv is not None else 0.0)
        return [cn, jac, aa, tsim, gsim]

    def _gen_training(self):
        rng = random.Random(self.random_state)
        X, y = [], []
        pos = list({(u, v) for u, ns in self.graph.items() for v in ns if u < v})
        m = min(len(pos), self.max_positive_samples)
        for u, v in rng.sample(pos, m):
            X.append(self._feats(u, v)); y.append(1)
        keys = list(self.graph)
        neg = 0
        while neg < m:
            u = rng.choice(keys)
            nu = self.graph.get(u, set())
            if not nu:
                continue
            nb = rng.choice(list(nu))
            nn = self.graph.get(nb, set())
            if not nn:
                continue
            v = rng.choice(list(nn))
            if u != v and v not in nu:
                X.append(self._feats(u, v)); y.append(0); neg += 1
        return np.array(X), np.array(y)

    def fit(self, train_df: pd.DataFrame) -> "SupervisedHybridReranker":
        self._build_graph(train_df)
        X, y = self._gen_training()
        self.rf.fit(X, y)
        return self

    def _text_neighbors(self, idx, current, k):
        sims = self.text @ self.text[idx]
        sims[idx] = -np.inf
        n = min(k + len(current) + 1, len(sims) - 1)
        top = np.argpartition(-sims, n)[:n]
        top = top[np.argsort(-sims[top])]
        out = []
        for j in top:
            a = self.authors[j]
            if a != self.authors[idx] and a not in current:
                out.append(a)
                if len(out) >= k:
                    break
        return out

    def recommend(self, author_id, top_n: int = 10) -> list:
        current = self.graph.get(author_id, set())
        idx = self.author_index.get(author_id)
        # candidatos estruturais (top por frequência de 2-hop) + textuais (top-M)
        freq: Counter = Counter()
        for nb in current:
            for c in self.graph.get(nb, set()):
                if c != author_id and c not in current:
                    freq[c] += 1
        cands = {c for c, _ in freq.most_common(self.candidate_pool_size)}
        if idx is not None and self.m_text > 0:
            cands.update(self._text_neighbors(idx, current, self.m_text))

        recs: list = []
        cl = list(cands)
        if cl:
            probs = self.rf.predict_proba([self._feats(author_id, c) for c in cl])[:, 1]
            recs = [c for c, _ in sorted(zip(cl, probs), key=lambda t: t[1], reverse=True)]
        if len(recs) < top_n:  # fallback popularidade
            for pop in self.popular_authors:
                if pop != author_id and pop not in recs and pop not in current:
                    recs.append(pop)
                    if len(recs) >= top_n:
                        break
        return recs[:top_n]
