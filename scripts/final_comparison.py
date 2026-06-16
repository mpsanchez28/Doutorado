"""Comparação final consistente de todos os modelos sob o mesmo protocolo.

Roda com PYTHONHASHSEED fixo (reprodutível). Avalia todos os modelos numa única passada
(overall + por regime) com as métricas da tese (Precision/Recall/F1/NDCG/MRR/MAP@K) e salva
runs/final_comparison.json para a tabela e o gráfico. Uso:
    PYTHONHASHSEED=0 python scripts/final_comparison.py
"""
import json
import os

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.oracle import IdealTopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.models.hybrid_cand import HybridReranker
from coauthor_rec.models.supervised_hybrid import SupervisedHybridReranker

print("PYTHONHASHSEED =", os.environ.get("PYTHONHASHSEED", "(não fixado!)"))
EVAL = load_config("eval")
set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]
KS = EVAL["evaluation"]["k_values"]

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
works_raw = pd.read_csv(resolve("data/raw/works.csv"))
train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
t0 = set(train_df["author_id"])
data, maps = build_hetero_data(merged, works_raw, work_ids=set(train_df["work_id"]),
                               max_coauthors_per_work=CAP)
author_map, paper_map = maps["author"], maps["paper"]

# embedding textual de autor (SciBERT) alinhado ao author_map
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
gnn_emb = np.load(resolve("runs/gnn/author_emb_scibert.npy"))

print("Construindo modelos…")
base = TopologyRecommender(max_coauthors_per_work=CAP).fit(train_df)
models = [
    base,
    IdealTopologyRecommender(base, gt).fit(train_df),
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(train_df),
    TextSimilarityRecommender(text_auth, author_map, name="Text (SciBERT)"),
    GNNReranker(gnn_emb, author_map, name="GNN-rerank").fit(train_df),
    HybridReranker(text_auth, author_map, text_emb=text_auth, m_text=100,
                   max_coauthors_per_work=CAP, name="Hybrid-cand").fit(train_df),
    SupervisedHybridReranker(author_map, text_auth, gnn_emb=gnn_emb, m_text=100,
                             max_coauthors_per_work=CAP, name="Sup-Hybrid").fit(train_df),
]
print("Avaliando (uma passada, estratificada)…")
res = evaluate_models(models, gt, train_graph, k_values=KS,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"],
                      t0_authors=t0, show_progress=False)

out = {m: {"overall": res[m]["overall"], "by_regime": res[m]["by_regime"],
           "regime_counts": res[m]["regime_counts"]} for m in res}
resolve("runs/final_comparison.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

METRICS = [("P", "Precision"), ("R", "Recall"), ("F1", "F1"),
           ("NDCG", "NDCG"), ("MRR", "MRR"), ("MAP", "MAP")]
for scope in ["overall", "warm", "cool"]:
    n = res[models[0].name]["regime_counts"].get(scope) if scope != "overall" else \
        sum(res[models[0].name]["regime_counts"].values())
    print(f"\n{'='*78}\nREGIME: {scope.upper()} (n={n})")
    for mk, mlabel in METRICS:
        print(f"\n-- {mlabel}@K (%) --")
        print("modelo".ljust(24) + "".join(f"{k:>8}" for k in KS))
        for m in res:
            dd = res[m]["overall"] if scope == "overall" else res[m]["by_regime"][scope]
            print(m.ljust(24) + "".join(f"{dd[k][mk]*100:>8.2f}" for k in KS))
print(f"\n-> runs/final_comparison.json")
