"""ABLAÇÃO DAS CAMADAS + peso de uso de cada modalidade (gaps #1 fusão por atenção, #2 GAT).

Sobre a base IA (KG T0 = data/processed/hetero_T0_ai.pt), avalia por Recall@K (via GNNReranker,
candidatos 2-hop) e mede QUANTO o modelo usa cada camada:

  (A) Encoder estrutural: GNN-SAGE vs GNN-GAT (gap #2).
  (B) Ablação de componentes: só-texto (SciBERT) · só-grafo (GNN) · FUSÃO COM PORTÃO.
  (C) Portão α por autor e por regime (gap #1): α = peso do ramo TEXTUAL na fusão.
      Esperado: α↑ do warm ao cold (a estrutura desaparece → o modelo passa a usar o texto).

Checkpoint incremental em runs/ablation/ablation.json (não perder treino se o job morrer).
Uso: PYTHONHASHSEED=0 python scripts/ablation_layers.py
"""
import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.transforms import ToUndirected

from coauthor_rec.config import load_config, resolve, set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.gnn.features import attach_text_features
from coauthor_rec.gnn.model import train_link_predictor, _device
from coauthor_rec.models.gnn_rec import GNNReranker
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.eval.regimes import classify_authors
from coauthor_rec.text.embed import author_embeddings

KS = [10, 50, 200]
HID, EPOCHS = 64, 60          # épocas moderadas: ablação é comparação relativa (kill-safe)
EVAL = load_config("eval"); set_seed(EVAL["seed"]); CAP = EVAL["graph"]["max_coauthors_per_work"]
WARM, COOL = EVAL["regimes"]["warm_min_coauthors"], EVAL["regimes"]["cool_min_coauthors"]
OUT = resolve("runs/ablation"); os.makedirs(OUT, exist_ok=True)
RESULTS = {"config": {"hidden": HID, "epochs": EPOCHS, "k": KS}, "models": {}, "gate": {}}


def save():
    with open(OUT / "ablation.json", "w") as fh:
        json.dump(RESULTS, fh, indent=2, ensure_ascii=False)


# ---------- dados ----------
merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
tr, te = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=CAP)
t0 = set(tr["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}

blob = torch.load(resolve("data/processed/hetero_T0_ai.pt"), weights_only=False)
data, maps = blob["data"], blob["maps"]
data, dims = attach_text_features(data, maps, tr, resolve("data/processed/text_emb/scibert.npz"))
co = data["author", "co_author", "author"].edge_index
pos = co[:, co[0] < co[1]]
data = ToUndirected()(data)
amap = maps["author"]                       # author_id -> índice (ordem do grafo)
N = len(amap)
print(f"[dados] {N} autores, {pos.size(1)} arestas T0, {len(gt)} alvos, feat autor={dims['author_dim']}")


def eval_emb(name, z, index):
    rr = GNNReranker(z, index, max_coauthors_per_work=CAP, name=name).fit(tr)
    r = evaluate_models([rr], gt, tg, k_values=KS, warm_min=WARM, cool_min=COOL,
                        t0_authors=t0, show_progress=False)[name]
    RESULTS["models"][name] = {"overall": r["overall"], "by_regime": r["by_regime"]}
    save()
    print(f"  {name:<22} R@10={r['overall'][10]['R']*100:5.2f}  R@50={r['overall'][50]['R']*100:5.2f}  "
          f"R@200={r['overall'][200]['R']*100:5.2f}")
    return r


# ---------- (A) encoder estrutural: SAGE vs GAT ----------
print("\n[A] Encoder estrutural (só-grafo):")
z_sage = train_link_predictor(data, pos, hidden=HID, layers=2, epochs=EPOCHS,
                              seed=EVAL["seed"], conv_type="sage", hard_negatives=False, device="cpu", log=print)
eval_emb("GNN-SAGE (grafo)", z_sage, amap)
z_gat = train_link_predictor(data, pos, hidden=HID, layers=2, epochs=EPOCHS,
                             seed=EVAL["seed"], conv_type="gat", hard_negatives=False, device="cpu", log=print)
eval_emb("GNN-GAT (grafo)", z_gat, amap)

# ---------- (B) só-texto ----------
print("\n[B] Componentes:")
sci = np.load(resolve("data/processed/text_emb/scibert.npz"), allow_pickle=True)
z_text_a, taidx = author_embeddings(tr, sci["emb"], list(sci["work_ids"]))
eval_emb("Texto (SciBERT)", z_text_a, taidx)

# alinha z_text à ordem do grafo (amap); autores sem texto -> zero
dt = z_text_a.shape[1]
Zt = np.zeros((N, dt), dtype=np.float32)
for aid, gi in amap.items():
    ti = taidx.get(aid)
    if ti is not None:
        Zt[gi] = z_text_a[ti]
Zg = z_sage.astype(np.float32)               # camada-grafo = melhor encoder (SAGE)


# ---------- (C) fusão com portão (α por autor) ----------
class GatedFusion(nn.Module):
    """Funde duas camadas já embutidas: z = α·Pt(Zt) + (1−α)·Pg(Zg), α=σ(gate([Zt,Zg]))."""
    def __init__(self, dt, dg, d=64):
        super().__init__()
        self.lnt, self.lng = nn.LayerNorm(dt), nn.LayerNorm(dg)
        self.pt, self.pg = nn.Linear(dt, d), nn.Linear(dg, d)
        self.gate = nn.Linear(dt + dg, 1)

    def forward(self, Zt, Zg):
        t, g = self.lnt(Zt), self.lng(Zg)
        a = torch.sigmoid(self.gate(torch.cat([t, g], 1)))
        return a * self.pt(t) + (1 - a) * self.pg(g), a.squeeze(-1)


def train_gated(Zt, Zg, pos, epochs=250, seed=42):
    dev = "cpu"
    torch.manual_seed(seed); g = torch.Generator().manual_seed(seed)
    Zt = torch.tensor(Zt, device=dev); Zg = torch.tensor(Zg, device=dev)
    P = pos.to(dev); n = Zt.size(0)
    model = GatedFusion(Zt.size(1), Zg.size(1)).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)
    for ep in range(epochs):
        model.train(); opt.zero_grad()
        z, _ = model(Zt, Zg)
        neg = torch.randint(0, n, (2, P.size(1)), generator=g).to(dev)   # negativos aleatórios
        s = torch.cat([(z[P[0]] * z[P[1]]).sum(-1), (z[neg[0]] * z[neg[1]]).sum(-1)])
        y = torch.cat([torch.ones(P.size(1), device=dev), torch.zeros(P.size(1), device=dev)])
        F.binary_cross_entropy_with_logits(s, y).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    model.eval()
    with torch.no_grad():
        z, a = model(Zt, Zg)
    return z.cpu().numpy(), a.cpu().numpy()


print("\n[C] Fusão com portão (texto ⊕ grafo):")
z_fus, alpha = train_gated(Zt, Zg, pos, seed=EVAL["seed"])
eval_emb("Fusão-portão", z_fus, amap)

# α por regime — o peso de USO de cada camada
targets = list(gt.keys())
reg_of = classify_authors(tg, targets, WARM, COOL, t0)
by = {}
for a in targets:
    by.setdefault(reg_of[a], []).append(float(alpha[amap[a]]))
RESULTS["gate"] = {"alpha_mean_overall": float(np.mean([alpha[amap[a]] for a in targets])),
                   "alpha_by_regime": {r: float(np.mean(v)) for r, v in by.items() if v},
                   "note": "alpha = peso do ramo TEXTUAL (1-alpha = grafo)"}
save()

print("\n=== PESO DE USO DE CADA CAMADA (α do portão) ===")
print(f"  média geral: texto={RESULTS['gate']['alpha_mean_overall']:.3f}  "
      f"grafo={1-RESULTS['gate']['alpha_mean_overall']:.3f}")
for r in ("warm", "cool", "cold"):
    if r in RESULTS["gate"]["alpha_by_regime"]:
        at = RESULTS["gate"]["alpha_by_regime"][r]
        print(f"  {r:<5} texto={at:.3f}  grafo={1-at:.3f}")
print("\nLeitura: α cresce do warm ao cold ⇒ sem estrutura, o modelo passa a se apoiar no texto.")
print(f"Artefato: {OUT/'ablation.json'}")
