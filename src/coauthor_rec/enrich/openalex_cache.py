"""Busca entidades do OpenAlex por ID, em lote, com cache em disco retomável.

Cada entidade (works, institutions…) tem um arquivo ``<cache_dir>/<entity>.jsonl`` com uma
linha por registro. IDs já presentes não são consultados de novo; IDs que a API não devolve
(registros removidos ou fundidos) são gravados como ``{"id": ..., "_missing": true}`` para não
serem repetidos. Consultas: filtro ``openalex:ID1|ID2|…`` (até 50 por requisição), em paralelo
sob um limite GLOBAL de taxa (o polite pool aceita até 10 req/s).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..data.orcid import _RateLimiter

API = "https://api.openalex.org/{entity}"


def short_id(x) -> str | None:
    """'https://openalex.org/W123' → 'W123' (aceita já curto)."""
    if not isinstance(x, str) or not x:
        return None
    return x.rstrip("/").split("/")[-1]


def _get(url: str, retries: int = 5, api_key: str | None = None) -> dict:
    from ..collect.openalex import OpenAlexQuotaExhausted
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                after = e.headers.get("Retry-After")
                wait = int(after) if after and after.isdigit() else 2 ** attempt
                if wait > 600:          # orçamento diário esgotado: não dormir horas em silêncio
                    raise OpenAlexQuotaExhausted(
                        f"Orçamento diário do OpenAlex esgotado (limite {e.headers.get('X-RateLimit-Limit')}"
                        f" créditos). Volta em {wait / 3600:.1f} h. Progresso salvo no cache; "
                        "com OPENALEX_API_KEY o orçamento é 10× maior.") from e
                time.sleep(wait)
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenAlex indisponível após {retries} tentativas: {url[:120]}")


def load_cache(cache_dir: str | Path, entity: str) -> dict[str, dict]:
    f = Path(cache_dir) / f"{entity}.jsonl"
    out = {}
    if f.exists():
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    out[rec["id"]] = rec
    return out


def fetch_by_ids(entity: str, ids, select: str, cache_dir: str | Path, mailto: str,
                 batch_size: int = 50, requests_per_second: float = 5, workers: int = 5,
                 verbose: bool = True) -> dict[str, dict]:
    """Devolve {id_curto: registro} para todos os ``ids`` (cache + API)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = load_cache(cache_dir, entity)
    wanted = sorted({short_id(i) for i in ids if short_id(i)})
    todo = [i for i in wanted if i not in cached]
    if verbose:
        print(f"[openalex:{entity}] {len(wanted) - len(todo)} em cache, {len(todo)} a buscar "
              f"({-(-len(todo) // batch_size)} consultas, ~{len(todo) / batch_size / requests_per_second / 60:.1f} min)",
              flush=True)
    from ..secrets import get_secret
    api_key = get_secret("OPENALEX_API_KEY")
    limiter = _RateLimiter(requests_per_second)
    sel = ",".join(sorted(set(select.split(",")) | {"id"}))

    def one(lot):
        limiter.wait()
        params = {"filter": "openalex:" + "|".join(lot), "per_page": len(lot),
                  "select": sel, "mailto": mailto}
        q = urllib.parse.urlencode(params)      # chave vai no cabeçalho (não vaza em logs)
        res = _get(f"{API.format(entity=entity)}?{q}", api_key=api_key)["results"]
        got = {}
        for rec in res:
            rec["id"] = short_id(rec["id"])
            got[rec["id"]] = rec
        return [got.get(i, {"id": i, "_missing": True}) for i in lot]

    lots = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    pool = ThreadPoolExecutor(max_workers=max(1, workers))
    with open(cache_dir / f"{entity}.jsonl", "a", encoding="utf-8") as fh:
        try:
            for n, fut in enumerate(as_completed([pool.submit(one, lot) for lot in lots]), 1):
                for rec in fut.result():
                    cached[rec["id"]] = rec
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if verbose and n % 200 == 0:
                    print(f"[openalex:{entity}] {n}/{len(lots)} consultas", flush=True)
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)   # cota/erro: para já; cache preservado
            raise
    pool.shutdown(wait=True)
    return {i: cached[i] for i in wanted}
