"""Diagnóstico dos coautores novos "fora de T0" (docs/LINHA_BASE.md §7, achado 1).

De 58% a 73% dos coautores novos de T1 não têm nenhum trabalho no corpus até 2021. Isto separa
dois fenômenos que a linha de base não distingue:

- **estreante real**: a pessoa não tinha publicação nenhuma até 2021 (no OpenAlex inteiro);
- **histórico fora da coleta**: tinha, mas o corpus não a alcançou — ou porque publicava em
  OUTRA área, ou porque publicava NA área mas estava a mais de 1 salto das sementes (a coleta é
  egocêntrica: sementes + seus coautores de T0).

Só MEDE. Nada daqui alimenta modelo algum: escolher quem coletar olhando o futuro seria vazamento.

Camada 1 (todos): /authors em lotes de 50 → trabalhos antes de 2022 = works_count − Σ counts_by_year
(ano ≥ 2022). Camada 2 (amostra de ``--amostra`` por base, entre os que tinham histórico):
/works agrupado por ano, filtrado pelo campo da base → trabalhos NA ÁREA até 2021 e em 2017–2021
(a janela da expansão dos candidatos).

Limitação: um "estreante" pode ser identidade fragmentada no OpenAlex sem ORCID (a pessoa tem
trabalhos antigos sob outro ID). Para quem tem ORCID, todos os IDs do corpus são somados.

Uso: python scripts/diagnose_outside_t0.py [bases…] [--amostra 100]
Saída: runs/fora_t0/<base>.json e docs/DIAGNOSTICO_FORA_T0.md (tabela).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.orcid import _RateLimiter  # noqa: E402
from coauthor_rec.enrich.openalex_cache import API, _get, fetch_by_ids  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.secrets import get_secret  # noqa: E402

CUTOFF = 2021


def works_before(rec: dict, cutoff: int = CUTOFF) -> int | None:
    if not rec or rec.get("_missing"):
        return None
    after = sum(c.get("works_count", 0) for c in rec.get("counts_by_year") or [] if c.get("year", 0) > cutoff)
    return max(int(rec.get("works_count") or 0) - after, 0)


def field_years(ids: list[str], field_id: int, mailto: str, api_key, limiter, cache: dict) -> dict:
    """Trabalhos por ano do(s) ID(s) da pessoa no campo ``field_id`` (1 consulta, cacheada)."""
    key = f"{field_id}|{'|'.join(sorted(ids))}"
    if key in cache:
        return {int(y): c for y, c in cache[key].items()}      # JSON grava os anos como texto
    limiter.wait()
    q = urllib.parse.urlencode({"filter": f"author.id:{'|'.join(ids)},primary_topic.field.id:{field_id}",
                                "group_by": "publication_year", "mailto": mailto})
    res = _get(f"{API.format(entity='works')}?{q}", api_key=api_key)
    out = {int(g["key"]): int(g["count"]) for g in res.get("group_by", []) if str(g["key"]).isdigit()}
    cache[key] = out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bases", nargs="*")
    ap.add_argument("--amostra", type=int, default=100)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    enr = yaml.safe_load(open(resolve("configs/enrich.yaml")))["openalex"]
    ev = load_config("eval")
    cap = load_filters()["max_coauthors_per_work"]
    bases = args.bases or cfg["gradiente"]
    cache_dir = resolve(enr["cache_dir"])
    fcache_f = cache_dir / "author_field_years.json"
    fcache = json.loads(fcache_f.read_text()) if fcache_f.exists() else {}
    api_key = get_secret("OPENALEX_API_KEY")
    out_dir = resolve("runs/fora_t0")
    out_dir.mkdir(parents=True, exist_ok=True)

    for base in bases:
        prof = cfg["bases"][base]
        field = prof["fields"][0]
        corpus = pd.read_parquet(resolve(prof["corpus"]), columns=["work_id", "author_id", "author_id_openalex",
                                                                    "author_name", "publication_date"])
        au = pd.read_csv(resolve(f"data/processed/autores_{base}.csv"), index_col=0, usecols=["canonical_id", "alvo"])
        P = build_protocol(corpus, au.index[au["alvo"]].tolist(), cfg.get("split"), cap,
                           ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
        pairs = [(a, b) for a in P.targets for b in P.gt[a] if b not in P.t0_authors]
        people = sorted({b for _, b in pairs})
        ids_of = (corpus[corpus["author_id"].isin(set(people))]
                  .groupby("author_id")["author_id_openalex"].agg(lambda s: sorted(set(s.dropna()))).to_dict())
        del corpus
        print(f"[{base}] {len(pairs)} pares / {len(people)} pessoas fora de T0", flush=True)

        # camada 1: histórico em qualquer área
        all_ids = sorted({i for v in ids_of.values() for i in v})
        recs = fetch_by_ids("authors", all_ids, "id,works_count,counts_by_year", cache_dir, enr["mailto"],
                            enr["batch_size"], enr["requests_per_second"], enr["workers"])
        before = {}
        for p in people:
            vals = [works_before(recs.get(i)) for i in ids_of.get(p, [])]
            vals = [v for v in vals if v is not None]
            before[p] = sum(vals) if vals else None

        # camada 2: histórico NA área (amostra entre os que tinham algum histórico)
        with_hist = sorted(p for p in people if before[p])
        rng = np.random.default_rng(42)
        sample = list(rng.choice(with_hist, size=min(args.amostra, len(with_hist)), replace=False)) if with_hist else []
        limiter = _RateLimiter(enr["requests_per_second"])
        with ThreadPoolExecutor(max_workers=enr["workers"]) as ex:
            fy = dict(zip(sample, ex.map(lambda p: field_years(ids_of[p], field, enr["mailto"], api_key,
                                                               limiter, fcache), sample)))
        fcache_f.write_text(json.dumps(fcache))
        in_field = {p: sum(c for y, c in d.items() if y <= CUTOFF) for p, d in fy.items()}
        in_window = {p: sum(c for y, c in d.items() if CUTOFF - 4 <= y <= CUTOFF) for p, d in fy.items()}

        # agregação por pessoa e por par
        n_p = len(people)
        unknown = sum(1 for p in people if before[p] is None)
        newcomer = sum(1 for p in people if before[p] == 0)
        hist = len(with_hist)
        frac_field = np.mean([in_field[p] > 0 for p in sample]) if sample else float("nan")
        frac_window = np.mean([in_window[p] > 0 for p in sample]) if sample else float("nan")
        pw = defaultdict(int)
        for _, b in pairs:
            pw["sem_registro" if before[b] is None else "estreante" if before[b] == 0 else "com_historico"] += 1
        res = {"base": base, "campo": field, "pares_fora_T0": len(pairs), "pessoas_fora_T0": n_p,
               "pares_novos_total": sum(len(P.gt[a]) for a in P.targets),
               "pessoas": {"estreante_real": newcomer, "com_historico_ate_2021": hist, "sem_registro_no_openalex": unknown},
               "pares": dict(pw),
               "amostra": {"n": len(sample), "frac_com_historico_na_area": round(float(frac_field), 4),
                           "frac_na_area_em_2017_2021": round(float(frac_window), 4),
                           "mediana_trabalhos_antes_2022": float(np.median([before[p] for p in sample])) if sample else None,
                           "mediana_trabalhos_na_area_antes_2022": float(np.median(list(in_field.values()))) if sample else None},
               "consultas": {"autores": -(-len(all_ids) // enr["batch_size"]), "amostra_area": len(sample)}}
        (out_dir / f"{base}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"[{base}] {json.dumps(res, ensure_ascii=False)}", flush=True)
    report(cfg)


def report(cfg):
    order = [b for b in cfg["gradiente"] if resolve(f"runs/fora_t0/{b}.json").exists()]
    R = {b: json.loads(resolve(f"runs/fora_t0/{b}.json").read_text()) for b in order}
    lab = {b: cfg["bases"][b]["label"] for b in order}

    def pct(x):
        return f"{100 * x:.1f}".replace(".", ",")

    def num(x):
        return f"{x:,}".replace(",", ".")
    L = ["# Diagnóstico dos coautores novos fora de T0", "",
         "> Gerado por `scripts/diagnose_outside_t0.py`. Método e leitura em [LINHA_BASE.md](LINHA_BASE.md) §8.", "",
         "## 1. Por pessoa (todas) e por par", "",
         "| Base | Pessoas fora de T0 | Estreante real | Com histórico até 2021 | Sem registro | Pares fora de T0 | Pares com estreante |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for b in order:
        r = R[b]
        n, p = r["pessoas_fora_T0"], r["pessoas"]
        L.append(f"| {lab[b]} | {num(n)} | {pct(p['estreante_real'] / n)} | {pct(p['com_historico_ate_2021'] / n)} | "
                 f"{pct(p['sem_registro_no_openalex'] / n)} | {num(r['pares_fora_T0'])} | "
                 f"{pct(r['pares'].get('estreante', 0) / r['pares_fora_T0'])} |")
    L += ["", "## 2. Entre os que tinham histórico — amostra: o histórico era na área?", "",
          "| Base | Amostra | Com trabalho na área até 2021 | Na área em 2017–2021 | Mediana de trabalhos até 2021 | Mediana na área |",
          "|---|---:|---:|---:|---:|---:|"]
    for b in order:
        a = R[b]["amostra"]
        L.append(f"| {lab[b]} | {a['n']} | {pct(a['frac_com_historico_na_area'])} | {pct(a['frac_na_area_em_2017_2021'])} | "
                 f"{a['mediana_trabalhos_antes_2022']:.0f} | {a['mediana_trabalhos_na_area_antes_2022']:.0f} |")
    L += ["", "## 3. Decomposição estimada dos pares fora de T0", "",
          "Estimativa: a fração da amostra (§2) aplicada aos pares com histórico.", "",
          "| Base | Estreante real | Histórico só em outra área | Histórico na área, fora da coleta | Sem registro |",
          "|---|---:|---:|---:|---:|"]
    for b in order:
        r = R[b]
        n = r["pares_fora_T0"]
        h = r["pares"].get("com_historico", 0)
        f = r["amostra"]["frac_com_historico_na_area"]
        L.append(f"| {lab[b]} | {pct(r['pares'].get('estreante', 0) / n)} | {pct(h * (1 - f) / n)} | "
                 f"{pct(h * f / n)} | {pct(r['pares'].get('sem_registro', 0) / n)} |")
    L.append("")
    resolve("docs/DIAGNOSTICO_FORA_T0.md").write_text("\n".join(L))
    print("escrito docs/DIAGNOSTICO_FORA_T0.md")


if __name__ == "__main__":
    main()
