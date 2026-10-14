"""T4 — diagnóstico de viabilidade dos cortes temporais (docs/ROBUSTEZ_T1_T4.md §3).

Para cada base e corte c (configs/robustez.yaml › t4), com horizonte fixo de H anos:
  - desenho "só sementes": KG só com os trabalhos das sementes (raw works.csv — histórico
    completo, coletado sem olhar coautorias). Conta alvos, coautorias novas em (c, c+H],
    regimes e alcance (coautor novo presente em T0);
  - corpus completo (sementes + candidatos), só para MEDIR o vazamento: nos cortes < 2021, os
    candidatos foram escolhidos pela coautoria até 2021, então parte do alcance do corpus
    completo vem de informação posterior ao corte.
Nada é treinado. Saídas: runs/robustez/t4/diagnostico.json e tabela impressa.
Uso: PYTHONHASHSEED=0 python scripts/diagnostico_t4.py [bases…]
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

from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402


def seed_work_ids(raw_dir) -> set:
    """Trabalhos do histórico das sementes (1ª parte da coleta; a expansão fica em *_cand)."""
    return set(pd.read_csv(resolve(raw_dir) / "works.csv", usecols=["id"])["id"])


def describe(P) -> dict:
    s = P.summary()
    return {"alvos": s["alvos"], "regimes": s["alvos_por_regime"], "pares_novos": s["pares_novos"],
            "alcance_T0": round(1 - s["fracao_inalcancavel"], 4), "pares_M9": s["pares_M9_removidos"]}


def main():
    rob = yaml.safe_load(open(resolve("configs/robustez.yaml")))
    t4 = rob["t4"]
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    ev = load_config("eval")
    cap = load_filters()["max_coauthors_per_work"]
    wr, cr = ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"]
    H, last = int(t4["horizonte_anos"]), int(t4["ultimo_ano_completo"])
    bases = sys.argv[1:] or cfg["gradiente"]
    out = {}
    for b in bases:
        t0 = time.time()
        prof = cfg["bases"][b]
        corpus = pd.read_parquet(resolve(prof["corpus"]), columns=["work_id", "author_id", "author_name",
                                                                    "publication_date"])
        year = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
        au = pd.read_csv(resolve(f"data/processed/autores_{b}.csv"), index_col=0, usecols=["canonical_id", "alvo"])
        alvos = au.index[au["alvo"]].tolist()
        sw = seed_work_ids(prof["raw_dir"])
        is_seed_work = corpus["work_id"].isin(sw)
        out[b] = {"trabalhos_sementes": int(corpus.loc[is_seed_work, "work_id"].nunique()),
                  "trabalhos_total": int(corpus["work_id"].nunique()), "cortes": {}}
        for c in t4["cortes"]:
            if c + H > last:
                out[b]["cortes"][c] = {"viavel": False, "motivo": f"horizonte termina em {c + H} > {last}"}
                continue
            window = year <= c + H
            sp = {"modo": "calendario", "t0_ate": c}
            so = build_protocol(corpus[window & is_seed_work], alvos, sp, cap, wr, cr)
            full = build_protocol(corpus[window], alvos, sp, cap, wr, cr)
            d_so, d_full = describe(so), describe(full)
            # pares alcançáveis no corpus completo mas não no "só sementes": devidos à expansão
            reach_so = {(a, x) for a in so.targets for x in so.gt[a] if x in so.t0_authors}
            reach_full = {(a, x) for a in full.targets for x in full.gt[a] if x in full.t0_authors}
            extra = len(reach_full - reach_so)
            out[b]["cortes"][c] = {"viavel": True, "janela_teste": f"{c + 1}–{c + H}", "so_sementes": d_so,
                                   "corpus_completo": d_full,
                                   "pares_alcancaveis_so_pela_expansao": extra,
                                   "expansao_usou_futuro": c < 2021}
            print(f"[{b}] corte {c} (teste {c + 1}–{c + H}): só sementes → {d_so['alvos']} alvos, "
                  f"{d_so['pares_novos']} pares, alcance {d_so['alcance_T0']:.1%} | corpus completo → alcance "
                  f"{d_full['alcance_T0']:.1%} ({extra} pares só pela expansão"
                  f"{', COM VAZAMENTO' if c < 2021 else ''})", flush=True)
        print(f"[{b}] {time.time() - t0:.0f} s", flush=True)
    dest = resolve(f"{rob['saida']}/t4")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "diagnostico.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"escrito {dest / 'diagnostico.json'}")


if __name__ == "__main__":
    main()
