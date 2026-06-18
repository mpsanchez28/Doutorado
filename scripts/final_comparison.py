"""Comparação final consistente de todos os modelos sob o mesmo protocolo.

Roda com PYTHONHASHSEED fixo (reprodutível). Avalia todos os modelos numa única passada
(overall + por regime) com as métricas da tese (Precision/Recall/F1/NDCG/MRR/MAP@K) e salva
runs/final_comparison.json para a tabela e o gráfico. Uso:
    PYTHONHASHSEED=0 python scripts/final_comparison.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.oracle import IdealTopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.models.hybrid_cand import HybridReranker
from coauthor_rec.models.supervised_hybrid import SupervisedHybridReranker

print("PYTHONHASHSEED =", os.environ.get("PYTHONHASHSEED", "(não fixado!)"))
EVAL = load_config("eval")
set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]
KS = EVAL["evaluation"]["k_values"]

WORKS_RAW = os.environ.get("WORKS_RAW", "data/raw/works.csv")
T0ACTIVE = "t0active" in sys.argv  # restringe aos autores ativos em T0 (exclui newcomers)
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
works_raw = pd.read_csv(resolve(WORKS_RAW))
train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
t0 = set(train_df["author_id"])
if T0ACTIVE:
    gt = {a: v for a, v in gt.items() if a in t0}
    print(f"[t0active] avaliando só autores ativos em T0: {len(gt)} alvos")
data, maps = build_hetero_data(merged, works_raw, work_ids=set(train_df["work_id"]),
                               max_coauthors_per_work=CAP)
author_map, paper_map = maps["author"], maps["paper"]

# embedding textual de autor (SciBERT) alinhado ao author_map
blob = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
emb, cpos = blob["emb"], {w: i for i, w in enumerate(blob["work_ids"])}
d = emb.shape[1]
ptext = np.zeros((len(paper_map), d), np.float32)
for wid, i in paper_map.items():
    if wid in cpos:
        ptext[i] = emb[cpos[wid]]
text_auth = np.zeros((len(author_map), d), np.float32)
cnt = np.zeros(len(author_map), np.float32)
for aid, wid in zip(train_df["author_id"], train_df["work_id"]):
    if aid in author_map and wid in paper_map:
        text_auth[author_map[aid]] += ptext[paper_map[wid]]; cnt[author_map[aid]] += 1
text_auth /= np.clip(cnt, 1.0, None)[:, None]
gnn_emb = np.load(resolve("runs/gnn/author_emb_scibert.npy"))

print("Construindo modelos…")
base = TopologyRecommender(max_coauthors_per_work=CAP).fit(train_df)
models = [
    base,
    IdealTopologyRecommender(base, gt).fit(train_df),
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(train_df),
    TextSimilarityRecommender(text_auth, author_map, name="Text (SciBERT)"),
    GNNReranker(gnn_emb, author_map, name="GNN-rerank").fit(train_df),
    HybridReranker(text_auth, author_map, text_emb=text_auth, m_text=100,
                   max_coauthors_per_work=CAP, name="Hybrid-cand").fit(train_df),
    SupervisedHybridReranker(author_map, text_auth, gnn_emb=gnn_emb, m_text=100,
                             max_coauthors_per_work=CAP, name="Sup-Hybrid").fit(train_df),
]
# Fusão CNN+GNN: usa os embeddings fundidos já treinados (fusion-run), ranqueados em 2-hop
_fus = resolve("runs/fusion/author_emb_scibert.npy")
if _fus.exists():
    fus_emb = np.load(_fus)
    if fus_emb.shape[0] == len(author_map):
        models.append(GNNReranker(fus_emb, author_map, name="Fusion (CNN+GNN)").fit(train_df))
print("Avaliando (uma passada, estratificada)…")
res = evaluate_models(models, gt, train_graph, k_values=KS,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"],
                      t0_authors=t0, show_progress=False)

# ----- ICs bootstrap por métrica (overall + warm + cool) -----
from coauthor_rec.eval.stats import bootstrap_metric_cis
NB = EVAL["statistics"]["n_bootstrap"]
print(f"Calculando ICs bootstrap ({NB} reamostragens)…")
out = {}
for m in res:
    ci_overall = bootstrap_metric_cis(res[m]["per_author"], KS, n_boot=NB, seed=EVAL["seed"])
    ci_regime = {r: bootstrap_metric_cis(res[m]["per_author_by_regime"][r], KS, n_boot=NB,
                                         seed=EVAL["seed"]) for r in ("warm", "cool")}
    out[m] = {"overall": res[m]["overall"], "by_regime": res[m]["by_regime"],
              "regime_counts": res[m]["regime_counts"],
              "overall_ci": ci_overall, "by_regime_ci": ci_regime}
resolve("runs/final_comparison.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

# ----- tabela markdown com IC (mean [lo–hi]) -----
LBL = {"Topology (Graph Coauthor)": "Baseline (CN)", "Ideal Topology (Oracle)": "Oráculo (teto)",
       "Hybrid (Graph + RandomForest)": "Híbrido RF", "Text (SciBERT)": "Texto (SciBERT)",
       "GNN-rerank": "GNN-rerank", "Hybrid-cand": "Cand. híbridos", "Sup-Hybrid": "Sup-Hybrid", "Fusion (CNN+GNN)": "Fusão (CNN+GNN)"}
METRICS = [("P", "Precision"), ("R", "Recall"), ("F1", "F1"),
           ("NDCG", "NDCG"), ("MRR", "MRR"), ("MAP", "MAP")]
counts = res[models[0].name]["regime_counts"]
md = ["# Tabela de Métricas com IC bootstrap (95%) — PYTHONHASHSEED=0", "",
      f"Bootstrap: {NB} reamostragens de autores (§4.6.3). Células: **média [IC95%]**, em %.",
      f"Corpus T0: warm={counts['warm']} · cool={counts['cool']} · cold={counts['cold']} · "
      f"newcomer={counts['newcomer']}.", ""]


def cell(model, scope, mk, k):
    if scope == "overall":
        mean = out[model]["overall"][k][mk]; ci = out[model]["overall_ci"][k][mk]
    else:
        mean = out[model]["by_regime"][scope][k][mk]; ci = out[model]["by_regime_ci"][scope][k][mk]
    return f"{mean*100:.2f} [{ci[0]*100:.2f}–{ci[1]*100:.2f}]"


for scope, title in [("overall", "Geral"), ("warm", "Warm"), ("cool", "Cool")]:
    n = sum(counts.values()) if scope == "overall" else counts[scope]
    md.append(f"## {title} (n={n})")
    for mk, mlabel in METRICS:
        md.append(f"\n### {mlabel}@K")
        md.append("| Modelo | " + " | ".join(f"@{k}" for k in KS) + " |")
        md.append("|" + "---|" * (len(KS) + 1))
        for m in res:
            md.append(f"| {LBL.get(m, m)} | " + " | ".join(cell(m, scope, mk, k) for k in KS) + " |")
    md.append("")
md += ["## Gráficos (com barras de erro = IC95%)", "",
       "- ![Métricas — geral](metricas_overall.png)", "- ![Métricas — cool](metricas_cool.png)", ""]
resolve("docs/TABELA_METRICAS.md").write_text("\n".join(md), encoding="utf-8")

# resumo no console (Recall com IC)
for scope in ["overall", "warm", "cool"]:
    print(f"\n== Recall@K (%) [IC95%] — {scope} ==")
    for m in res:
        print("  " + LBL.get(m, m).ljust(16) + " | ".join(cell(m, scope, "R", k) for k in (10, 200)))
print("\n-> runs/final_comparison.json + docs/TABELA_METRICAS.md")
