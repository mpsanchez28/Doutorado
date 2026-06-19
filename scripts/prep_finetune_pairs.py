"""Gera pares de treino para fine-tuning contrastivo do encoder, SÓ de T0 (sem vazamento).

Positivo = (perfil textual do autor A, perfil textual do autor B) quando A e B coautoram em T0.
Cada perfil = título+abstract dos artigos do autor (truncado). Saída JSONL para
sentence-transformers (MultipleNegativesRankingLoss usa os demais do lote como negativos).
Uso: PYTHONHASHSEED=0 python scripts/prep_finetune_pairs.py [max_pairs]
"""
import json
import random
import sys

import pandas as pd

from coauthor_rec.config import load_config, resolve
from coauthor_rec.split.temporal import chronological_split
from coauthor_rec.graph.coauthor import build_weighted_coauthor_edges

MAX_PAIRS = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
MAX_CHARS = 2000
EVAL = load_config("eval"); CAP = EVAL["graph"]["max_coauthors_per_work"]
rng = random.Random(EVAL["seed"])

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
tr, _ = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])

# perfil textual por autor (T0): título. abstract dos seus artigos, truncado
prof = {}
for aid, g in tr.groupby("author_id"):
    parts = []
    for _, r in g.drop_duplicates("work_id").iterrows():
        t = "" if pd.isna(r["title"]) else str(r["title"])
        a = "" if pd.isna(r["abstract"]) else str(r["abstract"])
        parts.append((t + ". " + a).strip())
    txt = " ".join(parts)[:MAX_CHARS].strip()
    if txt:
        prof[aid] = txt

edges = build_weighted_coauthor_edges(tr, max_coauthors_per_work=CAP)
pairs = [(a, b) for (a, b) in edges if a in prof and b in prof]
rng.shuffle(pairs)
pairs = pairs[:MAX_PAIRS]

out = resolve("data/processed/finetune_pairs.jsonl")
with open(out, "w", encoding="utf-8") as fh:
    for a, b in pairs:
        fh.write(json.dumps({"anchor": prof[a], "positive": prof[b]}, ensure_ascii=False) + "\n")
print(f"[prep] {len(pairs)} pares de coautoria (T0) · {len(prof)} perfis de autor -> {out}")
print(f"  exemplo: anchor='{prof[pairs[0][0]][:60]}…' positive='{prof[pairs[0][1]][:60]}…'")
