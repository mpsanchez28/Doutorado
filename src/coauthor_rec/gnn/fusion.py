"""Fusão multimodal end-to-end CNN + GNN (§4.4.1–4.4.3, Eq. 10).

Branch textual: CNN 1D sobre os embeddings token-level (BERT/SciBERT, congelados) de cada
artigo → vetor textual do artigo → média sobre os artigos do autor → z_text(a).
Branch estrutural: GNN heterogênea sobre o KG → z_graph(a).
Fusão: z_a = Dense(LayerNorm(z_text) ⊕ LayerNorm(z_graph)).
Predição de link por produto interno de z_a; treino conjunto (CNN+GNN+Dense) por link
prediction nas arestas CO_AUTHOR de T0 (split treino/val, hard negatives, early stopping).
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from .model import HeteroEncoder, _device, _score, _adj_from_edges, sample_hard_negatives


class TextCNN(nn.Module):
    """Conv1d sobre a sequência de tokens (canais = dim do encoder) + max-pool no tempo."""
    def __init__(self, in_dim: int, out_dim: int = 128, kernel: int = 3, chunk: int = 1024):
        super().__init__()
        self.conv = nn.Conv1d(in_dim, out_dim, kernel, padding=kernel // 2)
        self.chunk = chunk

    def forward(self, tokens, mask):  # tokens [P,L,H] (fp16), mask [P,L]
        outs = []
        for i in range(0, tokens.size(0), self.chunk):
            t = tokens[i:i + self.chunk].float()
            m = mask[i:i + self.chunk].float().unsqueeze(-1)
            t = (t * m).transpose(1, 2)           # [c,H,L], zera posições de padding
            h = F.relu(self.conv(t))               # [c,out,L]
            outs.append(h.max(dim=2).values)       # max-pool no tempo -> [c,out]
        return torch.cat(outs, 0)


class FusionModel(nn.Module):
    def __init__(self, data, text_in: int, text_out: int = 128, hidden: int = 128,
                 gnn_layers: int = 2, out_dim: int = 128):
        super().__init__()
        self.cnn = TextCNN(text_in, text_out)
        self.gnn = HeteroEncoder(data, hidden=hidden, layers=gnn_layers)
        self.ln_text = nn.LayerNorm(text_out)
        self.ln_graph = nn.LayerNorm(hidden)
        self.fuse = nn.Linear(text_out + hidden, out_dim)

    def _z_text(self, tokens, mask, agg):
        author_idx, paper_idx, counts = agg
        paper_text = self.cnn(tokens, mask)              # [P, text_out]
        z_text = torch.zeros(counts.size(0), paper_text.size(1), device=paper_text.device)
        z_text.index_add_(0, author_idx, paper_text[paper_idx])  # soma por autor (MPS-friendly)
        return z_text / counts.clamp(min=1.0).unsqueeze(1)       # média

    def forward(self, data, tokens, mask, agg):
        z_text = self._z_text(tokens, mask, agg)
        z_graph = self.gnn(data)                         # [n_authors, hidden]
        return self.fuse(torch.cat([self.ln_text(z_text), self.ln_graph(z_graph)], dim=1))


class AttentionFusionModel(FusionModel):
    """Fusão por PORTÃO (gated attention): em vez de concatenar, aprende um peso α(a) ∈ (0,1)
    por autor sobre o ramo textual vs. o estrutural. z_a = α·Wt·z_text + (1−α)·Wg·z_graph.

    α é interpretável — mede quanto o modelo USA cada camada; lê-se por autor e por regime
    (esperado: α↑ no cold-start, onde a estrutura desaparece). Fecha o gap #1 e serve de
    ablação direta da contribuição de cada modalidade.
    """
    def __init__(self, data, text_in, text_out=128, hidden=128, gnn_layers=2, out_dim=128,
                 conv_type="sage"):
        super().__init__(data, text_in, text_out, hidden, gnn_layers, out_dim)
        self.gnn = HeteroEncoder(data, hidden=hidden, layers=gnn_layers, conv_type=conv_type)
        self.proj_text = nn.Linear(text_out, out_dim)
        self.proj_graph = nn.Linear(hidden, out_dim)
        self.gate = nn.Linear(text_out + hidden, 1)      # α = σ(gate([z_text, z_graph]))
        self.fuse = None                                 # não usa a cabeça de concatenação

    def _fuse(self, z_text, z_graph):
        t, g = self.ln_text(z_text), self.ln_graph(z_graph)
        alpha = torch.sigmoid(self.gate(torch.cat([t, g], dim=1)))   # [n_authors, 1]
        z = alpha * self.proj_text(t) + (1.0 - alpha) * self.proj_graph(g)
        return z, alpha

    def forward(self, data, tokens, mask, agg, return_gate=False):
        z_text = self._z_text(tokens, mask, agg)
        z_graph = self.gnn(data)
        z, alpha = self._fuse(z_text, z_graph)
        return (z, alpha) if return_gate else z


def build_author_paper_agg(author_idx, paper_idx, n_authors, n_papers, device):
    """Índices de agregação autor->artigos (substitui mm esparso, não suportado no MPS).

    Retorna (author_idx [E], paper_idx [E], counts [n_authors]) — usado por index_add_.
    """
    a = torch.tensor(author_idx, dtype=torch.long)
    p = torch.tensor(paper_idx, dtype=torch.long)
    counts = torch.zeros(n_authors)
    counts.index_add_(0, a, torch.ones(len(author_idx)))
    return a.to(device), p.to(device), counts.to(device)


def train_fusion(data, tokens, mask, agg, pos_edge_index, text_in, text_out=128, hidden=128,
                 out_dim=128, gnn_layers=2, epochs=300, lr=0.005, weight_decay=5e-4,
                 seed=42, device=None, hard_negatives=True, val_fraction=0.1, patience=30,
                 log=print, fusion="concat", conv_type="sage", return_gate=False):
    """Treina a fusão end-to-end. Retorna embeddings finais de autor (numpy).

    ``fusion``: "concat" (Eq. 10, padrão) ou "attention" (portão α por autor). Com
    ``return_gate=True`` e fusão por atenção, retorna (emb, alpha) — α ∈ (0,1) por autor,
    peso do ramo textual. ``conv_type``: "sage" ou "gat" no encoder estrutural.
    """
    import numpy as np
    from torch_geometric.utils import negative_sampling

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    dev = device or _device()
    data = data.to(dev)
    tokens, mask = tokens.to(dev), mask.to(dev)
    agg = tuple(t.to(dev) for t in agg)  # (author_idx, paper_idx, counts)
    n_authors = data["author"].num_nodes

    pos = pos_edge_index
    perm = torch.randperm(pos.size(1), generator=torch.Generator().manual_seed(seed))
    n_val = int(pos.size(1) * val_fraction)
    val_pos = pos[:, perm[:n_val]].to(dev)
    train_pos = pos[:, perm[n_val:]].to(dev)
    use_val = val_pos.size(1) > 0

    neg_pool = None
    if hard_negatives:
        adj = _adj_from_edges(train_pos.cpu(), n_authors)
        s, d = sample_hard_negatives(adj, int(train_pos.size(1) * 1.5), rng)
        if len(s) >= train_pos.size(1) * 0.5:
            neg_pool = torch.tensor([s, d], dtype=torch.long, device=dev)

    def make_negs(n):
        if n <= 0:
            return torch.empty((2, 0), dtype=torch.long, device=dev)
        if neg_pool is not None:
            return neg_pool[:, torch.randint(neg_pool.size(1), (n,), device=dev)]
        return negative_sampling(train_pos, num_nodes=n_authors, num_neg_samples=n).to(dev)

    val_neg = make_negs(val_pos.size(1)) if use_val else None
    if fusion == "attention":
        model = AttentionFusionModel(data, text_in=text_in, text_out=text_out, hidden=hidden,
                                     gnn_layers=gnn_layers, out_dim=out_dim, conv_type=conv_type).to(dev)
    else:
        model = FusionModel(data, text_in=text_in, text_out=text_out, hidden=hidden,
                            gnn_layers=gnn_layers, out_dim=out_dim).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    def loss_on(z, p, ne):
        s = torch.cat([_score(z, p), _score(z, ne)])
        y = torch.cat([torch.ones(p.size(1), device=dev), torch.zeros(ne.size(1), device=dev)])
        return F.binary_cross_entropy_with_logits(s, y)

    best_val, best_state, bad = float("inf"), None, 0
    for ep in range(1, epochs + 1):
        model.train(); opt.zero_grad()
        z = model(data, tokens, mask, agg)
        loss = loss_on(z, train_pos, make_negs(train_pos.size(1)))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if use_val:
            model.eval()
            with torch.no_grad():
                vloss = loss_on(model(data, tokens, mask, agg), val_pos, val_neg).item()
        else:
            vloss = loss.item()
        if vloss < best_val - 1e-4:
            best_val, bad = vloss, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
        if ep % max(1, epochs // 12) == 0 or ep == 1:
            log(f"  época {ep:>3}/{epochs}  treino={loss.item():.4f}  val={vloss:.4f}  best={best_val:.4f}")
        if bad >= patience:
            log(f"  early-stopping em {ep}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        if fusion == "attention" and return_gate:
            z, alpha = model(data, tokens, mask, agg, return_gate=True)
            return z.cpu().numpy(), alpha.squeeze(-1).cpu().numpy()
        return model(data, tokens, mask, agg).cpu().numpy()
