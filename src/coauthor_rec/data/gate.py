"""Gate de qualidade do corpus (Seção 4.3.2).

Verifica limiares mínimos antes da modelagem profunda. Calcula também o peso médio de
CO_AUTHOR e o nº de pares com peso >= 3 a partir das arestas ponderadas.
"""
from __future__ import annotations

import pandas as pd

from ..graph.coauthor import build_weighted_coauthor_edges
from .clean import corpus_summary


def evaluate_gate(merged_df: pd.DataFrame, thresholds: dict) -> dict:
    """Avalia os cinco critérios do gate. Retorna {passed, checks, stats}."""
    stats = corpus_summary(merged_df)
    edges = build_weighted_coauthor_edges(merged_df)
    weights = [e["weight"] for e in edges.values()]
    mean_weight = sum(weights) / len(weights) if weights else 0.0
    pairs_ge_3 = sum(1 for w in weights if w >= 3)

    checks = {
        "works": (stats["works"], thresholds["min_works"], stats["works"] >= thresholds["min_works"]),
        "authors": (stats["authors"], thresholds["min_authors"], stats["authors"] >= thresholds["min_authors"]),
        "mean_coauthor_weight": (round(mean_weight, 3), thresholds["min_mean_coauthor_weight"],
                                  mean_weight >= thresholds["min_mean_coauthor_weight"]),
        "pairs_weight_ge_3": (pairs_ge_3, thresholds["min_pairs_weight_ge_3"],
                               pairs_ge_3 >= thresholds["min_pairs_weight_ge_3"]),
        "abstract_coverage": (round(stats["abstract_coverage"], 3), thresholds["min_abstract_coverage"],
                               stats["abstract_coverage"] >= thresholds["min_abstract_coverage"]),
    }
    passed = all(ok for *_, ok in checks.values())
    return {"passed": passed, "checks": checks, "stats": stats}
