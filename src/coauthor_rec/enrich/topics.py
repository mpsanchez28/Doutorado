"""Camada 1 — semântica temática a partir dos OpenAlex Topics.

Cada trabalho tem até ~3 tópicos com score; cada tópico pertence a uma hierarquia fixa
tópico → subcampo → campo → domínio (campos = classificação ASJC). Diferente dos Concepts,
a hierarquia é única por tópico e o score acompanha cada atribuição.

Saídas: ``work_topics`` (trabalho × tópico, com hierarquia e score), ``taxonomy`` (tópicos
únicos com seus ancestrais), ``work_keywords`` e o perfil temático do autor por nível.
"""
from __future__ import annotations

import pandas as pd

from .openalex_cache import short_id


def _name(d):
    return (d or {}).get("display_name")


def work_topics(records: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for wid, rec in records.items():
        if rec.get("_missing"):
            continue
        primary = short_id((rec.get("primary_topic") or {}).get("id"))
        for rank, t in enumerate(rec.get("topics") or [], 1):
            tid = short_id(t.get("id"))
            rows.append({
                "work_id": wid, "topic_id": tid, "topic": t.get("display_name"),
                "score": float(t.get("score") or 0.0), "rank": rank, "is_primary": tid == primary,
                "subfield_id": short_id((t.get("subfield") or {}).get("id")), "subfield": _name(t.get("subfield")),
                "field_id": short_id((t.get("field") or {}).get("id")), "field": _name(t.get("field")),
                "domain_id": short_id((t.get("domain") or {}).get("id")), "domain": _name(t.get("domain")),
            })
    return pd.DataFrame(rows, columns=["work_id", "topic_id", "topic", "score", "rank", "is_primary",
                                       "subfield_id", "subfield", "field_id", "field",
                                       "domain_id", "domain"])


def taxonomy(wt: pd.DataFrame) -> pd.DataFrame:
    """Tópicos únicos com seus ancestrais (base da hierarquia SKOS na ontologia)."""
    cols = ["topic_id", "topic", "subfield_id", "subfield", "field_id", "field", "domain_id", "domain"]
    return wt[cols].drop_duplicates("topic_id").sort_values("topic_id").reset_index(drop=True)


def work_keywords(records: dict[str, dict]) -> pd.DataFrame:
    rows = [{"work_id": wid, "keyword_id": short_id(k.get("id")), "keyword": k.get("display_name"),
             "score": float(k.get("score") or 0.0)}
            for wid, rec in records.items() if not rec.get("_missing")
            for k in rec.get("keywords") or []]
    return pd.DataFrame(rows, columns=["work_id", "keyword_id", "keyword", "score"])


def author_profile(corpus: pd.DataFrame, wt: pd.DataFrame, level: str = "subfield",
                   work_ids=None) -> pd.DataFrame:
    """Perfil temático do autor: soma dos scores dos tópicos dos seus trabalhos, agregada no
    ``level`` (topic | subfield | field), normalizada para somar 1 por autor.

    ``work_ids`` restringe aos trabalhos de um período (ex.: só T0, sem vazamento).
    """
    key = {"topic": "topic_id", "subfield": "subfield_id", "field": "field_id"}[level]
    aw = corpus[["author_id", "work_id"]].drop_duplicates()
    if work_ids is not None:
        aw = aw[aw["work_id"].isin(set(work_ids))]
    prof = (aw.merge(wt[["work_id", key, "score"]], on="work_id")
            .groupby(["author_id", key], as_index=False)["score"].sum())
    prof["weight"] = prof["score"] / prof.groupby("author_id")["score"].transform("sum")
    return prof.rename(columns={key: "unit"})[["author_id", "unit", "weight"]]


def coverage(wt: pd.DataFrame, n_works: int, base_field_ids=None) -> dict:
    per_work = wt.groupby("work_id").size()
    out = {
        "trabalhos_com_topico": int(per_work.size),
        "cobertura": round(per_work.size / max(n_works, 1), 4),
        "topicos_por_trabalho_media": round(float(per_work.mean()), 2) if len(per_work) else 0,
        "topicos_distintos": int(wt["topic_id"].nunique()),
        "subcampos_distintos": int(wt["subfield_id"].nunique()),
        "campos_distintos": int(wt["field_id"].nunique()),
    }
    if base_field_ids:
        prim = wt[wt["is_primary"]]
        out["primario_no_campo_da_base"] = round(float(prim["field_id"].isin(
            {str(f) for f in base_field_ids}).mean()), 4) if len(prim) else None
    return out
