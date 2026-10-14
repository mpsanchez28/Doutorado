"""Auditoria dos sorteios adicionais (43–44) já coletados em Economia e Matemática (docs/ROBUSTEZ_T1_T4.md §3.6).

Só dados locais, nenhuma chamada, nenhum resultado de modelo (a decisão de ampliar não pode
depender do desempenho). Para cada sorteio s e corte c ∈ {2019, 2021}:
  - quadro e regras (mesmo ``base()`` e mesmo procedimento do sorteio 42; deduplicação de
    AUTORES entre sorteios: quem saiu num sorteio não volta nos seguintes);
  - sobreposição: trabalhos sorteados repetidos entre sorteios; autores repetidos (deve ser 0);
    sementes de s que são coautoras (≤ c) de sementes do sorteio 42, ou candidatas atuais;
  - elegibilidade com a MESMA regra (E1–E8 com autorias ≤ c; ORCID do cache);
  - cobertura do que já existe localmente (histórico, ORCID, enriquecimento);
  - candidatos: ``candidate_universe_at_cut`` (universo gerado só pelos trabalhos das sementes de
    todos os sorteios até c), lacunas e custo.
Saída: runs/robustez/t4/auditoria_sorteios_v2.json (a auditoria_sorteios.json anterior usava o
universo v1, defeituoso, e está marcada como inválida nas contagens de candidatos)
Uso: PYTHONHASHSEED=0 python scripts/auditoria_sorteios.py [economia matematica]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.collect.openalex import candidate_universe_at_cut  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import author_table, authorship_levels, canonicalize  # noqa: E402
from coauthor_rec.enrich.openalex_cache import load_cache  # noqa: E402

CUTS = (2019, 2021)
J = 5


def years_of(s):
    return pd.to_datetime(s, errors="coerce").dt.year


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    filt = load_filters()
    hcfg, cap = filt.get("hygiene", {}), filt.get("max_coauthors_per_work")
    ev = load_config("eval")
    enr = yaml.safe_load(open(resolve("configs/enrich.yaml")))["openalex"]
    orcid_cache = resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
    works_cache = set(load_cache(resolve(enr["cache_dir"]), "works"))
    out = {}
    for b in sys.argv[1:] or ["economia", "matematica"]:
        t0 = time.time()
        raw = resolve(cfg["bases"][b]["raw_dir"])
        if not (raw / "seeds_full.csv").exists():
            out[b] = {"sorteios_extras": False}
            continue
        seeds = pd.read_csv(raw / "seeds_full.csv")
        a = pd.read_csv(raw / "authorships_full.csv")
        w = pd.read_csv(raw / "works_full.csv")
        wyear = dict(zip(w["id"], years_of(w["publication_date"])))
        seeds["ano_sorteio"] = seeds["seed_work_id"].map(wyear)
        used = set(pd.read_csv(raw / "seeds.csv")["author_id"])
        cur_cands = set(pd.read_csv(raw / "candidates.csv")["author_id"])
        res = {"sementes_por_sorteio": seeds["sample_seed"].value_counts().sort_index().to_dict(),
               "usadas_hoje (sorteio 42, 1ªs 1000 pela ordem)": len(used),
               "trabalhos_sorteados_repetidos_entre_sorteios": int(seeds["seed_work_id"].duplicated().sum()),
               "autores_repetidos_entre_sorteios": int(seeds["author_id"].duplicated().sum()),
               "nota_quadro": "mesmo filtro base() (área, idioma, ≥2004, sem limite superior) e sample(2000, seed=s) "
                              "independentes; autores já vistos em sorteios anteriores são excluídos (seen_cand) — "
                              "os sorteios 43–44 são amostras SEM reposição de autores condicionadas ao 42",
               "cortes": {}}

        # higienização dos trabalhos de TODAS as sementes (bruto completo) para a elegibilidade
        sw = set(a.loc[a["author_id"].isin(set(seeds["author_id"])), "work_id"])
        merged = clean_and_merge(a[a["work_id"].isin(sw)], w, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
        orc = set(seeds["author_orcid"].dropna())
        claims = {o: json.loads((orcid_cache / f"{o}.json").read_text()) for o in orc if (orcid_cache / f"{o}.json").exists()}
        df, _ = canonicalize(merged)
        df = authorship_levels(df, claims, hcfg.get("reject_name_mismatch", True))
        canon = dict(zip(df["author_id"], df["canonical_id"]))
        seeds["pessoa"] = [canon.get(x, f"orcid:{o}" if isinstance(o, str) else x) for x, o in zip(seeds["author_id"], seeds["author_orcid"])]
        dyear = years_of(df["publication_date"])
        for c in CUTS:
            th = author_table(df[dyear <= c], hcfg.get("author_criteria", {}), cap)
            sc = seeds[seeds["ano_sorteio"] <= c].copy()
            sc["elegivel"] = sc["pessoa"].map(th["eligible"]).fillna(False).astype(bool)
            # coautoria (≤ c) entre sementes de sorteios diferentes
            a_c = a[a["work_id"].map(wyear) <= c]
            s42 = set(sc.loc[sc["sample_seed"] == 42, "author_id"])
            w42 = set(a_c.loc[a_c["author_id"].isin(s42), "work_id"])
            co42 = set(a_c.loc[a_c["work_id"].isin(w42), "author_id"])
            per = {}
            for s, g in sc.groupby("sample_seed"):
                ids = set(g["author_id"])
                per[int(s)] = {"sorteadas_ate_c": len(g), "elegiveis_ate_c": int(g["elegivel"].sum()),
                               "orcid_no_cache": int(g["author_orcid"].isin(claims).sum()),
                               "coautoras_ate_c_de_sementes_42": int(len(ids & co42)) if s != 42 else None,
                               "entre_os_candidatos_atuais": int(len(ids & cur_cands)),
                               "trabalhos_ate_c": int(a_c.loc[a_c["author_id"].isin(ids), "work_id"].nunique()),
                               "trabalhos_sem_enriquecimento_em_cache": int(len(set(a.loc[a["author_id"].isin(ids), "work_id"]) - works_cache))}
            # candidatos gerados SÓ pelos trabalhos das sementes do corte (v2; a v1 usava os trabalhos
            # de todas as sementes do bruto — docs/REVISAO_CONSISTENCIA_PROTOCOLOS.md A0)
            allc = candidate_universe_at_cut(a[["work_id", "author_id"]], set(sc["author_id"]), cap, wyear, c,
                                             max_candidates=int(cfg.get("max_candidatos", 15000)), seed=int(cfg["coleta"].get("seed", 42)))
            only42 = candidate_universe_at_cut(a[["work_id", "author_id"]], s42, cap, wyear, c,
                                               max_candidates=int(cfg.get("max_candidatos", 15000)), seed=int(cfg["coleta"].get("seed", 42)))
            years_needed = list(range(c - J + 1, c + 1))
            miss_old = [y for y in years_needed if not 2017 <= y <= 2021]
            new = [x for x in allc if x not in cur_cands]
            ca = pd.read_parquet(raw / "authorships_cand.parquet", columns=["work_id", "author_id"])
            per_cy = ca.groupby("author_id")["work_id"].nunique().mean() / 5
            works_est = (len(new) * len(years_needed) + (len(allc) - len(new)) * len(miss_old)) * per_cy
            extra_seed_works = sum(v["trabalhos_sem_enriquecimento_em_cache"] for k, v in per.items() if k != 42)
            credits = (math.ceil(len(new) / 50) + (math.ceil((len(allc) - len(new)) / 50) if miss_old else 0)
                       + math.ceil(works_est / 200) + 2 * math.ceil((works_est + extra_seed_works) / 50))
            res["cortes"][c] = {"por_sorteio": per,
                                "elegiveis_total_todos_sorteios": int(sc["elegivel"].sum()),
                                "candidatos_todos_sorteios": len(allc), "candidatos_so_42": len(only42),
                                "candidatos_novos_vs_coletados": len(new), "anos_faltando_coletados": miss_old,
                                "trabalhos_a_coletar_est": int(works_est), "creditos_est": int(credits),
                                "nota_custo": "inclui enriquecimento dos trabalhos das sementes 43–44 fora do cache"}
            print(f"[{b}] corte {c}: por sorteio {{s: (sorteadas, elegíveis)}} = "
                  f"{ {k: (v['sorteadas_ate_c'], v['elegiveis_ate_c']) for k, v in per.items()} }; "
                  f"candidatos {len(allc)} (só 42: {len(only42)}), novos {len(new)}; ~{int(credits):,} créditos", flush=True)
        out[b] = res
        print(f"[{b}] {time.time() - t0:.0f} s", flush=True)
    dest = resolve("runs/robustez/t4")
    (dest / "auditoria_sorteios_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=int))
    print(f"escrito {dest / 'auditoria_sorteios_v2.json'}")


if __name__ == "__main__":
    main()
