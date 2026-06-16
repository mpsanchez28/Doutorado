"""Teste end-to-end dos baselines sobre o corpus sintético.

Verifica o invariante metodológico central: o oráculo (limite superior dado o espaço
de candidatos) nunca tem Recall inferior ao baseline no mesmo K.
"""
from coauthor_rec.config import set_seed
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.models.baseline import TopologyRecommender
from coauthor_rec.models.oracle import IdealTopologyRecommender
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.eval.evaluate import evaluate_models


def test_end_to_end_and_oracle_upper_bound(synthetic_corpus):
    set_seed(42)
    train, test = chronological_split(synthetic_corpus, train_fraction=0.8)
    train_graph, gt = build_ground_truth(train, test)

    baseline = TopologyRecommender().fit(train)
    oracle = IdealTopologyRecommender(baseline, gt).fit(train)
    hybrid = HybridCoauthorRecommender(candidate_pool_size=50,
                                       n_estimators=20).fit(train)

    k_values = [5, 10, 20]
    results = evaluate_models([baseline, oracle, hybrid], gt, train_graph,
                              k_values=k_values, show_progress=False)

    # Estrutura de saída presente.
    for name in (baseline.name, oracle.name, hybrid.name):
        assert name in results
        assert set(results[name]["by_regime"]) == {"warm", "cool", "cold"}

    # Oráculo é limite superior em Recall (mesmo espaço de candidatos).
    for k in k_values:
        r_base = results[baseline.name]["overall"][k]["R"]
        r_oracle = results[oracle.name]["overall"][k]["R"]
        assert r_oracle >= r_base - 1e-9

    # Contagem de autores por regime soma o total de alvos.
    counts = results[baseline.name]["regime_counts"]
    assert sum(counts.values()) == len(gt)
