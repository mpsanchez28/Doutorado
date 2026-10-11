"""Relatório da geração seletiva em cascata → docs/RESULTADOS_GERACAO_SELETIVA.md.

Lê runs/cascata/<base>.json (scripts/cascade_eval.py). Uso: python scripts/report_cascata.py
"""
from __future__ import annotations

import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

MODELOS = ["União RRF (sem aprendizado)", "LTR temporal (União RRF → LTR)", "Cascata: etapa 1 apenas",
           "Cascata: etapa 1 → LTR", "Cascata: etapa 1 → LTR (+ nota da etapa 1)"]


def pct(x):
    return f"{100 * x:.2f}".replace(".", ",")


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in cfg["gradiente"] if resolve(f"runs/cascata/{b}.json").exists()]
    R = {b: json.loads(resolve(f"runs/cascata/{b}.json").read_text()) for b in order}
    lab = {b: cfg["bases"][b]["label"] for b in order}
    hdr = "| | " + " | ".join(lab[b] for b in order) + " |"
    sep = "|---|" + "---:|" * len(order)
    L = ["# Resultados — geração seletiva em cascata", "",
         "> Gerado por `scripts/report_cascata.py` a partir de `runs/cascata/`. Método em",
         "> [GERACAO_SELETIVA.md](GERACAO_SELETIVA.md). Treino temporal (KG 2018 → 2019–2021); teste no KG 2021 → T1.",
         "> Valores em %. `*` = significativo contra o LTR temporal sobre a União RRF (teste pareado, Bonferroni).", "",
         "## 1. Geração — alcance do conjunto que a etapa 2 recebe (soma de pares)", ""]
    for var, title in (("estrita", "Avaliação estrita (todas as coautorias novas)"),
                       ("padrao_T0", "Avaliação padrão (só coautores presentes em T0)")):
        L += [f"### {title}", "", hdr, sep]
        for k, n in (("uniao_rrf@1000", "Top-1000 da União RRF (atual)"), ("etapa1@1000", "**Top-1000 da etapa 1**"),
                     ("conjunto_ampliado", "Conjunto ampliado inteiro (teto)")):
            L.append(f"| {n} | " + " | ".join(pct(R[b]["geracao"][var][k]) for b in order) + " |")
        L.append("| Ganho relativo da etapa 1 | " + " | ".join(
            f"{100 * (R[b]['geracao'][var]['etapa1@1000'] / R[b]['geracao'][var]['uniao_rrf@1000'] - 1):+.1f}%".replace(".", ",")
            for b in order) + " |")
        L.append("")
    L += ["Conjunto ampliado (mediana de candidatos por alvo): " + ", ".join(
        f"{lab[b]} {R[b]['geracao']['conjunto_ampliado_mediana']:,.0f}".replace(",", ".") for b in order) + ".", ""]

    for var, title in (("estrita", "estrita"), ("padrao_T0", "padrão")):
        for met in ("R@50", "NDCG@10"):
            L += [f"## Resultado final — {met}, avaliação {title}", "", "| Modelo | " +
                  " | ".join(lab[b] for b in order) + " |", sep]
            for m in MODELOS:
                cells = []
                for b in order:
                    o = R[b]["ordenacao"][var].get(m)
                    if o is None:
                        cells.append("—")
                        continue
                    t = R[b]["testes"].get(f"{var} | {m} vs LTR temporal (União RRF → LTR) | {met}", {})
                    cells.append(pct(o[met]) + ("*" if t.get("significativo") else ""))
                L.append(f"| {m} | " + " | ".join(cells) + " |")
            L.append("")
    L += ["## Etapa 1 — atributos mais usados (ganho, % do total)", ""]
    for b in order:
        imp = R[b]["etapa1_importancia"]
        L.append(f"- **{lab[b]}**: " + "; ".join(f"`{k}` {pct(v)}" for k, v in list(imp.items())[:6]))
    L.append("")
    resolve("docs/RESULTADOS_GERACAO_SELETIVA.md").write_text("\n".join(L))
    print("escrito docs/RESULTADOS_GERACAO_SELETIVA.md")


if __name__ == "__main__":
    main()
