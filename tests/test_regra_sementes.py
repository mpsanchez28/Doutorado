"""Regra entre sementes, da expansão ao ranking (ESPECIFICACAO §2, emenda E3).

- coleta (expansão): o universo exclui só as sementes DO CORTE, porque o histórico delas já está no
  bruto — isso evita reconsultar, não as retira da recomendação;
- ranking: excluem-se só a própria consulta (identidade canônica) e seus coautores anteriores;
  outra semente/alvo é recomendável e entra no gabarito como qualquer coautor novo.
A reprodução do universo histórico é testada à parte (test_universo_candidatos.py).
"""
import numpy as np
import pandas as pd

from coauthor_rec.collect.openalex import candidate_universe_at_cut
from coauthor_rec.models.kg_generators import rank_candidates
from coauthor_rec.models.kg_ltr import ranking_exclusions
from coauthor_rec.split.temporal import build_ground_truth

# autores do KG (identidades canônicas): s1, s2 = sementes do corte (ambas alvos); p = coautor
# anterior de s1; x = semente FORA do corte com laço permitido; y = autor sem laço com sementes
AUTHORS = ["s1", "s2", "p", "x", "y"]
AIDX = {a: i for i, a in enumerate(AUTHORS)}
PAST = {"s1": {"p"}, "p": {"s1"}}


def _rank(query, scores):
    ex = ranking_exclusions([query], PAST, AIDX)
    ranked, _ = rank_candidates(np.array([scores], dtype=float), ex, np.zeros(len(AUTHORS)), top=10)
    return [AUTHORS[i] for i in ranked[0]]


def test_self_is_excluded_by_canonical_identity():
    assert "s1" not in _rank("s1", [9, 1, 1, 1, 1])                  # escore máximo para si mesma


def test_other_seed_and_target_is_recommendable():
    assert _rank("s1", [0, 5, 0, 0, 0]) == ["s2"]                   # s2 também é alvo: não é bloqueada
    assert _rank("s2", [5, 0, 0, 0, 0]) == ["s1"]


def test_prior_coauthor_is_excluded():
    assert "p" not in _rank("s1", [0, 1, 9, 1, 1])
    assert "p" in _rank("s2", [1, 0, 9, 1, 1])                      # não é coautor anterior de s2


def test_ground_truth_keeps_other_targets_as_new_coauthors():
    tr = pd.DataFrame({"work_id": ["w1", "w1"], "author_id": ["s1", "p"]})
    te = pd.DataFrame({"work_id": ["w2", "w2", "w3", "w3"], "author_id": ["s1", "s2", "s1", "p"]})
    _, gt = build_ground_truth(tr, te)
    assert gt["s1"] == {"s2"} and gt["s2"] == {"s1"}                # p já era coautor: não é novo


def test_expansion_queue_excludes_only_cut_seeds_and_needs_a_permitted_tie():
    auth = pd.DataFrame([("w1", "s1"), ("w1", "x"), ("w2", "s2"), ("w2", "p"), ("w3", "y"), ("w3", "z"),
                         ("w4", "x"), ("w4", "q")], columns=["work_id", "author_id"])
    years = {"w1": 2020, "w2": 2019, "w3": 2018, "w4": 2023}
    u = candidate_universe_at_cut(auth, {"s1", "s2"}, None, years, 2021)
    assert "x" in u            # semente fora do corte, com laço ≤ corte com s1: candidata legítima
    assert "p" in u            # coautor de s2
    assert "y" not in u        # sem laço com semente do corte: não entra na expansão
    assert "q" not in u        # laço só posterior ao corte e com quem não é semente do corte
    assert not {"s1", "s2"} & set(u)   # sementes do corte: fora da FILA DE COLETA (histórico já no bruto)
