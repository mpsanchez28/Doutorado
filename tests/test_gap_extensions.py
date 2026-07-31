"""Testes das extensões (gaps #1 GAT, #2 fusão por atenção) — treino curto em CPU."""
import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch_geometric")

import torch
from torch_geometric.transforms import ToUndirected

from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.gnn.model import train_link_predictor
from coauthor_rec.gnn.fusion import train_fusion, build_author_paper_agg


def _corpus():
    rows = [
        ("W1", "A1", "[]", "2010-01-01"), ("W1", "A2", "[]", "2010-01-01"),
        ("W2", "A2", "[]", "2011-01-01"), ("W2", "A3", "[]", "2011-01-01"),
        ("W3", "A1", "[]", "2012-01-01"), ("W3", "A3", "[]", "2012-01-01"),
        ("W4", "A4", "[]", "2012-01-01"), ("W4", "A1", "[]", "2012-01-01"),
    ]
    return pd.DataFrame(rows, columns=["work_id", "author_id", "institution_ids", "publication_date"]) \
        .assign(title="t", abstract="a", language="en",
                publication_date=lambda d: pd.to_datetime(d["publication_date"]))


def _works_raw():
    c = lambda *p: json.dumps([{"id": i, "name": i, "score": s} for i, s in p])
    rows = [(w, "V1", c(("C1", 0.9)), json.dumps([]), 0) for w in ["W1", "W2", "W3", "W4"]]
    return pd.DataFrame(rows, columns=["id", "venue_id", "concepts", "referenced_works", "cited_by_count"])


def _graph_with_features():
    data, maps = build_hetero_data(_corpus(), _works_raw())
    torch.manual_seed(0)
    for nt in ("paper", "author"):
        data[nt].x = torch.cat([data[nt].x, torch.randn(data[nt].num_nodes, 8)], dim=1)
    co = data["author", "co_author", "author"].edge_index
    pos = co[:, co[0] < co[1]]
    return ToUndirected()(data), maps, pos


def test_gat_encoder_trains_cpu():
    data, maps, pos = _graph_with_features()
    z = train_link_predictor(data, pos, hidden=16, layers=2, epochs=5, device="cpu",
                             conv_type="gat")
    assert z.shape == (len(maps["author"]), 16)
    assert np.isfinite(z).all()


def test_attention_fusion_returns_gate_in_unit_interval():
    df = _corpus()
    data, maps = build_hetero_data(df, _works_raw())
    for nt in ("paper", "author"):
        data[nt].x = torch.cat([data[nt].x, torch.randn(data[nt].num_nodes, 4)], dim=1)
    P, L, H = len(maps["paper"]), 6, 16
    torch.manual_seed(0)
    tokens = torch.randn(P, L, H, dtype=torch.float16)
    mask = torch.ones(P, L, dtype=torch.uint8)
    ai, pi = [], []
    for aid, wid in zip(df["author_id"], df["work_id"]):
        ai.append(maps["author"][aid]); pi.append(maps["paper"][wid])
    agg = build_author_paper_agg(ai, pi, len(maps["author"]), P, torch.device("cpu"))
    co = data["author", "co_author", "author"].edge_index
    pos = co[:, co[0] < co[1]]
    data = ToUndirected()(data)

    z, alpha = train_fusion(data, tokens, mask, agg, pos, text_in=H, text_out=8, hidden=8,
                            out_dim=8, epochs=5, device="cpu", fusion="attention",
                            return_gate=True)
    n = len(maps["author"])
    assert z.shape == (n, 8)
    assert alpha.shape == (n,)
    assert ((alpha > 0) & (alpha < 1)).all()   # gate σ(·) estritamente em (0,1)
