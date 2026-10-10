"""Métricas de ranqueamento (Seção 5.1.6).

Precision@K, Recall@K, F1@K, NDCG@K, MRR@K e MAP. As implementações de NDCG e MRR@K
são portadas fielmente do notebook do estudo inicial; F1 é a média harmônica das médias
de Precision e Recall (consistente com a Tabela 12/13).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


def precision_at_k(recommended: list, relevant: set, k: int) -> float:
    if k <= 0:
        return 0.0
    hits = len(set(recommended[:k]) & relevant)
    return hits / k


def recall_at_k(recommended: list, relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    hits = len(set(recommended[:k]) & relevant)
    return hits / len(relevant)


def ndcg_at_k(recommended: list, relevant: set, k: int) -> float:
    """NDCG@K com ganho binário (relevante=1)."""
    if not relevant:
        return 0.0
    dcg = 0.0
    for i, item in enumerate(recommended[:k], 1):
        if item in relevant:
            dcg += 1.0 / np.log2(i + 1)
    idcg = 0.0
    for i in range(1, min(len(relevant), k) + 1):
        idcg += 1.0 / np.log2(i + 1)
    return dcg / idcg if idcg > 0 else 0.0


def mrr_at_k(recommended: list, relevant: set, k: int) -> float:
    """Reciprocal Rank do primeiro relevante dentro das top-K posições (0 se nenhum)."""
    if not relevant:
        return 0.0
    for rank, item in enumerate(recommended[:k], 1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def hits_at_k(recommended: list, relevant: set, k: int) -> float:
    """Hits@K = 1.0 se houver ao menos um acerto nas top-K posições, senão 0.0.

    Pedida explicitamente pela banca. A média entre autores = fração de autores com
    pelo menos uma recomendação correta no top-K (taxa de sucesso "pelo menos um")."""
    if not relevant:
        return 0.0
    return 1.0 if set(recommended[:k]) & relevant else 0.0


def average_precision_at_k(recommended: list, relevant: set, k: int) -> float:
    """Average Precision@K — base do MAP (média entre autores)."""
    if not relevant:
        return 0.0
    score, hits = 0.0, 0
    for i, item in enumerate(recommended[:k], 1):
        if item in relevant:
            hits += 1
            score += hits / i
    return score / min(len(relevant), k)


def f1(precision: float, recall: float) -> float:
    """Média harmônica (a partir de Precision e Recall médios)."""
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def per_author_scores(
    recommended: list,
    relevant: set,
    k_values: Iterable[int],
) -> dict[int, dict[str, float]]:
    """Calcula todas as métricas por autor para cada K (entrada dos testes pareados)."""
    out: dict[int, dict[str, float]] = {}
    for k in k_values:
        out[k] = {
            "P": precision_at_k(recommended, relevant, k),
            "R": recall_at_k(recommended, relevant, k),
            "NDCG": ndcg_at_k(recommended, relevant, k),
            "MRR": mrr_at_k(recommended, relevant, k),
            "AP": average_precision_at_k(recommended, relevant, k),
            "Hits": hits_at_k(recommended, relevant, k),
        }
    return out


RANK_KS = (5, 10, 20, 50, 100, 200)
ORACLE_POOLS = (200, 1000)


def ranking_report(ranked_ids: list, pool_hits: int, pool_size: int, relevant: set,
                   ks=RANK_KS, pools=ORACLE_POOLS) -> dict:
    """Métricas de um ranking (baseline) e do oráculo sobre o mesmo conjunto de candidatos.

    ``pool_hits``/``pool_size``: acertos e tamanho do conjunto completo de candidatos do
    gerador. Oráculo@P = reordenar perfeitamente os P primeiros (teto de um re-ranqueador que
    receba esse top-P). Recall sempre sobre TODOS os coautores novos (inclusive inalcançáveis).
    """
    n = len(relevant)
    pos = [i for i, c in enumerate(ranked_ids, 1) if c in relevant]
    hits_at = {k: sum(1 for p in pos if p <= k) for k in tuple(ks) + tuple(pools)}
    m = {"n_relevantes": n, "tamanho_conjunto": pool_size, "hits_conjunto": pool_hits,
         "alcance": pool_hits / n}
    for k in ks:
        m[f"R@{k}"] = hits_at[k] / n
        m[f"Hits@{k}"] = float(hits_at[k] > 0)
    m["NDCG@10"] = ndcg_at_k(ranked_ids, relevant, 10)
    m["MRR"] = 1.0 / pos[0] if pos else 0.0
    for p in pools:
        m[f"alcance@{p}"] = hits_at[p] / n
        for k in (10, 50):
            m[f"oraculo{p}_R@{k}"] = min(hits_at[p], k) / n
    for k in (10, 50):
        m[f"oraculo_total_R@{k}"] = min(pool_hits, k) / n
    return m
