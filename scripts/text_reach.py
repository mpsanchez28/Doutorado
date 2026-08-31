"""Diagnóstico: ALCANCE (teto de recall) dos candidatos textuais top-m — análogo ao
candidate_hops.py, mas para o gerador textual.

Mede, por regime e por m, a fração média de C_new(a) presente entre os top-m vizinhos
por cosseno SciBERT (excluindo o próprio autor e os coautores de T0), o alcance da
vizinhança de 2 saltos e o da união — ou seja, o máximo que um ranqueador PERFEITO
extrairia de cada pool. Compare com o Recall@K realizado (runs/final_comparison.json)
para decidir se o gargalo é a ordenação ou a geração/qualidade dos candidatos.

Uso: PYTHONHASHSEED=0 python scripts/text_reach.py
Saída: runs/text_reach.json + tabela no stdout.
"""
import itertools, json, os, sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from coauthor_rec.config import load_config, resolve  # noqa: E402
from coauthor_rec.split.temporal import chronological_split, build_ground_truth  # noqa: E402

EVAL = load_config("eval")
CAP = EVAL["graph"]["max_coauthors_per_work"]
WARM_MIN = EVAL["regimes"]["warm_min_coauthors"]
COOL_MIN = EVAL["regimes"]["cool_min_coauthors"]
MS = [50, 100, 200, 500, 1000]

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
t0 = set(train_df["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}
print(f"alvos T0-ativos: {len(gt)}")

regime = lambda a: ("warm" if len(train_graph.get(a, set())) >= WARM_MIN
                    else "cool" if len(train_graph.get(a, set())) >= COOL_MIN else "cold")
regimes = {a: regime(a) for a in gt}
print("regimes:", Counter(regimes.values()))

# embedding textual de autor = média dos embeddings SciBERT dos works de T0
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
emb, wids = blob["emb"].astype(np.float32), blob["work_ids"]
wpos = {w: i for i, w in enumerate(wids)}
authors = sorted(t0)
aidx = {a: i for i, a in enumerate(authors)}
A = np.zeros((len(authors), emb.shape[1]), np.float32)
cnt = np.zeros(len(authors), np.float32)
for aid, wid in zip(train_df["author_id"], train_df["work_id"]):
    j = wpos.get(wid)
    if j is not None:
        A[aidx[aid]] += emb[j]; cnt[aidx[aid]] += 1
A /= np.clip(cnt, 1.0, None)[:, None]
A /= np.clip(np.linalg.norm(A, axis=1, keepdims=True), 1e-9, None)
authors_arr = np.array(authors)

targets = list(gt.keys())
maxm = max(MS)
reach_t = {m: defaultdict(list) for m in MS}
reach_u = {m: defaultdict(list) for m in MS}
reach_2 = defaultdict(list)

for start in range(0, len(targets), 256):
    chunk = targets[start:start + 256]
    S = A[[aidx[a] for a in chunk]] @ A.T
    for row, a in enumerate(chunk):
        cur = train_graph.get(a, set())
        new = gt[a]; n_new = len(new); reg = regimes[a]
        two = {c for nb in cur for c in train_graph.get(nb, set()) if c != a and c not in cur}
        for key in (reg, "overall"):
            reach_2[key].append(len(new & two) / n_new)
        s = S[row].copy(); s[aidx[a]] = -np.inf
        need = min(maxm + len(cur) + 1, len(s) - 1)
        top = np.argpartition(-s, need)[:need]
        top = top[np.argsort(-s[top])]
        ordered = [authors_arr[j] for j in top if authors_arr[j] != a and authors_arr[j] not in cur]
        for m in MS:
            tm = set(ordered[:m]); u = tm | two
            for key in (reg, "overall"):
                reach_t[m][key].append(len(new & tm) / n_new)
                reach_u[m][key].append(len(new & u) / n_new)

pct = lambda d: {k: round(100 * float(np.mean(v)), 2) for k, v in d.items()}
out = {"n_targets": len(targets), "catalog": len(authors),
       "regime_counts": dict(Counter(regimes.values())),
       "reach_2hop": pct(reach_2),
       "reach_text": {m: pct(reach_t[m]) for m in MS},
       "reach_union": {m: pct(reach_u[m]) for m in MS}}
os.makedirs(resolve("runs"), exist_ok=True)
json.dump(out, open(resolve("runs/text_reach.json"), "w"), indent=1)

print(f"\n{'regime':>8} | 2-hop |" + "".join(f"  texto@{m:>4}" for m in MS))
for reg in ["overall", "warm", "cool", "cold"]:
    print(f"{reg:>8} | {out['reach_2hop'].get(reg, 0):5.2f} |" +
          "".join(f"  {out['reach_text'][m].get(reg, 0):8.2f}" for m in MS))
print(f"\n{'regime':>8} |" + "".join(f"  união@{m:>4}" for m in MS))
for reg in ["overall", "warm", "cool", "cold"]:
    print(f"{reg:>8} |" + "".join(f"  {out['reach_union'][m].get(reg, 0):8.2f}" for m in MS))
print("\npool = candidatos textuais top-m EXCLUINDO self e coautores de T0 (como no 2 etapas).")
print("Compare com Recall@200 realizado: se realizado ≈ união, o gargalo é o pool, não a ordenação.")
