"""Testes de significância pareados entre modelos (§4.6.3).

Roda todos os modelos num único processo (alvos alinhados), coleta os scores por autor
de cada métrica/regime e aplica Shapiro->t pareado/Wilcoxon com correção de Bonferroni e
IC bootstrap da diferença média. Salva runs/significance.json.

Uso: python scripts/significance.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.eval.stats import paired_test, bonferroni, bootstrap_ci
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.text.embed import author_embeddings

EVAL = load_config("eval")
set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]
K_VALUES = [10, 50]
METRICS = [("R", 10), ("R", 50), ("NDCG", 10)]
N_BOOT = EVAL["statistics"]["n_bootstrap"]
ALPHA = EVAL["statistics"]["alpha"]

# Pares a testar (A vs B): a hipótese de interesse e o que cada par responde.
PAIRS = [
    ("Hybrid (Graph + RandomForest)", "Topology (Graph Coauthor)"),  # RF melhora o baseline?
    ("Text:scibert", "Hybrid (Graph + RandomForest)"),               # texto bate a melhor topologia?
    ("Text:specter", "Hybrid (Graph + RandomForest)"),
    ("Text:scibert", "Text:tfidf"),                                  # transformer vs clássico
    ("Text:scibert", "Text:bert"),                                   # domínio vs genérico
    ("Text:specter", "Text:scibert"),                                # os dois líderes
]


def load_text_recommender(name, train_df):
    blob = np.load(resolve(f"data/processed/text_emb/{name}.npz"), allow_pickle=True)
    emb, work_ids = blob["emb"], list(blob["work_ids"])
    author_emb, aidx = author_embeddings(train_df, emb, work_ids)
    return TextSimilarityRecommender(author_emb, aidx, name=f"Text:{name}")


def main():
    merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
    train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
    train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
    t0 = set(train_df["author_id"])
    reg = classify_authors(train_graph, list(gt), EVAL["regimes"]["warm_min_coauthors"],
                           EVAL["regimes"]["cool_min_coauthors"], t0_authors=t0)

    print("Treinando modelos…")
    models = [
        TopologyRecommender(max_coauthors_per_work=CAP).fit(train_df),
        HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(train_df),
        load_text_recommender("tfidf", train_df),
        load_text_recommender("bert", train_df),
        load_text_recommender("scibert", train_df),
        load_text_recommender("specter", train_df),
    ]

    populations = {
        "T0-ativos (warm+cool+cold)": [a for a in gt if reg[a] in ("warm", "cool", "cold")],
        "warm": [a for a in gt if reg[a] == "warm"],
        "cool": [a for a in gt if reg[a] == "cool"],
    }

    report = {}
    for pop_name, authors in populations.items():
        gt_sub = {a: gt[a] for a in authors}
        if len(gt_sub) < 3:
            print(f"[{pop_name}] n={len(gt_sub)} — pulado (amostra insuficiente)")
            continue
        res = evaluate_models(models, gt_sub, train_graph, k_values=K_VALUES,
                              warm_min=EVAL["regimes"]["warm_min_coauthors"],
                              cool_min=EVAL["regimes"]["cool_min_coauthors"],
                              t0_authors=t0, show_progress=False)
        pa = {m: res[m]["per_author"] for m in res}  # [k][metric] -> lista alinhada

        c = len(PAIRS)  # comparações por (população, métrica) p/ Bonferroni
        alpha_adj = bonferroni(ALPHA, c)
        pop_block = {"n": len(gt_sub), "alpha_bonferroni": alpha_adj, "tests": []}
        print(f"\n===== {pop_name} (n={len(gt_sub)}) — α Bonferroni={alpha_adj:.4f} =====")
        for metric, k in METRICS:
            for a_name, b_name in PAIRS:
                va, vb = pa[a_name][k][metric], pa[b_name][k][metric]
                t = paired_test(va, vb, alpha=ALPHA)
                mean_diff, lo, hi = bootstrap_ci(np.array(va) - np.array(vb), n_boot=N_BOOT,
                                                 seed=EVAL["seed"])
                sig = (t["p_value"] is not None and t["p_value"] < alpha_adj)
                tag = f"{metric}@{k}"
                pop_block["tests"].append({
                    "metric": tag, "A": a_name, "B": b_name,
                    "mean_A": float(np.mean(va) * 100), "mean_B": float(np.mean(vb) * 100),
                    "mean_diff_pp": mean_diff * 100, "ci_pp": [lo * 100, hi * 100],
                    "test": t["test"], "p_value": t["p_value"], "significant": bool(sig),
                })
                star = "*" if sig else " "
                print(f"  {tag:8s} {a_name.split('(')[0][:18]:18s} vs {b_name.split('(')[0][:18]:18s} "
                      f"Δ={mean_diff*100:+6.2f}pp [{lo*100:+5.2f},{hi*100:+5.2f}] "
                      f"{str(t['test']):9s} p={t['p_value']:.4g} {star}")
        report[pop_name] = pop_block

    out = resolve("runs/significance.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[significance] -> {out}  (* = significativo após Bonferroni)")


if __name__ == "__main__":
    main()
