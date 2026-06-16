"""Testes das métricas estruturais do KG."""
import json

import pandas as pd
import pytest

pytest.importorskip("torch_geometric")

from coauthor_rec.graph.hetero import build_hetero_data
from coauthor_rec.graph.stats import compute_graph_stats


def _corpus():
    rows = [
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
    c = lambda *p: json.dumps([{"id": i, "name": i, "score": s} for i, s in p])
    rows = [
        ("W1", "V1", c(("C1", 0.9)), json.dumps([]), 5),
        ("W2", "V1", c(("C1", 0.5)), json.dumps(["W1"]), 2),
        ("W3", "V2", c(("C3", 0.8)), json.dumps([]), 0),
    ]
    return pd.DataFrame(rows, columns=["id", "venue_id", "concepts", "referenced_works", "cited_by_count"])


def test_stats_structure_and_values():
    data, _ = build_hetero_data(_corpus(), _works_raw())
    s = compute_graph_stats(data, clustering_sample=None)

    assert s["nodes"]["author"] == 3
    assert s["edges"]["author__co_author__author"] == 6  # simétrica

    co = s["coauthor_network"]
    # triângulo A1-A2-A3: 3 arestas não-dir., grafo completo -> densidade 1, clustering 1
    assert co["undirected_edges"] == 3
    assert co["density"] == 1.0
    assert co["isolated_authors"] == 0
    assert co["connected_components"] == 1
    assert co["giant_component_fraction"] == 1.0
    assert co["avg_clustering"] == 1.0

    cov = s["relation_coverage"]
    assert cov["authors_per_paper"] == 2.0          # 6 autorias / 3 papers
    assert cov["pct_papers_with_topic"] == 1.0      # todos com >=1 conceito
    assert cov["intra_corpus_citations"] == 1       # W2->W1

    # serializável
    json.dumps(s)
