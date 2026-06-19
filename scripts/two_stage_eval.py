"""Avalia o reranker de 2 etapas (RF→texto) na base IA vs Baseline/RF/Texto/Cand.híbridos,
com IC95% e significância pareada vs RF. Uso: PYTHONHASHSEED=0 python scripts/two_stage_eval.py
"""
import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.eval.stats import paired_test, bonferroni
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.hybrid_cand import HybridReranker
from coauthor_rec.models.two_stage import TwoStageReranker

EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
KS = EVAL["evaluation"]["k_values"]
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}  # T0-ativos
text_auth, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))

models = [
    TopologyRecommender(max_coauthors_per_work=CAP).fit(tr),
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(tr),
    TextSimilarityRecommender(text_auth, aidx, name="Texto"),
    HybridReranker(text_auth, aidx, text_emb=text_auth, m_text=100, max_coauthors_per_work=CAP, name="Cand. híbridos").fit(tr),
    TwoStageReranker(text_auth, aidx, max_coauthors_per_work=CAP, m_text=100).fit(tr),
]
res = evaluate_models(models, gt, tg, k_values=KS, t0_authors=t0,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"], show_progress=False)
RF = "Hybrid (Graph + RandomForest)"
LBL = {"Topology (Graph Coauthor)": "Baseline", RF: "Híbrido RF", "Texto": "Texto",
       "Cand. híbridos": "Cand. híbridos", "2-stage (RF→texto)": "2 etapas (RF→texto)"}

for scope in ["overall", "warm", "cool"]:
    print(f"\n=== Recall@K (%) — {scope} ===")
    print("modelo".ljust(20) + "".join(f"{k:>8}" for k in (5, 10, 50, 200)))
    for m in res:
        d = res[m]["overall"] if scope == "overall" else res[m]["by_regime"][scope]
        print(LBL[m].ljust(20) + "".join(f"{d[k]['R']*100:>8.2f}" for k in (5, 10, 50, 200)))

print("\n=== Significância: 2 etapas vs RF (Wilcoxon, α Bonferroni) ===")
a = bonferroni(EVAL["statistics"]["alpha"], 6)
for scope in ["overall", "warm", "cool"]:
    for k in (10, 50, 200):
        va = res["2-stage (RF→texto)"]["per_author" if scope == "overall" else "per_author_by_regime"]
        va = (va if scope == "overall" else va[scope])[k]["R"]
        vb = res[RF]["per_author" if scope == "overall" else "per_author_by_regime"]
        vb = (vb if scope == "overall" else vb[scope])[k]["R"]
        t = paired_test(va, vb, alpha=EVAL["statistics"]["alpha"])
        d = (np.mean(va) - np.mean(vb)) * 100
        sig = "*" if (t["p_value"] is not None and t["p_value"] < a) else " "
        print(f"  {scope:>7} R@{k:<3} Δ={d:+6.2f}pp  p={t['p_value']:.4g} {sig}")
