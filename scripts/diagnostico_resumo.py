"""Quanto a exigência de RESUMO altera a população avaliada (docs/ROBUSTEZ_T1_T4.md §3.5.2).

Só dados locais. Para as sementes sorteadas por trabalho ≤ corte, em cada base:
  - trabalhos das sementes (≤ corte) no bruto × com resumo;
  - sementes que perdem TODOS os trabalhos na limpeza (ficam fora do corpus);
  - elegibilidade E1–E8 (autorias ≤ corte) COM a exigência de resumo (protocolo) e SEM ela
    (diagnóstico: `abstract` retirado dos campos obrigatórios só nesta análise).
Não altera o protocolo; mede o efeito da regra. Saída: runs/robustez/diagnostico_resumo.json
Uso: PYTHONHASHSEED=0 python scripts/diagnostico_resumo.py [--cortes 2021] [--bases …]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data import clean as CL  # noqa: E402
from coauthor_rec.data.hygiene import author_table, authorship_levels, canonicalize  # noqa: E402


def eligibility(merged, claims, hcfg, cap, c):
    df, _ = canonicalize(merged)
    df = authorship_levels(df, claims, hcfg.get("reject_name_mismatch", True))
    yr = pd.to_datetime(df["publication_date"], errors="coerce").dt.year
    t = author_table(df[yr <= c], hcfg.get("author_criteria", {}), cap)
    return t, dict(zip(df["author_id"], df["canonical_id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", nargs="*", default=["medicina", "computacao", "matematica", "economia"])
    ap.add_argument("--cortes", nargs="*", type=int, default=[2021])
    args = ap.parse_args()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    filt = load_filters()
    hcfg, cap = filt.get("hygiene", {}), filt.get("max_coauthors_per_work")
    ev = load_config("eval")
    cache = resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
    f_out = resolve("runs/robustez/diagnostico_resumo.json")
    out = json.loads(f_out.read_text()) if f_out.exists() else {}
    base_cols = list(CL.ESSENTIAL_COLS)
    for b in args.bases:
        raw = resolve(cfg["bases"][b]["raw_dir"])
        seeds = pd.read_csv(raw / "seeds.csv")
        works = pd.read_csv(raw / "works.csv")
        wyear = dict(zip(works["id"], pd.to_datetime(works["publication_date"], errors="coerce").dt.year))
        seeds["ano_sorteio"] = seeds["seed_work_id"].map(wyear)
        auth = pd.read_csv(raw / "authorships.csv")
        claims = {o: json.loads((cache / f"{o}.json").read_text()) for o in seeds["author_orcid"].dropna()
                  if (cache / f"{o}.json").exists()}
        for c in args.cortes:
            sc = seeds[seeds["ano_sorteio"] <= c]
            ids = set(sc["author_id"])
            sw = set(auth.loc[auth["author_id"].isin(ids), "work_id"])
            a_s = auth[auth["work_id"].isin(sw)]
            res = {}
            for label, cols in (("com_resumo (protocolo)", base_cols), ("sem_exigir_resumo (diagnóstico)",
                                                                      [x for x in base_cols if x != "abstract"])):
                CL.ESSENTIAL_COLS = cols
                merged = CL.clean_and_merge(a_s, works, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
                CL.ESSENTIAL_COLS = base_cols
                t, canon = eligibility(merged, claims, hcfg, cap, c)
                pessoa = sc.apply(lambda r: canon.get(r["author_id"], f"orcid:{r['author_orcid']}"), axis=1)
                yr = pd.to_datetime(merged["publication_date"], errors="coerce").dt.year
                m_seed = merged[merged["author_id"].isin(ids) & (yr <= c)]
                res[label] = {"trabalhos_das_sementes_ate_c": int(m_seed["work_id"].nunique()),
                              "sementes_com_algum_trabalho_ate_c": int(m_seed["author_id"].nunique()),
                              "sementes_com_algum_trabalho_no_corpus": int(merged.loc[merged["author_id"].isin(ids), "author_id"].nunique()),
                              "elegiveis_ate_c": int(pessoa.map(t["eligible"]).fillna(False).sum())}
            a, s = res["com_resumo (protocolo)"], res["sem_exigir_resumo (diagnóstico)"]
            res["efeito_da_exigencia"] = {
                "trabalhos_ate_c_perdidos": s["trabalhos_das_sementes_ate_c"] - a["trabalhos_das_sementes_ate_c"],
                "fracao_trabalhos_perdidos": round(1 - a["trabalhos_das_sementes_ate_c"] / max(s["trabalhos_das_sementes_ate_c"], 1), 4),
                "sementes_que_ficam_sem_nenhum_trabalho": s["sementes_com_algum_trabalho_no_corpus"] - a["sementes_com_algum_trabalho_no_corpus"],
                "elegiveis_a_menos_por_causa_do_resumo": s["elegiveis_ate_c"] - a["elegiveis_ate_c"]}
            out.setdefault(b, {})[str(c)] = {"sementes_sorteadas_ate_c": len(sc), **res}
            print(f"[{b}:{c}] {json.dumps(out[b][str(c)], ensure_ascii=False)}", flush=True)
            f_out.write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
