"""Gráfico do cold-start na base de IA: Recall@K (cool e cold) por modelo.
Lê runs/cool_cold_frac0.8.json. Uso: python scripts/plot_ai_coldstart.py
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from coauthor_rec.config import resolve

d = json.loads(resolve("runs/cool_cold_frac0.8.json").read_text())
LBL = {"Topology (Graph Coauthor)": "Baseline (CN)", "Hybrid (Graph + RandomForest)": "Híbrido RF",
       "Text (SciBERT)": "Texto", "Hybrid-cand": "Cand. híbridos"}
MODELS = [m for m in ["Topology (Graph Coauthor)", "Hybrid (Graph + RandomForest)",
                      "Text (SciBERT)", "Hybrid-cand"] if m in d]
KS = sorted(int(k) for k in d[MODELS[0]]["by_regime"]["cool"])
colors = {"Topology (Graph Coauthor)": "#888", "Hybrid (Graph + RandomForest)": "#d62728",
          "Text (SciBERT)": "#2ca02c", "Hybrid-cand": "#1f77b4"}
mk = {"Topology (Graph Coauthor)": "o", "Hybrid (Graph + RandomForest)": "s",
      "Text (SciBERT)": "^", "Hybrid-cand": "D"}

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Base de IA — Recall@K por regime (cold-start)", fontsize=15, fontweight="bold")
for ax, (scope, n) in zip(axes, [("cool", d[MODELS[0]]["regime_counts"]["cool"]),
                                 ("cold", d[MODELS[0]]["regime_counts"]["cold"])]):
    for m in MODELS:
        ys = [d[m]["by_regime"][scope][str(k)]["R"] * 100 for k in KS]
        ax.plot(KS, ys, marker=mk[m], color=colors[m], label=LBL[m], linewidth=2, markersize=7)
    ax.set_title(f"{scope.upper()} (n={n})", fontweight="bold")
    ax.set_xlabel("K"); ax.set_ylabel("Recall@K (%)")
    ax.set_xscale("log"); ax.set_xticks(KS); ax.set_xticklabels(KS)
    ax.grid(True, alpha=0.3, linestyle="--"); ax.legend(fontsize=10)
plt.tight_layout(rect=[0, 0, 1, 0.95])
out = resolve("docs/ai_cool_cold.png")
plt.savefig(out, dpi=130, bbox_inches="tight")
print("->", out)
