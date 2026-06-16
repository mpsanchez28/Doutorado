"""Comparação de encoders textuais como recomendadores text-only.

Para cada encoder: encoda os artigos de T0, agrega em embeddings de autor, e avalia o
TextSimilarityRecommender sob o mesmo protocolo (P/R/F1/NDCG/MRR/MAP@K, warm/cool/cold).
Inclui o baseline topológico como referência. Embeddings de artigo são cacheados em disco.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .embed import paper_texts, author_embeddings
from .encoders import get_encoder
from ..models.text_sim import TextSimilarityRecommender
from ..eval.evaluate import evaluate_models


def _encode_papers(encoder_name: str, work_ids, texts, cache_dir: Path) -> np.ndarray:
    """Encoda (com cache em disco keyed por encoder + conjunto de works)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{encoder_name}.npz"
    if cache.exists():
        blob = np.load(cache, allow_pickle=True)
        if list(blob["work_ids"]) == list(work_ids):
            return blob["emb"]
    emb = get_encoder(encoder_name).encode(texts)
    np.savez(cache, emb=emb, work_ids=np.array(work_ids, dtype=object))
    return emb


def run_text_comparison(
    train_df: pd.DataFrame,
    ground_truth: dict,
    train_graph: dict,
    encoder_names,
    k_values,
    regimes,
    cache_dir: Path,
    max_coauthors_per_work: int | None = None,
    with_baseline: bool = True,
    log=print,
) -> dict:
    """Avalia cada encoder (text-only) + baseline topológico. Retorna results por modelo."""
    work_ids, texts = paper_texts(train_df)
    t0_authors = set(train_df["author_id"])
    results: dict = {}

    def _eval(model):
        return evaluate_models(
            [model], ground_truth, train_graph, k_values=k_values,
            warm_min=regimes["warm_min_coauthors"], cool_min=regimes["cool_min_coauthors"],
            t0_authors=t0_authors, show_progress=False)[model.name]

    if with_baseline:
        from ..models.baseline import TopologyRecommender
        log("[text-compare] baseline topológico (referência)…")
        base = TopologyRecommender(max_coauthors_per_work=max_coauthors_per_work).fit(train_df)
        results["Topology (ref)"] = _eval(base)

    for enc_name in encoder_names:
        log(f"[text-compare] encoder = {enc_name} …")
        paper_emb = _encode_papers(enc_name, work_ids, texts, cache_dir)
        author_emb, aidx = author_embeddings(train_df, paper_emb, work_ids)
        rec = TextSimilarityRecommender(author_emb, aidx, name=f"Text:{enc_name}")
        results[rec.name] = _eval(rec)
    return results


def comparison_table(results: dict, k_values, metric: str = "R") -> str:
    """Tabela compacta encoder x K para uma métrica (ex.: 'R' = Recall)."""
    label = {"R": "Recall", "P": "Precision", "NDCG": "NDCG", "MRR": "MRR", "MAP": "MAP"}[metric]
    lines = [f"{label}@K (%) — geral", "model".ljust(22) + "".join(f"{k:>8}" for k in k_values)]
    lines.append("-" * (22 + 8 * len(k_values)))
    for name, res in results.items():
        row = "".join(f"{res['overall'][k][metric] * 100:>8.2f}" for k in k_values)
        lines.append(name.ljust(22) + row)
    return "\n".join(lines)


def regime_table(results: dict, k_values, regime: str, metric: str = "R") -> str:
    """Tabela encoder x K restrita a um regime (warm|cool|cold|newcomer)."""
    label = {"R": "Recall", "P": "Precision", "NDCG": "NDCG", "MRR": "MRR", "MAP": "MAP"}[metric]
    any_counts = next(iter(results.values())).get("regime_counts", {})
    n = any_counts.get(regime, "?")
    lines = [f"{label}@K (%) — regime {regime.upper()} ({n} autores)",
             "model".ljust(22) + "".join(f"{k:>8}" for k in k_values)]
    lines.append("-" * (22 + 8 * len(k_values)))
    for name, res in results.items():
        b = res["by_regime"][regime]
        row = "".join(f"{b[k][metric] * 100:>8.2f}" for k in k_values)
        lines.append(name.ljust(22) + row)
    return "\n".join(lines)
