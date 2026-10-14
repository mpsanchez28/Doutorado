"""Universo de candidatos de um corte (docs/REVISAO_CONSISTENCIA_PROTOCOLOS.md A0).

O universo do corte é gerado SÓ pelos trabalhos das sementes do corte, com laço ≤ corte; uma
semente fora do corte pode ser candidata se tiver esse laço. A reprodução do universo histórico
(todas as sementes, T0 original) é testada à parte.
"""
import importlib.util
import json
import os

import pandas as pd

from coauthor_rec.collect.openalex import candidate_universe_at_cut, check_candidate_universe, select_candidates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# s1: semente do corte (sorteada por trabalho ≤ 2021); s2: semente FORA do corte (sorteada por trabalho > 2021)
AUTH = pd.DataFrame([
    ("w1", "s1"), ("w1", "a"),            # 2019: laço s1–a                       → a é candidato
    ("w2", "s2"), ("w2", "b"),            # 2019: b só é coautor da semente fora do corte → NÃO
    ("w3", "s1"), ("w3", "c"),            # 2022: laço posterior ao corte          → NÃO
    ("w4", "s1"), ("w4", "s2"),           # 2020: s2 é coautora de s1 até o corte  → s2 é candidata
    ("w5", "s2"), ("w5", "d"),            # 2023: trabalho que fez s2 ser sorteada → NÃO
], columns=["work_id", "author_id"])
YEARS = {"w1": 2019, "w2": 2019, "w3": 2022, "w4": 2020, "w5": 2023}


def test_universe_uses_only_cut_seeds_and_facts_until_cut():
    cands = candidate_universe_at_cut(AUTH, {"s1"}, cap=None, work_years=YEARS, cut=2021)
    assert cands == ["a", "s2"]
    chk = check_candidate_universe(cands, AUTH, {"s1"}, None, YEARS, 2021, all_seeds={"s1", "s2"})
    assert chk["ok"] and chk["sementes_fora_do_corte_candidatas_por_laco_legitimo"] == 1


def test_v1_defect_is_detected_by_the_check():
    """A versão v1 passava as autorias de TODAS as sementes: b (coautor só de s2) entrava."""
    v1 = select_candidates(AUTH, {"s1"}, None, YEARS, 2021)
    assert "b" in v1
    chk = check_candidate_universe(v1, AUTH, {"s1"}, None, YEARS, 2021)
    assert not chk["ok"] and chk["candidatos_sem_laco_ate_o_corte_com_semente_do_corte"] == 1


def test_cut_seeds_are_never_candidates_and_cap_applies():
    big = pd.concat([AUTH, pd.DataFrame([("w6", x) for x in ("s1", "e", "f", "g")], columns=["work_id", "author_id"])])
    yrs = {**YEARS, "w6": 2018}
    cands = candidate_universe_at_cut(big, {"s1"}, cap=3, work_years=yrs, cut=2021)   # w6 tem 4 autores > teto
    assert not {"e", "f", "g"} & set(cands) and "s1" not in cands
    assert check_candidate_universe(cands, big, {"s1"}, 3, yrs, 2021)["ok"]


def test_historical_universe_reproduction_is_separate():
    """Com todas as sementes e o T0 original, a função do corte reproduz select_candidates."""
    seeds = {"s1", "s2"}
    assert candidate_universe_at_cut(AUTH, seeds, None, YEARS, 2021) == select_candidates(AUTH, seeds, None, YEARS, 2021)


def test_collector_skips_already_queried_candidates(tmp_path):
    spec = importlib.util.spec_from_file_location("coletor_t4", os.path.join(ROOT, "scripts", "coletor_t4.py"))
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    old = pd.DataFrame({"author_id": [f"A{i:03d}" for i in range(120)], "situacao": "novo", "anos_faltando": "2017–2021"})
    old.to_csv(tmp_path / "lacunas_v1.csv", index=False)
    lots = C.build_lots(old, 2021, 5)
    assert [t for t, *_ in lots] == ["novo_0000", "novo_0001", "novo_0002"]
    (tmp_path / "estado.json").write_text(json.dumps({"lotes_feitos": ["novo_0000", "novo_0001"]}))  # 3º lote não terminou
    done = C.queried_ids(tmp_path, [tmp_path / "lacunas_v1.csv"], 2021, 5)
    assert done == set(old["author_id"][:100])
    new = pd.DataFrame({"author_id": ["A005", "A110", "B001"], "situacao": "novo", "anos_faltando": "2017–2021"})
    todo = new[~new["author_id"].isin(done)]
    lots2 = C.build_lots(todo, 2021, 5, prefix="v2_")
    assert lots2 == [("v2_novo_0000", ["A110", "B001"], "2017-01-01", "2021-12-31")]
