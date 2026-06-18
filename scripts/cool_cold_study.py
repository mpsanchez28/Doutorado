"""Aprofundamento dos regimes cool/cold: usa um corte temporal mais cedo (T0=50%) para
popular cool/cold (cold 3→27, cool 78→103) sem coletar dados novos, e compara os modelos
relevantes (Baseline, RF, Texto, Cand. híbridos) com IC95% bootstrap e significância pareada.
Sem GPU (reaproveita os embeddings SciBERT por artigo). Uso:
    PYTHONHASHSEED=0 python scripts/cool_cold_study.py [frac]
"""
import json
import sys

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.eval.stats import paired_test, bonferroni, bootstrap_metric_cis
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.oracle import IdealTopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.hybrid_cand import HybridReranker

FRAC = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8
EVAL = load_config("eval"); set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]
KS = EVAL["evaluation"]["k_values"]; NB = EVAL["statistics"]["n_bootstrap"]

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
emb, wids = blob["emb"], list(blob["work_ids"])

tr, te = chronological_split(merged, train_fraction=FRAC)
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
text_auth, aidx = author_embeddings(tr, emb, wids)
print(f"[cool/cold] T0={FRAC}: alvos={len(gt)}")

base = TopologyRecommender(max_coauthors_per_work=CAP).fit(tr)
models = [
    base,  # oráculo omitido (lento sobre muitos alvos; é apenas teto)
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(tr),
    TextSimilarityRecommender(text_auth, aidx, name="Text (SciBERT)"),
    HybridReranker(text_auth, aidx, text_emb=text_auth, m_text=100,
                   max_coauthors_per_work=CAP, name="Hybrid-cand").fit(tr),
]
res = evaluate_models(models, gt, tg, k_values=KS, t0_authors=t0,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"], show_progress=False)
counts = res[base.name]["regime_counts"]
print("regimes:", counts)

LBL = {base.name: "Baseline (CN)", "Ideal Topology (Oracle)": "Oráculo",
       "Hybrid (Graph + RandomForest)": "Híbrido RF", "Text (SciBERT)": "Texto",
       "Hybrid-cand": "Cand. híbridos"}
for scope in ["cool", "cold"]:
    print(f"\n===== {scope.upper()} (n={counts[scope]}) — Recall@K [IC95%] (%) =====")
    for m in res:
        ci = bootstrap_metric_cis(res[m]["per_author_by_regime"][scope], KS, n_boot=NB, seed=EVAL["seed"])
        row = "  ".join(f"@{k}:{res[m]['by_regime'][scope][k]['R']*100:.1f}[{ci[k]['R'][0]*100:.0f}-{ci[k]['R'][1]*100:.0f}]"
                        for k in (10, 50, 200))
        print(f"  {LBL[m]:16s} {row}")

# significância: Cand. híbridos e Texto vs RF, em cool e cold
print("\n===== Significância (Wilcoxon, α Bonferroni) =====")
rf = "Hybrid (Graph + RandomForest)"
pairs = [("Hybrid-cand", rf), ("Text (SciBERT)", rf)]
for scope in ["cool", "cold"]:
    a = bonferroni(EVAL["statistics"]["alpha"], len(pairs) * 2)
    print(f"-- {scope} (n={counts[scope]}, α={a:.4f}) --")
    for A, B in pairs:
        for k in (10, 200):
            va = res[A]["per_author_by_regime"][scope][k]["R"]
            vb = res[B]["per_author_by_regime"][scope][k]["R"]
            t = paired_test(va, vb, alpha=EVAL["statistics"]["alpha"])
            d = (np.mean(va) - np.mean(vb)) * 100
            sig = "*" if (t["p_value"] is not None and t["p_value"] < a) else " "
            print(f"   R@{k:<3} {LBL[A]:14s} vs RF  Δ={d:+5.1f}pp  p={t['p_value']:.4g} {sig}")

out = {m: {"by_regime": res[m]["by_regime"], "regime_counts": counts} for m in res}
resolve(f"runs/cool_cold_frac{FRAC}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(f"\n-> runs/cool_cold_frac{FRAC}.json")
