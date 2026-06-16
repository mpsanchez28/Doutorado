"""Testes do coletor que não dependem de rede:
dispatcher por modo, validações de config e extração de registros.
"""
import json

import pytest

from coauthor_rec.collect import openalex as OA


BASE_CFG = {
    "api": {"mailto": "test@example.com", "per_page": 50, "max_retries": 1},
    "filters": {"from_publication_year": 2004, "languages": ["en"]},
    "seed": {"type": "work", "id": None},
    "snowball": {"max_depth": 2, "target_works": 100, "max_authors_per_level": 10},
    "thematic": {"concept_ids": [], "min_concept_score": 0.3, "target_works": 100},
}


def test_dispatcher_unknown_mode(tmp_path):
    cfg = dict(BASE_CFG, mode="banana")
    with pytest.raises(ValueError, match="modo de coleta desconhecido"):
        OA.collect(cfg, tmp_path)


def test_snowball_requires_seed(tmp_path):
    cfg = dict(BASE_CFG, mode="snowball")
    with pytest.raises(ValueError, match="seed.id"):
        OA.collect(cfg, tmp_path)


def test_thematic_requires_concepts(tmp_path):
    cfg = dict(BASE_CFG, mode="thematic")
    with pytest.raises(ValueError, match="concept_ids"):
        OA.collect(cfg, tmp_path)


def test_hybrid_requires_concepts_and_seed(tmp_path):
    # sem concept_ids -> erro de tema
    cfg = dict(BASE_CFG, mode="hybrid")
    with pytest.raises(ValueError, match="concept_ids"):
        OA.collect(cfg, tmp_path)
    # com concept_ids mas sem seed.id -> erro de semente
    cfg = dict(BASE_CFG, mode="hybrid",
               thematic={"concept_ids": ["C1"], "min_concept_score": 0.3, "target_works": 100})
    with pytest.raises(ValueError, match="seed.id"):
        OA.collect(cfg, tmp_path)


def test_short_id():
    assert OA._short_id("https://openalex.org/W123") == "W123"
    assert OA._short_id("A55") == "A55"
    assert OA._short_id(None) is None


def test_extract_records_and_ingest():
    work = {
        "id": "https://openalex.org/W1",
        "publication_date": "2020-01-01",
        "title": "T",
        "abstract_inverted_index": {"redes": [0], "academicas": [1]},
        "language": "en",
        "primary_location": {"source": {"id": "https://openalex.org/S9",
                                         "display_name": "Venue", "issn_l": "1234-5678"}},
        "cited_by_count": 3,
        "referenced_works": ["https://openalex.org/W2"],
        "concepts": [{"id": "https://openalex.org/C1", "display_name": "CS", "score": 0.8}],
        "authorships": [
            {"author": {"id": "https://openalex.org/A1", "display_name": "Autor 1"},
             "institutions": [{"id": "https://openalex.org/I1"}]},
            {"author": {"id": "https://openalex.org/A2", "display_name": "Autor 2"},
             "institutions": []},
        ],
    }
    a_rows, w_row = OA._extract_records(work)
    assert w_row["id"] == "W1"
    assert w_row["abstract"] == "redes academicas"
    assert w_row["venue_issn_l"] == "1234-5678"
    assert json.loads(w_row["concepts"])[0]["id"] == "C1"
    assert {r["author_id"] for r in a_rows} == {"A1", "A2"}

    store = OA._new_store()
    authors = OA._ingest(store, work)
    assert set(authors) == {"A1", "A2"}
    assert OA._ingest(store, work) == []  # work repetido é ignorado
    assert len(store["work_rows"]) == 1
