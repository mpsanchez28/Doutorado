"""Diagnóstico DESCRITIVO por subconjunto de alvos (docs/AUDITORIA_SELECAO.md §5).

Usa só resultados já existentes (nenhum treino): os rankings por alvo do protocolo original
(runs/ltr_temporal/, runs/linha_base/) e a auditoria de elegibilidade até 2021
(runs/robustez/auditoria/). Os modelos foram treinados no protocolo ORIGINAL — esta análise
descreve como o desempenho se distribui entre subconjuntos; não estima o desempenho de um
protocolo corrigido nem determina, sozinha, a direção do viés de seleção.

Subconjuntos dos alvos avaliados no corte de 2021:
  todos            — alvos do protocolo original
  sorteio≤2021     — semente sorteada por trabalho publicado até 2021
  elegível≤2021    — elegível com dados até 2021 ("mantida")
  corrigido        — sorteio≤2021 ∩ elegível≤2021
  fora_corrigido   — alvos originais fora do corrigido
Modelos: LTR completo (modelo principal), LTR só coautoria, União RRF, Adamic-Adar, vizinhos comuns.
Por subconjunto: média com IC 95% (bootstrap sobre alvos) e diferença pareada
(LTR completo − controle) com IC 95% e p de Wilcoxon (sem correção — descritivo).

Saída: runs/robustez/auditoria/subconjuntos.json e docs/RESULTADOS_AUDITORIA_2021.md
Uso: python scripts/diagnostico_subconjuntos_2021.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import yaml
from scipy.stats import wilcoxon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

B = 2000
CONTROLS = ["LTR só coautoria", "União RRF", "Adamic-Adar", "Vizinhos comuns"]


def boot_mean(x, seed=0):
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(B, len(x)))].mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def pct(v):
    return f"{100 * v:.2f}".replace(".", ",")


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in cfg["gradiente"] if resolve(f"runs/robustez/auditoria/elegibilidade_{b}.csv").exists()]
    out, L = {}, ["# Diagnóstico descritivo por subconjunto de alvos (corte 2021)", "",
                  "> Gerado por `scripts/diagnostico_subconjuntos_2021.py`. **Análise descritiva**: modelos treinados no",
                  "> protocolo original; não estima o desempenho de um protocolo corrigido nem determina a direção do viés.",
                  "> Média por alvo com IC 95% (bootstrap, 2.000 reamostragens). Δ = LTR completo − controle, pareado por alvo.", ""]
    for b in order:
        lab = cfg["bases"][b]["label"]
        aud = pd.read_csv(resolve(f"runs/robustez/auditoria/elegibilidade_{b}.csv")).drop_duplicates("pessoa").set_index("pessoa")
        ltr = {"estrita": pd.read_parquet(resolve(f"runs/ltr_temporal/{b}.parquet")),
               "padrao": pd.read_parquet(resolve(f"runs/ltr_temporal/{b}_padrao_T0.parquet"))}
        lb = pd.read_parquet(resolve(f"runs/linha_base/{b}.parquet"))
        out[b] = {}
        for av, lvar in (("estrita", "com_M9"), ("padrao", "padrao_T0")):
            d = ltr[av]
            per = {"LTR completo": d[d["modelo"] == "LTR completo"].set_index("alvo"),
                   "LTR só coautoria": d[d["modelo"] == "LTR só coautoria"].set_index("alvo"),
                   "União RRF": d[d["modelo"] == "União RRF (sem aprendizado)"].set_index("alvo")}
            l = lb[lb["variante"] == lvar]
            per["Adamic-Adar"] = l[l["gerador"] == "coautoria_aa"].set_index("alvo")
            per["Vizinhos comuns"] = l[l["gerador"] == "coautoria_cn"].set_index("alvo")
            alvos = per["LTR completo"].index
            s_ok = aud["sorteio_ate_2021"].reindex(alvos).fillna(False).astype(bool)
            e_ok = (aud["status_2021"].reindex(alvos) == "mantida")
            subsets = {"todos": alvos, "sorteio≤2021": alvos[s_ok.values], "elegível≤2021": alvos[e_ok.values],
                       "corrigido": alvos[(s_ok & e_ok).values], "fora_corrigido": alvos[~(s_ok & e_ok).values]}
            res = {}
            for sname, idx in subsets.items():
                r = {"n": int(len(idx))}
                for met in ("R@50", "NDCG@10"):
                    a = per["LTR completo"].loc[idx, met].to_numpy()
                    r[f"LTR completo|{met}"] = boot_mean(a) if len(a) else None
                    for c in CONTROLS:
                        x = per[c][met].reindex(idx).to_numpy()
                        r[f"{c}|{met}"] = boot_mean(x) if len(x) else None
                        dd = a - x
                        if len(dd) > 1 and np.any(dd != 0):
                            p = float(wilcoxon(a, x).pvalue)
                        else:
                            p = None
                        r[f"Δ vs {c}|{met}"] = (*boot_mean(dd, seed=1), p) if len(dd) else None
                res[sname] = r
            out[b][av] = res
        # tabela (avaliação estrita e padrão; R@50 e NDCG@10)
        for av, avn in (("estrita", "estrita"), ("padrao", "padrão")):
            L += [f"## {lab} — avaliação {avn}", "",
                  "| Subconjunto | n | LTR completo R@50 [IC] | Δ vs só coautoria | Δ vs União RRF | Δ vs Adamic-Adar | Δ vs vizinhos comuns | LTR completo NDCG@10 [IC] | Δ NDCG@10 vs só coautoria |",
                  "|---|---:|---|---|---|---|---|---|---|"]
            for sname, r in out[b][av].items():
                if not r["n"]:
                    continue
                m, lo, hi = r["LTR completo|R@50"]
                n10, l10, h10 = r["LTR completo|NDCG@10"]

                def dlt(key):
                    v = r[key]
                    if v is None:
                        return "—"
                    mu, lo_, hi_, p = v
                    return f"{100 * mu:+.2f} [{100 * lo_:+.2f}; {100 * hi_:+.2f}]".replace(".", ",") + (f" p={p:.3f}" if p is not None else "")
                L.append(f"| {sname} | {r['n']} | {pct(m)} [{pct(lo)}; {pct(hi)}] | {dlt('Δ vs LTR só coautoria|R@50')} | "
                         f"{dlt('Δ vs União RRF|R@50')} | {dlt('Δ vs Adamic-Adar|R@50')} | {dlt('Δ vs Vizinhos comuns|R@50')} | "
                         f"{pct(n10)} [{pct(l10)}; {pct(h10)}] | {dlt('Δ vs LTR só coautoria|NDCG@10')} |")
            L.append("")
    dest = resolve("runs/robustez/auditoria")
    (dest / "subconjuntos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    resolve("docs/RESULTADOS_AUDITORIA_2021.md").write_text("\n".join(L))
    print("escrito docs/RESULTADOS_AUDITORIA_2021.md")


if __name__ == "__main__":
    main()
