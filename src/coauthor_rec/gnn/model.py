"""GNN heterogênea para predição de coautoria (§4.4.2).

Encoder: projeção por tipo de nó (Linear p/ author/paper com features; Embedding aprendível
p/ institution/venue/concept) seguida de camadas HeteroConv(SAGEConv) sobre todas as relações
(incluindo as reversas, via ToUndirected) — assim o autor agrega texto dos seus artigos,
coautores, instituições, conceitos e venues. Predição de link por produto interno dos
embeddings de autor. Treino self-supervised nas arestas CO_AUTHOR de T0 (sem vazamento de T1).
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn


def _device():
    return "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


class HeteroEncoder(nn.Module):
    def __init__(self, data, hidden: int = 128, layers: int = 2, dropout: float = 0.2,
                 featless=("institution", "venue", "concept")):
        super().__init__()
        from torch_geometric.nn import HeteroConv, SAGEConv

        self.hidden = hidden
        self.dropout = dropout
        self.featless = set(featless)
        # projeções de entrada por tipo de nó + LayerNorm (estabiliza escalas heterogêneas)
        self.proj = nn.ModuleDict()
        self.emb = nn.ModuleDict()
        self.in_norm = nn.ModuleDict()
        for nt in data.node_types:
            if nt in self.featless:
                self.emb[nt] = nn.Embedding(data[nt].num_nodes, hidden)
            else:
                self.proj[nt] = nn.Linear(data[nt].x.size(1), hidden)
            self.in_norm[nt] = nn.LayerNorm(hidden)

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(layers):
            # aggr="mean": essencial com hubs de alto grau (sum explodiria as ativações)
            self.convs.append(HeteroConv(
                {et: SAGEConv((-1, -1), hidden) for et in data.edge_types}, aggr="mean"))
            self.norms.append(nn.ModuleDict({nt: nn.LayerNorm(hidden) for nt in data.node_types}))

    def forward(self, data):
        x = {}
        for nt in data.node_types:
            if nt in self.featless:
                idx = torch.arange(data[nt].num_nodes, device=self.emb[nt].weight.device)
                h = self.emb[nt](idx)
            else:
                h = self.proj[nt](data[nt].x)
            x[nt] = self.in_norm[nt](h)
        for conv, norm in zip(self.convs, self.norms):
            x = conv(x, data.edge_index_dict)
            x = {k: F.dropout(F.relu(norm[k](v)), p=self.dropout, training=self.training)
                 for k, v in x.items()}
        return x["author"]


def _score(z, edge_index):
    return (z[edge_index[0]] * z[edge_index[1]]).sum(-1)


def train_link_predictor(data, pos_edge_index, hidden=128, layers=2, epochs=100,
                         lr=0.005, weight_decay=5e-4, seed=42, device=None, log=print):
    """Treina o encoder por predição de link nas arestas CO_AUTHOR de T0.

    ``pos_edge_index``: pares (i<j) de coautoria em T0 (autor->autor). Retorna embeddings
    finais de autor (numpy [n_authors, hidden]).
    """
    from torch_geometric.utils import negative_sampling

    torch.manual_seed(seed)
    dev = device or _device()
    data = data.to(dev)
    pos = pos_edge_index.to(dev)
    n_authors = data["author"].num_nodes

    model = HeteroEncoder(data, hidden=hidden, layers=layers).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    model.train()
    for ep in range(1, epochs + 1):
        opt.zero_grad()
        z = model(data)
        neg = negative_sampling(pos, num_nodes=n_authors, num_neg_samples=pos.size(1))
        pos_score = _score(z, pos)
        neg_score = _score(z, neg)
        scores = torch.cat([pos_score, neg_score])
        labels = torch.cat([torch.ones_like(pos_score), torch.zeros_like(neg_score)])
        loss = F.binary_cross_entropy_with_logits(scores, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)  # evita explosão
        opt.step()
        if ep % max(1, epochs // 10) == 0 or ep == 1:
            log(f"  época {ep:>3}/{epochs}  loss={loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        z = model(data).cpu().numpy()
    return z
