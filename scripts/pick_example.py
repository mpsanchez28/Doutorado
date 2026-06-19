"""Encontra um exemplo concreto e legível: um autor cool/cold cujo coautor futuro é
recuperado pelo TEXTO mas NÃO pela topologia (baseline/RF). Imprime nomes e posições.
Uso: PYTHONHASHSEED=0 python scripts/pick_example.py
"""
import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender

EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
name = dict(zip(merged["author_id"], merged["author_name"]))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
reg = classify_authors(tg, list(gt), EVAL["regimes"]["warm_min_coauthors"],
                       EVAL["regimes"]["cool_min_coauthors"], t0_authors=t0)
text_auth, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))

base = TopologyRecommender(max_coauthors_per_work=CAP).fit(tr)
rf = HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(tr)
text = TextSimilarityRecommender(text_auth, aidx)


def rank_of(recs, targets):
    for i, r in enumerate(recs, 1):
        if r in targets:
            return i, r
    return None, None


found = 0
for a in gt:
    if reg[a] not in ("cool", "cold") or a not in t0:
        continue
    new = gt[a]
    tr_rank, tr_hit = rank_of(text.recommend(a, 20), new)
    if tr_rank is None:
        continue
    rf_rank, _ = rank_of(rf.recommend(a, 50), new)
    bl_rank, _ = rank_of(base.recommend(a, 50), new)
    if rf_rank is None and bl_rank is None:  # texto acerta, topologia não
        print(f"\nEXEMPLO ({reg[a]}): {name.get(a, a)}  [{a}]")
        print(f"  coautoria futura (T1) recuperada: {name.get(tr_hit, tr_hit)}  [{tr_hit}]")
        print(f"  posição no ranking — Texto: {tr_rank} | RF (top50): {rf_rank} | Baseline (top50): {bl_rank}")
        print(f"  grau de coautoria em T0: {len(tg.get(a, set()))}")
        found += 1
        if found >= 3:
            break
