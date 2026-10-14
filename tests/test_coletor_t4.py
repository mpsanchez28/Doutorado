"""Coletor do T4: teto de gasto nunca ultrapassado, contabilidade persistida e paginação (API simulada)."""
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("coletor_t4", os.path.join(ROOT, "scripts", "coletor_t4.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def fake_api(pages_per_lot):
    """Simula /works paginado por cursor: cada lote tem ``pages_per_lot`` páginas de 1 trabalho."""
    calls = []

    def _http(url, key, retries=6):
        calls.append(url)
        cur = url.split("cursor=")[1]
        n = 0 if cur == "%2A" else int(cur)
        nxt = str(n + 1) if n + 1 < pages_per_lot else None
        w = {"id": f"https://openalex.org/W{len(calls)}", "publication_date": "2016-01-01", "authorships": [
            {"author": {"id": "https://openalex.org/A1", "display_name": "X"}, "institutions": []}]}
        return {"results": [w], "meta": {"next_cursor": nxt}}
    return _http, calls


def test_budget_is_never_exceeded_and_ledger_persists(tmp_path, monkeypatch):
    _http, calls = fake_api(pages_per_lot=3)
    monkeypatch.setattr(C, "_http", _http)
    led = C.Ledger(tmp_path, limit=5)
    a, w = C.collect_lot(["A1"], "2015-01-01", "2019-12-31", 20, "en", None, led, "lote0")
    assert len(w) == 3 and led.spent == 3                      # 3 páginas = 3 créditos
    with pytest.raises(C.BudgetExceeded):                      # 2º lote precisaria de 3 > 2 restantes
        C.collect_lot(["A2"], "2015-01-01", "2019-12-31", 20, "en", None, led, "lote1")
    assert led.spent == 5 and len(calls) == 5                  # parou NO teto, sem consulta extra
    saved = json.loads((tmp_path / "gasto.json").read_text())
    assert saved["gasto_creditos"] == 5 and saved["limite_creditos"] == 5
    assert sum(1 for _ in open(tmp_path / "consultas.jsonl")) == 5
    led2 = C.Ledger(tmp_path, limit=5)                         # retomada lê o gasto persistido
    assert led2.spent == 5 and not led2.can(1)


def test_filter_reproduces_original_expansion_query(monkeypatch, tmp_path):
    _http, calls = fake_api(pages_per_lot=1)
    monkeypatch.setattr(C, "_http", _http)
    C.collect_lot(["A1", "A2"], "2015-01-01", "2016-12-31", 20, "en", None, C.Ledger(tmp_path, 10), "x")
    q = calls[0]
    for part in ("language%3Aen", "from_publication_date%3A2015-01-01", "to_publication_date%3A2016-12-31",
                 "primary_topic.field.id%3A20", "authorships.author.id%3AA1%7CA2", "per-page=200"):
        assert part in q


def test_enrich_lean_skips_cached_and_charges_per_query(tmp_path, monkeypatch):
    cache = tmp_path / "works.jsonl"
    cache.write_text('{"funders": [{"id": "https://openalex.org/F1"}], "id": "W1"}\n')
    assert C.cached_ids(cache) == {"W1"}                       # ignora ids aninhados (URLs)
    calls = []

    def _http(url, key, retries=6):
        calls.append(url)
        return {"results": [{"id": "https://openalex.org/W2"}]}
    monkeypatch.setattr(C, "_http", _http)
    led = C.Ledger(tmp_path / "led", limit=1)
    n_todo, n_cached, recs = C.enrich_lean("works", ["W1", "W2", "W3"], "id,topics", cache, "x@y", None, led)
    assert (n_todo, n_cached, len(calls), led.spent) == (2, 1, 1, 1)      # 1 consulta para W2+W3
    assert C.cached_ids(cache) == {"W1", "W2", "W3"}            # W3 gravado como _missing
    import pytest
    with pytest.raises(C.BudgetExceeded):                      # teto esgotado: nenhuma consulta nova
        C.enrich_lean("works", ["W9"], "id", cache, "x@y", None, led)
    assert len(calls) == 1
