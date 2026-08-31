"""Reranker de duas etapas: precisão do RF no topo + alcance do texto na cauda.

Estágio 1 (precisão): candidatos de 2 saltos ranqueados pelo Random Forest topológico
(Common Neighbors, Jaccard, Adamic-Adar) — preserva a forte ordenação do topo do RF.
Estágio 2 (alcance): anexa, DEPOIS, os vizinhos mais próximos por similaridade textual
(SciBERT) ainda não cobertos — recupera coautores fora da vizinhança de 2 saltos.

Corrige a falha do Sup-Hybrid (texto poluindo o topo): aqui o texto entra só na cauda,
sem competir com os candidatos estruturais nas primeiras posições.

Ajustes pós-diagnóstico (runs/text_reach.json):
- ``fill_to_k``: a cauda textual se estende até preencher ``top_n`` recomendações
  (m efetivo = max(m_text, top_n - |estágio 1|)). Motivação: com m_text=100 fixo e
  K=200, o teto do pool em cold era exatamente 4,70% — o modelo entregava 100% do
  teto e ainda assim perdia para o texto-only (6,16%), que equivale a m=K. Com
  fill_to_k, o teto do 2 etapas domina o do texto-only por construção em todo K.
- ``popularity_fallback``: liga/desliga o preenchimento final por popularidade.
  Com a cauda adaptativa ele só atua para autores sem embedding; desligá-lo permite
  medir sua contribuição isolada (e ele ocupava posições após a cauda em cold).
Defaults (m_text=100, fill_to_k=False, popularity_fallback=True) reproduzem
exatamente o comportamento e os números anteriores.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from .base import BaseRecommender
from .hybrid_rf import HybridCoauthorRecommender
from .hybrid_cand import _l2norm


class TwoStageReranker(BaseRecommender):
    def __init__(self, text_emb, author_index: dict, max_coauthors_per_work: int | None = None,
                 m_text: int = 100, candidate_pool_size: int = 200, n_estimators: int = 200,
                 random_state: int = 42, fill_to_k: bool = False,
                 popularity_fallback: bool = True, name: str = "2-stage (RF→texto)"):
        super().__init__(name)
        self.rf = HybridCoauthorRecommender(candidate_pool_size=candidate_pool_size,
                                            n_estimators=n_estimators, random_state=random_state,
                                            max_coauthors_per_work=max_coauthors_per_work)
        self.text = _l2norm(text_emb)
        self.author_index = author_index
        self.authors = np.array(list(author_index.keys()))
        self.m_text = m_text
        self.fill_to_k = fill_to_k
        self.popularity_fallback = popularity_fallback

    def fit(self, train_df: pd.DataFrame) -> "TwoStageReranker":
        self.rf.fit(train_df)  # constrói o grafo e treina a RF topológica
        return self

    def recommend(self, author_id, top_n: int = 10) -> list:
        g = self.rf.graph
        current = g.get(author_id, set())
        # ---- Estágio 1: 2-hop ranqueado pela RF ----
        freq: Counter = Counter()
        for nb in current:
            for c in g.get(nb, set()):
                if c != author_id and c not in current:
                    freq[c] += 1
        pool = [c for c, _ in freq.most_common(self.rf.candidate_pool_size)]
        struct: list = []
        if pool:
            probs = self.rf.rf_model.predict_proba([self.rf._extract_features(author_id, c) for c in pool])[:, 1]
            struct = [c for c, _ in sorted(zip(pool, probs), key=lambda t: t[1], reverse=True)]

        # ---- Estágio 2: cauda textual (top-M vizinhos, fora do estágio 1) ----
        idx = self.author_index.get(author_id)
        m_eff = self.m_text
        if self.fill_to_k:  # cauda adaptativa: preenche até top_n
            m_eff = max(self.m_text, top_n - len(struct))
        tail: list = []
        if idx is not None and m_eff > 0:
            sims = self.text @ self.text[idx]
            sims[idx] = -np.inf
            k = min(m_eff + len(current) + len(struct) + 1, len(sims) - 1)
            top = np.argpartition(-sims, k)[:k]
            top = top[np.argsort(-sims[top])]
            seen = set(struct)
            for j in top:
                au = self.authors[j]
                if au != author_id and au not in current and au not in seen:
                    tail.append(au)
                    if len(tail) >= m_eff:
                        break

        recs = struct + tail
        if self.popularity_fallback and len(recs) < top_n:  # fallback popularidade
            for pop in self.rf.popular_authors:
                if pop != author_id and pop not in recs and pop not in current:
                    recs.append(pop)
                    if len(recs) >= top_n:
                        break
        return recs[:top_n]
