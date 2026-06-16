"""Injeta embeddings textuais como features dos nós Paper/Author do KG (§4.4.2-4.4.3).

Concatena às features bibliométricas placeholder os embeddings textuais (ex.: SciBERT)
cacheados pelo módulo textual, alinhados aos índices de nó do HeteroData. Instituições,
venues e conceitos permanecem sem features (o modelo usa Embedding aprendível para eles).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def attach_text_features(data, maps: dict, train_df: pd.DataFrame, cache_path: str | Path):
    """Anexa embeddings textuais a data['paper'].x e data['author'].x.

    ``cache_path``: .npz gerado pelo text-compare (emb + work_ids).
    Author = bibliométrico(3) ⊕ média dos embeddings dos seus artigos (T0).
    Paper  = bibliométrico(2) ⊕ embedding textual do artigo.
    Retorna (data, info_dims).
    """
    import torch

    blob = np.load(cache_path, allow_pickle=True)
    emb, cache_wids = blob["emb"], list(blob["work_ids"])
    cache_pos = {w: i for i, w in enumerate(cache_wids)}
    d = emb.shape[1]

    paper_map, author_map = maps["paper"], maps["author"]
    paper_text = np.zeros((len(paper_map), d), dtype=np.float32)
    for wid, idx in paper_map.items():
        pos = cache_pos.get(wid)
        if pos is not None:
            paper_text[idx] = emb[pos]

    author_text = np.zeros((len(author_map), d), dtype=np.float32)
    cnt = np.zeros(len(author_map), dtype=np.float32)
    for aid, wid in zip(train_df["author_id"], train_df["work_id"]):
        ai, wp = author_map.get(aid), paper_map.get(wid)
        if ai is not None and wp is not None:
            author_text[ai] += paper_text[wp]
            cnt[ai] += 1
    author_text /= np.clip(cnt, 1.0, None)[:, None]

    def _standardize(t):  # z-score por coluna (estabiliza escalas bibliométrico⊕texto)
        mu, sd = t.mean(0, keepdim=True), t.std(0, keepdim=True)
        return (t - mu) / sd.clamp(min=1e-6)

    data["paper"].x = _standardize(torch.cat([data["paper"].x, torch.from_numpy(paper_text)], dim=1))
    data["author"].x = _standardize(torch.cat([data["author"].x, torch.from_numpy(author_text)], dim=1))
    return data, {"text_dim": d,
                  "author_dim": data["author"].x.size(1),
                  "paper_dim": data["paper"].x.size(1)}
