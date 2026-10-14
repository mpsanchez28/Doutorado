"""Cria uma cópia congelada das entradas da reconstrução (ESPECIFICACAO_METODOLOGICA §2, emenda E2).

Copia, para cada base e corte: o bruto usado (sementes, autorias, trabalhos, candidatos, expansão
original), os dados coletados pelo T4 (com estado.json e as lacunas v1, que definem o que já foi
consultado), os registros ORCID de todas as pessoas com ORCID nesses dados, os registros de
enriquecimento (trabalhos e instituições, com ancestrais) e as configurações. Nenhuma chamada a API.

Deve rodar SEM coleta em andamento (a coleta grava nos caches globais). A cópia é selada (somente
leitura) e verificada; um registro ausente na origem é listado como ausente — nunca buscado.

Uso: python scripts/congelar_entradas.py S1 economia:2019,2021 matematica:2021
Saídas: data/snapshots/<id>/ (fora do Git) e runs/robustez/snapshots/<id>.json (manifesto compacto)
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import resolve  # noqa: E402
from coauthor_rec.data.snapshot import create_snapshot, verify_snapshot  # noqa: E402

RAW_FILES = ("seeds.csv", "authorships.csv", "works.csv", "candidates.csv", "authorships_cand.parquet", "works_cand.parquet")


def _orcid(x) -> str | None:
    return str(x).rstrip("/").split("/")[-1] if isinstance(x, str) and x.strip() else None


def main():
    sid, specs = sys.argv[1], sys.argv[2:]
    t0 = time.time()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    files, orcids, wids, iids = {}, set(), set(), set()
    plan = {}
    for spec in specs:
        base, cuts = spec.split(":")
        raw = resolve(cfg["bases"][base]["raw_dir"])
        for f in RAW_FILES:
            files[f"raw/{base}/{f}"] = raw / f
        auths = [pd.read_csv(raw / "authorships.csv", usecols=["work_id", "author_orcid", "institution_ids"]),
                 pd.read_parquet(raw / "authorships_cand.parquet", columns=["work_id", "author_orcid", "institution_ids"])]
        wids |= set(pd.read_csv(raw / "works.csv", usecols=["id"])["id"]) | set(pd.read_parquet(raw / "works_cand.parquet", columns=["id"])["id"])
        for c in cuts.split(","):
            d = resolve(f"data/robustez/t4/{base}_{c}")
            for p in sorted(d.glob("*.parquet")) + [d / "estado.json"]:
                files[f"t4/{base}_{c}/{p.name}"] = p
                if p.name.startswith("auth_"):
                    a = pd.read_parquet(p)
                    if len(a.columns):
                        auths.append(a[["work_id", "author_orcid", "institution_ids"]])
                elif p.name.startswith("works_"):
                    w = pd.read_parquet(p)
                    if "id" in w:
                        wids |= set(w["id"])
            v1 = resolve(f"runs/robustez/t4/reconstrucao_{base}_{c}/lacunas.csv")
            if v1.exists():
                files[f"t4/{base}_{c}/lacunas_v1.csv"] = v1
        for a in auths:
            orcids |= {o for o in a["author_orcid"].map(_orcid) if o}
            iids |= {i for blob in a["institution_ids"].dropna() for i in json.loads(blob) if i}
        plan[base] = cuts.split(",")
    for f in sorted(resolve("configs").glob("*.yaml")) + [resolve("configs/ontology/coauthor-rec.ttl")]:
        files[f"configs/{f.name}"] = f
    # instituições: as referenciadas + ancestrais (linhagem) presentes no cache
    oa = resolve(yaml.safe_load(open(resolve("configs/enrich.yaml")))["openalex"]["cache_dir"])
    lineage = {}
    with open(oa / "institutions.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                lineage[r["id"]] = [p.rstrip("/").split("/")[-1] for p in (r.get("lineage") or []) if p]
    iids |= {p for i in list(iids) for p in lineage.get(i, [])}
    print(f"[congelar] {len(files)} arquivos, {len(orcids):,} ORCID, {len(wids):,} trabalhos, {len(iids):,} instituições",
          flush=True)
    dest = resolve(f"data/snapshots/{sid}")
    hc = yaml.safe_load(open(resolve("configs/filters.yaml")))["hygiene"]["orcid_api"]["cache_dir"]
    man = create_snapshot(dest, files, orcid_dir=resolve(hc), orcid_ids=orcids,
                          jsonl_subsets={"openalex/works.jsonl": (oa / "works.jsonl", wids),
                                         "openalex/institutions.jsonl": (oa / "institutions.jsonl", iids)},
                          meta={"id": sid, "bases_cortes": plan,
                                "nota": "entradas da reconstrução retrospectiva; metadados atuais na data do congelamento"})
    v = verify_snapshot(dest)
    compact = {"id": sid, "criado_em": man["criado_em"], "bases_cortes": plan, "sha256_combinado": man["sha256_combinado"],
               "arquivos": {k: {"bytes": e["bytes"], "sha256": e["sha256"]} for k, e in man["arquivos"].items()},
               "orcid": man["orcid"], "subconjuntos": man["subconjuntos"], "verificacao": v["ok"],
               "tempo_s": round(time.time() - t0, 1), "local": str(dest.relative_to(resolve(".")))}
    out = resolve(f"runs/robustez/snapshots/{sid}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(compact, ensure_ascii=False, indent=1))
    print(f"[congelar] {sid}: verificado; ORCID {man['orcid']['registros']:,} (ausentes {man['orcid']['ausentes_na_origem']:,}); "
          f"trabalhos {man['subconjuntos']['openalex/works.jsonl']['registros']:,} "
          f"(ausentes {man['subconjuntos']['openalex/works.jsonl']['ausentes_na_origem']:,}); {compact['tempo_s']} s", flush=True)


if __name__ == "__main__":
    main()
