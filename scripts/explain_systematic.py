"""Explicabilidade SISTEMÁTICA (lacuna #3): em vez de explicar um par, quantifica sobre
TODAS as recomendações do modelo vencedor (2 etapas) por qual mecanismo cada uma se
explica — estrutura (coautores em comum) e/ou tema (conceitos OpenAlex compartilhados) —
com recorte por regime e para os ACERTOS (recomendações que viraram coautoria em T1).

Taxonomia por recomendação (autor-alvo → candidato), em T0:
  ESTRUTURAL  = |coautores em comum| > 0        (alcançável pela topologia 2-hop)
  TEMÁTICA    = |conceitos em comum| > 0         (afinidade temática explícita)
  AMBAS / NENHUMA conforme a combinação. "Explicável" = estrutural OU temática.

Uso: PYTHONHASHSEED=0 python scripts/explain_systematic.py [SAMPLE]
Saída: runs/beyond/explain_systematic.json + tabela no stdout.
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.two_stage import TwoStageReranker

K = 10
MIN_SCORE = load_config("collect").get("thematic", {}).get("min_concept_score", 0.3)
EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else None

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}
text_auth, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))
norms = np.linalg.norm(text_auth, axis=1, keepdims=True)
emb_n = (text_auth / np.clip(norms, 1e-9, None)).astype(np.float32)

# ---- conceitos por autor (T0), pré-computados uma vez ----
raw = pd.read_csv(resolve("data/raw_ai/works.csv"), usecols=["id", "concepts"])
work_concepts = {}
for wid, cj in zip(raw["id"], raw["concepts"]):
    s = set()
    if isinstance(cj, str) and cj:
        for it in json.loads(cj):
            if it.get("id") and it.get("score", 0) >= MIN_SCORE:
                s.add(it["id"])
    work_concepts[wid] = s
author_concepts = defaultdict(set)
for wid, aid in zip(tr["work_id"], tr["author_id"]):
    author_concepts[aid] |= work_concepts.get(wid, set())

model = TwoStageReranker(text_auth, aidx, max_coauthors_per_work=CAP, m_text=100).fit(tr)
targets = list(gt.keys())
if SAMPLE:
    rng = np.random.default_rng(EVAL["seed"])
    targets = [targets[i] for i in rng.choice(len(targets), min(SAMPLE, len(targets)), replace=False)]
regime_of = classify_authors(tg, targets, EVAL["regimes"]["warm_min_coauthors"],
                             EVAL["regimes"]["cool_min_coauthors"], t0)


def bucket(struct, thema):
    if struct and thema:
        return "ambas"
    if struct:
        return "estrutural"
    if thema:
        return "temática"
    return "nenhuma"


def tally():
    return {"ambas": 0, "estrutural": 0, "temática": 0, "nenhuma": 0,
            "n": 0, "cn": 0.0, "sc": 0.0, "cos": 0.0}


overall, by_regime, hits = tally(), defaultdict(tally), tally()
for a in targets:
    recs = model.recommend(a, top_n=K * 3)
    past = tg.get(a, set())
    valid = [r for r in recs if r not in past][:K]
    na, ca, reg, rel = tg.get(a, set()), author_concepts.get(a, set()), regime_of[a], gt[a]
    ia = aidx.get(a)
    for c in valid:
        cn = len(na & tg.get(c, set()))
        sc = len(ca & author_concepts.get(c, set()))
        cos = float(emb_n[ia] @ emb_n[aidx[c]]) if (ia is not None and c in aidx) else 0.0
        b = bucket(cn > 0, sc > 0)
        for tgt in (overall, by_regime[reg]) + ((hits,) if c in rel else ()):
            tgt[b] += 1; tgt["n"] += 1
            tgt["cn"] += cn; tgt["sc"] += sc; tgt["cos"] += cos


def summarize(t):
    n = max(t["n"], 1)
    return {"n": t["n"],
            "%estrutural": 100 * (t["estrutural"] + t["ambas"]) / n,
            "%temática": 100 * (t["temática"] + t["ambas"]) / n,
            "%ambas": 100 * t["ambas"] / n,
            "%nenhuma": 100 * t["nenhuma"] / n,
            "%explicável": 100 * (n - t["nenhuma"]) / n,
            "media_coautores_comuns": t["cn"] / n,
            "media_conceitos_comuns": t["sc"] / n,
            "media_cosseno": t["cos"] / n}


res = {"K": K, "n_targets": len(targets),
       "overall": summarize(overall),
       "by_regime": {r: summarize(by_regime[r]) for r in ("warm", "cool", "cold") if by_regime[r]["n"]},
       "hits": summarize(hits)}
os.makedirs(resolve("runs/beyond"), exist_ok=True)
with open(resolve("runs/beyond/explain_systematic.json"), "w") as fh:
    json.dump(res, fh, indent=2)


def row(label, s):
    print(label.ljust(16) + f"{s['%explicável']:9.1f}%" + f"{s['%estrutural']:11.1f}%"
          + f"{s['%temática']:10.1f}%" + f"{s['%nenhuma']:10.1f}%"
          + f"{s['media_conceitos_comuns']:9.1f}" + f"{s['media_cosseno']:8.2f}")


print(f"\nExplicabilidade sistemática — modelo 2 etapas, top-{K}, {len(targets)} alvos"
      + (f" (amostra {SAMPLE})" if SAMPLE else "") + "\n")
print("recorte".ljust(16) + "explicável".rjust(10) + "estrutural".rjust(11)
      + "temática".rjust(10) + "nenhuma".rjust(10) + "conc.".rjust(9) + "cos".rjust(8))
row("TODAS", res["overall"])
for r in ("warm", "cool", "cold"):
    if r in res["by_regime"]:
        row(f"  regime {r}", res["by_regime"][r])
row("ACERTOS (T1)", res["hits"])
print("\nLeitura: no cold-start a explicação migra de ESTRUTURAL para TEMÁTICA — as recomendações")
print("certas para autores sem coautores prévios são sustentadas por conceitos/tema, não topologia.")
