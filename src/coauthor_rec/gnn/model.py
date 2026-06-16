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


def _adj_from_edges(pos_edge_index, n):
    """Lista de adjacência (índices) a partir de pares i<j (autor-autor, simétrica)."""
    adj = [set() for _ in range(n)]
    u, v = pos_edge_index
    for a, b in zip(u.tolist(), v.tolist()):
        adj[a].add(b); adj[b].add(a)
    return adj


def sample_hard_negatives(adj, n_samples, rng):
    """Negativos difíceis: pares a 2 saltos sem aresta direta (como no Híbrido RF)."""
    keys = [i for i, s in enumerate(adj) if s]
    src, dst = [], []
    tries = 0
    while len(src) < n_samples and tries < n_samples * 50 and keys:
        tries += 1
        u = rng.choice(keys)
        nb = rng.choice(tuple(adj[u]))
        nn = adj[nb]
        if not nn:
            continue
        w = rng.choice(tuple(nn))
        if w != u and w not in adj[u]:
            src.append(u); dst.append(w)
    return src, dst


def train_link_predictor(data, pos_edge_index, hidden=128, layers=2, epochs=300,
                         lr=0.005, weight_decay=5e-4, seed=42, device=None,
                         hard_negatives=True, val_fraction=0.1, patience=30, log=print):
    """Treina o encoder por predição de link nas arestas CO_AUTHOR de T0.

    Melhorias: negativos difíceis (2 saltos), split de arestas treino/validação e
    early-stopping pela loss de validação. Retorna embeddings de autor (numpy).
    """
    import numpy as np
    from torch_geometric.utils import negative_sampling

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    dev = device or _device()
    data = data.to(dev)
    n_authors = data["author"].num_nodes

    # split de arestas positivas T0: treino / validação (early stopping)
    pos = pos_edge_index
    perm = torch.randperm(pos.size(1), generator=torch.Generator().manual_seed(seed))
    n_val = int(pos.size(1) * val_fraction)
    val_pos = pos[:, perm[:n_val]].to(dev)
    train_pos = pos[:, perm[n_val:]].to(dev)
    use_val = val_pos.size(1) > 0  # grafos minúsculos podem não ter aresta de validação

    # pool de hard negatives PRECOMPUTADO uma vez (não por época — evita loop Python lento).
    neg_pool = None
    if hard_negatives:
        adj = _adj_from_edges(train_pos.cpu(), n_authors)
        n_pool = int(train_pos.size(1) * 1.5)
        s, d = sample_hard_negatives(adj, n_pool, rng)
        if len(s) >= train_pos.size(1) * 0.5:
            neg_pool = torch.tensor([s, d], dtype=torch.long, device=dev)

    def make_negs(n):
        if n <= 0:
            return torch.empty((2, 0), dtype=torch.long, device=dev)
        if neg_pool is not None:  # amostra barata do pool
            cols = torch.randint(neg_pool.size(1), (n,), device=dev)
            return neg_pool[:, cols]
        return negative_sampling(train_pos, num_nodes=n_authors, num_neg_samples=n).to(dev)

    val_neg = make_negs(val_pos.size(1)) if use_val else None
    model = HeteroEncoder(data, hidden=hidden, layers=layers).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    def loss_on(z, p, ne):
        s = torch.cat([_score(z, p), _score(z, ne)])
        y = torch.cat([torch.ones(p.size(1), device=dev), torch.zeros(ne.size(1), device=dev)])
        return F.binary_cross_entropy_with_logits(s, y)

    best_val, best_state, bad = float("inf"), None, 0
    for ep in range(1, epochs + 1):
        model.train(); opt.zero_grad()
        z = model(data)
        loss = loss_on(z, train_pos, make_negs(train_pos.size(1)))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if use_val:
            model.eval()
            with torch.no_grad():
                vloss = loss_on(model(data), val_pos, val_neg).item()
        else:
            vloss = loss.item()  # sem aresta de validação: monitora a própria loss
        if vloss < best_val - 1e-4:
            best_val, best_state, bad = vloss, {k: v.detach().cpu().clone()
                                                for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
        if ep % max(1, epochs // 12) == 0 or ep == 1:
            log(f"  época {ep:>3}/{epochs}  treino={loss.item():.4f}  val={vloss:.4f}  best={best_val:.4f}")
        if bad >= patience:
            log(f"  early-stopping em {ep} (sem melhora há {patience} épocas)")
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        return model.to(dev)(data).cpu().numpy()
