"""Testes do split temporal e da verdade fundamental (anti-vazamento)."""
from coauthor_rec.split.temporal import chronological_split, build_ground_truth


def test_no_temporal_leakage(synthetic_corpus):
    train, test = chronological_split(synthetic_corpus, train_fraction=0.8)
    train_max = train["publication_date"].max()
    test_min = test["publication_date"].min()
    # Toda interação de treino é anterior (ou igual no corte) às de teste.
    assert train_max <= test_min
    # Works disjuntos entre treino e teste.
    assert set(train["work_id"]) & set(test["work_id"]) == set()


def test_ground_truth_excludes_past_coauthors(synthetic_corpus):
    train, test = chronological_split(synthetic_corpus, train_fraction=0.8)
    train_graph, gt = build_ground_truth(train, test)
    assert len(gt) > 0  # há novos links para avaliar
    for author, new_links in gt.items():
        past = train_graph.get(author, set())
        # Nenhum link do ground truth pode já existir no passado.
        assert new_links.isdisjoint(past)
        assert author not in new_links


def test_split_fraction(synthetic_corpus):
    train, test = chronological_split(synthetic_corpus, train_fraction=0.8)
    total = synthetic_corpus["work_id"].nunique()
    assert train["work_id"].nunique() == int(total * 0.8)
