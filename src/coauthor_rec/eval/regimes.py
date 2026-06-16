"""Regimes de avaliação warm / cool / cold (Seção 4.6.1, Tabela 9).

Classificação operacional por grau de coautoria observado em T0 (não mede senioridade).
O regime de um par é o mais restritivo dos dois autores (cold > cool > warm).
"""
from __future__ import annotations

WARM, COOL, COLD = "warm", "cool", "cold"
_ORDER = {COLD: 3, COOL: 2, WARM: 1}  # mais restritivo = maior


def author_regime(degree: int, warm_min: int = 5, cool_min: int = 1) -> str:
    """Classifica um autor pelo nº de coautores distintos em T0."""
    if degree >= warm_min:
        return WARM
    if degree >= cool_min:
        return COOL
    return COLD


def classify_authors(
    train_graph: dict[str, set],
    authors,
    warm_min: int = 5,
    cool_min: int = 1,
) -> dict:
    """Mapeia cada autor-alvo ao seu regime, usando o grau em T0 (0 se ausente)."""
    return {
        a: author_regime(len(train_graph.get(a, set())), warm_min, cool_min)
        for a in authors
    }


def pair_regime(regime_a: str, regime_b: str) -> str:
    """Regime do par = o mais restritivo dos dois (cold > cool > warm)."""
    return regime_a if _ORDER[regime_a] >= _ORDER[regime_b] else regime_b
