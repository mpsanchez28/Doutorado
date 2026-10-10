"""KG T0 materializado, protocolo com M9 e geradores por meta-caminho."""
import json

import numpy as np
import pandas as pd

from coauthor_rec.eval.protocol import build_protocol, m9_suspects
from coauthor_rec.graph.kg import build_kg_t0, validate_kg
from coauthor_rec.models.kg_generators import KGIndex, rank_candidates


def _row(w, a, name, date, insts=()):
    return {"work_id": w, "author_id": a, "author_name": name, "publication_date": pd.Timestamp(date),
            "level": "A", "author_position": "middle", "title": f"t {w}", "abstract": "graph mining",
            "institution_ids": json.dumps(list(insts))}


def _corpus():
    r = [
        # T0: A–B (W1), B–C (W2), A–D (W3); E está na mesma instituição de A (W4, solo + F)
        _row("W1", "A", "Ana Souza", "2019-01-01", ["I1"]), _row("W1", "B", "Bruno Lima", "2019-01-01", ["I2"]),
        _row("W2", "B", "Bruno Lima", "2020-01-01", ["I2"]), _row("W2", "C", "Carla Dias", "2020-01-01", ["I3"]),
        _row("W3", "A", "Ana Souza", "2020-06-01", ["I1"]), _row("W3", "D", "João Silva", "2020-06-01", ["I4"]),
        _row("W4", "E", "Eva Rocha", "2021-03-01", ["I1"]), _row("W4", "F", "Fabio Reis", "2021-03-01", ["I5"]),
        # T1: A–C (nova, alcançável por 2 saltos), A–E (nova, via instituição), A–D2 (homônimo de D → M9)
        _row("W5", "A", "Ana Souza", "2022-05-01", ["I1"]), _row("W5", "C", "Carla Dias", "2022-05-01", ["I3"]),
        _row("W6", "A", "Ana Souza", "2023-01-01", ["I1"]), _row("W6", "E", "Eva Rocha", "2023-01-01", ["I1"]),
        _row("W7", "A", "Ana Souza", "2023-02-01", ["I1"]), _row("W7", "D2", "Joao Silva", "2023-02-01", ["I4"]),
    ]
    return pd.DataFrame(r)


def _enrich(tmp, corpus):
    from coauthor_rec.enrich.institutions import author_institution_years
    author_institution_years(corpus).to_parquet(tmp / "author_institution_years.parquet")
    pd.DataFrame({"institution_id": [f"I{i}" for i in range(1, 6)], "country": ["BR"] * 5}) \
        .to_parquet(tmp / "institutions.parquet")
    pd.DataFrame({"child": ["I4"], "parent": ["I1"]}).to_parquet(tmp / "institution_lineage.parquet")
    pd.DataFrame(columns=["institution_id", "other_id", "relationship"]).to_parquet(
        tmp / "institution_associated.parquet")
    pd.DataFrame({"work_id": ["W1", "W2", "W3", "W4", "W5"], "topic_id": ["T1", "T1", "T2", "T1", "T1"],
                  "score": [1.0] * 5, "rank": [1] * 5}).to_parquet(tmp / "work_topics.parquet")
    pd.DataFrame({"topic_id": ["T1", "T2"], "subfield_id": [1, 2], "field_id": [1, 1], "domain_id": [1, 1]}) \
        .to_parquet(tmp / "taxonomy.parquet")
    pd.DataFrame({"author_id": ["A", "C", "C"], "kind": ["employment"] * 3, "org_key": ["ror:x", "ror:x", "ror:y"],
                  "start": [2010.0, 2015.0, 2023.0], "end": [np.nan, 2018.0, np.nan]}) \
        .to_parquet(tmp / "author_affiliations_orcid.parquet")


def _works():
    return pd.DataFrame({"id": [f"W{i}" for i in range(1, 8)],
                         "venue_id": ["S1", "S1", "S2", "S2", "S1", "S1", "S1"],
                         "referenced_works": [json.dumps(r) for r in
                                              (["X9"], ["W1", "X9"], [], ["W3"], [], [], [])]})


def test_m9_flags_homonym_of_old_coauthor():
    names = {"D": {"joao silva"}, "D2": {"joao silva"}, "C": {"carla dias"}}
    assert m9_suspects({"A": {"D"}}, {"A": {"D2", "C"}}, names) == {("A", "D2")}


def test_protocol_applies_m9_and_keeps_raw_version():
    P = build_protocol(_corpus(), ["A"], {"modo": "calendario", "t0_ate": 2021}, cap=50)
    assert P.cutoff == 2021
    assert P.gt_raw["A"] == {"C", "E", "D2"}
    assert P.gt["A"] == {"C", "E"} and P.m9_pairs == {("A", "D2")}
    assert P.regimes["A"] == "cool"


def test_kg_t0_has_no_future_facts_and_is_valid(tmp_path):
    c = _corpus()
    _enrich(tmp_path, c)
    kg = build_kg_t0(c, _works(), tmp_path, cutoff=2021)
    assert set(kg["wrote"]["work_id"]) == {"W1", "W2", "W3", "W4"}
    assert set(kg["cites"]["cited_id"]) == {"X9", "W1", "W3"}
    assert len(kg["hasEmployment"]) == 2                      # vínculo de 2023 fica fora
    rep = validate_kg(kg, 2021)
    assert rep["valido"], rep["violacoes"]


def test_generators_scores_and_exclusion(tmp_path):
    c = _corpus()
    _enrich(tmp_path, c)
    kg = build_kg_t0(c, _works(), tmp_path, cutoff=2021)
    idx = KGIndex(kg, cap=50, cutoff=2021, texts=None, verbose=False)
    a, cc, e, d = (idx.aidx[x] for x in ("A", "C", "E", "D"))
    rows = np.array([a])
    cn = idx.scores("coautoria_cn", rows)[0]
    assert cn[cc] == 1 and cn[e] == 0                         # C via B; E não está a 2 saltos
    inst = idx.scores("instituicao", rows)[0]
    assert inst[e] > 0 and inst[cc] == 0                      # E compartilha I1 com A
    root = idx.scores("org_mae", rows)[0]
    assert root[d] > 0                                        # I4 é parte de I1
    cit = idx.scores("citacao", rows)[0]
    assert cit[idx.aidx["B"]] > 0 and cit[e] > 0              # W2 cita W1; W4 cita W3
    ex = idx.scores("ex_colegas", rows)[0]
    assert ex[cc] == 1                                        # ror:x em períodos sobrepostos
    ppr = idx.scores("ppr", rows)[0]
    assert ppr[cc] > 0 and ppr[e] == 0                        # E fora do componente de A
    exclude = [{idx.aidx["B"], d, a}]                         # coautores de T0 + o próprio
    ranked, pools = rank_candidates(idx.scores("topico", rows), exclude, idx.degree, top=10)
    assert a not in ranked[0] and idx.aidx["B"] not in ranked[0]
    assert set(pools[0]) == {cc, e, idx.aidx["F"]}


def test_ltr_pairs_labels_and_generation_ablation(tmp_path):
    from coauthor_rec.models.kg_ltr import build_pairs, feature_columns, GROUPS
    c = _corpus()
    _enrich(tmp_path, c)
    kg = build_kg_t0(c, _works(), tmp_path, cutoff=2021)
    idx = KGIndex(kg, cap=50, cutoff=2021, texts=None, verbose=False)
    P = build_protocol(c, ["A"], {"modo": "calendario", "t0_ate": 2021}, cap=50)
    gens = [g for g in ("coautoria_cn", "coautoria_aa", "coautoria_ra", "ppr", "instituicao", "org_mae",
                        "topico", "periodico", "citacao", "acoplamento", "ex_colegas", "popularidade")]
    groups = {k: v for k, v in GROUPS.items() if k != "texto"}
    pairs, reach = build_pairs(idx, kg, P.targets, P.train_graph, P.gt, gens=gens,
                               union_groups=groups, verbose=False)
    lab = dict(zip(idx.authors[pairs["cand"]], pairs["rotulo"]))
    assert lab["C"] == 1 and lab["E"] == 1 and lab.get("F", 0) == 0
    assert "B" not in lab and "D" not in lab                  # coautores de T0 excluídos
    r = reach.iloc[0]
    assert r["todos"] == 2 and r["sem_instituicao"] == 2      # E também vem por tópico/citação
    cols = feature_columns(["coautoria", "atividade"])
    assert "ppr_pos" in cols and "grau_cand" in cols and set(cols) <= set(pairs.columns)
