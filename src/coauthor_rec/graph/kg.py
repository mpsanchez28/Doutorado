"""KG T0 materializado por base — as instâncias da ontologia (configs/ontology/coauthor-rec.ttl).

A amostra RDF (``graph/ontology.py``) serve para validar e consultar o esquema; os modelos
precisam do grafo INTEIRO de cada base. Aqui ele é materializado como uma tabela por relação
da ontologia (parquet), cada fato com o ano em que passou a valer, e cortado no fim de T0:
só entra o que já era conhecido até ``cutoff``. É esse corte que impede vazamento — o KG é
uma fotografia do mundo em 31/12/``cutoff``.

Relações (nome = propriedade da ontologia):

=====================  ==========================================  =========================
relação                colunas                                     origem
=====================  ==========================================  =========================
wrote                  author_id, work_id, year, level, position   corpus higienizado
atInstitution          author_id, work_id, institution_id, year    autorias (camada 2)
partOf                 child, parent                               lineage OpenAlex/ROR
relatedInstitution     institution_id, other_id, relationship      OpenAlex Institutions
locatedIn              institution_id, country                     OpenAlex Institutions
hasTopic               work_id, topic_id, score, rank              OpenAlex Topics (camada 1)
broader                topic_id, subfield_id, field_id, domain_id  taxonomia Topics
publishedIn            work_id, venue_id, year                     OpenAlex (primary_location)
cites                  work_id, cited_id, year                     OpenAlex (referenced_works)
hasEmployment          author_id, org_key, start, end              ORCID (camada 3)
=====================  ==========================================  =========================

``cites`` mantém também referências a trabalhos FORA do corpus (servem ao acoplamento
bibliográfico: dois autores que citam a mesma obra). ``hasEmployment`` só guarda vínculos
iniciados até o corte; os que terminam depois ficam em aberto (``end`` nulo) — no corte,
ainda estavam vigentes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RELATIONS = ("wrote", "atInstitution", "partOf", "relatedInstitution", "locatedIn",
             "hasTopic", "broader", "publishedIn", "cites", "hasEmployment")


def _jlist(v) -> list:
    if isinstance(v, (list, np.ndarray)):
        return list(v)
    try:
        out = json.loads(v) if isinstance(v, str) and v else []
        return out if isinstance(out, list) else []
    except ValueError:
        return []


def build_kg_t0(corpus: pd.DataFrame, works_raw: pd.DataFrame, enrich_dir: str | Path,
                cutoff: int, employment_kinds=("employment",)) -> dict[str, pd.DataFrame]:
    """Monta as tabelas de relação do KG com os fatos conhecidos até ``cutoff`` (inclusive).

    ``corpus``: autorias higienizadas (pessoa canônica em ``author_id``);
    ``works_raw``: works brutos (``id``, ``venue_id``, ``referenced_works``);
    ``enrich_dir``: saídas do enriquecimento (``data/processed/enrich_<base>``).
    """
    e = Path(enrich_dir)
    year = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
    c0 = corpus[year <= cutoff].assign(year=year[year <= cutoff].astype(int))
    t0_works = set(c0["work_id"])
    kg: dict[str, pd.DataFrame] = {}

    kg["wrote"] = (c0[["author_id", "work_id", "year", "level", "author_position"]]
                   .rename(columns={"author_position": "position"})
                   .drop_duplicates(["author_id", "work_id"]).reset_index(drop=True))

    aiy = pd.read_parquet(e / "author_institution_years.parquet")
    kg["atInstitution"] = aiy[aiy["work_id"].isin(t0_works)].reset_index(drop=True)

    inst = pd.read_parquet(e / "institutions.parquet")
    kg["partOf"] = pd.read_parquet(e / "institution_lineage.parquet")
    kg["relatedInstitution"] = pd.read_parquet(e / "institution_associated.parquet")
    kg["locatedIn"] = inst.loc[inst["country"].notna(), ["institution_id", "country"]].reset_index(drop=True)

    wt = pd.read_parquet(e / "work_topics.parquet")
    kg["hasTopic"] = wt.loc[wt["work_id"].isin(t0_works),
                            ["work_id", "topic_id", "score", "rank"]].reset_index(drop=True)
    tax = pd.read_parquet(e / "taxonomy.parquet")
    kg["broader"] = tax[["topic_id", "subfield_id", "field_id", "domain_id"]].drop_duplicates("topic_id")

    w = works_raw[works_raw["id"].isin(t0_works)].drop_duplicates("id")
    wy = c0.drop_duplicates("work_id").set_index("work_id")["year"]
    pub = w.loc[w["venue_id"].notna(), ["id", "venue_id"]].rename(columns={"id": "work_id"})
    pub["year"] = pub["work_id"].map(wy).astype(int)
    kg["publishedIn"] = pub.reset_index(drop=True)
    cites = [(wid, r) for wid, refs in zip(w["id"], w["referenced_works"]) for r in _jlist(refs) if r]
    ct = pd.DataFrame(cites, columns=["work_id", "cited_id"]).drop_duplicates()
    ct["year"] = ct["work_id"].map(wy).astype(int)
    kg["cites"] = ct.reset_index(drop=True)

    f = e / "author_affiliations_orcid.parquet"
    aff = pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["author_id", "kind", "org_key",
                                                                      "start", "end"])
    emp = aff[aff["kind"].isin(employment_kinds) & aff["org_key"].notna()
              & aff["start"].notna() & (aff["start"] <= cutoff)].copy()
    emp.loc[emp["end"] > cutoff, "end"] = np.nan          # vigente no corte → em aberto
    kg["hasEmployment"] = emp[["author_id", "org_key", "start", "end"]].drop_duplicates().reset_index(drop=True)
    return kg


def validate_kg(kg: dict[str, pd.DataFrame], cutoff: int) -> dict:
    """Checagens de consistência com a ontologia e com o corte temporal.

    Retorna contagens por relação, coberturas e uma lista de violações (vazia = KG válido).
    """
    v, out = [], {"corte_T0": cutoff, "relacoes": {k: int(len(df)) for k, df in kg.items()}}
    for rel in ("wrote", "atInstitution", "publishedIn", "cites"):
        if len(kg[rel]) and int(kg[rel]["year"].max()) > cutoff:
            v.append(f"{rel}: fato com ano > {cutoff} (vazamento)")
    emp = kg["hasEmployment"]
    if len(emp) and ((emp["start"] > cutoff).any() or (emp["end"] > cutoff).any()):
        v.append("hasEmployment: vínculo posterior ao corte (vazamento)")
    works = set(kg["wrote"]["work_id"])
    authors = set(kg["wrote"]["author_id"])
    for rel, col in (("atInstitution", "work_id"), ("hasTopic", "work_id"), ("publishedIn", "work_id"),
                     ("cites", "work_id")):
        orphans = int((~kg[rel][col].isin(works)).sum())
        if orphans:
            v.append(f"{rel}: {orphans} fatos com trabalho fora de T0 (domínio cr:Work violado)")
    orphans = int((~kg["atInstitution"]["author_id"].isin(authors)).sum())
    if orphans:
        v.append(f"atInstitution: {orphans} fatos com autor sem autoria em T0")
    unknown_topics = int((~kg["hasTopic"]["topic_id"].isin(set(kg["broader"]["topic_id"]))).sum())
    if unknown_topics:
        v.append(f"hasTopic: {unknown_topics} tópicos fora da taxonomia (cr:broader incompleto)")
    if kg["partOf"]["child"].eq(kg["partOf"]["parent"]).any():
        v.append("partOf: instituição parte de si mesma")
    nw = max(len(works), 1)
    out["entidades"] = {"autores": len(authors), "trabalhos": len(works),
                        "instituicoes": int(kg["atInstitution"]["institution_id"].nunique()),
                        "periodicos": int(kg["publishedIn"]["venue_id"].nunique()),
                        "topicos": int(kg["hasTopic"]["topic_id"].nunique()),
                        "organizacoes_orcid": int(kg["hasEmployment"]["org_key"].nunique())}
    out["cobertura"] = {
        "trabalhos_com_topico": round(kg["hasTopic"]["work_id"].nunique() / nw, 4),
        "trabalhos_com_periodico": round(kg["publishedIn"]["work_id"].nunique() / nw, 4),
        "trabalhos_com_referencias": round(kg["cites"]["work_id"].nunique() / nw, 4),
        "referencias_dentro_do_corpus": round(float(kg["cites"]["cited_id"].isin(works).mean())
                                              if len(kg["cites"]) else 0.0, 4),
        "autores_com_instituicao": round(kg["atInstitution"]["author_id"].nunique() / max(len(authors), 1), 4),
        "autores_com_vinculo_orcid": round(kg["hasEmployment"]["author_id"].nunique() / max(len(authors), 1), 4),
    }
    out["violacoes"] = v
    out["valido"] = not v
    return out


def save_kg(kg: dict[str, pd.DataFrame], out_dir: str | Path, manifest: dict) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for rel, df in kg.items():
        df.to_parquet(out / f"{rel}.parquet", index=False)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def load_kg(kg_dir: str | Path) -> dict[str, pd.DataFrame]:
    d = Path(kg_dir)
    return {rel: pd.read_parquet(d / f"{rel}.parquet") for rel in RELATIONS}
