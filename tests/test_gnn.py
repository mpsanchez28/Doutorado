"""Testes da GNN heterogênea (forward/treino curto em CPU, sem download)."""
import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch_geometric")

import torch
from torch_geometric.transforms import ToUndirected

from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.gnn.model import train_link_predictor
from coauthor_rec.models.gnn_rec import GNNRecommender


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


def test_gnn_train_and_recommend_cpu():
    data, maps = build_hetero_data(_corpus(), _works_raw())
    # injeta "texto" aleatório nas features de paper/author (mock, sem download)
    torch.manual_seed(0)
    for nt in ("paper", "author"):
        extra = torch.randn(data[nt].num_nodes, 8)
        data[nt].x = torch.cat([data[nt].x, extra], dim=1)

    co = data["author", "co_author", "author"].edge_index
    pos = co[:, co[0] < co[1]]
    data = ToUndirected()(data)

    z = train_link_predictor(data, pos, hidden=16, layers=2, epochs=5, device="cpu")
    assert z.shape == (len(maps["author"]), 16)
    assert np.isfinite(z).all()

    rec = GNNRecommender(z, maps["author"])
    out = rec.recommend("A1", top_n=2)
    assert "A1" not in out
    assert all(a in maps["author"] for a in out)
