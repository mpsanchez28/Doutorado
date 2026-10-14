"""Compara os conjuntos recalculados com a cópia congelada S1 com as execuções v2 (ESPECIFICACAO, emenda E2).

Elegibilidade (quem entra/sai e por quê), universo, alvos, positivos, corpus e fase de treino.
Só lê arquivos de conjuntos e relatórios; nenhuma métrica de modelo.
Uso: python scripts/comparar_congelado_v2.py  →  runs/robustez/t4/comparacao_S1_v2.json
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

S = "S1_20261014_econ_mat"
PAIRS = [("economia", 2019, "h3"), ("economia", 2021, "h3"), ("economia", 2021, "ate2026-10-08"),
         ("matematica", 2021, "h3"), ("matematica", 2021, "ate2026-10-08")]


def main():
    out = {}
    for b, c, tag in PAIRS:
        d2 = resolve(f"runs/robustez/t4/reconstrucao_{b}_{c}_v2_coletado_{tag}")
        ds = resolve(f"runs/robustez/t4/reconstrucao_{b}_{c}_v2_{S}_coletado_{tag}")
        r2, rs = (json.loads((d / "relatorio.json").read_text()) for d in (d2, ds))
        e2, es = (pd.read_csv(d / "elegibilidade.csv").set_index("author_id") for d in (d2, ds))
        ent = es.index[es["elegivel_c"] & ~e2.reindex(es.index)["elegivel_c"].fillna(False).astype(bool)]
        sai = e2.index[e2["elegivel_c"] & ~es.reindex(e2.index)["elegivel_c"].fillna(False).astype(bool)]
        c2, cs = (set(pd.read_csv(d / "candidatos.csv")["author_id"]) for d in (d2, ds))
        a2, as_ = (pd.read_csv(d / "alvos.csv").set_index("alvo") for d in (d2, ds))
        common = a2.index.intersection(as_.index)
        p2, ps = r2["corpus_local_parcial"]["protocolo"], rs["corpus_local_parcial"]["protocolo"]
        res = {"elegiveis": {"v2": int(e2["elegivel_c"].sum()), "S1": int(es["elegivel_c"].sum()),
                             "entram": {a: {"pessoa": es.loc[a, "pessoa"], "motivo_v2": e2.loc[a, "reprova_c"] if a in e2.index else "ausente"} for a in ent},
                             "saem": {a: {"pessoa": e2.loc[a, "pessoa"], "motivo_S1": es.loc[a, "reprova_c"] if a in es.index else "ausente"} for a in sai}},
               "pessoa_canonica_mudou": int((e2["pessoa"] != es.reindex(e2.index)["pessoa"]).sum()),
               "universo": {"v2": len(c2), "S1": len(cs), "iguais": c2 == cs},
               "alvos": {"v2": len(a2), "S1": len(as_), "so_v2": sorted(set(a2.index) - set(as_.index)),
                         "so_S1": sorted(set(as_.index) - set(a2.index)),
                         "n_coautores_novos_diferente": int((a2.loc[common, "n_coautores_novos"] != as_.loc[common, "n_coautores_novos"]).sum())},
               "protocolo": {k: (p2.get(k), ps.get(k)) for k in ("pares_novos", "pares_M9_removidos", "pares_alcancaveis_em_T0", "alvos_avaliacao_padrao")},
               "corpus": {"v2": (r2["corpus_local_parcial"]["trabalhos"], r2["corpus_local_parcial"]["pessoas"]),
                          "S1": (rs["corpus_local_parcial"]["trabalhos"], rs["corpus_local_parcial"]["pessoas"])},
               "orcid_S1": {k: rs.get(k) for k in ("orcid_usado_na_elegibilidade", "orcid_usado_na_higienizacao")},
               "orcid_v2": {k: r2.get(k) for k in ("orcid_usado_na_elegibilidade", "orcid_usado_na_higienizacao")}}
        f2 = (r2.get("modelo") or {}).get("especificacao_e_checagens", {}).get("fase_de_treino", {})
        fs = rs.get("fase_de_treino", {})
        res["fase_de_treino"] = {k: (f2.get(k), fs.get(k)) for k in ("sementes_da_fase (sorteio ≤ c')", "universo_da_fase",
                                                                       "universo_da_fase_com_algum_trabalho_coletado")}
        res["fase_de_treino"]["universo_que_sao_sementes (histórico do bruto, só S1)"] = fs.get("universo_da_fase_que_sao_sementes (histórico do bruto)")
        m2 = r2.get("modelo", {})
        res["fase_de_treino"]["consultas (sementes, candidatos)"] = (
            (m2.get("especificacao_e_checagens", {}).get("consultas_treino_sementes_da_fase"),
             m2.get("especificacao_e_checagens", {}).get("consultas_treino_candidatos_da_fase")),
            (fs.get("consultas", {}).get("sementes"), fs.get("consultas", {}).get("candidatos")))
        res["fase_de_treino"]["positivos_treino"] = (m2.get("positivos_treino"), fs.get("consultas", {}).get("positivos"))
        out[f"{b} {c} {tag}"] = res
        print(f"== {b} {c} {tag}: eleg {res['elegiveis']['v2']}→{res['elegiveis']['S1']} (+{len(ent)} −{len(sai)}); "
              f"universo igual={res['universo']['iguais']}; alvos {len(a2)}→{len(as_)}; n_novos diferentes {res['alvos']['n_coautores_novos_diferente']}; "
              f"protocolo {res['protocolo']}; corpus {res['corpus']}; fase {res['fase_de_treino']}", flush=True)
    resolve("runs/robustez/t4/comparacao_S1_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
