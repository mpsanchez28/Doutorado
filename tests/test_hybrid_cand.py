"""Teste do reranker de candidatos híbridos (estrutural ∪ textual)."""
import numpy as np
import pandas as pd

from coauthor_rec.models.hybrid_cand import HybridReranker


def _train_df():
    rows = [
        ("W1", "A1"), ("W1", "A2"),   # A1-A2
        ("W2", "A2"), ("W2", "A3"),   # A2-A3  -> A1 e A3 a 2 saltos
        ("W3", "A4"), ("W3", "A5"),   # A4-A5 (componente separada)
    ]
    return pd.DataFrame(rows, columns=["work_id", "author_id"])


def test_hybrid_unites_structural_and_textual_candidates():
    idx = {"A1": 0, "A2": 1, "A3": 2, "A4": 3, "A5": 4}
    # embeddings: A1 textualmente perto de A4 (fora do 2-hop de A1)
    emb = np.array([[1, 0], [0.9, 0.1], [0.2, 0.9], [0.98, 0.05], [0, 1]], dtype=np.float32)
    rec = HybridReranker(emb, idx, text_emb=emb, m_text=2).fit(_train_df())

    out = rec.recommend("A1", top_n=4)
    assert "A1" not in out
    assert "A2" not in out          # coautor direto é excluído
    # A3 vem do 2-hop; A4 vem da vizinhança textual (não alcançável por 2 saltos)
    assert "A3" in out and "A4" in out


def test_m_text_zero_is_structural_only():
    idx = {"A1": 0, "A2": 1, "A3": 2, "A4": 3, "A5": 4}
    emb = np.eye(5, dtype=np.float32)
    rec = HybridReranker(emb, idx, text_emb=emb, m_text=0).fit(_train_df())
    out = rec.recommend("A1", top_n=10)
    assert "A4" not in out[:1]       # sem candidatos textuais, A4 não é prioridade estrutural
