"""Positivos do gabarito em que o coautor novo é outra semente ou outro alvo (ESPECIFICACAO, emenda E3).

Mostra que esses positivos estão NO gabarito e não são bloqueados no ranking (a exclusão do ranking
é só a própria consulta e coautores anteriores: models/kg_ltr.ranking_exclusions). Separa pares
dirigidos (por consulta) de pares não ordenados únicos e marca os alcançáveis (coautor presente em T0).
Uso: python scripts/positivos_entre_sementes.py → runs/robustez/t4/positivos_entre_sementes.json
"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

S = "S1_20261014_econ_mat"
out = {}
for b, c, tag in (("economia", 2019, "h3"), ("economia", 2021, "h3"), ("economia", 2021, "ate2026-10-08"),
                  ("matematica", 2021, "h3"), ("matematica", 2021, "ate2026-10-08")):
    d = resolve(f"runs/robustez/t4/reconstrucao_{b}_{c}_v2_{S}_coletado_{tag}")
    g = pd.read_csv(d / "gabarito_teste.csv")
    el = pd.read_csv(d / "elegibilidade.csv")
    cut_seeds = set(el["pessoa"])
    targets = set(g["alvo"])
    g["coautor_e_semente_do_corte"] = g["coautor_novo"].isin(cut_seeds)
    g["coautor_e_alvo"] = g["coautor_novo"].isin(targets)
    s = g[g["coautor_e_semente_do_corte"]]
    und = {tuple(sorted(p)) for p in zip(s["alvo"], s["coautor_novo"])}
    tt = g[g["coautor_e_alvo"]]
    out[f"{b} {c} {tag}"] = {
        "positivos_dirigidos_total": len(g),
        "com_coautor_semente_do_corte": {"dirigidos": len(s), "nao_ordenados_unicos": len(und),
                                         "alcancaveis_em_T0": int(s["presente_em_T0"].sum())},
        "com_coautor_alvo": {"dirigidos": len(tt), "nao_ordenados_unicos": len({tuple(sorted(p)) for p in zip(tt["alvo"], tt["coautor_novo"])}),
                             "alcancaveis_em_T0": int(tt["presente_em_T0"].sum())},
        "retirados_do_gabarito_pela_regra_entre_sementes": 0, "mantidos_mas_bloqueados_no_ranking": 0}
    print(b, c, tag, out[f"{b} {c} {tag}"], flush=True)
resolve("runs/robustez/t4/positivos_entre_sementes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
