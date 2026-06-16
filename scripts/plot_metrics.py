"""Gráfico comparativo das métricas da tese (Precision/Recall/F1/NDCG/MRR/MAP @K).

Lê runs/final_comparison.json e gera um painel por métrica (x=K, linhas=modelos), no estilo
da Figura 2 da qualificação. Uso: python scripts/plot_metrics.py [regime]  (overall|warm|cool)
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from coauthor_rec.config import resolve

regime = sys.argv[1] if len(sys.argv) > 1 else "overall"
data = json.loads(resolve("runs/final_comparison.json").read_text())

# ordem e estilo dos modelos (subconjunto legível)
MODELS = ["Topology (Graph Coauthor)", "Ideal Topology (Oracle)", "Hybrid (Graph + RandomForest)",
          "Text (SciBERT)", "GNN-rerank", "Hybrid-cand", "Sup-Hybrid"]
LABELS = {"Topology (Graph Coauthor)": "Baseline (CN)", "Ideal Topology (Oracle)": "Oráculo",
          "Hybrid (Graph + RandomForest)": "Híbrido RF", "Text (SciBERT)": "Texto (SciBERT)",
          "GNN-rerank": "GNN-rerank", "Hybrid-cand": "Cand. híbridos", "Sup-Hybrid": "Sup-Hybrid"}
MODELS = [m for m in MODELS if m in data]
METRICS = [("P", "Precision@K"), ("R", "Recall@K"), ("F1", "F1@K"),
           ("NDCG", "NDCG@K"), ("MRR", "MRR@K"), ("MAP", "MAP@K")]

any_model = data[MODELS[0]]
KS = sorted((int(k) for k in any_model["overall"].keys()))
colors = plt.cm.tab10.colors
markers = ["o", "s", "^", "D", "v", "P", "X"]

fig, axes = plt.subplots(2, 3, figsize=(16, 9))
n = any_model["regime_counts"].get(regime) if regime != "overall" else \
    sum(any_model["regime_counts"].values())
fig.suptitle(f"Comparação de modelos — métricas de ranqueamento (regime: {regime}, n={n})",
             fontsize=15, fontweight="bold")

for ax, (mk, mlabel) in zip(axes.flat, METRICS):
    for i, model in enumerate(MODELS):
        d = data[model]["overall"] if regime == "overall" else data[model]["by_regime"][regime]
        ys = [d[str(k)][mk] * 100 for k in KS]
        ax.plot(KS, ys, marker=markers[i % len(markers)], color=colors[i % len(colors)],
                label=LABELS[model], linewidth=1.8, markersize=6)
    ax.set_title(mlabel, fontweight="bold")
    ax.set_xlabel("K"); ax.set_ylabel(f"{mlabel} (%)")
    ax.set_xscale("log"); ax.set_xticks(KS); ax.set_xticklabels(KS)
    ax.grid(True, alpha=0.3, linestyle="--")
axes.flat[0].legend(fontsize=8, loc="best")
plt.tight_layout(rect=[0, 0, 1, 0.97])
outpng = resolve(f"docs/metricas_{regime}.png")
plt.savefig(outpng, dpi=130, bbox_inches="tight")
print(f"-> {outpng}")
