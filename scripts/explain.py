"""Recomendação explicável: para um par (autor-alvo, candidato), mostra a EVIDÊNCIA —
coautores em comum (estrutura), similaridade textual, conceitos compartilhados e termos
em comum dos abstracts. Demonstra interpretabilidade. Default: Ajzen → Fishbein.
Uso: PYTHONHASHSEED=0 python scripts/explain.py [author_id_alvo author_id_candidato]
"""
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.text.embed import author_embeddings

A = sys.argv[1] if len(sys.argv) > 2 else "A5038084567"  # Icek Ajzen
B = sys.argv[2] if len(sys.argv) > 2 else "A5065215114"  # Martin Fishbein

EVAL = load_config("eval"); CAP = EVAL["graph"]["max_coauthors_per_work"]
m = pd.read_parquet(resolve("data/processed/corpus.parquet"))
raw = pd.read_csv(resolve("data/raw_ai/works.csv")).set_index("id")
name = dict(zip(m["author_id"], m["author_name"]))
tr, te = chronological_split(m, train_fraction=EVAL["split"]["train_fraction"])
adj, _ = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
emb, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))


def concepts_of(aid):
    works = tr[tr["author_id"] == aid]["work_id"].unique()
    c = Counter()
    for w in works:
        if w in raw.index:
            for it in json.loads(raw.loc[w, "concepts"] or "[]"):
                if it.get("name"):
                    c[it["name"]] += 1
    return c, list(works)


def abstracts_of(aid):
    works = set(tr[tr["author_id"] == aid]["work_id"])
    return " ".join(str(t) for t in tr[tr["work_id"].isin(works)].drop_duplicates("work_id")["abstract"])


print(f"POR QUE recomendar  {name.get(B, B)}  para  {name.get(A, A)}?\n")

# 1. estrutura
na, nb = adj.get(A, set()), adj.get(B, set())
common = na & nb
print(f"1) Estrutura (coautoria T0): {name.get(A,A)} tem {len(na)} coautores; em comum com o "
      f"candidato: {len(common)}")
print(f"   → coautores em comum (2-hop): {[name.get(c,c) for c in list(common)[:5]] or 'NENHUM — fora do alcance topológico'}")

# 2. texto
if A in aidx and B in aidx:
    va, vb = emb[aidx[A]], emb[aidx[B]]
    cos = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
    print(f"\n2) Similaridade textual (SciBERT, perfil de abstracts): cosseno = {cos:.3f}")

# 3. conceitos compartilhados
ca, _ = concepts_of(A); cb, _ = concepts_of(B)
shared = [(k, ca[k] + cb[k]) for k in (set(ca) & set(cb))]
shared.sort(key=lambda x: -x[1])
print(f"\n3) Conceitos OpenAlex em comum: {[k for k, _ in shared[:8]] or '—'}")

# 4. termos em comum dos abstracts (TF-IDF)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [abstracts_of(A), abstracts_of(B)]
    if all(docs):
        v = TfidfVectorizer(stop_words="english", max_features=4000, ngram_range=(1, 2), min_df=1)
        X = v.fit_transform(docs).toarray()
        terms = np.array(v.get_feature_names_out())
        overlap = np.minimum(X[0], X[1])
        top = terms[np.argsort(-overlap)[:10]]
        print(f"\n4) Termos/temas em comum (abstracts): {list(top)}")
except Exception as e:
    print("   (termos indisponíveis:", e, ")")

print("\nLeitura: sem coautores em comum, a topologia não alcança esse par; a recomendação vem")
print("da AFINIDADE TEMÁTICA (texto) — é o mecanismo que sustenta os ganhos em cool/cold.")
