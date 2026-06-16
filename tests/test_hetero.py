"""Testes da materialização do KG heterogêneo (graph/hetero.py)."""
import json

import pandas as pd
import pytest

pytest.importorskip("torch_geometric")

from coauthor_rec.graph.hetero import build_hetero_data, NODE_TYPES, EDGE_TYPES


def _corpus():
    rows = [
        # work W1: A1, A2 (instituição I1); W2: A2, A3; W3: A1, A3
        ("W1", "A1", '["I1"]', "2010-01-01"),
        ("W1", "A2", '["I1"]', "2010-01-01"),
        ("W2", "A2", "[]", "2011-01-01"),
        ("W2", "A3", '["I2"]', "2011-01-01"),
        ("W3", "A1", "[]", "2012-01-01"),
        ("W3", "A3", "[]", "2012-01-01"),
    ]
    return pd.DataFrame(rows, columns=["work_id", "author_id", "institution_ids", "publication_date"]) \
        .assign(title="t", abstract="a", language="en",
                publication_date=lambda d: pd.to_datetime(d["publication_date"]))


def _works_raw():
    def concepts(*pairs):
        return json.dumps([{"id": c, "name": c, "score": s} for c, s in pairs])
    rows = [
        ("W1", "V1", concepts(("C1", 0.9), ("C2", 0.2)), json.dumps([]), 5),
        ("W2", "V1", concepts(("C1", 0.5)), json.dumps(["W1"]), 2),  # W2 cita W1 (intra-corpus)
        ("W3", "V2", concepts(("C3", 0.8)), json.dumps(["W9"]), 0),  # W9 fora do corpus -> ignorado
    ]
    return pd.DataFrame(rows, columns=["id", "venue_id", "concepts", "referenced_works", "cited_by_count"])


def test_build_hetero_node_and_edge_types():
    data, maps = build_hetero_data(_corpus(), _works_raw())
    # todos os tipos de nó presentes
    for nt in NODE_TYPES:
        assert nt in data.node_types
    # contagens de nós
    assert len(maps["author"]) == 3        # A1,A2,A3
    assert len(maps["paper"]) == 3         # W1,W2,W3
    assert len(maps["institution"]) == 2   # I1,I2
    assert len(maps["venue"]) == 2         # V1,V2
    # C2 tem score 0.2 (<0.3) -> só C1 e C3 entram
    assert set(maps["concept"]) == {"C1", "C3"}


def test_build_hetero_edges():
    data, maps = build_hetero_data(_corpus(), _works_raw())
    # WRITES: 6 autorias
    assert data["author", "writes", "paper"].edge_index.size(1) == 6
    # CO_AUTHOR simétrica: 3 pares (A1-A2, A2-A3, A1-A3) -> 6 direções
    assert data["author", "co_author", "author"].edge_index.size(1) == 6
    assert data["author", "co_author", "author"].edge_attr.size(0) == 6
    # CITES intra-corpus: só W2->W1 (W3->W9 descartado)
    assert data["paper", "cites", "paper"].edge_index.size(1) == 1
    # HAS_TOPIC: W1->C1, W2->C1, W3->C3 = 3 (C2 abaixo do score)
    assert data["paper", "has_topic", "concept"].edge_index.size(1) == 3
    # features de author têm 3 dims
    assert data["author"].x.size(1) == 3


def test_coauthor_cap_removes_large_cliques():
    # work grande com 5 autores; cap=4 deve eliminar a clique desse work
    big = pd.DataFrame(
        [("WB", f"B{i}", "[]", "2010-01-01") for i in range(5)],
        columns=["work_id", "author_id", "institution_ids", "publication_date"],
    ).assign(title="t", abstract="a", language="en",
             publication_date=lambda d: pd.to_datetime(d["publication_date"]))
    raw = pd.DataFrame([("WB", "V1", json.dumps([]), json.dumps([]), 0)],
                       columns=["id", "venue_id", "concepts", "referenced_works", "cited_by_count"])
    sem = build_hetero_data(big, raw)[0]["author", "co_author", "author"].edge_index.size(1)
    com = build_hetero_data(big, raw, max_coauthors_per_work=4)[0]["author", "co_author", "author"].edge_index.size(1)
    assert sem == 20    # C(5,2)=10 pares * 2 direções
    assert com == 0     # clique removida pelo teto
    # WRITES preservado mesmo com o teto (artigo permanece no corpus)
    assert build_hetero_data(big, raw, max_coauthors_per_work=4)[0]["author", "writes", "paper"].edge_index.size(1) == 5


def test_temporal_restriction():
    # só W1 e W2 (treino) -> A1,A2,A3 ainda aparecem; W3 e suas arestas somem
    data, maps = build_hetero_data(_corpus(), _works_raw(), work_ids={"W1", "W2"})
    assert len(maps["paper"]) == 2
    assert "C3" not in maps["concept"]  # C3 só existia em W3
