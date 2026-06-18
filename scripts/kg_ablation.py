"""Ablação da KG: a riqueza heterogênea ajuda a GNN, ou basta a co-autoria?
Treina duas GNNs (mesmas épocas/seed) — (A) KG completo (6 relações) e (B) só co-autoria —
e compara o GNN-rerank por regime. Uso: PYTHONHASHSEED=0 python scripts/kg_ablation.py
"""
import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData
from torch_geometric.transforms import ToUndirected

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.gnn.features import attach_text_features
from coauthor_rec.gnn.model import train_link_predictor
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.eval.evaluate import evaluate_models

EPOCHS = 150
EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
KS = EVAL["evaluation"]["k_values"]; SEED = EVAL["seed"]
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
works_raw = pd.read_csv(resolve("data/raw_ai/works.csv"))
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])

full, maps = build_hetero_data(merged, works_raw, work_ids=set(tr["work_id"]), max_coauthors_per_work=CAP)
full, _ = attach_text_features(full, maps, tr, resolve("data/processed/text_emb/scibert.npz"))
author_map = maps["author"]
co = full["author", "co_author", "author"].edge_index
pos = co[:, co[0] < co[1]]

# (B) grafo reduzido: só autores (com features) + co_autoria
red = HeteroData()
red["author"].x = full["author"].x
red["author"].num_nodes = full["author"].num_nodes
red["author", "co_author", "author"].edge_index = co
red["author", "co_author", "author"].edge_attr = full["author", "co_author", "author"].edge_attr

out = resolve("runs/ablation"); out.mkdir(parents=True, exist_ok=True)
# (A) KG completo: reaproveita a GNN já treinada na base IA (runs/gnn, mesmas features).
emb_full = np.load(resolve("runs/gnn/author_emb_scibert.npy"))
assert emb_full.shape[0] == len(author_map), "emb full desalinhado — rode gnn-run antes"
# (B) só co-autoria: treina UMA GNN (rápido, evita kill), salva, e avalia.
print(f"[ablação] (A) KG completo reaproveitado; treinando (B) só co-autoria ({EPOCHS} épocas)…")
emb_co = train_link_predictor(ToUndirected()(red), pos, epochs=EPOCHS, seed=SEED)
np.save(out / "emb_coauthor.npy", emb_co)

recs = {
    "GNN (KG completo)": GNNReranker(emb_full, author_map, name="GNN (KG completo)").fit(tr),
    "GNN (só co-autoria)": GNNReranker(emb_co, author_map, name="GNN (só co-autoria)").fit(tr),
}
res = evaluate_models(list(recs.values()), gt, train_graph, k_values=KS, t0_authors=t0,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"], show_progress=False)
print(f"\n{'modelo':>22} | {'warm R@200':>11} {'cool R@200':>11} {'overall R@50':>13}")
print("-" * 64)
for name in recs:
    by = res[name]["by_regime"]
    print(f"{name:>22} | {by['warm'][200]['R']*100:>10.2f}% {by['cool'][200]['R']*100:>10.2f}% "
          f"{res[name]['overall'][50]['R']*100:>12.2f}%")
print("\nSe (KG completo) ≈ (só co-autoria), as relações heterogêneas extras não ajudam a GNN.")
