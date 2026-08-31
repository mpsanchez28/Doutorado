"""T3 — Sensibilidade ao TETO de coautores por artigo (banca: "20 em vez de 50?").

Re-avalia Baseline (2-hop), Híbrido RF e 2 etapas na base IA com
max_coauthors_per_work ∈ {10, 20, 50, ∞}, reportando: (a) nº de arestas de coautoria
removidas por cada teto e (b) o efeito em Recall@K. Se as métricas mudam pouco, o teto de
50 é justificável (base IA tem ~6,6 autores/artigo). Determinístico (PYTHONHASHSEED=0).
Uso: PYTHONHASHSEED=0 python scripts/sens_cap.py
Saída: runs/sens_cap/sens_cap.json + tabela.
"""
import json
import os

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.text.embed import author_embeddings
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.two_stage import TwoStageReranker

CAPS = [10, 20, 50, None]          # None = ∞ (sem teto)
KS = [10, 50, 200]
EVAL = load_config("eval"); set_seed(EVAL["seed"])
WARM, COOL = EVAL["regimes"]["warm_min_coauthors"], EVAL["regimes"]["cool_min_coauthors"]

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
t0 = set(tr["author_id"])
text_auth, aidx = author_embeddings(tr, blob["emb"], list(blob["work_ids"]))


def n_edges(tg):
    return sum(len(v) for v in tg.values()) // 2   # pares de coautoria (simétrico)


LBL = {"Topology (Graph Coauthor)": "Baseline", "Hybrid (Graph + RandomForest)": "Híbrido RF",
       "2-stage (RF→texto)": "2 etapas"}
os.makedirs(resolve("runs/sens_cap"), exist_ok=True)
# Resumível: carrega o que já foi calculado e pula (o ambiente mata jobs longos).
jpath = resolve("runs/sens_cap/sens_cap.json")
out = json.loads(jpath.read_text()) if jpath.exists() else {"caps": [], "results": {}}
print(f"{'cap':>5} {'arestas':>9} {'modelo':<12} {'R@10':>7} {'R@50':>7} {'R@200':>7}")
for cap in CAPS:
    ckey = "inf" if cap is None else str(cap)
    if ckey in out["results"]:            # já calculado numa execução anterior
        continue
    tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=cap)
    gt = {a: v for a, v in gt.items() if a in t0}
    ne = n_edges(tg)
    models = [
        TopologyRecommender(max_coauthors_per_work=cap).fit(tr),
        HybridCoauthorRecommender(max_coauthors_per_work=cap).fit(tr),
        TwoStageReranker(text_auth, aidx, max_coauthors_per_work=cap, m_text=100).fit(tr),
    ]
    res = evaluate_models(models, gt, tg, k_values=KS, warm_min=WARM, cool_min=COOL,
                          t0_authors=t0, show_progress=False)
    out["caps"].append(ckey)
    out["results"][ckey] = {"n_coauthor_edges": ne, "n_targets": len(gt),
                            "models": {m: {"overall": res[m]["overall"]} for m in res}}
    with open(resolve("runs/sens_cap/sens_cap.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    for m in res:
        o = res[m]["overall"]
        print(f"{ckey:>5} {ne:>9} {LBL[m]:<12} {o[10]['R']*100:6.2f}% {o[50]['R']*100:6.2f}% {o[200]['R']*100:6.2f}%")
    print()

print("Leitura: se Recall varia pouco entre 20/50/∞, o teto de 50 não distorce os resultados")
print("(base IA ~6,6 autores/artigo; poucos artigos ultrapassam o teto). Artefato: runs/sens_cap/sens_cap.json")
