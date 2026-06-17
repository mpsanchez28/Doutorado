"""Análise estatística (Seção 4.6.3).

Testes pareados entre modelos sobre o mesmo conjunto de autores-alvo: Shapiro-Wilk
decide entre t pareado e Wilcoxon; correção de Bonferroni para múltiplas comparações;
intervalos de confiança por bootstrap sobre os autores.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def paired_test(values_a, values_b, alpha: float = 0.05) -> dict:
    """Teste pareado entre dois vetores de desempenho por autor.

    Aplica Shapiro-Wilk às diferenças; se normal (p>alpha) usa t pareado, senão Wilcoxon.
    """
    a = np.asarray(values_a, dtype=float)
    b = np.asarray(values_b, dtype=float)
    diff = a - b
    n = len(diff)
    result = {
        "n": n,
        "mean_diff": float(np.mean(diff)) if n else 0.0,
        "test": None,
        "statistic": None,
        "p_value": None,
        "normal": None,
    }
    if n < 3 or np.allclose(diff, 0):
        result["test"] = "none"
        result["p_value"] = 1.0
        return result

    _, p_norm = stats.shapiro(diff)
    result["normal"] = bool(p_norm > alpha)
    if result["normal"]:
        stat, p = stats.ttest_rel(a, b)
        result["test"] = "paired_t"
    else:
        stat, p = stats.wilcoxon(a, b)
        result["test"] = "wilcoxon"
    result["statistic"] = float(stat)
    result["p_value"] = float(p)
    return result


def bonferroni(alpha: float, n_comparisons: int) -> float:
    """Nível de significância ajustado para múltiplas comparações."""
    return alpha / n_comparisons if n_comparisons > 0 else alpha


def bootstrap_metric_cis(per_author: dict, k_values, n_boot: int = 100,
                         ci: float = 0.95, seed: int = 42) -> dict:
    """IC bootstrap por métrica (reamostra autores com reposição), incluindo F1 e MAP.

    ``per_author[k][metric]`` = lista por autor das métricas cruas (P, R, NDCG, MRR, AP).
    Retorna ``{k: {metric: [lo, hi]}}`` para P, R, F1, NDCG, MRR, MAP (em fração 0–1).
    """
    rng = np.random.default_rng(seed)
    lo_p, hi_p = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    out: dict = {}
    for k in k_values:
        arrs = {m: np.asarray(per_author[k][m], dtype=float) for m in per_author[k]}
        n = len(next(iter(arrs.values()))) if arrs else 0
        if n == 0:
            out[k] = {}
            continue
        boot = {m: [] for m in ("P", "R", "F1", "NDCG", "MRR", "MAP")}
        for _ in range(n_boot):
            idx = rng.integers(0, n, n)
            mp, mr = arrs["P"][idx].mean(), arrs["R"][idx].mean()
            boot["P"].append(mp); boot["R"].append(mr)
            boot["F1"].append(2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0)
            boot["NDCG"].append(arrs["NDCG"][idx].mean())
            boot["MRR"].append(arrs["MRR"][idx].mean())
            boot["MAP"].append(arrs["AP"][idx].mean())
        out[k] = {m: [float(np.percentile(v, lo_p)), float(np.percentile(v, hi_p))]
                  for m, v in boot.items()}
    return out


def bootstrap_ci(
    values,
    n_boot: int = 100,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """IC por bootstrap sobre os autores. Retorna (média, low, high)."""
    rng = np.random.default_rng(seed)
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return 0.0, 0.0, 0.0
    means = np.array([rng.choice(v, size=len(v), replace=True).mean() for _ in range(n_boot)])
    low = float(np.percentile(means, (1 - ci) / 2 * 100))
    high = float(np.percentile(means, (1 + ci) / 2 * 100))
    return float(v.mean()), low, high
