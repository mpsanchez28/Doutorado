"""Testes da classificação de regimes (warm/cool/cold/newcomer)."""
from coauthor_rec.eval.regimes import classify_authors, author_regime, pair_regime


def test_author_regime_thresholds():
    assert author_regime(5) == "warm"
    assert author_regime(4) == "cool"
    assert author_regime(1) == "cool"
    assert author_regime(0) == "cold"                       # ativo em T0 (default)
    assert author_regime(0, active_in_t0=False) == "newcomer"


def test_classify_separates_newcomer_from_cold():
    # A1: 5 coautores (warm); A2: 2 (cool); A3: 0 mas tem artigo T0 (cold);
    # A4: 0 e sem artigo T0 (newcomer)
    graph = {"A1": set("bcdef"), "A2": {"x", "y"}, "A3": set()}
    t0 = {"A1", "A2", "A3"}  # A4 ausente de T0
    reg = classify_authors(graph, ["A1", "A2", "A3", "A4"], t0_authors=t0)
    assert reg == {"A1": "warm", "A2": "cool", "A3": "cold", "A4": "newcomer"}


def test_classify_backward_compatible_without_t0():
    # sem t0_authors, todo grau 0 vira cold (3 regimes)
    reg = classify_authors({"A1": set()}, ["A1", "A2"])
    assert reg == {"A1": "cold", "A2": "cold"}


def test_pair_regime_most_restrictive():
    assert pair_regime("warm", "cold") == "cold"
    assert pair_regime("newcomer", "cool") == "newcomer"
    assert pair_regime("warm", "cool") == "cool"
