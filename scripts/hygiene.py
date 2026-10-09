"""Higienização de autores de uma base (docs/HIGIENIZACAO.md).

  raw (authorships+works) → limpeza (filters.yaml) → registros ORCID (cache) →
  pessoa canônica + níveis A/B/C/X + vínculo I1/I2/I3 → corpus higienizado +
  autores elegíveis (E1–E8) + relatório com funil de atrito.

Saídas:
  <corpus da base>                         corpus higienizado (author_id = pessoa canônica)
  data/processed/autores_<base>.csv        tabela de autores com E1–E8 e `eligible`
  runs/<base>/hygiene.json                 relatório (níveis, fusões, funil)

Uso:
    PYTHONHASHSEED=0 python scripts/hygiene.py computacao
    PYTHONHASHSEED=0 python scripts/hygiene.py computacao --offline   # só cache ORCID
"""
from __future__ import annotations

import argparse, json, os, sys

import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import hygienize  # noqa: E402
from coauthor_rec.data.orcid import fetch_claims  # noqa: E402


def run(base_key: str, offline: bool = False, verbose: bool = True):
    profiles = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    prof = profiles["bases"][base_key]
    filt = load_filters()
    hcfg = filt.get("hygiene", {})
    eval_cfg = load_config("eval")
    raw_dir = resolve(prof["raw_dir"])

    auth = pd.read_csv(raw_dir / "authorships.csv")
    works = pd.read_csv(raw_dir / "works.csv")
    unresolved = int(auth["author_id"].isna().sum())
    merged = clean_and_merge(auth, works, min_year=eval_cfg["split"]["min_year"],
                             language=eval_cfg["split"]["language"])

    claims = {}
    if "author_orcid" in merged.columns and merged["author_orcid"].notna().any():
        api = hcfg.get("orcid_api", {})
        orcids = merged["author_orcid"].dropna().unique()
        if offline:
            cache = resolve(api.get("cache_dir", "data/cache/orcid"))
            claims = {o: json.loads((cache / f"{o}.json").read_text())
                      for o in orcids if (cache / f"{o}.json").exists()}
            print(f"[hygiene] --offline: {len(claims)}/{len(orcids)} ORCIDs no cache")
        else:
            claims = fetch_claims(orcids, resolve(api.get("cache_dir", "data/cache/orcid")),
                                  api.get("requests_per_second", 8), verbose=verbose)
    else:
        print("[hygiene] AVISO: sem coluna author_orcid — coleta antiga. Todas as autorias "
              "ficam no máximo nível C e ninguém é elegível com require_orcid. Re-colete "
              "(build_base.py <base> --recollect).")

    corpus, table, report = hygienize(merged, claims, hcfg, filt.get("max_coauthors_per_work"))
    report = {"base": base_key, "raw_dir": prof["raw_dir"],
              "autorias_brutas": int(len(auth)), "autorias_sem_author_id": unresolved,
              "orcids_consultados": len(claims), **report}

    corpus_path = resolve(prof["corpus"])
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(corpus_path, index=False)
    table.to_csv(resolve(f"data/processed/autores_{base_key}.csv"))
    out = resolve(f"runs/{base_key}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hygiene.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    if verbose:
        a = report["autorias"]
        print(f"\n[hygiene:{base_key}] autorias brutas {report['autorias_brutas']} "
              f"(sem author_id: {unresolved})  ·  após limpeza {a['total']}")
        print(f"  níveis  A={a['nivel_A']}  B={a['nivel_B']}  C={a['nivel_C']}  X={a['nivel_X']}")
        c = report["canonicalizacao"]
        print(f"  pessoa canônica: {c['author_ids']} author_ids → {c['persons_canonical']} pessoas "
              f"({c['orcids_fragmented']} ORCIDs fragmentados fundidos; "
              f"{c['author_ids_conflict']} ids em conflito)")
        print(f"  vínculo institucional: {report['vinculo_institucional']}")
        print("  funil de elegibilidade:")
        for r in report["funil_elegibilidade"]:
            print(f"    {r['restantes']:>8}  {r['etapa']}")
        print(f"  -> {prof['corpus']} · data/processed/autores_{base_key}.csv · runs/{base_key}/hygiene.json")
    return corpus, table, report


if __name__ == "__main__":
    profiles = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    ap = argparse.ArgumentParser()
    ap.add_argument("base", choices=list(profiles["bases"]))
    ap.add_argument("--offline", action="store_true", help="usa só o cache do ORCID")
    args = ap.parse_args()
    run(args.base, offline=args.offline)
