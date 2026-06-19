"""Diagramas para o relatório/tese: (1) fluxo metodológico e (2) conceito do espaço de
candidatos (2-hop vs alcance textual vs cold-start). Salva PNGs em docs/.
Uso: python scripts/make_diagrams.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from coauthor_rec.config import resolve

AC, AC2, GR, RD, MU = "#1F4E79", "#3b82f6", "#16a34a", "#d62728", "#6b7280"


def box(ax, x, y, w, h, text, fc="#eef3f8", ec=AC, tc="#0f1720", fs=10, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, color=MU):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=1.6))


# ---- Diagrama 1: fluxo metodológico ----
fig, ax = plt.subplots(figsize=(11, 6.2)); ax.set_xlim(0, 11); ax.set_ylim(0, 6.2); ax.axis("off")
fig.suptitle("Fluxo metodológico — recomendação de coautoria (T0→T1)", fontsize=14, fontweight="bold")
box(ax, 0.3, 5.0, 2.3, 0.8, "OpenAlex\n(coleta temática IA)", fc="#dbeafe", bold=True)
box(ax, 2.9, 5.0, 2.1, 0.8, "Limpeza + Gate\nde qualidade")
box(ax, 5.3, 5.0, 2.3, 0.8, "KG heterogêneo\n(5 entidades / 6 relações)")
box(ax, 7.9, 5.0, 2.8, 0.8, "Split temporal T0/T1\nGround truth = C_new")
for x in (2.6, 5.0, 7.6): arrow(ax, x, 5.4, x + 0.3, 5.4)
# duas vertentes
box(ax, 1.0, 3.2, 3.4, 0.9, "Vertente ESTRUTURAL\nCommon Neighbors · Random Forest · GNN", fc="#fde2e1", ec=RD, bold=True)
box(ax, 6.0, 3.2, 3.6, 0.9, "Vertente TEXTUAL\nSciBERT (CNN) · embeddings de autor", fc="#dcfce7", ec=GR, bold=True)
arrow(ax, 5.5, 5.0, 2.7, 4.1, RD); arrow(ax, 7.0, 5.0, 7.8, 4.1, GR)
box(ax, 3.2, 1.6, 4.6, 0.9, "GERAÇÃO DE CANDIDATOS\n2-hop  ∪  vizinhos textuais (híbrido)", fc="#fff7ed", ec="#b45309", bold=True)
arrow(ax, 2.7, 3.2, 4.6, 2.5, RD); arrow(ax, 7.8, 3.2, 6.4, 2.5, GR)
box(ax, 3.4, 0.2, 4.2, 0.8, "Ranking → Top-K  →  Avaliação\nP/R/F1/NDCG/MRR/MAP · warm/cool/cold · IC95%")
arrow(ax, 5.5, 1.6, 5.5, 1.0)
ax.text(5.5, 2.78, "← gargalo identificado: o pool de candidatos →", ha="center", fontsize=9, color="#b45309", style="italic")
fig.savefig(resolve("docs/diagrama_fluxo.png"), dpi=130, bbox_inches="tight"); plt.close(fig)

# ---- Diagrama 2: espaço de candidatos ----
fig, ax = plt.subplots(figsize=(11, 4.6)); ax.axis("off"); ax.set_xlim(0, 11); ax.set_ylim(0, 4.6)
fig.suptitle("Espaço de candidatos: por que o texto alcança o que a topologia não vê",
             fontsize=14, fontweight="bold")
def author(ax, x, y, lab, c=AC):
    ax.add_patch(Circle((x, y), 0.16, fc=c, ec="white", lw=1.2, zorder=3))
    ax.text(x, y - 0.34, lab, ha="center", fontsize=8, color="#0f1720")
# warm/cool: alvo com vizinhos
ax.text(2.2, 4.0, "Autor com histórico (warm/cool)", ha="center", fontsize=10, fontweight="bold")
author(ax, 2.2, 3.1, "alvo", AC)
for dx in (-0.9, 0, 0.9): author(ax, 2.2 + dx, 2.3, "coautor", MU)
for dx in (-1.4, -0.5, 0.5, 1.4): author(ax, 2.2 + dx, 1.5, "2-hop", "#94a3b8")
for dx in (-0.9, 0, 0.9):
    ax.plot([2.2, 2.2 + dx], [3.1, 2.3], color="#cbd5e1", lw=1, zorder=1)
author(ax, 3.9, 2.0, "coautor\nFUTURO", GR)
ax.add_patch(FancyArrowPatch((2.6, 2.6), (3.7, 2.1), arrowstyle="-|>", mutation_scale=12, color=GR, lw=1.8, ls="--"))
ax.text(3.5, 2.7, "similaridade\ntextual", color=GR, fontsize=8, ha="center")
ax.text(2.2, 0.7, "2-hop alcança ~5% dos coautores futuros;\no texto traz candidatos fora do grafo.", ha="center", fontsize=8.5, color=MU)
# cold: alvo sem vizinhos
ax.text(8.0, 4.0, "Autor sem histórico (cold-start)", ha="center", fontsize=10, fontweight="bold")
author(ax, 7.0, 2.4, "alvo\n(0 coautores)", RD)
ax.text(7.0, 1.7, "2-hop = ∅\n→ topologia: 0%", ha="center", fontsize=8.5, color=RD)
author(ax, 9.2, 2.4, "coautor\nFUTURO", GR)
ax.add_patch(FancyArrowPatch((7.25, 2.4), (8.95, 2.4), arrowstyle="-|>", mutation_scale=12, color=GR, lw=1.8, ls="--"))
ax.text(8.1, 2.75, "só o texto\nrecomenda", color=GR, fontsize=8.5, ha="center")
fig.savefig(resolve("docs/diagrama_candidatos.png"), dpi=130, bbox_inches="tight"); plt.close(fig)
print("-> docs/diagrama_fluxo.png, docs/diagrama_candidatos.png")
