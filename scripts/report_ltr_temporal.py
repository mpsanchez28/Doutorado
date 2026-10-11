"""Relatório do treino temporal do re-ranqueador → docs/RESULTADOS_LTR_TEMPORAL.md.

Lê runs/ltr_temporal/<base>.json (scripts/temporal_ltr.py). Uso: python scripts/report_ltr_temporal.py
"""
from __future__ import annotations

import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

GRUPOS = ["coautoria", "instituicao", "topico", "periodico", "citacao", "ex_colegas", "texto", "atividade"]
NOME_G = {"coautoria": "Coautoria", "instituicao": "Instituição", "topico": "Tópicos", "periodico": "Periódico",
          "citacao": "Citação/acoplamento", "ex_colegas": "Ex-colegas ORCID", "texto": "Texto TF-IDF",
          "atividade": "Atividade"}
MODELOS = ["União RRF (sem aprendizado)", "LTR completo (validação cruzada)", "LTR só coautoria", "LTR completo",
           "LTR completo — só sementes como consultas", "LTR completo — parâmetros padrão"]
ROTULO = {"LTR só coautoria": "LTR temporal só coautoria", "LTR completo": "**LTR temporal completo**",
          "LTR completo — só sementes como consultas": "LTR temporal completo, só sementes",
          "LTR completo — parâmetros padrão": "LTR temporal completo, parâmetros padrão"}


def pct(x):
    return f"{100 * x:.2f}".replace(".", ",")


def pp(x):
    return f"{100 * x:+.2f}".replace(".", ",")


def sig(r, a, b, met):
    t = r["testes"].get(f"{a} vs {b} | {met}")
    return "*" if t and t["significativo"] else ""


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in cfg["gradiente"] if resolve(f"runs/ltr_temporal/{b}.json").exists()]
    R = {b: json.loads(resolve(f"runs/ltr_temporal/{b}.json").read_text()) for b in order}
    lab = {b: cfg["bases"][b]["label"] for b in order}
    hdr = "| Modelo | " + " | ".join(lab[b] for b in order) + " |"
    sep = "|---|" + "---:|" * len(order)
    L = ["# Resultados — treino temporal do re-ranqueador", "",
         "> Gerado por `scripts/report_ltr_temporal.py` a partir de `runs/ltr_temporal/`. Método em",
         "> [ABLACAO_KG.md](ABLACAO_KG.md) §7. Treino: KG até 2018 → coautorias novas de 2019–2021 (sementes e",
         "> candidatos como consultas). Teste: KG até 2021 → T1, mesmos alvos e candidatos da ablação. Valores em %,",
         "> média por alvo, com M9. `*` = significativo (teste pareado, Bonferroni).", "",
         "## 1. Tamanho do treino", "",
         "| Base | Consultas (sementes + candidatos) | Pares de treino | Positivos de treino | dos quais de sementes | Positivos no teste |",
         "|---|---:|---:|---:|---:|---:|"]
    for b in order:
        r = R[b]
        q = r["consultas_treino"]
        L.append(f"| {lab[b]} | {q['sementes']} + {q['candidatos']} | {r['pares_treino']:,} | {r['positivos_treino']:,} | "
                 f"{r['positivos_treino_sementes']:,} | {r['positivos_teste']:,} |".replace(",", "."))
    L.append("")
    for i, met in enumerate(("R@10", "R@50", "NDCG@10"), 2):
        L += [f"## {i}. {met}", "", hdr, sep]
        for m in MODELOS:
            cells = []
            for b in order:
                o = R[b]["ordenacao"]
                if m not in o:
                    cells.append("—")
                    continue
                s = ""
                if m == "LTR completo" and met != "R@10":
                    s = sig(R[b], m, "União RRF (sem aprendizado)", met) and "ᴿ"
                    s += sig(R[b], m, "LTR só coautoria", met) and "ᶜ"
                    s += sig(R[b], m, "LTR completo (validação cruzada)", met) and "ⱽ"
                cells.append(pct(o[m][met]) + s)
            L.append(f"| {ROTULO.get(m, m)} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["Marcas no LTR temporal completo: diferença significativa contra ᴿ a União RRF, ᶜ o LTR temporal só "
          "coautoria, ⱽ o LTR por validação cruzada.", ""]

    L += ["## 5. Leave-one-out — Δ ao retirar cada grupo (R@50 / NDCG@10)", "", "| Grupo retirado | " +
          " | ".join(lab[b] for b in order) + " |", sep]
    for g in GRUPOS:
        cells = []
        for b in order:
            o = R[b]["ordenacao"]
            d50 = o[f"sem {g}"]["R@50"] - o["LTR completo"]["R@50"]
            d10 = o[f"sem {g}"]["NDCG@10"] - o["LTR completo"]["NDCG@10"]
            cells.append(f"{pp(d50)}{sig(R[b], 'LTR completo', f'sem {g}', 'R@50')} / "
                         f"{pp(d10)}{sig(R[b], 'LTR completo', f'sem {g}', 'NDCG@10')}")
        L.append(f"| {NOME_G[g]} | " + " | ".join(cells) + " |")
    L.append("")
    L += ["## 6. Add-one — Δ ao somar cada grupo à coautoria (R@50 / NDCG@10)", "", "| Grupo somado | " +
          " | ".join(lab[b] for b in order) + " |", sep]
    for g in GRUPOS:
        if g in ("coautoria", "atividade"):
            continue
        cells = []
        for b in order:
            o = R[b]["ordenacao"]
            a = f"coautoria + {g}"
            cells.append(f"{pp(o[a]['R@50'] - o['LTR só coautoria']['R@50'])}{sig(R[b], a, 'LTR só coautoria', 'R@50')} / "
                         f"{pp(o[a]['NDCG@10'] - o['LTR só coautoria']['NDCG@10'])}{sig(R[b], a, 'LTR só coautoria', 'NDCG@10')}")
        L.append(f"| {NOME_G[g]} | " + " | ".join(cells) + " |")
    L.append("")
    L += ["## 7. Peso de cada grupo no LTR temporal completo (|SHAP| médio, % do total)", "",
          "| Grupo | " + " | ".join(lab[b] for b in order) + " |", sep]
    for g in GRUPOS:
        L.append(f"| {NOME_G[g]} | " + " | ".join(pct(R[b]["importancia_shap"].get(g, 0)) for b in order) + " |")
    cont = {b: sum(R[b]["importancia_shap"].get(g, 0) for g in ("topico", "citacao", "texto")) for b in order}
    L.append("| *Conteúdo (tópicos + citação + texto)* | " + " | ".join(f"*{pct(cont[b])}*" for b in order) + " |")
    L.append("")
    L += ["## 8. Por regime — NDCG@10 (só coautoria → completo, treino temporal)", ""]
    for b in order:
        L += [f"**{lab[b]}**", "", "| Regime | Só coautoria | Completo | União RRF |", "|---|---:|---:|---:|"]
        for reg, d in R[b]["por_regime"].items():
            L.append(f"| {reg} | {pct(d['LTR só coautoria']['NDCG@10'])} | {pct(d['LTR completo']['NDCG@10'])} | "
                     f"{pct(d['União RRF (sem aprendizado)']['NDCG@10'])} |")
        L.append("")
    if all("padrao_T0" in R[b] for b in order):
        L += ["## 9. Avaliação padrão — só coautorias novas com pessoas presentes em T0", "",
              "Mesmos modelos e rankings; o gabarito exclui coautores sem trabalho em T0. Marcas no LTR completo: "
              "ᴿ contra a União RRF, ᶜ contra o só coautoria (Bonferroni próprio).", "",
              "| Base | Alvos | Modelo | R@10 | R@50 | NDCG@10 | Hits@10 |", "|---|---:|---|---:|---:|---:|---:|"]
        for b in order:
            pt = R[b]["padrao_T0"]
            for m in ("União RRF (sem aprendizado)", "LTR só coautoria", "LTR completo"):
                o = pt["ordenacao"][m]
                mk = {}
                if m == "LTR completo":
                    for met in ("R@50", "NDCG@10"):
                        t1 = pt["testes"].get(f"LTR completo vs União RRF (sem aprendizado) | {met}", {})
                        t2 = pt["testes"].get(f"LTR completo vs LTR só coautoria | {met}", {})
                        mk[met] = ("ᴿ" if t1.get("significativo") else "") + ("ᶜ" if t2.get("significativo") else "")
                L.append(f"| {lab[b]} | {pt['alvos']} | {ROTULO.get(m, m)} | {pct(o['R@10'])} | "
                         f"{pct(o['R@50'])}{mk.get('R@50', '')} | {pct(o['NDCG@10'])}{mk.get('NDCG@10', '')} | "
                         f"{pct(o['Hits@10'])} |")
        L.append("")
    resolve("docs/RESULTADOS_LTR_TEMPORAL.md").write_text("\n".join(L))
    print("escrito docs/RESULTADOS_LTR_TEMPORAL.md")


if __name__ == "__main__":
    main()
