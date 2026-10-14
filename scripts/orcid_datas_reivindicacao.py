"""Sensibilidade do E3 às DATAS DE CRIAÇÃO dos itens do ORCID (docs/PROTOCOLO_CORRIGIDO_2021.md §4).

O E3 atual exige ≥1 trabalho reivindicado no registro ORCID DE HOJE. Aqui, para cada semente,
relê-se o registro público (API pública v3.0, gratuita; token /read-public se houver) e guarda-se,
para cada grupo de trabalho com DOI: a data de criação MAIS ANTIGA entre os itens do grupo
(`created-date`, carimbo de quando o item foi adicionado ao registro) e quem o adicionou
(`source`: a própria pessoa ou um cliente integrado).

Sensibilidade: E3 "datado" = só valem reivindicações cujo item foi criado até o fim do corte.
NÃO é prova de disponibilidade histórica: o carimbo não diz se o item estava público no corte,
pode refletir sincronização automática, e a documentação não informa se reinserções o
reiniciam (ver PROTOCOLO_CORRIGIDO_2021 §4).

Uso: PYTHONHASHSEED=0 python scripts/orcid_datas_reivindicacao.py [--cortes 2021] [--bases …]
Saídas: data/cache/orcid_datas/<orcid>.json (registro compacto), runs/robustez/orcid_datas/sensibilidade.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import author_table, authorship_levels, canonicalize  # noqa: E402
from coauthor_rec.data.orcid import API, _RateLimiter, _get, orcid_token  # noqa: E402


def _ts(v):
    try:
        return datetime.fromtimestamp(int(v["value"]) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, KeyError, ValueError):
        return None


def parse_dates(record: dict | None) -> dict:
    """{doi: {"criado": AAAA-MM-DD mais antigo do grupo, "fontes": [...]} } a partir de /record."""
    out = {}
    groups = (((record or {}).get("activities-summary") or {}).get("works") or {}).get("group") or []
    for g in groups:
        dois = {e.get("external-id-value", "").lower().replace("https://doi.org/", "").strip()
                for e in ((g.get("external-ids") or {}).get("external-id") or [])
                if (e.get("external-id-type") or "").lower() == "doi" and e.get("external-id-value")}
        if not dois:
            continue
        dates, sources = [], []
        for w in g.get("work-summary") or []:
            d = _ts(w.get("created-date"))
            if d:
                dates.append(d)
            src = w.get("source") or {}
            sources.append("pessoa" if src.get("source-orcid") else
                           ("cliente:" + ((src.get("source-name") or {}).get("value") or "?")) if src.get("source-client-id")
                           else "desconhecida")
        for doi in dois:
            prev = out.get(doi, {"criado": None, "fontes": []})
            cand = min([x for x in (prev["criado"], *(dates or [None])) if x], default=None)
            out[doi] = {"criado": cand, "fontes": sorted(set(prev["fontes"]) | set(sources))}
    return out


def fetch_dates(orcids, cache_dir, rps=10, workers=8):
    cache_dir.mkdir(parents=True, exist_ok=True)
    todo = [o for o in sorted(set(orcids)) if not (cache_dir / f"{o}.json").exists()]
    token = orcid_token()
    limiter = _RateLimiter(min(rps, 10 if token else 6))
    print(f"[orcid-datas] {len(set(orcids)) - len(todo)} em cache, {len(todo)} a ler "
          f"({'com token' if token else 'anônimo'})", flush=True)

    def one(o):
        rec = _get(API.format(orcid=o), limiter, token)
        (cache_dir / f"{o}.json").write_text(json.dumps({"existe": rec is not None, "dois": parse_dates(rec)}))
        return o
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        for i, _ in enumerate(as_completed([pool.submit(one, o) for o in todo]), 1):
            if i % 500 == 0:
                print(f"[orcid-datas] {i}/{len(todo)}", flush=True)
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", nargs="*", default=["medicina", "computacao", "matematica", "economia"])
    ap.add_argument("--cortes", nargs="*", type=int, default=[2021])
    args = ap.parse_args()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    filt = load_filters()
    hcfg, cap = filt.get("hygiene", {}), filt.get("max_coauthors_per_work")
    ev = load_config("eval")
    claims_dir = resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
    dates_dir = resolve("data/cache/orcid_datas")
    seeds_all = {b: pd.read_csv(resolve(cfg["bases"][b]["raw_dir"]) / "seeds.csv") for b in args.bases}
    t0 = time.time()
    n_read = fetch_dates(pd.concat(seeds_all.values())["author_orcid"].dropna(), dates_dir)
    out = {"leituras_orcid": n_read, "nota": "sensibilidade; não é prova de disponibilidade histórica", "bases": {}}
    for b in args.bases:
        raw = resolve(cfg["bases"][b]["raw_dir"])
        seeds = seeds_all[b]
        works = pd.read_csv(raw / "works.csv")
        wyear = dict(zip(works["id"], pd.to_datetime(works["publication_date"], errors="coerce").dt.year))
        seeds["ano_sorteio"] = seeds["seed_work_id"].map(wyear)
        auth = pd.read_csv(raw / "authorships.csv")
        sw = set(auth.loc[auth["author_id"].isin(set(seeds["author_id"])), "work_id"])
        merged = clean_and_merge(auth[auth["work_id"].isin(sw)], works, min_year=ev["split"]["min_year"],
                                 language=ev["split"]["language"])
        claims = {o: json.loads((claims_dir / f"{o}.json").read_text()) for o in seeds["author_orcid"].dropna()
                  if (claims_dir / f"{o}.json").exists()}
        dated = {o: json.loads((dates_dir / f"{o}.json").read_text()) for o in seeds["author_orcid"].dropna()
                 if (dates_dir / f"{o}.json").exists()}
        res = {}
        for c in args.cortes:
            fim = f"{c}-12-31"
            claims_c = {}
            for o, cl in claims.items():
                dd = (dated.get(o) or {}).get("dois", {})
                keep = [x for x in cl.get("dois", []) if (dd.get(x) or {}).get("criado") and dd[x]["criado"] <= fim]
                claims_c[o] = {**cl, "dois": keep}
            yr = pd.to_datetime(merged["publication_date"], errors="coerce").dt.year
            rows = {}
            for name, cl in (("atual", claims), ("datado", claims_c)):
                df, _ = canonicalize(merged)
                df = authorship_levels(df, cl, hcfg.get("reject_name_mismatch", True))
                rows[name] = author_table(df[yr <= c], hcfg.get("author_criteria", {}), cap)
                canon = dict(zip(df["author_id"], df["canonical_id"]))
            sc = seeds[seeds["ano_sorteio"] <= c].copy()
            sc["pessoa"] = [canon.get(a, f"orcid:{o}" if isinstance(o, str) else a) for a, o in zip(sc["author_id"], sc["author_orcid"])]
            for name, t in rows.items():
                sc[f"elegivel_{name}"] = sc["pessoa"].map(t["eligible"]).fillna(False).astype(bool)
            # cobertura das datas entre as reivindicações das sementes do corte
            all_d = [((dated.get(o) or {}).get("dois", {}).get(x) or {}) for o in sc["author_orcid"].dropna()
                     for x in (claims.get(o) or {}).get("dois", [])]
            with_date = [x for x in all_d if x.get("criado")]
            srcs = pd.Series([f for x in all_d for f in x.get("fontes", [])])
            res[c] = {
                "sementes_do_corte": len(sc),
                "elegiveis_regra_atual": int(sc["elegivel_atual"].sum()),
                "elegiveis_E3_datado": int(sc["elegivel_datado"].sum()),
                "saem_com_E3_datado": int((sc["elegivel_atual"] & ~sc["elegivel_datado"]).sum()),
                "entram_com_E3_datado": int((~sc["elegivel_atual"] & sc["elegivel_datado"]).sum()),
                "reivindicacoes_das_sementes": len(all_d),
                "com_data_de_criacao": len(with_date),
                "criadas_ate_o_fim_do_corte": int(sum(x["criado"] <= fim for x in with_date)),
                "criadas_depois": int(sum(x["criado"] > fim for x in with_date)),
                "itens_por_fonte": {"pessoa": int((srcs == "pessoa").sum()),
                                    "cliente_integrado": int(srcs.str.startswith("cliente:").sum()),
                                    "desconhecida": int((srcs == "desconhecida").sum())},
                "clientes_mais_frequentes": srcs[srcs.str.startswith("cliente:")].value_counts().head(5).to_dict(),
            }
            resolve("runs/robustez/orcid_datas").mkdir(parents=True, exist_ok=True)
            sc.to_csv(resolve(f"runs/robustez/orcid_datas/elegibilidade_{b}_{c}.csv"), index=False)
            print(f"[{b}:{c}] {json.dumps(res[c], ensure_ascii=False)}", flush=True)
        out["bases"][b] = res
    out["tempo_s"] = round(time.time() - t0, 1)
    resolve(f"runs/robustez/orcid_datas/sensibilidade_{'_'.join(map(str, args.cortes))}_{len(args.bases)}bases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("escrito runs/robustez/orcid_datas/sensibilidade.json")


if __name__ == "__main__":
    main()
