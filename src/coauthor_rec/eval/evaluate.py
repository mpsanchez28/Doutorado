"""Harness de avaliação: roda modelos sobre o ground truth com split temporal,
agrega métricas globalmente e por regime (warm/cool/cold), e guarda os scores por
autor para os testes pareados/bootstrap.

Replica o protocolo do estudo inicial (filtra coautores passados das recomendações,
search_limit = max_k * 3) e estende com a estratificação por regime e estatística.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from tqdm import tqdm

from . import metrics as M
from .regimes import classify_authors, REGIMES


def _empty_bucket(k_values):
    return {k: defaultdict(list) for k in k_values}


def evaluate_models(
    models,
    ground_truth: dict,
    train_graph: dict,
    k_values=(5, 10, 20, 50, 100, 200),
    warm_min: int = 5,
    cool_min: int = 1,
    t0_authors: set | None = None,
    show_progress: bool = True,
) -> dict:
    """Avalia modelos. Retorna estrutura com:

    results[model_name]["overall"][k] = {P,R,F1,NDCG,MRR,MAP}
    results[model_name]["by_regime"][regime][k] = {...}
    results[model_name]["per_author"][k][metric] = [valores por autor]  (p/ estatística)
    """
    k_values = list(k_values)
    max_k = max(k_values)
    search_limit = max_k * 3

    target_authors = list(ground_truth.keys())
    regime_of = classify_authors(train_graph, target_authors, warm_min, cool_min, t0_authors)

    results: dict = {}
    for model in models:
        overall = _empty_bucket(k_values)
        by_regime = {r: _empty_bucket(k_values) for r in REGIMES}

        iterator = tqdm(target_authors, desc=model.name, unit="autor") if show_progress \
            else target_authors
        for author_id in iterator:
            relevant = ground_truth[author_id]
            recs = model.recommend(author_id, top_n=search_limit)
            past = train_graph.get(author_id, set())
            valid = [r for r in recs if r not in past][:max_k]

            scores = M.per_author_scores(valid, relevant, k_values)
            regime = regime_of[author_id]
            for k in k_values:
                for metric, value in scores[k].items():
                    overall[k][metric].append(value)
                    by_regime[regime][k][metric].append(value)

        results[model.name] = {
            "overall": _aggregate(overall, k_values),
            "by_regime": {r: _aggregate(b, k_values) for r, b in by_regime.items()},
            "per_author": overall,                  # arrays por autor (overall)
            "per_author_by_regime": by_regime,      # arrays por autor (por regime) p/ ICs
            "regime_counts": _regime_counts(regime_of),
        }
    return results


def _aggregate(bucket, k_values) -> dict:
    out = {}
    for k in k_values:
        p = float(np.mean(bucket[k]["P"])) if bucket[k]["P"] else 0.0
        r = float(np.mean(bucket[k]["R"])) if bucket[k]["R"] else 0.0
        out[k] = {
            "P": p,
            "R": r,
            "F1": M.f1(p, r),
            "NDCG": float(np.mean(bucket[k]["NDCG"])) if bucket[k]["NDCG"] else 0.0,
            "MRR": float(np.mean(bucket[k]["MRR"])) if bucket[k]["MRR"] else 0.0,
            "MAP": float(np.mean(bucket[k]["AP"])) if bucket[k]["AP"] else 0.0,
            "Hits": float(np.mean(bucket[k]["Hits"])) if bucket[k]["Hits"] else 0.0,
        }
    return out


def _regime_counts(regime_of) -> dict:
    counts = {r: 0 for r in REGIMES}
    for r in regime_of.values():
        counts[r] += 1
    return counts
