"""Coletor das lacunas da reconstrução do T4, com TETO DE GASTO (docs/ROBUSTEZ_T1_T4.md §3.5).

Lê as lacunas de runs/robustez/t4/reconstrucao_<base>_<c>/lacunas.csv e coleta, no OpenAlex:
  1. histórico na área dos candidatos NOVOS na janela (c−J+1 … c);
  2. os anos que faltam aos candidatos JÁ coletados (fora de 2017–2021);
  3. enriquecimento dos trabalhos novos (tópicos) e das instituições novas — via o cache
     existente (enrich/openalex_cache.fetch_by_ids), consultando só o que falta;
  4. registros ORCID dos candidatos novos (gratuito; cache existente).

As consultas de LISTA reproduzem as da expansão original (collect/openalex.py ›
expand_candidates): idioma, área (campo do primary topic), janela de datas e OR de até 50 autores;
paginação por cursor com 200 por página; registros extraídos com a MESMA função
(_extract_records). Cada consulta de lista custa 1 crédito (tabela de custos do /rate-limit).

Garantias:
  - teto: ANTES de cada consulta verifica gasto + custo ≤ limite; se não couber, para (com o
    progresso salvo) — o teto nunca é ultrapassado pela contagem própria;
  - contabilização persistida: gasto.json (total e por tipo) + consultas.jsonl (uma linha por
    consulta: tipo, lote, página, resultados, instante);
  - retomada: cada lote concluído é gravado (auth_<k>.parquet, works_<k>.parquet) e marcado em
    estado.json; uma nova execução pula o que já foi feito;
  - conferência: lê /rate-limit (gratuito) antes e depois e registra o gasto efetivo informado
    pela API ao lado da contagem própria.
A chave da API vai no cabeçalho Authorization (nunca na URL nem nos logs).

Uso: PYTHONHASHSEED=0 python scripts/coletor_t4.py economia --corte 2019 --limite 2600
Saídas: data/robustez/t4/<base>_<c>/ (dados) e runs/robustez/t4/coleta_<base>_<c>/ (contabilidade)
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.collect.openalex import _extract_records  # noqa: E402
from coauthor_rec.config import load_filters, resolve  # noqa: E402
from coauthor_rec.secrets import get_secret  # noqa: E402

API = "https://api.openalex.org"
PER_PAGE, LOT = 200, 50


class BudgetExceeded(RuntimeError):
    """A próxima consulta ultrapassaria o teto: coleta interrompida com o progresso salvo."""


class Ledger:
    def __init__(self, dirpath, limit: int):
        self.dir = dirpath
        self.dir.mkdir(parents=True, exist_ok=True)
        self.f = self.dir / "gasto.json"
        self.log = self.dir / "consultas.jsonl"
        st = json.loads(self.f.read_text()) if self.f.exists() else {}
        self.limit = limit
        self.spent = int(st.get("gasto_creditos", 0))
        self.by_type = st.get("por_tipo", {})
        self.meta = st.get("conferencia_api", {})

    def can(self, cost: int) -> bool:
        return self.spent + cost <= self.limit

    def charge(self, kind: str, cost: int, **info):
        if not self.can(cost):
            raise BudgetExceeded(f"teto de {self.limit} créditos: gasto {self.spent} + {cost} ultrapassaria")
        self.spent += cost
        self.by_type[kind] = self.by_type.get(kind, 0) + cost
        with open(self.log, "a") as fh:
            fh.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tipo": kind,
                                 "creditos": cost, **info}, ensure_ascii=False) + "\n")
        self.save()

    def save(self):
        self.f.write_text(json.dumps({"limite_creditos": self.limit, "gasto_creditos": self.spent,
                                      "por_tipo": self.by_type, "conferencia_api": self.meta},
                                     ensure_ascii=False, indent=1))


def _http(url: str, key: str | None, retries: int = 6) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                wait = int(ra) if ra and ra.isdigit() else 2 ** attempt
                if wait > 600:
                    raise RuntimeError("orçamento diário do OpenAlex esgotado — retome amanhã") from e
                time.sleep(wait)
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, json.JSONDecodeError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenAlex indisponível após {retries} tentativas")


def rate_limit(key) -> dict:
    """Leitura gratuita do consumo da chave (créditos do dia e pré-pagos)."""
    try:
        r = _http(f"{API}/rate-limit", key)["rate_limit"]
        return {k: r.get(k) for k in ("credits_used", "credits_remaining", "onetime_credits_remaining",
                                      "prepaid_remaining_usd", "daily_used_usd", "resets_at")}
    except Exception as exc:  # conferência é auxiliar; não impede a coleta
        return {"erro": str(exc)[:200]}


def collect_lot(ids, date_from, date_to, area_field, lang, key, ledger, lot_tag):
    """Uma consulta de lista paginada por cursor; cada página = 1 crédito (verificado antes)."""
    flt = (f"language:{lang},from_publication_date:{date_from},to_publication_date:{date_to},"
           f"primary_topic.field.id:{area_field},authorships.author.id:{'|'.join(ids)}")
    cursor, rows_a, rows_w, page = "*", [], [], 0
    while cursor:
        if not ledger.can(1):
            raise BudgetExceeded(f"teto atingido antes da página {page} do lote {lot_tag}")
        q = urllib.parse.urlencode({"filter": flt, "per-page": PER_PAGE, "cursor": cursor})
        res = _http(f"{API}/works?{q}", key)
        ledger.charge("lista_historico", 1, lote=lot_tag, pagina=page, resultados=len(res.get("results", [])))
        for w in res.get("results", []):
            a, wr = _extract_records(w)
            rows_a.extend(a)
            rows_w.append(wr)
        cursor = res.get("meta", {}).get("next_cursor") if res.get("results") else None
        page += 1
    return rows_a, rows_w


_ID_RE = None


def cached_ids(path) -> set:
    """IDs já presentes num cache .jsonl (só o 'id' de topo, curto: W123/I456), sem decodificar o JSON."""
    import re
    global _ID_RE
    _ID_RE = _ID_RE or re.compile(rb'"id": "([A-Z][0-9]+)"')
    out = set()
    if path.exists():
        with open(path, "rb") as fh:
            for line in fh:
                m = _ID_RE.search(line)
                if m:
                    out.add(m.group(1).decode())
    return out


def enrich_lean(entity, ids, select, cache_path, mailto, key, ledger, batch=LOT):
    """Consulta só os IDs ausentes do cache, 50 por consulta (1 crédito cada, cobrado antes)."""
    have = cached_ids(cache_path)
    todo = sorted(set(ids) - have)
    sel = ",".join(sorted(set(select.split(",")) | {"id"}))
    recs = []
    with open(cache_path, "a", encoding="utf-8") as fh:
        for k in range(0, len(todo), batch):
            lot = todo[k:k + batch]
            if not ledger.can(1):
                raise BudgetExceeded(f"teto atingido no enriquecimento de {entity}")
            q = urllib.parse.urlencode({"filter": "openalex:" + "|".join(lot), "per-page": len(lot),
                                        "select": sel, "mailto": mailto})
            res = _http(f"{API}/{entity}?{q}", key)
            ledger.charge(f"enriquecimento_{entity}", 1, ids=len(lot), resultados=len(res.get("results", [])))
            got = {}
            for r in res.get("results", []):
                r["id"] = r["id"].rstrip("/").split("/")[-1]
                got[r["id"]] = r
            for i in lot:
                rec = got.get(i, {"id": i, "_missing": True})
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                recs.append(rec)
            fh.flush()
    return len(todo), len(ids) - len(todo), recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--corte", type=int, required=True)
    ap.add_argument("--limite", type=int, required=True, help="teto TOTAL de créditos (listas + enriquecimento)")
    ap.add_argument("--janela", type=int, default=5)
    ap.add_argument("--sem-enriquecimento", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = cfg["bases"][args.base]
    enr = yaml.safe_load(open(resolve("configs/enrich.yaml")))
    filt = load_filters()
    lang, field = filt.get("language", "en"), prof["fields"][0]
    c = args.corte
    gaps = pd.read_csv(resolve(f"runs/robustez/t4/reconstrucao_{args.base}_{c}/lacunas.csv"))
    data_dir = resolve(f"data/robustez/t4/{args.base}_{c}")
    data_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(resolve(f"runs/robustez/t4/coleta_{args.base}_{c}"), args.limite)
    state_f = data_dir / "estado.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"lotes_feitos": [], "enriquecimento": {}}
    key = get_secret("OPENALEX_API_KEY")
    if "antes" not in ledger.meta:
        ledger.meta["antes"] = rate_limit(key)
        ledger.save()
    t0 = time.time()

    # lotes: novos (janela inteira) e já coletados (anos que faltam, agrupados em intervalos contíguos)
    lots = []
    new = sorted(gaps.loc[gaps["situacao"] == "novo", "author_id"])
    for i in range(0, len(new), LOT):
        lots.append((f"novo_{i // LOT:04d}", new[i:i + LOT], f"{c - args.janela + 1}-01-01", f"{c}-12-31"))
    old = gaps[gaps["situacao"] == "ja_coletado"]
    if len(old):
        years = sorted({int(y) for ys in old["anos_faltando"].astype(str) for y in ys.split(",") if y})
        spans, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                spans.append(cur)
                cur = [y]
        spans.append(cur)
        ids = sorted(old["author_id"])
        for sp in spans:
            for i in range(0, len(ids), LOT):
                lots.append((f"anos{sp[0]}-{sp[-1]}_{i // LOT:04d}", ids[i:i + LOT], f"{sp[0]}-01-01", f"{sp[-1]}-12-31"))
    print(f"[coletor] {len(lots)} lotes ({len(state['lotes_feitos'])} já feitos); gasto até agora "
          f"{ledger.spent}/{ledger.limit} créditos", flush=True)

    stopped = None
    try:
        for tag, ids, d0, d1 in lots:
            if tag in state["lotes_feitos"]:
                continue
            a, w = collect_lot(ids, d0, d1, field, lang, key, ledger, tag)
            pd.DataFrame(a).to_parquet(data_dir / f"auth_{tag}.parquet", index=False)
            pd.DataFrame(w).to_parquet(data_dir / f"works_{tag}.parquet", index=False)
            state["lotes_feitos"].append(tag)
            state_f.write_text(json.dumps(state, indent=1))
            if len(state["lotes_feitos"]) % 25 == 0:
                print(f"[coletor] {len(state['lotes_feitos'])}/{len(lots)} lotes; gasto {ledger.spent}", flush=True)

        # enriquecimento: tópicos dos trabalhos novos e instituições novas (só o que falta no cache).
        # Rotina enxuta: lê só os IDs do cache (sem decodificar o JSON inteiro), consulta em lotes
        # de 50 e anexa ao MESMO arquivo, no mesmo formato de enrich/openalex_cache.fetch_by_ids;
        # cada consulta é cobrada ANTES de ser feita (teto verificado por consulta).
        if not args.sem_enriquecimento:
            oa = enr["openalex"]
            cache_dir = resolve(oa["cache_dir"])
            works_new = pd.concat([pd.read_parquet(p) for p in sorted(data_dir.glob("works_*.parquet"))], ignore_index=True)
            auth_new = pd.concat([pd.read_parquet(p) for p in sorted(data_dir.glob("auth_*.parquet"))], ignore_index=True)
            inst_ids = sorted({i for blob in auth_new["institution_ids"].dropna() for i in json.loads(blob) if i})
            plan = [("works", sorted(set(works_new["id"].dropna())), enr["topics"]["select"]),
                    ("institutions", inst_ids, enr["institutions"]["select"])]
            for entity, ids_all, select in plan:
                n_todo, n_cached, recs = enrich_lean(entity, ids_all, select, cache_dir / f"{entity}.jsonl",
                                                     oa["mailto"], key, ledger)
                state["enriquecimento"][entity] = {"ids": len(ids_all), "ja_em_cache": n_cached, "consultados": n_todo}
                if entity == "institutions":          # ancestrais (hierarquia) que faltam no cache
                    parents = sorted({p.rstrip("/").split("/")[-1] for r in recs for p in (r.get("lineage") or [])
                                      if p} - set(ids_all))
                    n2, c2, _ = enrich_lean(entity, parents, select, cache_dir / f"{entity}.jsonl", oa["mailto"], key, ledger)
                    state["enriquecimento"]["institutions_ancestrais"] = {"ids": len(parents), "ja_em_cache": c2, "consultados": n2}
                state_f.write_text(json.dumps(state, indent=1))
                print(f"[coletor] enriquecimento {entity}: {n_todo} consultados ({n_cached} já em cache); gasto {ledger.spent}",
                      flush=True)

        # ORCID dos candidatos novos (gratuito; cache existente)
        from coauthor_rec.data.orcid import fetch_claims
        auth_new = pd.concat([pd.read_parquet(p) for p in sorted(data_dir.glob("auth_*.parquet"))], ignore_index=True)
        orcids = auth_new.loc[auth_new["author_id"].isin(set(new)), "author_orcid"].dropna().unique()
        hc = filt.get("hygiene", {}).get("orcid_api", {})
        before = sum((resolve(hc.get("cache_dir", "data/cache/orcid")) / f"{o}.json").exists() for o in orcids)
        fetch_claims(orcids, resolve(hc.get("cache_dir", "data/cache/orcid")), hc.get("requests_per_second", 15),
                     verbose=False, workers=hc.get("workers", 12))
        state["orcid"] = {"orcids_candidatos_novos": int(len(orcids)), "ja_em_cache": int(before),
                          "leituras": int(len(orcids) - before)}
        state_f.write_text(json.dumps(state, indent=1))
    except BudgetExceeded as exc:
        stopped = str(exc)
        print(f"[coletor] INTERROMPIDO pelo teto: {exc}", flush=True)
    finally:
        ledger.meta["depois"] = rate_limit(key)
        b, a = ledger.meta.get("antes", {}), ledger.meta["depois"]
        try:
            ledger.meta["gasto_informado_pela_api"] = {
                "creditos_do_dia": (a["credits_used"] or 0) - (b["credits_used"] or 0),
                "creditos_pre_pagos": (b["onetime_credits_remaining"] or 0) - (a["onetime_credits_remaining"] or 0),
                "nota": "inclui qualquer outro uso da mesma chave no período; os créditos do dia zeram à meia-noite UTC"}
        except (KeyError, TypeError):
            pass
        ledger.meta["interrompido"] = stopped
        ledger.meta["tempo_s"] = round(time.time() - t0, 1)
        ledger.save()
        print(f"[coletor] gasto contado {ledger.spent}/{ledger.limit} créditos por tipo {ledger.by_type}; "
              f"API: {ledger.meta.get('gasto_informado_pela_api')}", flush=True)


if __name__ == "__main__":
    main()
