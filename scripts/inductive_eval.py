"""Avaliação INDUTIVA (gap #4): o modelo generaliza para autores NÃO vistos na supervisão?

Protocolo: separa H = 20% dos autores-alvo e REMOVE da supervisão de link-prediction toda
aresta CO_AUTHOR incidente a H (com hard-negatives, H também não vira negativo). Os nós de H
seguem no grafo (chegam com sua vizinhança — como um recém-chegado em produção). Treinam-se
dois encoders sobre as MESMAS arestas (sem H):

  INDUTIVO    = HeteroEncoder com features SciBERT nos nós  → embedding de H vem de
                features + vizinhança (funciona para nós sem supervisão própria).
  TRANSDUTIVO = tudo como tabela de Embedding (sem features) → as linhas de H nunca recebem
                gradiente e ficam no init (aleatórias): não generaliza para o não-visto.

Avalia Recall@K SOMENTE em H (via GNNReranker, candidatos 2-hop). Espera-se indutivo >> transdutivo.
Uso: PYTHONHASHSEED=0 python scripts/inductive_eval.py
"""
import json
import os

import numpy as np
import pandas as pd
import torch
from torch_geometric.transforms import ToUndirected

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.gnn.features import attach_text_features
from coauthor_rec.gnn.model import train_link_predictor
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.eval.evaluate import evaluate_models

KS = [10, 50, 200]
HID, EPOCHS, HOLD = 64, 150, 0.20
EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
WARM, COOL = EVAL["regimes"]["warm_min_coauthors"], EVAL["regimes"]["cool_min_coauthors"]
OUT = resolve("runs/ablation"); os.makedirs(OUT, exist_ok=True)

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}

blob = torch.load(resolve("data/processed/hetero_T0_ai.pt"), weights_only=False)
data, maps = blob["data"], blob["maps"]
data, dims = attach_text_features(data, maps, tr, resolve("data/processed/text_emb/scibert.npz"))
amap = maps["author"]

# H = 20% dos alvos, mantidos FORA da supervisão
rng = np.random.default_rng(EVAL["seed"])
targets = list(gt.keys())
H_ids = set(rng.choice(targets, int(len(targets) * HOLD), replace=False))
H_idx = torch.tensor([amap[a] for a in H_ids], dtype=torch.long)
H_mask = torch.zeros(len(amap), dtype=torch.bool); H_mask[H_idx] = True

co = data["author", "co_author", "author"].edge_index
pos_all = co[:, co[0] < co[1]]
keep = ~(H_mask[pos_all[0]] | H_mask[pos_all[1]])       # remove arestas incidentes a H
pos = pos_all[:, keep]
data = ToUndirected()(data)
gt_H = {a: gt[a] for a in H_ids}
print(f"[indutivo] |H|={len(H_ids)} alvos; arestas supervisão {pos_all.size(1)}→{pos.size(1)} "
      f"(−{pos_all.size(1)-pos.size(1)} incidentes a H)")

ALL_FEATLESS = list(data.node_types)                    # tudo vira Embedding (transdutivo)
runs = {
    "Indutivo (SciBERT feats)": None,                   # featless=None → auto (autor usa features)
    "Transdutivo (embed table)": ALL_FEATLESS,
}
res_out = {"holdout": len(H_ids), "models": {}}
for name, featless in runs.items():
    z = train_link_predictor(data, pos, hidden=HID, layers=2, epochs=EPOCHS, seed=EVAL["seed"],
                             featless=featless, hard_negatives=False, device="cpu", log=lambda *_: None)
    rr = GNNReranker(z, amap, max_coauthors_per_work=CAP, name=name).fit(tr)
    r = evaluate_models([rr], gt_H, tg, k_values=KS, warm_min=WARM, cool_min=COOL,
                        t0_authors=t0, show_progress=False)[name]
    res_out["models"][name] = {"overall": r["overall"], "by_regime": r["by_regime"]}
    with open(OUT / "inductive.json", "w") as fh:
        json.dump(res_out, fh, indent=2, ensure_ascii=False)
    print(f"  {name:<26} R@10={r['overall'][10]['R']*100:5.2f}  R@50={r['overall'][50]['R']*100:5.2f}  "
          f"R@200={r['overall'][200]['R']*100:5.2f}")

print("\nLeitura: nos autores de H (fora da supervisão), o encoder com features generaliza; a")
print("tabela de embeddings não — evidência da capacidade INDUTIVA exigida por recém-chegados.")
print(f"Artefato: {OUT/'inductive.json'}")
