"""Reduz uma base coletada às N primeiras sementes (bases.yaml › coleta.max_seeds).

As sementes estão em ordem aleatória (embaralhamento com semente fixa na coleta ``seeded``),
então as N primeiras são uma subamostra aleatória — e o resultado é idêntico ao de uma coleta
que tivesse parado em N sementes: ficam os trabalhos com ao menos uma das N sementes (seus
históricos completos, com todos os coautores).

Guarda os arquivos completos como ``*_full.csv`` e move resultados derivados da versão
anterior (higienização, enriquecimento) para ``runs/<base>/obsoleto/`` e
``data/processed/obsoleto/`` — nada desatualizado se mistura aos números novos.

Uso: python scripts/subset_seeds.py economia 1000
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime

import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402


def main(base: str, n: int) -> None:
    prof = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))["bases"][base]
    raw = resolve(prof["raw_dir"])
    for f in ("authorships", "works", "seeds"):
        full = raw / f"{f}_full.csv"
        if not full.exists():
            shutil.copy2(raw / f"{f}.csv", full)            # backup do bruto completo (uma vez)
    seeds = pd.read_csv(raw / "seeds_full.csv")
    seeds = seeds.sort_values("order") if "order" in seeds else seeds
    keep = seeds.head(n)
    a = pd.read_csv(raw / "authorships_full.csv")
    w = pd.read_csv(raw / "works_full.csv")
    works_keep = set(a.loc[a["author_id"].isin(set(keep["author_id"])), "work_id"])
    a2, w2 = a[a["work_id"].isin(works_keep)], w[w["id"].isin(works_keep)]
    a2.to_csv(raw / "authorships.csv", index=False)
    w2.to_csv(raw / "works.csv", index=False)
    keep.to_csv(raw / "seeds.csv", index=False)

    # resultados derivados da versão anterior → obsoleto (não se misturam aos novos)
    obs_runs, obs_data = resolve(f"runs/{base}/obsoleto"), resolve("data/processed/obsoleto")
    obs_runs.mkdir(parents=True, exist_ok=True); obs_data.mkdir(parents=True, exist_ok=True)
    for f in ("hygiene.json", "gate.json", "audit.json", "audit_sample.csv", "enrich.json", "expand.json"):
        p = resolve(f"runs/{base}/{f}")
        if p.exists():
            shutil.move(str(p), obs_runs / f)
    for p in (resolve(prof["corpus"]), resolve(f"data/processed/autores_{base}.csv"),
              resolve(f"data/processed/enrich_{base}")):
        if p.exists():
            shutil.move(str(p), obs_data / f"{p.name}.{len(seeds)}sementes")

    prev = json.loads(resolve(f"runs/{base}/collect.json").read_text()) \
        if resolve(f"runs/{base}/collect.json").exists() else {}
    stats = {**prev, "works": len(w2), "authors": int(a2["author_id"].nunique()), "n_seeds": len(keep),
             "subset": {"de_sementes": len(seeds), "para_sementes": len(keep),
                        "trabalhos_antes": len(w), "em": datetime.now().isoformat(timespec="seconds"),
                        "nota": "N primeiras sementes (ordem aleatória) — scripts/subset_seeds.py"}}
    resolve(f"runs/{base}/collect.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False))
    print(f"[subset:{base}] sementes {len(seeds)} → {len(keep)} · trabalhos {len(w)} → {len(w2)} · "
          f"autorias {len(a)} → {len(a2)} · autores {a['author_id'].nunique()} → {a2['author_id'].nunique()}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
