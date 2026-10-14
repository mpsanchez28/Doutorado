"""Cópia congelada: isolamento do cache global, falha explícita em divergência ou ausência.

Usa só diretórios temporários (nunca o cache de produção)."""
import json

import pytest

from coauthor_rec.data.snapshot import SnapshotError, create_snapshot, verify_snapshot
from coauthor_rec.enrich.openalex_cache import load_cache


def _global(tmp_path):
    g = tmp_path / "global"
    (g / "orcid").mkdir(parents=True)
    (g / "openalex").mkdir()
    (g / "raw").mkdir()
    (g / "orcid" / "0000-0001.json").write_text(json.dumps({"orcid": "0000-0001", "dois": ["10.1/a"]}))
    (g / "orcid" / "0000-0002.json").write_text(json.dumps({"orcid": "0000-0002", "dois": []}))
    (g / "openalex" / "works.jsonl").write_text(
        "".join(json.dumps({"id": i, "t": i}) + "\n" for i in ("W1", "W2", "W3")))
    (g / "raw" / "seeds.csv").write_text("author_id\nA1\n")
    return g


def _snap(g, dest):
    return create_snapshot(dest, {"raw/economia/seeds.csv": g / "raw" / "seeds.csv"}, orcid_dir=g / "orcid",
                           orcid_ids=["0000-0001", "0000-0009"],
                           jsonl_subsets={"openalex/works.jsonl": (g / "openalex" / "works.jsonl", {"W1", "W3"})})


def test_changes_to_global_cache_do_not_reach_the_frozen_copy(tmp_path):
    g = _global(tmp_path)
    s = tmp_path / "snap"
    man = _snap(g, s)
    assert man["orcid"]["registros"] == 1 and man["orcid"]["ausentes_na_origem"] == 1   # ausente ≠ buscado
    assert (s / "orcid_ausentes.txt").read_text() == "0000-0009\n"
    # o cache global muda depois do congelamento
    (g / "orcid" / "0000-0001.json").write_text(json.dumps({"orcid": "0000-0001", "dois": ["10.1/a", "10.1/b"]}))
    (g / "orcid" / "0000-0009.json").write_text(json.dumps({"orcid": "0000-0009", "dois": ["10.1/c"]}))
    with open(g / "openalex" / "works.jsonl", "a") as fh:
        fh.write(json.dumps({"id": "W1", "t": "novo"}) + "\n")
    assert verify_snapshot(s)["ok"]
    assert json.loads((s / "orcid" / "0000-0001.json").read_text())["dois"] == ["10.1/a"]
    assert not (s / "orcid" / "0000-0009.json").exists()
    assert set(load_cache(s / "openalex", "works")) == {"W1", "W3"}
    assert load_cache(s / "openalex", "works")["W1"]["t"] == "W1"


def test_tampering_or_missing_inputs_fail_explicitly(tmp_path):
    g = _global(tmp_path)
    s = tmp_path / "snap"
    _snap(g, s)
    f = s / "orcid" / "0000-0001.json"
    f.chmod(0o644)
    f.write_text("{}")
    with pytest.raises(SnapshotError, match="divergente"):
        verify_snapshot(s)
    s2 = tmp_path / "snap2"
    _snap(g, s2)
    (s2 / "raw" / "economia" / "seeds.csv").unlink()
    with pytest.raises(SnapshotError, match="ausente"):
        verify_snapshot(s2)
    with pytest.raises(SnapshotError, match="obrigatória ausente"):
        create_snapshot(tmp_path / "snap3", {"raw/x.csv": g / "nao_existe.csv"})


def test_sealed_copy_is_read_only_and_not_overwritten(tmp_path):
    g = _global(tmp_path)
    s = tmp_path / "snap"
    _snap(g, s)
    assert not (s / "raw" / "economia" / "seeds.csv").stat().st_mode & 0o222
    assert not (s / "raw" / "economia" / "seeds.csv").is_symlink()
    with pytest.raises(SnapshotError, match="já existe"):
        _snap(g, s)


def test_partial_line_from_concurrent_write_fails(tmp_path):
    g = _global(tmp_path)
    with open(g / "openalex" / "works.jsonl", "a") as fh:
        fh.write('{"id": "W4", "t"')                       # gravação concorrente interrompida
    with pytest.raises(SnapshotError, match="incompleta"):
        _snap(g, tmp_path / "snap")
