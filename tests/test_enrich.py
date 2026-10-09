"""Testes do enriquecimento (camadas 1–3) e da ontologia — dados sintéticos, sem rede."""
import json

import pandas as pd
import pytest

from coauthor_rec.enrich import careers as CA
from coauthor_rec.enrich import institutions as IN
from coauthor_rec.enrich import topics as TO

T = lambda tid, name, sc, sf, f="20", d="2": {  # noqa: E731
    "id": f"https://openalex.org/{tid}", "display_name": name, "score": sc,
    "subfield": {"id": f"https://openalex.org/subfields/{sf}", "display_name": f"SF{sf}"},
    "field": {"id": f"https://openalex.org/fields/{f}", "display_name": f"F{f}"},
    "domain": {"id": f"https://openalex.org/domains/{d}", "display_name": f"D{d}"}}

WORKS = {
    "W1": {"id": "W1", "primary_topic": {"id": "https://openalex.org/T1"},
           "topics": [T("T1", "Macro", 0.9, "2002"), T("T2", "Finanças", 0.4, "2003")],
           "keywords": [{"id": "https://openalex.org/keywords/inflation", "display_name": "inflation", "score": 0.7}]},
    "W2": {"id": "W2", "primary_topic": {"id": "https://openalex.org/T3"},
           "topics": [T("T3", "Física", 0.99, "3106", f="31", d="3")]},
    "W3": {"id": "W3", "_missing": True},
}
CORPUS = pd.DataFrame({
    "work_id": ["W1", "W1", "W2"], "author_id": ["orcid:A", "orcid:B", "orcid:A"],
    "author_id_openalex": ["A1", "A2", "A1"], "author_name": ["Ana Souza", "Bruno Lima", "Ana Souza"],
    "institution_ids": ['["I1"]', '["I2"]', '["I1","I3"]'],
    "publication_date": ["2015-01-01", "2015-01-01", "2018-06-01"],
    "title": ["t1", "t1", "t2"], "doi": ["10.1/w1", "10.1/w1", None],
    "level": ["A", "B", "A"], "inst_level": ["I1", "I2", "I2"], "author_position": ["first", "last", "first"]})


def test_topics_hierarchy_profile_and_coverage():
    wt = TO.work_topics(WORKS)
    assert len(wt) == 3 and set(wt["work_id"]) == {"W1", "W2"}          # W3 ausente ignorado
    assert wt.loc[wt.topic_id == "T1", "is_primary"].item()
    assert TO.taxonomy(wt).set_index("topic_id").loc["T3", "field_id"] == "31"
    prof = TO.author_profile(CORPUS, wt, "subfield")
    assert abs(prof.groupby("author_id")["weight"].sum() - 1).max() < 1e-9   # normalizado
    cov = TO.coverage(wt, n_works=3, base_field_ids=[20])
    assert cov["primario_no_campo_da_base"] == 0.5                          # W2 é de física
    assert len(TO.work_keywords(WORKS)) == 1


def test_institutions_lineage_and_dated_affiliation():
    recs = {"I1": {"id": "I1", "display_name": "USP", "ror": "https://ror.org/036rp1748",
                   "type": "education", "country_code": "BR", "geo": {"city": "São Paulo"},
                   "lineage": ["https://openalex.org/I1"], "ids": {"wikidata": "https://www.wikidata.org/wiki/Q835960"},
                   "associated_institutions": [{"id": "https://openalex.org/I3", "relationship": "child"}]},
            "I3": {"id": "I3", "display_name": "Hospital Univ.", "ror": None, "type": "healthcare",
                   "country_code": "BR", "geo": {}, "lineage": ["https://openalex.org/I3", "https://openalex.org/I1"],
                   "ids": {}}}
    inst = IN.institutions_table(recs)
    assert inst.set_index("institution_id").loc["I3", "parents"] == ["I1"]
    assert inst.set_index("institution_id").loc["I1", "wikidata"] == "Q835960"
    assert IN.lineage_edges(inst).to_dict("records") == [{"child": "I3", "parent": "I1"}]
    aiy = IN.author_institution_years(CORPUS)
    assert set(aiy[aiy.author_id == "orcid:A"]["institution_id"]) == {"I1", "I3"}
    assert IN.associated_edges(recs).iloc[0]["relationship"] == "child"


def _cache(tmp_path):
    cl = {"A": [{"section": "employments", "name": "MIT", "country": "US", "ror": None,
                 "other_id": "RINGGOLD:2167", "start": 2010, "end": 2014},
                {"section": "educations", "name": "USP", "country": "BR", "ror": "036rp1748",
                 "other_id": None, "start": 2004, "end": 2009}],
          "B": [{"section": "employments", "name": "Massachusetts Inst. Tech.", "country": "US",
                 "ror": None, "other_id": "RINGGOLD:2167", "start": 2012, "end": None}],
          "C": [{"section": "employments", "name": "MIT", "country": "US", "ror": None,
                 "other_id": "RINGGOLD:2167", "start": 2020, "end": None}]}
    for o, affs in cl.items():
        (tmp_path / f"{o}.json").write_text(json.dumps({"orcid": o, "exists": True, "affiliations": affs}))
    return CA.career_affiliations(["orcid:A", "orcid:B", "orcid:C", "W9"], tmp_path,
                                  ["employments"], ["educations"])


def test_careers_org_key_summary_and_excolleagues_without_leakage(tmp_path):
    aff = _cache(tmp_path)
    assert set(aff["org_key"]) == {"RINGGOLD:2167", "ror:036rp1748"}       # ROR > id ORCID > nome
    s = CA.career_summary(aff, cutoff=2015)
    assert s.loc["orcid:A", "ultima_formacao"] == 2009
    assert s.loc["orcid:C", "n_empregadores"] == 0                          # vínculo após o corte
    idx = CA.ExColleagueIndex(aff)
    assert idx.shared("orcid:A", "orcid:B", cutoff=2015) == ["RINGGOLD:2167"]   # 2012–2014 sobrepõe
    assert idx.shared("orcid:A", "orcid:C", cutoff=2025) == []              # sem sobreposição
    assert idx.shared("orcid:B", "orcid:C", cutoff=2018) == []              # C começa depois do corte
    assert idx.shared("orcid:B", "orcid:C", cutoff=2022) == ["RINGGOLD:2167"]


def test_ontology_sample_is_valid_and_queryable(tmp_path):
    pytest.importorskip("rdflib")
    from rdflib import Graph
    from coauthor_rec.graph import ontology as ON
    wt = TO.work_topics(WORKS)
    inst = IN.institutions_table({"I1": {"id": "I1", "display_name": "USP", "ror": "https://ror.org/036rp1748",
                                         "type": "education", "country_code": "BR", "geo": {},
                                         "lineage": ["https://openalex.org/I1"], "ids": {}}})
    aff = _cache(tmp_path)
    g = ON.build_sample_graph(CORPUS, ["orcid:A"], wt, inst, aff, CA.ExColleagueIndex(aff), cutoff=2015)
    tbox = Graph().parse("configs/ontology/coauthor-rec.ttl")
    v = ON.validate(g, tbox)
    assert v["nao_declaradas"] == [] and v["triplas"] > 50
    q = ON.run_queries(g)
    assert ["A", 2] in q["autorias_por_nivel_de_evidencia"]
    assert q["coautores_ex_colegas"] == [[1]]          # A e B: coautores e ex-colegas (MIT)
    assert Graph().parse(data=g.serialize(format="turtle"), format="turtle")  # Turtle reabre
