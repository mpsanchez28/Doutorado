"""Testes de valores conhecidos para as métricas de ranqueamento."""
import math

from coauthor_rec.eval import metrics as M


REC = ["a", "b", "c", "d", "e"]
REL = {"b", "d"}


def test_precision_recall():
    # hits em top-2 = {b} -> 1; em top-5 = {b,d} -> 2
    assert M.precision_at_k(REC, REL, 2) == 0.5
    assert M.recall_at_k(REC, REL, 5) == 1.0
    assert M.precision_at_k(REC, REL, 5) == 2 / 5


def test_mrr_first_relevant_position():
    # primeiro relevante 'b' está na posição 2 -> 1/2
    assert M.mrr_at_k(REC, REL, 5) == 0.5


def test_hits_at_k():
    # 'b' entra no top-2 -> Hits@2 = 1; nenhum relevante no top-1 -> Hits@1 = 0
    assert M.hits_at_k(REC, REL, 2) == 1.0
    assert M.hits_at_k(REC, REL, 1) == 0.0
    assert M.hits_at_k(REC, set(), 5) == 0.0        # sem relevantes -> 0
    # se k=1, nenhum relevante no top-1 -> 0
    assert M.mrr_at_k(REC, REL, 1) == 0.0


def test_ndcg_known_value():
    # relevantes em posições 2 e 4 -> DCG = 1/log2(3) + 1/log2(5)
    dcg = 1 / math.log2(3) + 1 / math.log2(5)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)  # ideal: posições 1 e 2
    assert M.ndcg_at_k(REC, REL, 5) == dcg / idcg


def test_map_known_value():
    # AP = (1/2 + 2/4) / 2 = 0.5
    assert M.average_precision_at_k(REC, REL, 5) == 0.5


def test_empty_relevant_set_is_zero():
    assert M.precision_at_k(REC, set(), 5) == 0.0
    assert M.ndcg_at_k(REC, set(), 5) == 0.0
    assert M.mrr_at_k(REC, set(), 5) == 0.0


def test_f1_harmonic_mean():
    assert M.f1(0.5, 0.5) == 0.5
    assert M.f1(0.0, 1.0) == 0.0
