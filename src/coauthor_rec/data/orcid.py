"""Cliente da API pública do ORCID (pub.orcid.org v3.0) para a higienização de autores.

Para cada ORCID, extrai do registro público o que a pessoa DECLAROU sobre si:
  - nomes (given/family, credit name, outros nomes)   → checagem de consistência de nome
  - DOIs dos trabalhos reivindicados                  → autoria nível A (reivindicada)
  - afiliações (org, país, ROR/outros IDs, anos)      → vínculo autor–instituição

``parse_record`` é puro (testável sem rede); ``fetch_claims`` faz as requisições com
cache em disco (um JSON por ORCID — retomável) e taxa educada. Registros inexistentes
ou privados viram ``{"exists": False}`` (não é erro: muitos ORCIDs têm pouco conteúdo público).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://pub.orcid.org/v3.0/{orcid}/record"
AFFIL_SECTIONS = ("employments", "educations", "invited-positions", "distinctions",
                  "memberships", "services", "qualifications")


def _val(d, *path):
    """Navega dicts aninhados do JSON do ORCID tolerando None em qualquer nível."""
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _year(date) -> int | None:
    y = _val(date, "year", "value")
    try:
        return int(y) if y else None
    except (TypeError, ValueError):
        return None


def parse_record(orcid: str, record: dict | None) -> dict:
    """Converte o JSON de /record em ``claims`` (o que o ORCID atesta sobre a pessoa)."""
    if not record:
        return {"orcid": orcid, "exists": False, "names": [], "dois": [], "affiliations": []}
    name = _val(record, "person", "name") or {}
    names = [" ".join(x for x in (_val(name, "given-names", "value"),
                                  _val(name, "family-name", "value")) if x)]
    if _val(name, "credit-name", "value"):
        names.append(_val(name, "credit-name", "value"))
    for o in _val(record, "person", "other-names", "other-name") or []:
        if o.get("content"):
            names.append(o["content"])

    dois = set()
    for g in _val(record, "activities-summary", "works", "group") or []:
        for e in _val(g, "external-ids", "external-id") or []:
            if (e.get("external-id-type") or "").lower() == "doi" and e.get("external-id-value"):
                dois.add(e["external-id-value"].lower().replace("https://doi.org/", "").strip())

    affiliations = []
    for sec in AFFIL_SECTIONS:
        for g in _val(record, "activities-summary", sec, "affiliation-group") or []:
            for s in g.get("summaries") or []:
                for v in s.values():
                    org = (v or {}).get("organization") or {}
                    dis = org.get("disambiguated-organization") or {}
                    src = (dis.get("disambiguation-source") or "").upper()
                    ident = (dis.get("disambiguated-organization-identifier") or "").rstrip("/")
                    affiliations.append({
                        "section": sec,
                        "name": org.get("name"),
                        "country": _val(org, "address", "country"),
                        "ror": ident.split("/")[-1] if src == "ROR" and ident else None,
                        "other_id": f"{src}:{ident}" if src and src != "ROR" and ident else None,
                        "start": _year(v.get("start-date")),
                        "end": _year(v.get("end-date")),
                    })
    return {"orcid": orcid, "exists": True, "names": [n for n in names if n],
            "dois": sorted(dois), "affiliations": affiliations}


def _get(url: str, retries: int = 4) -> dict | None:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "coauthor-rec/hygiene"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 409, 410):          # inexistente / desativado / privado
                return None
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"ORCID API indisponível após {retries} tentativas: {url}")


class _RateLimiter:
    """Limita a taxa GLOBAL de requisições entre threads (intervalo mínimo entre inícios)."""
    def __init__(self, per_second: float):
        import threading
        self.gap, self.next, self.lock = 1.0 / per_second, time.monotonic(), threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - now))


def fetch_claims(orcids, cache_dir: str | Path, requests_per_second: float = 8,
                 verbose: bool = True, workers: int = 8) -> dict[str, dict]:
    """Busca (ou lê do cache) os claims de cada ORCID. Retomável: o que já está no cache
    não é refeito. Requisições em paralelo (``workers``) sob um limite GLOBAL de taxa —
    a API pública do ORCID aceita até 24 req/s por IP. Retorna {orcid: claims}."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    out, todo = {}, []
    for o in sorted({o for o in orcids if isinstance(o, str) and o}):
        f = cache / f"{o}.json"
        if f.exists():
            out[o] = json.loads(f.read_text())
        else:
            todo.append(o)
    if verbose:
        print(f"[orcid] {len(out)} em cache, {len(todo)} a buscar "
              f"(~{len(todo) / requests_per_second / 60:.1f} min a {requests_per_second}/s)",
              flush=True)
    limiter = _RateLimiter(requests_per_second)

    def one(o):
        limiter.wait()
        claims = parse_record(o, _get(API.format(orcid=o)))
        (cache / f"{o}.json").write_text(json.dumps(claims, ensure_ascii=False))
        return o, claims

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, fut in enumerate(as_completed([pool.submit(one, o) for o in todo]), 1):
            o, claims = fut.result()
            out[o] = claims
            if verbose and i % 1000 == 0:
                print(f"[orcid] {i}/{len(todo)}", flush=True)
    return out
