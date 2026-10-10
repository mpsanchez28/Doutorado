"""Relatório da ablação das relações do KG → docs/RESULTADOS_ABLACAO_KG.md.

Lê runs/ablacao_kg/<base>.json (scripts/ablation_kg.py). Uso: python scripts/report_ablacao_kg.py
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
NOME_G = {"coautoria": "Coautoria", "instituicao": "Instituição", "topico": "Tópicos",
          "periodico": "Periódico", "citacao": "Citação/acoplamento", "ex_colegas": "Ex-colegas ORCID",
          "texto": "Texto TF-IDF", "atividade": "Atividade (grau, produção, anos)"}


def pct(x):
    return f"{100 * x:.2f}".replace(".", ",")


def pp(x):
    s = f"{100 * x:+.2f}".replace(".", ",")
    return s


def mark(res, a, b, met):
    t = res["testes"].get(f"{a} vs {b} | {met}")
    return "*" if t and t["significativo"] else ""


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in cfg["gradiente"] if resolve(f"runs/ablacao_kg/{b}.json").exists()]
    R = {b: json.loads(resolve(f"runs/ablacao_kg/{b}.json").read_text()) for b in order}
    lab = {b: cfg["bases"][b]["label"] for b in order}
    L = ["# Resultados — ablação das relações do KG", "",
         "> Gerado por `scripts/report_ablacao_kg.py` a partir de `runs/ablacao_kg/`. Método e leitura em",
         "> [ABLACAO_KG.md](ABLACAO_KG.md). Valores em %, média por alvo, gabarito com M9. `*` = diferença",
         "> significativa no teste pareado com correção de Bonferroni.", ""]

    L += ["## 1. Ordenação — modelos sobre o mesmo conjunto de candidatos (top-1000 da União)", ""]
    for met in ("R@10", "R@50", "NDCG@10"):
        L += [f"### {met}", "", "| Modelo | " + " | ".join(lab[b] for b in order) + " |",
              "|---|" + "---:|" * len(order)]
        for m in ["União RRF (sem aprendizado)", "LTR só coautoria", "LTR completo"]:
            cells = []
            for b in order:
                v = R[b]["ordenacao"][m][met]
                s = ""
                if m == "LTR completo" and met in ("R@50", "NDCG@10"):
                    s = mark(R[b], "LTR completo", "LTR só coautoria", met)
                cells.append(pct(v) + s)
            L.append(f"| {m} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["`*` no LTR completo: diferença significativa contra o LTR só coautoria.", ""]

    L += ["## 2. Ganho de cada relação — leave-one-out (Δ do NDCG@10 ao retirar o grupo)", "",
          "Negativo = a relação ajudava (retirá-la piora). Base de comparação: LTR completo.", "",
          "| Grupo retirado | " + " | ".join(lab[b] for b in order) + " |", "|---|" + "---:|" * len(order)]
    for g in GRUPOS:
        cells = []
        for b in order:
            o = R[b]["ordenacao"]
            d = o[f"sem {g}"]["NDCG@10"] - o["LTR completo"]["NDCG@10"]
            cells.append(pp(d) + mark(R[b], "LTR completo", f"sem {g}", "NDCG@10"))
        L.append(f"| {NOME_G[g]} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 3. Ganho de cada relação — add-one (Δ do NDCG@10 ao somar o grupo à coautoria)", "",
          "| Grupo somado | " + " | ".join(lab[b] for b in order) + " |", "|---|" + "---:|" * len(order)]
    for g in GRUPOS:
        if g in ("coautoria", "atividade"):
            continue
        cells = []
        for b in order:
            o = R[b]["ordenacao"]
            d = o[f"coautoria + {g}"]["NDCG@10"] - o["LTR só coautoria"]["NDCG@10"]
            cells.append(pp(d) + mark(R[b], f"coautoria + {g}", "LTR só coautoria", "NDCG@10"))
        L.append(f"| {NOME_G[g]} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 4. Peso de cada relação no modelo completo (|SHAP| médio, % do total)", "",
          "| Grupo | " + " | ".join(lab[b] for b in order) + " |", "|---|" + "---:|" * len(order)]
    for g in GRUPOS:
        L.append(f"| {NOME_G[g]} | " + " | ".join(pct(R[b]["importancia_shap"].get(g, 0)) for b in order) + " |")
    L.append("")

    L += ["## 5. Geração — Alcance@1000 da União sem cada relação (soma de pares)", "",
          "| Conjunto | " + " | ".join(lab[b] for b in order) + " |", "|---|" + "---:|" * len(order)]
    L.append("| Todos os meta-caminhos | " + " | ".join(pct(R[b]["geracao_alcance1000"]["todos"]) for b in order) + " |")
    for g in GRUPOS:
        if g == "atividade":
            continue
        L.append(f"| sem {NOME_G[g]} | " + " | ".join(
            f"{pct(R[b]['geracao_alcance1000'][f'sem_{g}'])} ({pp(R[b]['geracao_alcance1000'][f'sem_{g}'] - R[b]['geracao_alcance1000']['todos'])})"
            for b in order) + " |")
    L.append("")

    L += ["## 6. Por regime — NDCG@10 (LTR só coautoria → LTR completo)", ""]
    for b in order:
        pr = R[b]["por_regime"]
        L += [f"**{lab[b]}**", "", "| Regime | Só coautoria | Completo | União RRF |", "|---|---:|---:|---:|"]
        for r, d in pr.items():
            L.append(f"| {r} | {pct(d['LTR só coautoria']['NDCG@10'])} | {pct(d['LTR completo']['NDCG@10'])} | "
                     f"{pct(d['União RRF (sem aprendizado)']['NDCG@10'])} |")
        L.append("")
    L += ["## 7. Tamanho do problema de aprendizado", "",
          "| Base | Alvos | Pares (alvo, candidato) | Positivos no conjunto | Coautorias novas | α Bonferroni |",
          "|---|---:|---:|---:|---:|---:|"]
    for b in order:
        r = R[b]
        L.append(f"| {lab[b]} | {r['alvos']} | {r['pares']:,} | {r['positivos_no_conjunto']:,} | {r['pares_novos']:,} | "
                 f"{r['alfa_bonferroni']:.4f} |".replace(",", "."))
    L.append("")
    out = resolve("docs/RESULTADOS_ABLACAO_KG.md")
    out.write_text("\n".join(L))
    print(f"escrito {out}")


if __name__ == "__main__":
    main()
