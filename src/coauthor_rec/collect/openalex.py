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
import time
from pathlib import Path

import pandas as pd

from ..data.clean import reconstruct_abstract


class OpenAlexQuotaExhausted(RuntimeError):
    """O orçamento diário de créditos do OpenAlex acabou (HTTP 429). Volta à meia-noite UTC."""


def retry_after(exc: Exception) -> float | None:
    """Segundos de espera pedidos por um HTTP 429 (None se não for 429)."""
    resp = getattr(exc, "response", None)
    if resp is None or getattr(resp, "status_code", None) != 429:
        return None
    after = resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Reset")
    return float(after) if after and str(after).replace(".", "", 1).isdigit() else 10.0


def quota_error(exc: Exception) -> OpenAlexQuotaExhausted | None:
    """Converte um 429 de COTA DIÁRIA esgotada (espera > 2 min) numa mensagem explícita.
    Um 429 de excesso momentâneo de taxa (espera curta) devolve None — repetir resolve."""
    resp = getattr(exc, "response", None)
    if resp is None or getattr(resp, "status_code", None) != 429:
        return None
    if (retry_after(exc) or 0) <= 120:
        return None
    after = resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Reset")
    hours = f"{int(after) / 3600:.1f} h" if after and str(after).isdigit() else "a meia-noite UTC"
    return OpenAlexQuotaExhausted(
        f"Orçamento diário do OpenAlex esgotado (restante: {resp.headers.get('X-RateLimit-Remaining')}"
        f" de {resp.headers.get('X-RateLimit-Limit')} créditos). Volta em {hours}. "
        "Com OPENALEX_API_KEY (gratuita) o orçamento é 10× maior.")


def _require_pyalex(mailto: str):
    try:
        import pyalex
        from pyalex import Works
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pyalex não instalado. Rode: pip install pyalex") from exc
    from ..secrets import get_secret
    pyalex.config.email = mailto
    pyalex.config.api_key = get_secret("OPENALEX_API_KEY")
    pyalex.config.max_retries = 5
    # 429 NÃO entra no retry: o pyalex respeita o Retry-After, que, com a cota diária
    # esgotada, manda dormir até a meia-noite UTC (horas) em silêncio. Erro explícito.
    pyalex.config.retry_http_codes = [500, 502, 503, 504]
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
    doi = work.get("doi")
    work_row = {
        "id": wid,
        # DOI normalizado (minúsculo, sem prefixo) — chave para verificar no registro
        # ORCID se o autor REIVINDICOU o trabalho (higienização, nível A).
        "doi": doi.lower().replace("https://doi.org/", "") if doi else None,
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
        orcid = author.get("orcid")
        authorship_rows.append({
            "work_id": wid,
            "author_id": _short_id(author.get("id")),
            "author_name": author.get("display_name"),
            "institution_ids": json.dumps([_short_id(i.get("id")) for i in institutions]),
            # --- campos de veracidade do autor (fase de higienização/auditoria) ---
            "author_orcid": orcid.rstrip("/").split("/")[-1] if orcid else None,
            "raw_author_name": au.get("raw_author_name"),
            "author_position": au.get("author_position"),
            "is_corresponding": au.get("is_corresponding"),
            "institution_names": json.dumps([i.get("display_name") for i in institutions]),
            # ROR das instituições — cruzado com as afiliações do registro ORCID.
            "institution_rors": json.dumps([i["ror"].rstrip("/").split("/")[-1]
                                            for i in institutions if i.get("ror")]),
            "countries": json.dumps(au.get("countries") or
                                    [i.get("country_code") for i in institutions if i.get("country_code")]),
        })
    return authorship_rows, work_row


# --------------------------------------------------------------------------- #
# Acumulador compartilhado pelos dois modos.
# --------------------------------------------------------------------------- #
def _new_store() -> dict:
    return {"seen_works": set(), "authorship_rows": [], "work_rows": [], "author_ids": set()}


def _ingest(store: dict, work: dict, count_cap: int | None = None) -> list[str]:
    """Adiciona um work ao acumulador (se inédito). Retorna os author_ids desse work.

    ``count_cap``: works com mais autores que isso continuam no bruto, mas seus autores
    NÃO contam para o critério de parada (não geram arestas — teto de coautores)."""
    wid = _short_id(work.get("id"))
    if not wid or wid in store["seen_works"]:
        return []
    store["seen_works"].add(wid)
    a_rows, w_row = _extract_records(work)
    store["authorship_rows"].extend(a_rows)
    store["work_rows"].append(w_row)
    counts = count_cap is None or len(a_rows) <= count_cap
    authors = []
    for r in a_rows:
        if r["author_id"]:
            if counts:
                store["author_ids"].add(r["author_id"])
            authors.append(r["author_id"])
    return authors


def _area_filter(th: dict) -> dict:
    """Filtro de área para a API: campo do *primary topic* (Topics, recomendado — um campo
    por trabalho) ou Concepts (legado; a API casa QUALQUER marcação, inclusive score 0)."""
    fields = [str(f) for f in (th.get("field_ids") or []) if f]
    if fields:
        return {"primary_topic": {"field": {"id": "|".join(fields)}}}
    concepts = [c for c in (th.get("concept_ids") or []) if c]
    if concepts:
        return {"concepts": {"id": "|".join(concepts)}}
    raise ValueError("defina thematic.field_ids (Topics) ou thematic.concept_ids (Concepts).")


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
    area = _area_filter(th)
    concept_ids = [c for c in (th.get("concept_ids") or []) if c]
    # Critério de parada: por AUTORES distintos (target_authors) — adequado à tarefa de
    # recomendação de coautoria, pois fixa o tamanho do catálogo entre bases/áreas — ou,
    # na ausência dele, por works (target_works, comportamento original). max_works é o
    # teto de segurança quando se fixa autores (evita coleta desenfreada em áreas de
    # equipes pequenas, onde cada work agrega poucos autores novos).
    target_authors = th.get("target_authors")
    target_works = th.get("target_works")
    max_works = th.get("max_works") or (target_works or 100_000)
    if not target_authors and not target_works:
        raise ValueError("configs: defina thematic.target_authors ou thematic.target_works.")

    def done(store) -> bool:
        if target_authors and len(store["author_ids"]) >= target_authors:
            return True
        if target_works and len(store["seen_works"]) >= target_works:
            return True
        return len(store["seen_works"]) >= max_works

    from_year = config["filters"]["from_publication_year"]
    langs = config["filters"]["languages"]
    per_page = config["api"]["per_page"]

    store = _new_store()
    query = Works().filter(
        language="|".join(langs),
        from_publication_date=f"{from_year}-01-01",
        **area,  # OR entre campos/conceitos
    )
    if verbose:
        alvo = (f"{target_authors} autores (teto {max_works} works)"
                if target_authors else f"{target_works} works")
        print(f"[thematic] área={area}, alvo={alvo}")
    pages = 0
    for page in query.paginate(per_page=per_page, n_max=None):
        for work in page:
            _ingest(store, work)
        pages += 1
        if verbose and pages % 20 == 0:
            print(f"[thematic] {len(store['seen_works'])} works / "
                  f"{len(store['author_ids'])} autores…")
        if done(store):
            break

    return _write(store, out_dir, verbose,
                  extra={"mode": "thematic", "concept_ids": concept_ids,
                         "target_authors": target_authors, "max_works": max_works})


# --------------------------------------------------------------------------- #
# Modo seeded: sementes aleatórias + histórico completo (docs/SELECAO_BASES.md).
# --------------------------------------------------------------------------- #
def seeded_collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Amostragem representativa que preserva a estrutura da rede.

    1. Sorteia trabalhos ALEATÓRIOS da área (``sample`` + seeds — reprodutível; a ordem
       padrão da API é por citações e enviesaria a densidade).
    2. Os autores desses trabalhos (com ORCID, se ``require_orcid``) viram candidatos a
       SEMENTE, em ordem embaralhada com semente fixa.
    3. Coleta o HISTÓRICO COMPLETO das sementes na área (lotes de ``batch_size`` autores
       por consulta, OR no filtro) — os coautores entram no catálogo.
    4. Para em ``target_authors`` pessoas distintas (ou ``max_works`` / ``max_seeds``).

    Grava também ``seeds.csv``: só as sementes têm histórico completo na área, então são
    elas os alvos naturais da avaliação (após a elegibilidade E1–E8 da higienização).
    """
    import random

    Works = _require_pyalex(config["api"]["mailto"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    th, sd = config["thematic"], config.get("seeding", {})
    area = _area_filter(th)
    cap = sd.get("count_cap")                 # teto de coautores (arestas); de filters.yaml
    target_authors = th.get("target_authors")          # None = sem parada por autores
    max_works = th.get("max_works") or 100_000
    max_seeds = sd.get("max_seeds")
    if not target_authors and not max_seeds:
        raise ValueError("seeded: defina coleta.max_seeds e/ou target_authors (critério de parada).")
    sample_size = min(int(sd.get("sample_size", 2000)), 10_000)   # limite da API
    sample_seeds = list(sd.get("sample_seeds", [42, 43, 44, 45, 46, 47, 48, 49]))
    batch = int(sd.get("batch_size", 50))
    require_orcid = sd.get("require_orcid", True)
    per_work = sd.get("candidates_per_work", 1)   # None/0 = todos os autores do artigo
    rng = random.Random(sd.get("seed", 42))
    per_page = config["api"]["per_page"]

    def base():
        return Works().filter(language="|".join(config["filters"]["languages"]),
                              from_publication_date=f"{config['filters']['from_publication_year']}-01-01",
                              **area)

    store = _new_store()
    seeds: list[dict] = []
    seen_cand: set[str] = set()

    def done() -> bool:
        return ((target_authors and len(store["author_ids"]) >= target_authors)
                or len(store["seen_works"]) >= max_works
                or (max_seeds is not None and len(seeds) >= max_seeds))

    if verbose:
        print(f"[seeded] área={area}, parada: {max_seeds} sementes"
              + (f" ou {target_authors} autores (só works ≤{cap} autores)" if target_authors else "")
              + f"; teto {max_works} works; sorteios de {sample_size} works")
    for s in sample_seeds:
        if done():
            break
        cands = []
        try:
            pages = list(base().sample(sample_size, seed=s).paginate(
                method="page", per_page=min(per_page, 200), n_max=sample_size))
        except Exception as exc:
            if (q := quota_error(exc)) is not None:
                raise q from exc
            raise
        for page in pages:
            for w in page:
                elig = []
                for au in w.get("authorships", []):
                    a = au.get("author") or {}
                    aid = _short_id(a.get("id"))
                    if not aid or aid in seen_cand or (require_orcid and not a.get("orcid")):
                        continue
                    elig.append((aid, a.get("orcid")))
                # Um autor por artigo (padrão): cada artigo pesa igual. Tomar TODOS os
                # autores super-representa quem publica em equipes grandes (viés de
                # tamanho — um artigo de 8 autores renderia 8 candidatos).
                if per_work and len(elig) > per_work:
                    elig = rng.sample(elig, per_work)
                for aid, orcid in elig:
                    seen_cand.add(aid)
                    cands.append({"author_id": aid, "author_orcid":
                                  orcid.rstrip("/").split("/")[-1] if orcid else None,
                                  "sample_seed": s, "seed_work_id": _short_id(w.get("id"))})
        rng.shuffle(cands)
        if verbose:
            print(f"[seeded] sorteio seed={s}: {len(cands)} candidatos a semente")
        for i in range(0, len(cands), batch):
            if done():
                break
            lot = cands[i:i + batch]
            for attempt in range(3):
                try:
                    pager = base().filter(
                        authorships={"author": {"id": "|".join(c["author_id"] for c in lot)}}
                    ).paginate(per_page=per_page, n_max=None)
                    for page in pager:
                        for work in page:
                            _ingest(store, work, count_cap=cap)   # dedup por work: repetir é seguro
                    break
                except Exception as exc:
                    if (q := quota_error(exc)) is not None:
                        raise q from exc                         # cota esgotada: aborta explícito
                    if (ra := retry_after(exc)) is not None and attempt < 2:
                        time.sleep(min(ra, 60) + 1)              # excesso momentâneo de taxa
                        continue
                    if attempt == 2:
                        # Nunca pular um lote em silêncio: a base ficaria incompleta parecendo
                        # completa (as sementes do lote sumiriam sem registro).
                        raise RuntimeError(f"lote {i // batch} falhou 3 vezes; coleta abortada: {exc}") from exc
                    if verbose:
                        print(f"  [aviso] lote {i // batch} falhou ({exc}); nova tentativa")
                    time.sleep(5 * (attempt + 1))
            for c in lot:
                c["order"] = len(seeds)
                seeds.append(c)
            if verbose and (i // batch) % 10 == 0:
                print(f"[seeded] {len(seeds)} sementes · {len(store['seen_works'])} works · "
                      f"{len(store['author_ids'])} autores")

    pd.DataFrame(seeds).to_csv(out_dir / "seeds.csv", index=False)
    return _write(store, out_dir, verbose,
                  extra={"mode": "seeded", "area_filter": area, "n_seeds": len(seeds),
                         "authors_counted": len(store["author_ids"]), "count_cap": cap,
                         "target_authors": target_authors, "max_works": max_works,
                         "sample_seeds_used": sorted({c["sample_seed"] for c in seeds})})


# --------------------------------------------------------------------------- #
# Expansão: histórico dos CANDIDATOS (coautores das sementes) até o fim de T0.
# --------------------------------------------------------------------------- #
def select_candidates(authorships: pd.DataFrame, seeds: set[str], cap: int | None,
                      work_years: dict | None = None, t0_end_year: int | None = None) -> list[str]:
    """Candidatos = coautores das sementes em trabalhos de T0 (ano ≤ ``t0_end_year``), dentro do
    teto de coautores, que não são sementes.

    **Sem vazamento:** coautores que só aparecem em T1 NÃO entram — escolher o catálogo com base
    em quem colaborou com as sementes no futuro colocaria os próprios positivos no universo de
    candidatos e inflaria qualquer avaliação. Eles seguem na verdade fundamental.
    """
    a = authorships.dropna(subset=["author_id"])
    if work_years is not None and t0_end_year is not None:
        a = a[a["work_id"].map(work_years) <= t0_end_year]
    if cap:
        team = a.groupby("work_id")["author_id"].transform("nunique")
        a = a[team <= cap]
    return sorted(set(a["author_id"]) - set(seeds))


def expand_candidates(config: dict, raw_dir: str | Path, t0_end_year: int,
                      verbose: bool = True, chunk_lots: int = 100, workers: int = 4,
                      window_years: int | None = None) -> dict:
    """Coleta o histórico NO CAMPO, até 31/12 de ``t0_end_year``, de cada candidato.

    Por quê: na coleta ``seeded`` só as sementes têm histórico completo; um coautor aparece
    só com o trabalho feito junto à semente (mediana 1). No piloto de Economia, só 12,9% dos
    coautores novos de T1 estavam presentes em T0 — e 45% dos ausentes já publicavam no campo
    antes do corte (artefato da coleta). Só o período T0 é necessário: os alvos são as
    sementes, cujo T1 já está completo.

    Grava ``authorships_cand.parquet``, ``works_cand.parquet`` e ``candidates.csv`` em ``raw_dir``.
    Retomável: lotes processados em blocos (``chunk_lots``) gravados em ``cand_parts/``.
    """
    Works = _require_pyalex(config["api"]["mailto"])
    raw = Path(raw_dir)
    parts = raw / "cand_parts"
    parts.mkdir(exist_ok=True)
    th, sd = config["thematic"], config.get("seeding", {})
    area, cap = _area_filter(th), sd.get("count_cap")
    seeds = set(pd.read_csv(raw / "seeds.csv")["author_id"])
    wdates = pd.read_csv(raw / "works.csv", usecols=["id", "publication_date"])
    years = dict(zip(wdates["id"], pd.to_datetime(wdates["publication_date"], errors="coerce").dt.year))
    cands = select_candidates(pd.read_csv(raw / "authorships.csv", usecols=["work_id", "author_id"]),
                              seeds, cap, years, t0_end_year)
    pd.DataFrame({"author_id": cands}).to_csv(raw / "candidates.csv", index=False)
    batch, per_page = int(sd.get("batch_size", 50)), config["api"]["per_page"]
    lots = [cands[i:i + batch] for i in range(0, len(cands), batch)]
    chunks = [lots[i:i + chunk_lots] for i in range(0, len(lots), chunk_lots)]
    if verbose:
        print(f"[expand] {len(seeds)} sementes · {len(cands)} candidatos · {len(lots)} lotes "
              f"em {len(chunks)} blocos · histórico {start}–{t0_end_year} · área={area}", flush=True)

    start = (t0_end_year - window_years + 1) if window_years else config["filters"]["from_publication_year"]
    start = max(start, config["filters"]["from_publication_year"])

    def base():
        return Works().filter(language="|".join(config["filters"]["languages"]),
                              from_publication_date=f"{start}-01-01",
                              to_publication_date=f"{t0_end_year}-12-31", **area)

    for k, chunk in enumerate(chunks):
        out_a, out_w = parts / f"auth_{k:04d}.parquet", parts / f"works_{k:04d}.parquet"
        if out_a.exists() and out_w.exists():
            continue                                        # bloco já feito (retomada)
        def fetch_lot(lot):
            st = _new_store()
            for attempt in range(6):
                try:
                    for page in base().filter(authorships={"author": {"id": "|".join(lot)}}
                                              ).paginate(per_page=per_page, n_max=None):
                        for work in page:
                            _ingest(st, work)
                    return st
                except Exception as exc:
                    if (q := quota_error(exc)) is not None:
                        raise q from exc
                    if attempt == 5:
                        raise RuntimeError(f"expansão: lote falhou 6 vezes; blocos anteriores salvos: {exc}") from exc
                    ra = retry_after(exc)                    # 429 de taxa: espera o pedido
                    time.sleep(min(ra, 60) + 1 if ra is not None else 5 * (attempt + 1))

        from concurrent.futures import ThreadPoolExecutor
        rows_a, rows_w = [], []
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            for st in pool.map(fetch_lot, chunk):             # erro em qualquer lote → aborta o bloco
                rows_a.extend(st["authorship_rows"]); rows_w.extend(st["work_rows"])
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown(wait=True)
        a = pd.DataFrame(rows_a)
        w = pd.DataFrame(rows_w)
        (a.drop_duplicates(["work_id", "author_id"]) if len(a) else a).to_parquet(out_a, index=False)
        (w.drop_duplicates("id") if len(w) else w).to_parquet(out_w, index=False)
        if verbose:
            print(f"[expand] bloco {k + 1}/{len(chunks)}: +{len(w)} works", flush=True)

    a = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("auth_*.parquet"))], ignore_index=True)
    w = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("works_*.parquet"))], ignore_index=True)
    a = a.drop_duplicates(["work_id", "author_id"])
    w = w.drop_duplicates("id")
    # parquet: o histórico dos candidatos tem centenas de milhares de trabalhos com abstract
    a.to_parquet(raw / "authorships_cand.parquet", index=False)
    w.to_parquet(raw / "works_cand.parquet", index=False)
    stats = {"mode": "expand_candidates", "candidates": len(cands), "t0_end_year": t0_end_year,
             "history_from_year": start,
             "works_cand": len(w), "authorships_cand": len(a),
             "authors_cand_rows": int(a["author_id"].nunique()) if len(a) else 0}
    if verbose:
        print(f"[expand] concluído: {stats}", flush=True)
    return stats


# --------------------------------------------------------------------------- #
# Dispatcher por modo.
# --------------------------------------------------------------------------- #
def collect(config: dict, out_dir: str | Path, verbose: bool = True) -> dict:
    """Despacha conforme ``config['mode']`` (snowball | thematic | hybrid | seeded)."""
    mode = config.get("mode", "snowball")
    if mode == "snowball":
        return snowball_collect(config, out_dir, verbose)
    if mode == "thematic":
        return thematic_collect(config, out_dir, verbose)
    if mode == "hybrid":
        return hybrid_collect(config, out_dir, verbose)
    if mode == "seeded":
        return seeded_collect(config, out_dir, verbose)
    raise ValueError(
        f"modo de coleta desconhecido: {mode!r} (use 'snowball', 'thematic', 'hybrid' ou 'seeded')."
    )
