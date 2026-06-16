"""Coleta de corpus do OpenAlex (pyalex), em dois modos selecionáveis por config:

  "snowball" — a partir de um artigo/autor-semente, expandindo pela rede de coautoria
               (método do Estudo Inicial, Cap. 5).
  "thematic" — recorte por Concept do OpenAlex, com janela temporal/idioma
               (cenário aberto da proposta da tese, Cap. 4.2.1).

Ambos salvam duas tabelas compatíveis com o estudo inicial (authorships.csv, works.csv)
e preservam metadados extras do KG heterogêneo (institutions, venue/ISSN, concepts) para
reuso nos módulos de 2027. Requer ``pyalex`` (extra de instalação).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.clean import reconstruct_abstract


def _require_pyalex(mailto: str):
    try:
        import pyalex
        from pyalex import Works
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pyalex não instalado. Rode: pip install pyalex") from exc
    pyalex.config.email = mailto
    pyalex.config.max_retries = 5
    return Works


def _short_id(openalex_id: str | None) -> str | None:
    """Converte 'https://openalex.org/W123' -> 'W123'."""
    if not openalex_id:
        return None
    return openalex_id.rstrip("/").split("/")[-1]


def _extract_records(work: dict) -> tuple[list[dict], dict]:
    """De um work do OpenAlex extrai (linhas de autoria, metadados do work)."""
    wid = _short_id(work.get("id"))
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    work_row = {
        "id": wid,
        "publication_date": work.get("publication_date"),
        "title": work.get("title"),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "language": work.get("language"),
        "venue_id": _short_id(source.get("id")),
        "venue_name": source.get("display_name"),
        "venue_issn_l": source.get("issn_l"),
        "cited_by_count": work.get("cited_by_count"),
        "referenced_works": json.dumps(
            [_short_id(r) for r in work.get("referenced_works", [])]
        ),
        "concepts": json.dumps([
            {"id": _short_id(c.get("id")), "name": c.get("display_name"),
             "score": c.get("score")}
            for c in work.get("concepts", [])
        ]),
    }
    authorship_rows = []
    for au in work.get("authorships", []):
        author = au.get("author") or {}
        institutions = au.get("institutions") or []
        authorship_rows.append({
            "work_id": wid,
            "author_id": _short_id(author.get("id")),
            "author_name": author.get("display_name"),
            "institution_ids": json.dumps([_short_id(i.get("id")) for i in institutions]),
        })
    return authorship_rows, work_row


# --------------------------------------------------------------------------- #
# Acumulador compartilhado pelos dois modos.
# --------------------------------------------------------------------------- #
def _new_store() -> dict:
    return {"seen_works": set(), "authorship_rows": [], "work_rows": [], "author_ids": set()}


def _ingest(store: dict, work: dict) -> list[str]:
    """Adiciona um work ao acumulador (se inédito). Retorna os author_ids desse work."""
    wid = _short_id(work.get("id"))
    if not wid or wid in store["seen_works"]:
        return []
    store["seen_works"].add(wid)
    a_rows, w_row = _extract_records(work)
    store["authorship_rows"].extend(a_rows)
    store["work_rows"].append(w_row)
    authors = []
    for r in a_rows:
        if r["author_id"]:
            store["author_ids"].add(r["author_id"])
            authors.append(r["author_id"])
    return authors


def _write(store: dict, out_dir: Path, verbose: bool, extra: dict | None = None) -> dict:
    authorships_df = pd.DataFrame(store["authorship_rows"])
    works_df = pd.DataFrame(store["work_rows"])
    if not authorships_df.empty:
        authorships_df = authorships_df.drop_duplicates(["work_id", "author_id"])
    if not works_df.empty:
        works_df = works_df.drop_duplicates("id")
    authorships_df.to_csv(out_dir / "authorships.csv", index=False)
    works_df.to_csv(out_dir / "works.csv", index=False)
    stats = {
        "works": len(works_df),
        "authors": int(authorships_df["author_id"].nunique()) if not authorships_df.empty else 0,
        "out_dir": str(out_dir),
    }
    if extra:
        stats.update(extra)
    if verbose:
        print(f"[collect] concluído: {stats}")
    return stats


# --------------------------------------------------------------------------- #
# Modos baseados em semente: snowball (puro) e hybrid (semente + filtro temático).
# --------------------------------------------------------------------------- #
def _run_seed_snowball(config: dict, out_dir: Path, concept_ids: list[str] | None,
                       mode_label: str, verbose: bool) -> dict:
    """Núcleo do snowball a partir de semente.

    Se ``concept_ids`` for fornecido, a expansão é restrita a works associados a esses
    Concepts (modo híbrido); caso contrário, expande sem recorte temático (snowball puro).
    """
    Works = _require_pyalex(config["api"]["mailto"])

    sb = config["snowball"]
    target = sb["target_works"]
    max_depth = sb["max_depth"]
    max_per_level = sb["max_authors_per_level"]
    from_year = config["filters"]["from_publication_year"]
    langs = config["filters"]["languages"]
    per_page = config["api"]["per_page"]

    seed = config["seed"]
    seed_id = seed.get("id")
    if not seed_id:
        raise ValueError("configs/collect.yaml: defina seed.id (OpenAlex ID da semente).")

    store = _new_store()

    def works_filter():
        f = Works().filter(
            language="|".join(langs),
            from_publication_date=f"{from_year}-01-01",
        )
        if concept_ids:  # recorte temático na expansão (modo híbrido)
            f = f.filter(concepts={"id": "|".join(concept_ids)})
        return f

    if seed["type"] == "work":
        frontier = set(_ingest(store, Works()[seed_id]))
    else:  # semente = autor
        frontier = {_short_id(seed_id)}

    depth = 0
    while depth < max_depth and len(store["seen_works"]) < target and frontier:
        if verbose:
            print(f"[{mode_label}] nível {depth}: {len(frontier)} autores, "
                  f"{len(store['seen_works'])} works")
        next_frontier: set[str] = set()
        for author_id in list(frontier)[:max_per_level]:
            if len(store["seen_works"]) >= target:
                break
            try:
                pager = works_filter().filter(
                    authorships={"author": {"id": author_id}}
                ).paginate(per_page=per_page, n_max=None)
                for page in pager:
                    for work in page:
                        for a in _ingest(store, work):
                            if a not in frontier:
                                next_frontier.add(a)
                    if len(store["seen_works"]) >= target:
                        break
            except Exception as exc:  # pragma: no cover
                if verbose:
                    print(f"  [aviso] falha no autor {author_id}: {exc}")
        frontier = next_frontier
        depth += 1

    extra = {"mode": mode_label, "depth_reached": depth}
    if concept_ids:
        extra["concept_ids"] = concept_ids
    return _write(store, out_dir, verbose, extra=extra)


def snowball_collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Coleta snowball pura a partir de uma semente (work ou author)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return _run_seed_snowball(config, out_dir, concept_ids=None,
                              mode_label="snowball", verbose=verbose)


def hybrid_collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Coleta híbrida: snowball a partir de semente, restrito aos Concepts temáticos."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    concept_ids = [c for c in (config.get("thematic", {}).get("concept_ids") or []) if c]
    if not concept_ids:
        raise ValueError(
            "configs/collect.yaml: modo híbrido exige thematic.concept_ids (1+ Concept IDs) "
            "além de seed.id."
        )
    return _run_seed_snowball(config, out_dir, concept_ids=concept_ids,
                              mode_label="hybrid", verbose=verbose)


# --------------------------------------------------------------------------- #
# Modo thematic (recorte por Concept).
# --------------------------------------------------------------------------- #
def thematic_collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Coleta por recorte temático: works associados a um ou mais Concepts do OpenAlex."""
    Works = _require_pyalex(config["api"]["mailto"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    th = config["thematic"]
    concept_ids = [c for c in (th.get("concept_ids") or []) if c]
    if not concept_ids:
        raise ValueError(
            "configs/collect.yaml: defina thematic.concept_ids (1+ OpenAlex Concept IDs)."
        )
    target = th["target_works"]
    from_year = config["filters"]["from_publication_year"]
    langs = config["filters"]["languages"]
    per_page = config["api"]["per_page"]

    store = _new_store()
    query = Works().filter(
        language="|".join(langs),
        from_publication_date=f"{from_year}-01-01",
        concepts={"id": "|".join(concept_ids)},  # OR entre conceitos
    )
    if verbose:
        print(f"[thematic] conceitos={concept_ids}, alvo={target} works")
    for page in query.paginate(per_page=per_page, n_max=target):
        for work in page:
            _ingest(store, work)
        if len(store["seen_works"]) >= target:
            break

    return _write(store, out_dir, verbose,
                  extra={"mode": "thematic", "concept_ids": concept_ids})


# --------------------------------------------------------------------------- #
# Dispatcher por modo.
# --------------------------------------------------------------------------- #
def collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Despacha conforme ``config['mode']`` (snowball | thematic | hybrid)."""
    mode = config.get("mode", "snowball")
    if mode == "snowball":
        return snowball_collect(config, out_dir, verbose)
    if mode == "thematic":
        return thematic_collect(config, out_dir, verbose)
    if mode == "hybrid":
        return hybrid_collect(config, out_dir, verbose)
    raise ValueError(
        f"modo de coleta desconhecido: {mode!r} (use 'snowball', 'thematic' ou 'hybrid')."
    )
