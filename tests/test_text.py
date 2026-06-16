"""Testes do módulo textual (sem download de modelos: usa TF-IDF e embeddings sintéticos)."""
import numpy as np
import pandas as pd

from coauthor_rec.text.embed import paper_texts, author_embeddings
from coauthor_rec.text.encoders import TfidfEncoder, get_encoder, available_encoders
from coauthor_rec.models.text_sim import TextSimilarityRecommender


def _corpus():
    rows = [
        ("W1", "A1", "Graph neural networks", "We study GNNs for link prediction."),
        ("W1", "A2", "Graph neural networks", "We study GNNs for link prediction."),
        ("W2", "A3", "Cooking recipes", "A study about pasta and tomato sauce."),
        ("W3", "A4", "Deep learning on graphs", "Message passing and graph embeddings."),
    ]
    return pd.DataFrame(rows, columns=["work_id", "author_id", "title", "abstract"])


def test_paper_texts_and_tfidf():
    wids, texts = paper_texts(_corpus())
    assert len(wids) == 3  # W1,W2,W3 (W1 aparece 2x, dedup por work)
    emb = TfidfEncoder(dim=4).encode(texts)
    assert emb.shape[0] == 3 and emb.shape[1] >= 1


def test_author_embeddings_mean():
    df = _corpus()
    wids, _ = paper_texts(df)
    # embeddings de artigo fixos: W1=[1,0], W2=[0,1], W3=[1,1]
    pe = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float32)
    ae, aidx = author_embeddings(df, pe, wids)
    assert set(aidx) == {"A1", "A2", "A3", "A4"}
    # A1 e A2 só têm W1 -> [1,0]
    assert np.allclose(ae[aidx["A1"]], [1.0, 0.0])
    assert np.allclose(ae[aidx["A3"]], [0.0, 1.0])  # só W2


def test_text_recommender_ranks_similar_authors():
    # A1 perto de A2; A3 ortogonal. recomendação de A1 deve trazer A2 antes de A3.
    emb = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    aidx = {"A1": 0, "A2": 1, "A3": 2}
    rec = TextSimilarityRecommender(emb, aidx)
    out = rec.recommend("A1", top_n=2)
    assert out[0] == "A2"
    assert "A1" not in out  # não recomenda a si mesmo


def test_registry():
    assert set(available_encoders()) >= {"tfidf", "bert", "scibert", "specter"}
    assert get_encoder("tfidf").__class__.__name__ == "TfidfEncoder"
