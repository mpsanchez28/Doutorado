"""Testes da higienização de autores (pessoa canônica, níveis, vínculo, elegibilidade)."""
import json

import pandas as pd

from coauthor_rec.data import hygiene as H
from coauthor_rec.data.orcid import parse_record

CRIT = {"require_orcid": True, "forbid_id_conflict": True, "min_claimed_works": 1,
        "min_works_with_ror": 1, "min_works": 2, "max_works_per_year": 30,
        "max_institutions_same_year": 3, "max_name_mismatch_rate": 0.0,
        "require_small_team_work": True}
CFG = {"reject_name_mismatch": True, "min_edge_level": "C", "author_criteria": CRIT}


def row(work, aid, name, orcid=None, raw=None, doi=None, rors=(), inames=(), ctry=(),
        date="2015-01-01", insts=None):
    return {"work_id": work, "author_id": aid, "author_name": name, "author_orcid": orcid,
            "raw_author_name": raw if raw is not None else name, "doi": doi,
            "institution_rors": json.dumps(list(rors)), "institution_names": json.dumps(list(inames)),
            "countries": json.dumps(list(ctry)), "publication_date": date,
            "institution_ids": json.dumps(insts if insts is not None else [f"I{r}" for r in rors])}


CLAIMS = {
    # Ana: reivindica W1; vínculo com a USP por ROR
    "0000-0001": {"exists": True, "names": ["Ana Souza"], "dois": ["10.1/w1"],
                  "affiliations": [{"ror": "036rp1748", "name": "Universidade de São Paulo",
                                    "country": "BR", "start": 2010, "end": None}]},
    # Bruno: vínculo só por RINGGOLD (sem ROR) — casa por nome+país
    "0000-0002": {"exists": True, "names": ["Bruno Lima"], "dois": [],
                  "affiliations": [{"ror": None, "name": "MIT", "country": "US",
                                    "start": 2000, "end": 2012}]},
    # ORCID cujo registro é de OUTRA pessoa (nome incompatível)
    "0000-0009": {"exists": True, "names": ["Zhang Wei"], "dois": [], "affiliations": []},
}


def test_names_compatible():
    assert H.names_compatible("J. Smith", "John Smith") is True
    assert H.names_compatible("Zhang Wei", "Wei Zhang") is True
    assert H.names_compatible("José da Silva", "Jose Silva") is True       # acento + partícula
    assert H.names_compatible("Ana Souza", "Carlos Pereira") is False
    assert H.names_compatible("Ana", None) is None


def test_canonicalize_merges_fragmented_ids_and_flags_conflict():
    df = pd.DataFrame([row("W1", "A1", "Ana Souza", "0000-0001"),
                       row("W2", "A2", "Ana Souza", "0000-0001"),      # mesmo ORCID, outro id
                       row("W3", "A3", "Rui Alves", "0000-0003"),
                       row("W4", "A3", "Rui Alves", "0000-0004")])     # 1 id, 2 ORCIDs
    out, st = H.canonicalize(df)
    assert out.loc[out.author_id == "A1", "canonical_id"].iloc[0] == "orcid:0000-0001"
    assert out.loc[out.author_id == "A2", "canonical_id"].iloc[0] == "orcid:0000-0001"
    assert out.loc[out.author_id == "A3", "id_conflict"].all()
    assert st["orcids_fragmented"] == 1 and st["author_ids_merged"] == 2
    assert st["author_ids_conflict"] == 1


def test_levels_A_B_C_X_and_orcid_name_downgrade():
    df = pd.DataFrame([
        row("W1", "A1", "Ana Souza", "0000-0001", doi="10.1/w1"),        # A: reivindicado
        row("W2", "A1", "Ana Souza", "0000-0001", doi="10.1/w2"),        # B: não reivindicado
        row("W3", "A5", "Carla Dias"),                                   # C: sem ORCID
        row("W4", "A6", "Davi Rocha", raw="Pedro Nunes"),                # X: nome do artigo ≠
        row("W5", "A7", "Bruno Lima", "0000-0009", doi="10.1/w5"),       # ORCID de outra pessoa → C
    ])
    df, _ = H.canonicalize(df)
    lv = H.authorship_levels(df, CLAIMS).set_index("work_id")["level"]
    assert list(lv[["W1", "W2", "W3", "W4", "W5"]]) == ["A", "B", "C", "X", "C"]


def test_institution_levels_ror_name_country_and_year():
    df = pd.DataFrame([
        row("W1", "A1", "Ana Souza", "0000-0001", rors=["036rp1748"]),                    # I1 ROR
        row("W2", "A2", "Bruno Lima", "0000-0002", rors=["042nb2s44"], inames=["MIT"],
            ctry=["US"], date="2011-05-01"),                                              # I1 nome+país
        row("W3", "A2", "Bruno Lima", "0000-0002", rors=["042nb2s44"], inames=["MIT"],
            ctry=["US"], date="2020-05-01"),                                              # ano fora → I2
        row("W4", "A5", "Carla Dias"),                                                    # I3
    ])
    df, _ = H.canonicalize(df)
    il = H.authorship_levels(df, CLAIMS).set_index("work_id")["inst_level"]
    assert list(il[["W1", "W2", "W3", "W4"]]) == ["I1", "I1", "I2", "I3"]


def test_eligibility_criteria_and_funnel():
    df = pd.DataFrame([
        # Ana: elegível (ORCID, 1 reivindicado, ROR, 2 trabalhos, equipe pequena)
        row("W1", "A1", "Ana Souza", "0000-0001", doi="10.1/w1", rors=["036rp1748"]),
        row("W2", "A1", "Ana Souza", "0000-0001", doi="10.1/w2", rors=["036rp1748"]),
        # Carla: sem ORCID → reprova E1
        row("W1", "A5", "Carla Dias", rors=["x"]), row("W2", "A5", "Carla Dias", rors=["x"]),
        # Bruno: ORCID mas nada reivindicado → reprova E3
        row("W1", "A2", "Bruno Lima", "0000-0002", doi="10.1/w1", rors=["y"]),
        row("W2", "A2", "Bruno Lima", "0000-0002", doi="10.1/w2", rors=["y"]),
    ])
    df, _ = H.canonicalize(df)
    df = H.authorship_levels(df, CLAIMS)
    t = H.author_table(df, CRIT, max_coauthors=50)
    assert t.loc["orcid:0000-0001", "eligible"]
    assert not t.loc["A5", "E1_orcid"]
    assert not t.loc["orcid:0000-0002", "E3_reivindicado"]
    f = H.funnel(t)
    assert f[0]["restantes"] == 3 and f[-1]["restantes"] == 1


def test_e6_multiaffiliation_on_one_paper_is_plausible_but_disjoint_groups_are_not():
    # 4 instituições co-listadas numa mesma autoria = 1 grupo (legítimo)
    assert H._n_components([["U", "H", "I", "L"]]) == 1
    # mesma combinação repetida + subconjuntos continuam 1 grupo
    assert H._n_components([["U", "H"], ["H", "I"], ["U"]]) == 1
    # 4 trabalhos no ano, cada um num lugar desconexo = 4 grupos (identidade fundida?)
    assert H._n_components([["A"], ["B"], ["C"], ["D"]]) == 4
    multi = [row(f"W{i}", "A1", "Ana Souza", "0000-0001", doi="10.1/w1" if i == 1 else None,
                 rors=["r"], insts=["U", "H", "I", "L"]) for i in (1, 2)]
    fused = [row(f"V{i}", "A2", "Bruno Lima", "0000-0002", rors=["r"], insts=[f"X{i}"])
             for i in range(1, 6)]
    df, _ = H.canonicalize(pd.DataFrame(multi + fused))
    t = H.author_table(H.authorship_levels(df, CLAIMS), CRIT, 50)
    assert t.loc["orcid:0000-0001", "E6_plausivel"]
    assert not t.loc["orcid:0000-0002", "E6_plausivel"]


def test_hygienize_unifies_person_across_ids_in_corpus():
    df = pd.DataFrame([
        row("W1", "A1", "Ana Souza", "0000-0001", doi="10.1/w1", rors=["036rp1748"], date="2012-01-01"),
        row("W1", "A9", "Rui Alves", rors=["z"], date="2012-01-01"),
        row("W2", "A2", "Ana Souza", "0000-0001", rors=["036rp1748"], date="2020-01-01"),  # fragmento
        row("W2", "A9", "Rui Alves", rors=["z"], date="2020-01-01"),
        row("W3", "A6", "Davi Rocha", raw="Pedro Nunes"),                                  # X sai
    ])
    corpus, table, rep = H.hygienize(df, CLAIMS, CFG, max_coauthors=50)
    ana = corpus[corpus.author_id == "orcid:0000-0001"]
    assert set(ana.work_id) == {"W1", "W2"}                 # mesma pessoa nos dois períodos
    assert "W3" not in set(corpus.work_id)
    assert rep["canonicalizacao"]["orcids_fragmented"] == 1
    assert rep["autorias"]["nivel_X"] == 1


def test_parse_record_extracts_names_dois_and_affiliations():
    rec = {"person": {"name": {"given-names": {"value": "Josiah"}, "family-name": {"value": "Carberry"},
                               "credit-name": None},
                      "other-names": {"other-name": [{"content": "J. S. Carberry"}]}},
           "activities-summary": {
               "works": {"group": [{"external-ids": {"external-id": [
                   {"external-id-type": "doi", "external-id-value": "10.5555/ABC"}]}}]},
               "employments": {"affiliation-group": [{"summaries": [{"employment-summary": {
                   "organization": {"name": "Brown University", "address": {"country": "US"},
                                    "disambiguated-organization": {
                                        "disambiguated-organization-identifier": "https://ror.org/05gq02987",
                                        "disambiguation-source": "ROR"}},
                   "start-date": {"year": {"value": "1929"}}, "end-date": None}}]}]}}}
    c = parse_record("0000-0002-1825-0097", rec)
    assert c["exists"] and "Josiah Carberry" in c["names"] and "J. S. Carberry" in c["names"]
    assert c["dois"] == ["10.5555/abc"]
    a = c["affiliations"][0]
    assert a["ror"] == "05gq02987" and a["country"] == "US" and a["start"] == 1929
    assert parse_record("x", None)["exists"] is False


def test_orcid_rate_limiter_gives_up_and_fetch_stops_fast(tmp_path, monkeypatch):
    import time
    import pytest
    from coauthor_rec.data import orcid as OR
    lim = OR._RateLimiter(100, max_pause=0.01, give_up_after=0.02)
    with pytest.raises(OR.OrcidRateLimited):
        for _ in range(10):
            lim.next = 0                       # simula janelas de pausa já vencidas
            lim.throttle("0.01")
    # fetch_claims: falha persistente → cancela o restante e sai rápido (não espera tudo)
    calls = []

    def fake_get(url, limiter=None, token=None, retries=6):
        calls.append(url)
        time.sleep(0.01)
        raise OR.OrcidRateLimited("429 persistente")
    monkeypatch.setattr(OR, "_get", fake_get)
    monkeypatch.setattr(OR, "orcid_token", lambda: None)
    t = time.time()
    with pytest.raises(OR.OrcidRateLimited):
        OR.fetch_claims([f"0000-{i:04d}" for i in range(2000)], tmp_path, 1000, verbose=False, workers=4)
    assert time.time() - t < 5 and len(calls) < 200


def test_orcid_get_retries_transient_incomplete_read(monkeypatch):
    import http.client
    import io
    import json as _json
    from coauthor_rec.data import orcid as OR
    calls = {"n": 0}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def flaky(req, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http.client.IncompleteRead(b"")       # resposta cortada na 1ª tentativa
        return Resp(_json.dumps({"ok": 1}).encode())
    monkeypatch.setattr(OR.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(OR.time, "sleep", lambda s: None)
    assert OR._get("https://pub.orcid.org/v3.0/x/record") == {"ok": 1} and calls["n"] == 2
