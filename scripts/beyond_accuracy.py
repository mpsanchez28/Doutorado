"""Avaliação MULTIDIMENSIONAL (lacuna #5): diversidade (ILD), novidade e cobertura de
catálogo — reportadas AO LADO do Recall (só fazem sentido lidas com a acurácia).

Modelos: Baseline (2-hop) · Híbrido RF · Texto (SciBERT) · 2 etapas (RF→texto).
Uso: PYTHONHASHSEED=0 python scripts/beyond_accuracy.py [SAMPLE]
     (SAMPLE opcional = nº de alvos amostrados, p/ execução rápida)
Saída: runs/beyond/beyond.json + tabela no stdout.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval import beyond as BY
from coauthor_rec.eval import metrics as M
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.two_stage import TwoStageReranker

KS = [5, 10, 20]
EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else None

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}           # alvos T0-ativos
text_auth, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))
# perfis L2-normalizados p/ ILD (cosseno = produto interno)
norms = np.linalg.norm(text_auth, axis=1, keepdims=True)
emb_n = (text_auth / np.clip(norms, 1e-9, None)).astype(np.float32)

pop = BY.popularity_from_graph(tg)                      # p(c) p/ novidade
catalog = set(tr["author_id"].unique())                 # autores recomendáveis
targets = list(gt.keys())
if SAMPLE:
    rng = np.random.default_rng(EVAL["seed"])
    targets = [targets[i] for i in rng.choice(len(targets), min(SAMPLE, len(targets)), replace=False)]
regime_of = classify_authors(tg, targets, EVAL["regimes"]["warm_min_coauthors"],
                             EVAL["regimes"]["cool_min_coauthors"], t0)

models = [
    TopologyRecommender(max_coauthors_per_work=CAP).fit(tr),
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(tr),
    TextSimilarityRecommender(emb_n, aidx, name="Texto"),
    TwoStageReranker(text_auth, aidx, max_coauthors_per_work=CAP, m_text=100).fit(tr),
]
LBL = {"Topology (Graph Coauthor)": "Baseline", "Hybrid (Graph + RandomForest)": "Híbrido RF",
       "Texto": "Texto", "2-stage (RF→texto)": "2 etapas"}

max_k = max(KS)
out = {}
for model in models:
    acc = {k: {"R": [], "ILD": [], "NOV": []} for k in KS}
    cov = {k: set() for k in KS}
    nov_reg = {k: {} for k in KS}                       # novidade por regime
    for a in targets:
        recs = model.recommend(a, top_n=max_k * 3)
        past = tg.get(a, set())
        valid = [r for r in recs if r not in past][:max_k]
        rel = gt[a]
        reg = regime_of[a]
        for k in KS:
            acc[k]["R"].append(M.recall_at_k(valid, rel, k))
            acc[k]["ILD"].append(BY.intra_list_diversity(valid, k, emb_n, aidx))
            acc[k]["NOV"].append(BY.novelty(valid, k, pop))
            cov[k].update(valid[:k])
            nov_reg[k].setdefault(reg, []).append(BY.novelty(valid, k, pop))
    name = LBL.get(model.name, model.name)
    out[name] = {
        str(k): {
            "R": float(np.mean(acc[k]["R"])),
            "ILD": float(np.mean(acc[k]["ILD"])),
            "NOV": float(np.mean(acc[k]["NOV"])),
            "COV": len(cov[k]) / max(len(catalog), 1),
            "NOV_by_regime": {r: float(np.mean(v)) for r, v in nov_reg[k].items() if v},
        } for k in KS
    }

os.makedirs(resolve("runs/beyond"), exist_ok=True)
with open(resolve("runs/beyond/beyond.json"), "w") as fh:
    json.dump({"n_targets": len(targets), "catalog": len(catalog), "models": out}, fh, indent=2)

print(f"\nAvaliação multidimensional — {len(targets)} alvos, catálogo {len(catalog)} autores"
      + (f" (amostra {SAMPLE})" if SAMPLE else "") + "\n")
for k in KS:
    print(f"=== K = {k} ===")
    print("modelo".ljust(12) + "Recall".rjust(9) + "ILD(div)".rjust(10)
          + "Novidade".rjust(10) + "Cobertura".rjust(11))
    for name, d in out.items():
        r = d[str(k)]
        print(name.ljust(12) + f"{r['R']*100:8.2f}%" + f"{r['ILD']:10.3f}"
              + f"{r['NOV']:10.2f}" + f"{r['COV']*100:10.2f}%")
    print()
print("Novidade por regime (K=10) — quanto maior, mais long-tail:")
for name, d in out.items():
    br = d["10"]["NOV_by_regime"]
    print("  " + name.ljust(12) + "  ".join(f"{r}={br[r]:.2f}" for r in ("warm", "cool", "cold") if r in br))
print("\nLeitura: diversidade/novidade altas só valem se o Recall acompanhar. Um recomendador")
print("aleatório maximiza ambas e é inútil — por isso a leitura é conjunta.")
