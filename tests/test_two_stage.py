"""Teste do reranker de 2 etapas (estrutura no topo, texto na cauda)."""
import numpy as np
import pandas as pd

from coauthor_rec.models.two_stage import TwoStageReranker


def _train_df():
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
    rec = TwoStageReranker(text, idx, m_text=2, n_estimators=20).fit(df)
    out = rec.recommend("A", top_n=4)
    assert "A" not in out
    assert all(a in idx for a in out)
    # estágio 1 (estrutural) deve preceder a cauda textual quando há candidatos 2-hop
    g = rec.rf.graph
    two_hop = {c for nb in g.get("A", set()) for c in g.get(nb, set())
               if c != "A" and c not in g.get("A", set())}
    if two_hop and out:
        assert out[0] in two_hop  # topo vem da estrutura
