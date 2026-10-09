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

    from coauthor_rec.data.raw import load_raw
    auth, works = load_raw(raw_dir)          # sementes + histórico dos candidatos (se expandido)
    unresolved = int(auth["author_id"].isna().sum())
    merged = clean_and_merge(auth, works, min_year=eval_cfg["split"]["min_year"],
                             language=eval_cfg["split"]["language"])

    claims = {}
    if "author_orcid" in merged.columns and merged["author_orcid"].notna().any():
        api = hcfg.get("orcid_api", {})
        # Só quem aparece em ≥1 work dentro do teto de coautores (os demais não geram
        # arestas e reprovam em E8) — evita milhares de consultas inúteis em consórcios.
        cap = filt.get("max_coauthors_per_work")
        team = merged.groupby("work_id")["author_id"].transform("nunique")
        small = merged[team <= cap] if cap else merged
        # Com a expansão, o bruto traz também os coautores dos candidatos (3º grau). Para
        # caber na cota do ORCID, só sementes e candidatos têm o registro consultado — são
        # os únicos usados como alvo (E1–E8) ou como candidatos com trajetória (camada 3).
        cpath = raw_dir / "candidates.csv"
        if cpath.exists():
            pessoas = set(pd.read_csv(raw_dir / "seeds.csv")["author_id"]) | set(pd.read_csv(cpath)["author_id"])
            small = small[small["author_id"].isin(pessoas)]
        orcids = small["author_orcid"].dropna().unique()
        if offline:
            cache = resolve(api.get("cache_dir", "data/cache/orcid"))
            claims = {o: json.loads((cache / f"{o}.json").read_text())
                      for o in orcids if (cache / f"{o}.json").exists()}
            print(f"[hygiene] --offline: {len(claims)}/{len(orcids)} ORCIDs no cache")
        else:
            claims = fetch_claims(orcids, resolve(api.get("cache_dir", "data/cache/orcid")),
                                  api.get("requests_per_second", 15), verbose=verbose,
                                  workers=api.get("workers", 12))
    else:
        print("[hygiene] AVISO: sem coluna author_orcid — coleta antiga. Todas as autorias "
              "ficam no máximo nível C e ninguém é elegível com require_orcid. Re-colete "
              "(build_base.py <base> --recollect).")

    corpus, table, report = hygienize(merged, claims, hcfg, filt.get("max_coauthors_per_work"))

    # Sementes (coleta seeded): só elas têm histórico completo na área → alvos de
    # avaliação = sementes ∩ elegíveis (E1–E8). Em coletas sem seeds.csv, todo elegível.
    seeds_path = raw_dir / "seeds.csv"
    if seeds_path.exists():
        canon = dict(zip(corpus["author_id_openalex"], corpus["author_id"]))
        sd = pd.read_csv(seeds_path)
        seed_ids = {canon.get(a, f"orcid:{o}" if isinstance(o, str) else a)
                    for a, o in zip(sd["author_id"], sd.get("author_orcid", [None] * len(sd)))}
        table["is_seed"] = table.index.isin(seed_ids)
    else:
        table["is_seed"] = True
    table["alvo"] = table["eligible"] & table["is_seed"]
    report["sementes"] = {"total": int(table["is_seed"].sum()),
                          "elegiveis_alvos": int(table["alvo"].sum()),
                          "seeds_csv": seeds_path.exists()}

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
        s = report["sementes"]
        print(f"  sementes: {s['total']} · ALVOS de avaliação (semente ∩ elegível): {s['elegiveis_alvos']}")
        print(f"  -> {prof['corpus']} · data/processed/autores_{base_key}.csv · runs/{base_key}/hygiene.json")
    return corpus, table, report


if __name__ == "__main__":
    profiles = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    ap = argparse.ArgumentParser()
    ap.add_argument("base", choices=list(profiles["bases"]))
    ap.add_argument("--offline", action="store_true", help="usa só o cache do ORCID")
    args = ap.parse_args()
    run(args.base, offline=args.offline)
