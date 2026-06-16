"""Significância do reranker de candidatos híbridos vs Híbrido RF / GNN / texto.

Constrói todos os modelos num processo (alvos alinhados), coleta scores por autor e aplica
Shapiro->t/Wilcoxon + Bonferroni + IC bootstrap. Uso: python scripts/significance_hybrid.py
"""
import json

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.eval.stats import paired_test, bonferroni, bootstrap_ci
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.hybrid_cand import HybridReranker
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.models.text_sim import TextSimilarityRecommender

EVAL = load_config("eval")
set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]
K_VALUES = [10, 50, 200]
METRICS = [("R", 10), ("R", 50), ("R", 200), ("NDCG", 10)]

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
works_raw = pd.read_csv(resolve("data/raw/works.csv"))
train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
t0 = set(train_df["author_id"])
reg = classify_authors(train_graph, list(gt), EVAL["regimes"]["warm_min_coauthors"],
                       EVAL["regimes"]["cool_min_coauthors"], t0_authors=t0)

data, maps = build_hetero_data(merged, works_raw, work_ids=set(train_df["work_id"]),
                               max_coauthors_per_work=CAP)
author_map, paper_map = maps["author"], maps["paper"]

# embedding textual de autor alinhado ao author_map
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
emb, cpos = blob["emb"], {w: i for i, w in enumerate(blob["work_ids"])}
d = emb.shape[1]
ptext = np.zeros((len(paper_map), d), np.float32)
for wid, i in paper_map.items():
    if wid in cpos:
        ptext[i] = emb[cpos[wid]]
text_auth = np.zeros((len(author_map), d), np.float32)
cnt = np.zeros(len(author_map), np.float32)
for aid, wid in zip(train_df["author_id"], train_df["work_id"]):
    if aid in author_map and wid in paper_map:
        text_auth[author_map[aid]] += ptext[paper_map[wid]]; cnt[author_map[aid]] += 1
text_auth /= np.clip(cnt, 1.0, None)[:, None]

print("Construindo modelos…")
gnn_emb = np.load(resolve("runs/gnn/author_emb_scibert.npy"))
models = {
    "Hybrid-cand": HybridReranker(text_auth, author_map, text_emb=text_auth, m_text=100,
                                  max_coauthors_per_work=CAP, name="Hybrid-cand").fit(train_df),
    "RF": HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(train_df),
    "GNN": GNNReranker(gnn_emb, author_map, name="GNN").fit(train_df),
    "Text": TextSimilarityRecommender(text_auth, author_map, name="Text"),
}
PAIRS = [("Hybrid-cand", "RF"), ("Hybrid-cand", "GNN"), ("Hybrid-cand", "Text"), ("RF", "GNN")]

pops = {"T0-ativos": [a for a in gt if reg[a] in ("warm", "cool", "cold")],
        "warm": [a for a in gt if reg[a] == "warm"],
        "cool": [a for a in gt if reg[a] == "cool"]}

report = {}
for pop, authors in pops.items():
    gt_sub = {a: gt[a] for a in authors}
    res = evaluate_models(list(models.values()), gt_sub, train_graph, k_values=K_VALUES,
                          warm_min=EVAL["regimes"]["warm_min_coauthors"],
                          cool_min=EVAL["regimes"]["cool_min_coauthors"], t0_authors=t0,
                          show_progress=False)
    pa = {name: res[m.name]["per_author"] for name, m in models.items()}
    alpha_adj = bonferroni(EVAL["statistics"]["alpha"], len(PAIRS))
    print(f"\n===== {pop} (n={len(gt_sub)}) — α Bonferroni={alpha_adj:.4f} =====")
    block = []
    for metric, k in METRICS:
        for A, B in PAIRS:
            va, vb = pa[A][k][metric], pa[B][k][metric]
            t = paired_test(va, vb, alpha=EVAL["statistics"]["alpha"])
            mdiff, lo, hi = bootstrap_ci(np.array(va) - np.array(vb),
                                         n_boot=EVAL["statistics"]["n_bootstrap"], seed=EVAL["seed"])
            sig = t["p_value"] is not None and t["p_value"] < alpha_adj
            block.append({"metric": f"{metric}@{k}", "A": A, "B": B, "mean_A": float(np.mean(va)*100),
                          "mean_B": float(np.mean(vb)*100), "diff_pp": mdiff*100,
                          "ci": [lo*100, hi*100], "p": t["p_value"], "sig": bool(sig)})
            print(f"  {metric}@{k:<3} {A:11s} vs {B:4s}  Δ={mdiff*100:+6.2f}pp "
                  f"[{lo*100:+5.2f},{hi*100:+5.2f}]  p={t['p_value']:.4g} {'*' if sig else ''}")
    report[pop] = {"n": len(gt_sub), "alpha": alpha_adj, "tests": block}

resolve("runs/significance_hybrid.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
print("\n[significance_hybrid] -> runs/significance_hybrid.json (* = signif. após Bonferroni)")
