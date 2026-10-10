"""Relatório consolidado da linha de base e dos oráculos → docs/RESULTADOS_LINHA_BASE.md.

Lê runs/linha_base/<base>.{json,parquet} (scripts/baseline_oracle.py). Médias por alvo
(macro), exceto a decomposição do erro, que soma pares (micro).
Uso: python scripts/report_linha_base.py
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

NOMES = {"coautoria_cn": "Coautoria: vizinhos comuns", "coautoria_aa": "Coautoria: Adamic-Adar",
         "coautoria_ra": "Coautoria: Resource Allocation", "ppr": "PageRank personalizado",
         "instituicao": "KG: mesma instituição", "org_mae": "KG: mesma organização-mãe",
         "topico": "KG: tópicos (cosseno)", "periodico": "KG: mesmo periódico",
         "citacao": "KG: citação direta", "acoplamento": "KG: acoplamento bibliográfico",
         "ex_colegas": "KG: ex-colegas (ORCID)", "texto_tfidf": "Texto: TF-IDF",
         "popularidade": "Popularidade (grau)", "uniao_rrf": "**União (RRF)**"}


def pct(x):
    return f"{100 * x:.2f}".replace(".", ",")


def num(x):
    return f"{x:,.0f}".replace(",", ".")


def main():
    bases_cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in bases_cfg["gradiente"] if resolve(f"runs/linha_base/{b}.json").exists()]
    res = {b: json.loads(resolve(f"runs/linha_base/{b}.json").read_text()) for b in order}
    per = {b: pd.read_parquet(resolve(f"runs/linha_base/{b}.parquet")) for b in order}
    label = {b: bases_cfg["bases"][b]["label"] for b in order}
    L = ["# Resultados — linha de base e oráculos por meta-caminho do KG", "",
         "> Gerado por `scripts/report_linha_base.py` a partir de `runs/linha_base/`. Método e leitura em",
         "> [LINHA_BASE.md](LINHA_BASE.md). Valores em %, média por alvo (macro), gabarito **com M9**,",
         "> salvo indicação.", ""]

    # ---- protocolo
    L += ["## 1. Protocolo por base", "",
          "| Base | Alvos | warm | cool | cold | newcomer | Pares novos | Removidos M9 | Coautor novo fora de T0 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for b in order:
        p = res[b]["protocolo"]
        r = p["alvos_por_regime"]
        L.append(f"| {label[b]} | {p['alvos']} | {r.get('warm', 0)} | {r.get('cool', 0)} | {r.get('cold', 0)} | "
                 f"{r.get('newcomer', 0)} | {num(p['pares_novos'])} | {p['pares_M9_removidos']} | "
                 f"{pct(p['fracao_inalcancavel'])} |")
    L += ["", "*Coautor novo fora de T0*: o coautor de T1 não tem nenhum trabalho no corpus até 2021 — "
          "nenhum modelo baseado no histórico pode recomendá-lo (teto absoluto = 100 − esse valor).", ""]

    # ---- KG
    L += ["## 2. KG T0 materializado", "",
          "| Base | Válido | Autores | Trabalhos | Instituições | Periódicos | Tópicos | Org. ORCID | wrote | cites | "
          "Trab. c/ tópico | c/ periódico | c/ refs | Refs no corpus | Autores c/ vínculo ORCID |",
          "|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for b in order:
        k = res[b]["kg"]
        e, c, r = k["entidades"], k["cobertura"], k["relacoes"]
        L.append(f"| {label[b]} | {'sim' if k['valido'] else 'NÃO'} | {num(e['autores'])} | {num(e['trabalhos'])} | "
                 f"{num(e['instituicoes'])} | {num(e['periodicos'])} | {num(e['topicos'])} | "
                 f"{num(e['organizacoes_orcid'])} | {num(r['wrote'])} | {num(r['cites'])} | "
                 f"{pct(c['trabalhos_com_topico'])} | {pct(c['trabalhos_com_periodico'])} | "
                 f"{pct(c['trabalhos_com_referencias'])} | {pct(c['referencias_dentro_do_corpus'])} | "
                 f"{pct(c['autores_com_vinculo_orcid'])} |")
    L.append("")

    # ---- por base
    L += ["## 3. Geradores por base (baseline e oráculo)", "",
          "Baseline = ordenar pelo escore do próprio meta-caminho. Oráculo = reordenar perfeitamente o "
          "conjunto do gerador. *Alcance@1000*: fração dos coautores novos entre os 1.000 primeiros "
          "candidatos (teto de um re-ranqueador sobre esse top-1000). *Alcance total*: dentro de todo o "
          "conjunto com escore > 0. *Conjunto*: mediana de candidatos por alvo.", ""]
    for b in order:
        g = res[b]["resultados"]["com_M9"]["geral"]
        d = per[b][per[b]["variante"] == "com_M9"]
        med = d.groupby("gerador")["tamanho_conjunto"].median()
        L += [f"### {label[b]} ({res[b]['protocolo']['alvos']} alvos)", "",
              "| Gerador | R@10 | R@50 | NDCG@10 | Hits@10 | MRR | Alcance@200 | Alcance@1000 | Alcance total | Conjunto |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for gen in res[b]["geradores"] + ["uniao_rrf"]:
            r = g[gen]
            L.append(f"| {NOMES.get(gen, gen)} | {pct(r['R@10'])} | {pct(r['R@50'])} | {pct(r['NDCG@10'])} | "
                     f"{pct(r['Hits@10'])} | {pct(r['MRR'])} | {pct(r['alcance@200'])} | "
                     f"{pct(r['alcance@1000'])} | {pct(r['alcance'])} | {num(med[gen])} |")
        L.append("")

    # ---- gradiente
    key = ["coautoria_aa", "ppr", "instituicao", "topico", "acoplamento", "texto_tfidf", "uniao_rrf"]
    for metric, title in (("R@50", "R@50 (baseline)"), ("alcance@1000", "Alcance@1000 (oráculo)")):
        L += [f"## 4{'a' if metric == 'R@50' else 'b'}. Gradiente — {title}", "",
              "| Gerador | " + " | ".join(label[b] for b in order) + " |",
              "|---|" + "---:|" * len(order)]
        for gen in key:
            L.append(f"| {NOMES[gen]} | " + " | ".join(
                pct(res[b]["resultados"]["com_M9"]["geral"][gen][metric]) for b in order) + " |")
        L.append("")

    # ---- decomposição do erro (micro, união)
    L += ["## 5. Onde se perde cada coautoria nova (União RRF, soma de pares)", "",
          "| Base | Fora de T0 | Em T0, fora do conjunto | No conjunto, fora do top-1000 | "
          "Top-1000, fora do top-50 | Acerto no top-50 |", "|---|---:|---:|---:|---:|---:|"]
    for b in order:
        d = per[b][(per[b]["variante"] == "com_M9") & (per[b]["gerador"] == "uniao_rrf")]
        n = d["n_relevantes"].sum()
        t0 = res[b]["protocolo"]["pares_alcancaveis_em_T0"]
        pool = d["hits_conjunto"].sum()
        top1000 = (d["alcance@1000"] * d["n_relevantes"]).sum()
        top50 = (d["R@50"] * d["n_relevantes"]).sum()
        L.append(f"| {label[b]} | {pct(1 - t0 / n)} | {pct((t0 - pool) / n)} | {pct((pool - top1000) / n)} | "
                 f"{pct((top1000 - top50) / n)} | {pct(top50 / n)} |")
    L.append("")

    # ---- regimes
    L += ["## 6. Por regime — R@50 / Alcance@1000", ""]
    for b in order:
        rr = res[b]["resultados"]["com_M9"]
        regs = [r for r in ("warm", "cool", "cold", "newcomer") if r in rr]
        L += [f"**{label[b]}** — " + ", ".join(f"{r}: n={rr[r]['n']}" for r in regs), "",
              "| Gerador | " + " | ".join(regs) + " |", "|---|" + "---:|" * len(regs)]
        for gen in key:
            L.append(f"| {NOMES[gen]} | " + " | ".join(
                f"{pct(rr[r][gen]['R@50'])} / {pct(rr[r][gen]['alcance@1000'])}" for r in regs) + " |")
        L.append("")

    # ---- sensibilidade M9
    L += ["## 7. Sensibilidade à M9 — R@50 da União (com / sem a regra)", "",
          "| Base | Com M9 | Sem M9 | Δ (pp) |", "|---|---:|---:|---:|"]
    for b in order:
        a = res[b]["resultados"]["com_M9"]["geral"]["uniao_rrf"]["R@50"]
        s = res[b]["resultados"]["sem_M9"]["geral"]["uniao_rrf"]["R@50"]
        L.append(f"| {label[b]} | {pct(a)} | {pct(s)} | {pct(a - s)} |")
    L.append("")
    out = resolve("docs/RESULTADOS_LINHA_BASE.md")
    out.write_text("\n".join(L))
    print(f"escrito {out}")


if __name__ == "__main__":
    main()
