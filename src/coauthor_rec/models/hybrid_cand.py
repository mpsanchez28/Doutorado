"""Recomendador com geração de candidatos HÍBRIDA (estrutural + textual).

Candidatos = vizinhança de 2 saltos (coautores de coautores) ∪ top-M autores por
similaridade textual (cosseno sobre embeddings de autor). O ranqueamento usa um embedding
escolhido (texto, GNN ou fusão). Objetivo: dar ao ranqueador acesso a coautores futuros que
a topologia de 2 saltos não alcança (gargalo identificado nas ablações), preservando a força
do texto em regimes de baixa conectividade.
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .base import BaseRecommender


def _l2norm(emb):
    emb = np.asarray(emb, dtype=np.float32)
    return emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)


class HybridReranker(BaseRecommender):
    def __init__(self, rank_emb, author_index: dict, text_emb=None, m_text: int = 50,
                 max_coauthors_per_work: int | None = None, name: str = "Hybrid candidates"):
        super().__init__(name)
        self.rank = _l2norm(rank_emb)                       # ranqueamento
        self.text = _l2norm(text_emb) if text_emb is not None else self.rank  # geração textual
        self.author_index = author_index
        self.authors = np.array(list(author_index.keys()))
        self.m_text = m_text
        self.graph: dict = defaultdict(set)
        self.popular_authors: list = []
        self.max_coauthors_per_work = max_coauthors_per_work

    def fit(self, train_df: pd.DataFrame) -> "HybridReranker":
        cap = self.max_coauthors_per_work
        for _, group in train_df.groupby("work_id"):
            authors = group["author_id"].tolist()
            if len(authors) > 1 and not (cap is not None and len(authors) > cap):
                for a, b in itertools.combinations(authors, 2):
                    self.graph[a].add(b); self.graph[b].add(a)
        pop = Counter({a: len(n) for a, n in self.graph.items()})
        self.popular_authors = [a for a, _ in pop.most_common()]
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
        idx = self.author_index.get(author_id)
        current = self.graph.get(author_id, set())
        cands: set = set()
        if author_id in self.graph:  # candidatos estruturais (2 saltos)
            cands |= {c for nb in current for c in self.graph.get(nb, set())
                      if c != author_id and c not in current}
        if idx is not None and self.m_text > 0:  # candidatos textuais (top-M)
            cands.update(self._text_neighbors(idx, current, self.m_text))

        recs: list = []
        if idx is not None and cands:
            cl = [c for c in cands if self.author_index.get(c) is not None]
            rows = [self.author_index[c] for c in cl]
            s = self.rank[rows] @ self.rank[idx]
            recs = [cl[i] for i in np.argsort(-s)]
        if len(recs) < top_n:  # fallback popularidade
            for pop in self.popular_authors:
                if pop != author_id and pop not in recs and pop not in current:
                    recs.append(pop)
                    if len(recs) >= top_n:
                        break
        return recs[:top_n]
