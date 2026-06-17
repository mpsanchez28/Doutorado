"""Testes da análise estatística (bootstrap CIs por métrica)."""
from coauthor_rec.eval.stats import bootstrap_metric_cis, paired_test, bonferroni


def test_bootstrap_metric_cis_structure_and_bounds():
    # per_author[k][metric] = listas por autor (P,R,NDCG,MRR,AP)
    per_author = {10: {"P": [0.2, 0.4, 0.0, 0.6, 0.2], "R": [0.1, 0.3, 0.0, 0.5, 0.1],
                       "NDCG": [0.2, 0.2, 0.1, 0.4, 0.1], "MRR": [0.5, 0.0, 0.0, 1.0, 0.0],
                       "AP": [0.1, 0.2, 0.0, 0.3, 0.1]}}
    cis = bootstrap_metric_cis(per_author, [10], n_boot=200, seed=1)
    assert set(cis[10]) == {"P", "R", "F1", "NDCG", "MRR", "MAP"}
    for m, (lo, hi) in cis[10].items():
        assert lo <= hi                          # intervalo coerente
        assert 0.0 <= lo and hi <= 1.0           # métricas em [0,1]


def test_bootstrap_empty_is_safe():
    cis = bootstrap_metric_cis({10: {"P": [], "R": [], "NDCG": [], "MRR": [], "AP": []}},
                               [10], n_boot=10)
    assert cis[10] == {}


def test_bonferroni():
    assert bonferroni(0.05, 5) == 0.01
