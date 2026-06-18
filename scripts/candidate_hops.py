"""Experimento 2-hop vs 3-hop: mede o TETO de alcance dos candidatos (fração de coautores
futuros alcançáveis) e o custo (tamanho do pool), por regime. Responde "compensa 3 saltos?"
sem treinar reranker — se o candidato não está no pool, nenhum modelo o recupera.
Uso: PYTHONHASHSEED=0 python scripts/candidate_hops.py
"""
import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.regimes import classify_authors

EVAL = load_config("eval"); CAP = EVAL["graph"]["max_coauthors_per_work"]
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
adj, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)  # adj = coautoria T0 (não-dir.)
t0 = set(tr["author_id"])
reg = classify_authors(adj, list(gt), EVAL["regimes"]["warm_min_coauthors"],
                       EVAL["regimes"]["cool_min_coauthors"], t0_authors=t0)


def hops(a):
    nb = adj.get(a, set())
    two = set()
    for x in nb:
        two |= adj.get(x, set())
    two -= nb | {a}
    three = set(two)
    for c in two:
        three |= adj.get(c, set())
    three -= nb | {a}
    return two, three


rows = {r: {"cr2": [], "cr3": [], "p2": [], "p3": []} for r in ("warm", "cool", "cold", "all")}
for a, new in gt.items():
    if a not in t0 or not new:
        continue
    two, three = hops(a)
    cr2 = len(two & new) / len(new)
    cr3 = len(three & new) / len(new)
    for key in (reg[a], "all"):
        if key not in rows:
            continue
        rows[key]["cr2"].append(cr2); rows[key]["cr3"].append(cr3)
        rows[key]["p2"].append(len(two)); rows[key]["p3"].append(len(three))

print(f"{'regime':>8} {'n':>5} | {'alcance 2-hop':>14} {'alcance 3-hop':>14} | {'pool 2-hop':>11} {'pool 3-hop':>11}")
print("-" * 80)
for r in ("all", "warm", "cool", "cold"):
    d = rows[r]
    if not d["cr2"]:
        print(f"{r:>8} {0:>5} | (sem alvos ativos em T0)"); continue
    n = len(d["cr2"])
    print(f"{r:>8} {n:>5} | {np.mean(d['cr2'])*100:>13.1f}% {np.mean(d['cr3'])*100:>13.1f}% | "
          f"{np.mean(d['p2']):>11.0f} {np.mean(d['p3']):>11.0f}")
print("\nalcance = fração dos coautores futuros (C_new) presentes no pool de candidatos;")
print("pool = nº médio de candidatos gerados (custo). 3-hop só ajuda se o alcance subir mais que o pool.")
