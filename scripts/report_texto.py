"""Relatório TF-IDF × SPECTER2 × ambos → docs/RESULTADOS_TEXTO_SPECTER2.md.

Lê runs/linha_base_ambos/<base>.json (geradores isolados) e runs/ltr_temporal[_specter2|_ambos]/
(modelo principal). Testes pareados por alvo contra a variante TF-IDF (Bonferroni).
Uso: python scripts/report_texto.py
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
from coauthor_rec.eval.stats import bonferroni, paired_test  # noqa: E402

VARS = {"tfidf": "runs/ltr_temporal", "specter2": "runs/ltr_temporal_specter2", "ambos": "runs/ltr_temporal_ambos"}
NOME = {"tfidf": "TF-IDF", "specter2": "SPECTER2", "ambos": "TF-IDF + SPECTER2"}


def pct(x):
    return f"{100 * x:.2f}".replace(".", ",")


def load(b, var, padrao=False):
    f = resolve(f"{VARS[var]}/{b}{'_padrao_T0' if padrao else ''}.parquet")
    return pd.read_parquet(f) if f.exists() else None


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    order = [b for b in cfg["gradiente"] if resolve(f"runs/ltr_temporal_specter2/{b}.json").exists()]
    lab = {b: cfg["bases"][b]["label"] for b in order}
    sep = "|---|" + "---:|" * len(order)
    L = ["# Resultados — TF-IDF × SPECTER2", "",
         "> Gerado por `scripts/report_texto.py`. Método em [TEXTO_SPECTER2.md](TEXTO_SPECTER2.md). Valores em %.",
         "> `*` = diferença significativa contra a variante TF-IDF (teste pareado por alvo, Bonferroni).", ""]

    # ---- geradores isolados
    gb = [b for b in order if resolve(f"runs/linha_base_ambos/{b}.json").exists()]
    if gb:
        L += ["## 1. Gerador textual isolado (mesmo protocolo da linha de base)", "",
              "| Gerador | Métrica | " + " | ".join(lab[b] for b in gb) + " |", "|---|---|" + "---:|" * len(gb)]
        R = {b: json.loads(resolve(f"runs/linha_base_ambos/{b}.json").read_text())["resultados"] for b in gb}
        for g, n in (("texto_tfidf", "TF-IDF"), ("texto_specter2", "SPECTER2"), ("uniao_rrf", "União RRF (com os dois)")):
            for var, met, mn in (("com_M9", "R@50", "R@50 estrita"), ("com_M9", "NDCG@10", "NDCG@10 estrita"),
                                 ("com_M9", "alcance@1000", "Alcance@1000 estrita"),
                                 ("padrao_T0", "R@50", "R@50 padrão"), ("padrao_T0", "alcance@1000", "Alcance@1000 padrão")):
                L.append(f"| {n} | {mn} | " + " | ".join(pct(R[b][var]["geral"][g][met]) for b in gb) + " |")
        L.append("")

    # ---- modelo principal
    comps = [(v, m) for v in ("specter2", "ambos") for m in ("LTR completo", "coautoria + texto")]
    alpha = bonferroni(0.05, len(comps) * 2 * 2 * max(len(order), 1))
    for padrao, title in ((False, "estrita"), (True, "padrão")):
        for met in ("R@50", "NDCG@10"):
            L += [f"## LTR temporal — {met}, avaliação {title}", "", "| Modelo | Texto | " +
                  " | ".join(lab[b] for b in order) + " |", "|---|---|" + "---:|" * len(order)]
            for m in ("LTR só coautoria", "coautoria + texto", "LTR completo"):
                for var in ("tfidf", "specter2", "ambos"):
                    if m == "LTR só coautoria" and var != "tfidf":
                        continue
                    cells = []
                    for b in order:
                        d, ref = load(b, var, padrao), load(b, "tfidf", padrao)
                        if d is None or m not in set(d["modelo"]):
                            cells.append("—")
                            continue
                        x = d[d["modelo"] == m].set_index("alvo")[met]
                        mark = ""
                        if var != "tfidf" and ref is not None:
                            y = ref[ref["modelo"] == m].set_index("alvo")[met].reindex(x.index)
                            r = paired_test(x.to_numpy(), y.to_numpy())
                            mark = "*" if r["p_value"] is not None and r["p_value"] < alpha else ""
                        cells.append(pct(x.mean()) + mark)
                    L.append(f"| {m} | {NOME[var] if m != 'LTR só coautoria' else '—'} | " + " | ".join(cells) + " |")
            L.append("")

    L += ["## Peso do grupo texto no LTR temporal completo (|SHAP|, % do total)", "", "| Texto | " +
          " | ".join(lab[b] for b in order) + " |", sep]
    for var in ("tfidf", "specter2", "ambos"):
        cells = []
        for b in order:
            f = resolve(f"{VARS[var]}/{b}.json")
            cells.append(pct(json.loads(f.read_text())["importancia_shap"].get("texto", 0)) if f.exists() else "—")
        L.append(f"| {NOME[var]} | " + " | ".join(cells) + " |")
    L += ["", f"α de Bonferroni: {alpha:.4f}.", ""]
    resolve("docs/RESULTADOS_TEXTO_SPECTER2.md").write_text("\n".join(L))
    print("escrito docs/RESULTADOS_TEXTO_SPECTER2.md")


if __name__ == "__main__":
    main()
