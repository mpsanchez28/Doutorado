"""Teste do reranker supervisionado sobre pool híbrido (treino + recomendação em mini-grafo)."""
import numpy as np
import pandas as pd

from coauthor_rec.models.supervised_hybrid import SupervisedHybridReranker, FEATURES


def _train_df():
    # grupos com sobreposição p/ gerar vizinhos em comum (features topológicas != 0)
    rows = []
    for w, authors in [("W1", "AB"), ("W2", "BC"), ("W3", "CA"), ("W4", "BD"),
                       ("W5", "DE"), ("W6", "EC"), ("W7", "AF"), ("W8", "FB")]:
        for a in authors:
            rows.append((w, a))
    return pd.DataFrame(rows, columns=["work_id", "author_id"])


def test_fit_and_recommend():
    df = _train_df()
    authors = sorted(df["author_id"].unique())
    idx = {a: i for i, a in enumerate(authors)}
    rng = np.random.default_rng(0)
    text = rng.normal(size=(len(authors), 8)).astype(np.float32)
    gnn = rng.normal(size=(len(authors), 8)).astype(np.float32)

    rec = SupervisedHybridReranker(idx, text, gnn_emb=gnn, m_text=2,
                                   max_positive_samples=1000, n_estimators=20).fit(df)
    # RF treinou com 5 features
    assert rec.rf.n_features_in_ == len(FEATURES)
    out = rec.recommend("A", top_n=3)
    assert "A" not in out
    assert all(a in idx for a in out)


def test_features_vector_length():
    df = _train_df()
    idx = {a: i for i, a in enumerate(sorted(df["author_id"].unique()))}
    text = np.eye(len(idx), dtype=np.float32)
    rec = SupervisedHybridReranker(idx, text, gnn_emb=None, m_text=1).fit(df)
    f = rec._feats("A", "C")
    assert len(f) == 5            # CN, Jaccard, AA, text_sim, gnn_sim(=0 sem gnn)
    assert f[4] == 0.0            # sem gnn_emb -> gnn_sim zero
