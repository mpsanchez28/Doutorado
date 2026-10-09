"""Camada 2 — instituições (OpenAlex Institutions, que incorpora o ROR).

Para cada instituição das autorias higienizadas: ROR, tipo (education, healthcare,
company, government, facility, nonprofit, archive, other), país, cidade/coordenadas,
Wikidata, hierarquia (``lineage``: a instituição e suas ancestrais) e associações
(parent/child/related). Do corpus vem o vínculo datado autor × instituição × ano.
"""
from __future__ import annotations

import json

import pandas as pd

from .openalex_cache import short_id


def _jlist(v) -> list:
    if isinstance(v, list):
        return v
    try:
        out = json.loads(v) if isinstance(v, str) and v else []
        return out if isinstance(out, list) else []
    except ValueError:
        return []


def author_institution_years(corpus: pd.DataFrame) -> pd.DataFrame:
    """(author_id, work_id, institution_id, year) — vínculo datado vindo das autorias."""
    years = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
    rows = [{"author_id": a, "work_id": w, "institution_id": i, "year": None if pd.isna(y) else int(y)}
            for a, w, blob, y in zip(corpus["author_id"], corpus["work_id"],
                                     corpus["institution_ids"], years)
            for i in _jlist(blob) if i]
    return pd.DataFrame(rows, columns=["author_id", "work_id", "institution_id", "year"]).drop_duplicates()


def institutions_table(records: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for iid, r in records.items():
        if r.get("_missing"):
            continue
        geo = r.get("geo") or {}
        lineage = [short_id(x) for x in (r.get("lineage") or []) if short_id(x)]
        rows.append({
            "institution_id": iid, "name": r.get("display_name"),
            "ror": short_id(r.get("ror")), "type": r.get("type"),
            "country": r.get("country_code"), "city": geo.get("city"),
            "latitude": geo.get("latitude"), "longitude": geo.get("longitude"),
            "wikidata": short_id((r.get("ids") or {}).get("wikidata")),
            "parents": [x for x in lineage if x != iid],
        })
    return pd.DataFrame(rows, columns=["institution_id", "name", "ror", "type", "country", "city",
                                       "latitude", "longitude", "wikidata", "parents"])


def lineage_edges(inst: pd.DataFrame) -> pd.DataFrame:
    """Arestas PART_OF (instituição → ancestral), a partir do ``lineage`` do OpenAlex."""
    rows = [{"child": c, "parent": p} for c, ps in zip(inst["institution_id"], inst["parents"]) for p in ps]
    return pd.DataFrame(rows, columns=["child", "parent"])


def associated_edges(records: dict[str, dict]) -> pd.DataFrame:
    """Associações declaradas (parent / child / related) entre instituições."""
    rows = [{"institution_id": iid, "other_id": short_id(a.get("id")), "relationship": a.get("relationship")}
            for iid, r in records.items() if not r.get("_missing")
            for a in r.get("associated_institutions") or []]
    return pd.DataFrame(rows, columns=["institution_id", "other_id", "relationship"])


def coverage(inst: pd.DataFrame, aiy: pd.DataFrame, n_authorships: int) -> dict:
    return {
        "instituicoes": int(len(inst)),
        "com_ror": round(float(inst["ror"].notna().mean()), 4) if len(inst) else 0,
        "com_wikidata": round(float(inst["wikidata"].notna().mean()), 4) if len(inst) else 0,
        "com_ancestral": round(float(inst["parents"].map(bool).mean()), 4) if len(inst) else 0,
        "paises": int(inst["country"].nunique()),
        "tipos": inst["type"].value_counts().to_dict(),
        "autorias_com_instituicao": round(aiy[["author_id", "work_id"]].drop_duplicates().shape[0]
                                          / max(n_authorships, 1), 4),
    }
