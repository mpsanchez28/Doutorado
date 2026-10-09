"""Testes das peças puras da coleta seeded (filtro de área e contagem com teto)."""
import pytest

from coauthor_rec.collect import openalex as O


def _work(wid, n_authors):
    return {"id": f"https://openalex.org/{wid}", "authorships": [
        {"author": {"id": f"https://openalex.org/A{wid}{i}", "display_name": f"Autor {i}"},
         "institutions": []} for i in range(n_authors)]}


def test_area_filter_prefers_topics_fields():
    assert O._area_filter({"field_ids": [20, 26]}) == {"primary_topic": {"field": {"id": "20|26"}}}
    assert O._area_filter({"concept_ids": ["C1"]}) == {"concepts": {"id": "C1"}}
    # campos têm prioridade sobre Concepts quando ambos existem
    assert "primary_topic" in O._area_filter({"field_ids": [17], "concept_ids": ["C1"]})
    with pytest.raises(ValueError):
        O._area_filter({})


def test_ingest_count_cap_keeps_work_but_does_not_count_consortium_authors():
    store = O._new_store()
    O._ingest(store, _work("W1", 3), count_cap=50)
    O._ingest(store, _work("W2", 120), count_cap=50)     # consórcio: fora da contagem
    assert len(store["seen_works"]) == 2                  # o trabalho fica no bruto
    assert len(store["author_ids"]) == 3                  # só os autores do W1 contam
    O._ingest(store, _work("W3", 120))                    # sem teto: conta todos
    assert len(store["author_ids"]) == 123
