"""Testes de valores conhecidos das métricas beyond-accuracy (diversidade/novidade)."""
import math

import numpy as np

from coauthor_rec.eval import beyond as B


def test_ild_orthogonal_is_one():
    # dois perfis ortogonais (cosseno 0) -> ILD = 1 - 0 = 1
    emb = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    idx = {"a": 0, "b": 1}
    assert abs(B.intra_list_diversity(["a", "b"], 2, emb, idx) - 1.0) < 1e-6


def test_ild_identical_is_zero():
    # perfis idênticos (cosseno 1) -> ILD = 0
    emb = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    idx = {"a": 0, "b": 1}
    assert abs(B.intra_list_diversity(["a", "b"], 2, emb, idx)) < 1e-6


def test_ild_needs_two_embeddings():
    emb = np.array([[1.0, 0.0]], dtype=np.float32)
    assert B.intra_list_diversity(["a", "x"], 2, emb, {"a": 0}) == 0.0


def test_novelty_self_information():
    # p=0.25 -> -log2(0.25)=2 ; p=0.5 -> 1 ; média = 1.5
    pop = {"a": 0.25, "b": 0.5}
    assert abs(B.novelty(["a", "b"], 2, pop) - 1.5) < 1e-9


def test_novelty_unknown_gets_floor():
    # 'x' ausente -> recebe menor popularidade (0.25) -> -log2(0.25)=2
    pop = {"a": 0.25}
    assert abs(B.novelty(["x"], 1, pop) - 2.0) < 1e-9


def test_popularity_normalized_in_unit_interval():
    tg = {"a": {"b", "c"}, "b": {"a"}, "c": set()}
    pop = B.popularity_from_graph(tg)
    assert all(0 < v <= 1 for v in pop.values())
    assert pop["a"] == 2 / 3  # grau 2 de 3 autores
