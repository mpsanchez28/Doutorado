"""Regimes de avaliação warm / cool / cold (+ newcomer) — Seção 4.6.1, Tabela 9.

Classificação operacional por grau de coautoria observado em T0 (não mede senioridade).
A qualificação define cold como "0 coautores, ≥1 artigo em T0"; autores sem nenhum artigo
em T0 (estreantes que só aparecem em T1) ficam num bucket separado **newcomer**, pois não
têm perfil em T0 para consulta (nem topológico nem textual).

O regime de um par é o mais restritivo dos dois (newcomer > cold > cool > warm).
"""
from __future__ import annotations

WARM, COOL, COLD, NEWCOMER = "warm", "cool", "cold", "newcomer"
REGIMES = (WARM, COOL, COLD, NEWCOMER)
_ORDER = {NEWCOMER: 4, COLD: 3, COOL: 2, WARM: 1}  # mais restritivo = maior


def author_regime(degree: int, warm_min: int = 5, cool_min: int = 1,
                  active_in_t0: bool = True) -> str:
    """Classifica um autor pelo nº de coautores distintos em T0.

    ``active_in_t0=False`` (autor sem artigo em T0) força o regime ``newcomer``.
    """
    if degree >= warm_min:
        return WARM
    if degree >= cool_min:
        return COOL
    return COLD if active_in_t0 else NEWCOMER


def classify_authors(
    train_graph: dict[str, set],
    authors,
    warm_min: int = 5,
    cool_min: int = 1,
    t0_authors: set | None = None,
) -> dict:
    """Mapeia cada autor-alvo ao seu regime.

    ``t0_authors``: conjunto de autores com ≥1 artigo em T0. Se fornecido, autores de grau 0
    fora desse conjunto viram ``newcomer``; se None, todo grau 0 é ``cold`` (comportamento
    de 3 regimes, retrocompatível).
    """
    out = {}
    for a in authors:
        degree = len(train_graph.get(a, set()))
        active = True if t0_authors is None else (a in t0_authors)
        out[a] = author_regime(degree, warm_min, cool_min, active_in_t0=active)
    return out


def pair_regime(regime_a: str, regime_b: str) -> str:
    """Regime do par = o mais restritivo dos dois (newcomer > cold > cool > warm)."""
    return regime_a if _ORDER[regime_a] >= _ORDER[regime_b] else regime_b
