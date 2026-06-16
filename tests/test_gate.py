"""Testes do gate de qualidade do corpus."""
from coauthor_rec.data.gate import evaluate_gate


THRESHOLDS_SMALL = {
    "min_works": 100000,  # inalcançável p/ corpus sintético
    "min_authors": 2000,
    "min_mean_coauthor_weight": 1.3,
    "min_pairs_weight_ge_3": 30,
    "min_abstract_coverage": 0.70,
}

THRESHOLDS_LENIENT = {
    "min_works": 1,
    "min_authors": 1,
    "min_mean_coauthor_weight": 0.0,
    "min_pairs_weight_ge_3": 0,
    "min_abstract_coverage": 0.0,
}


def test_gate_fails_small_corpus(synthetic_corpus):
    result = evaluate_gate(synthetic_corpus, THRESHOLDS_SMALL)
    assert result["passed"] is False
    assert result["checks"]["works"][2] is False


def test_gate_passes_lenient(synthetic_corpus):
    result = evaluate_gate(synthetic_corpus, THRESHOLDS_LENIENT)
    assert result["passed"] is True
    assert result["stats"]["works"] > 0
    assert 0.0 <= result["stats"]["abstract_coverage"] <= 1.0
