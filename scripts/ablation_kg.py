"""Ablação das relações do KG com um re-ranqueador aprendido (LambdaMART), numa base.

Duas ablações, sobre o mesmo protocolo da linha de base (corte 2021, M9, alvos elegíveis):

- **Geração**: Alcance@1000 da União RRF com todos os meta-caminhos vs. sem cada grupo —
  quanto cada relação traz de candidatos que as outras não trazem.
- **Ordenação**: LambdaMART (validação cruzada em 5 dobras de alvos) sobre o MESMO conjunto
  de candidatos (top-1000 da união), com todos os grupos de atributos, só coautoria (+
  atividade), sem cada grupo e coautoria + cada grupo. Testes pareados (Wilcoxon/t,
  Bonferroni) contra o modelo completo e contra o só-coautoria; importância por grupo
  (ganho do LightGBM e |SHAP| médio).

Saídas: runs/ablacao_kg/<base>.{json,parquet}. Uso:
  PYTHONHASHSEED=0 python scripts/ablation_kg.py economia [--batch 32]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_config, load_filters, resolve, set_seed  # noqa: E402
from coauthor_rec.data.raw import load_raw_works  # noqa: E402
from coauthor_rec.eval.metrics import ranking_report  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.eval.stats import bonferroni, paired_test  # noqa: E402
from coauthor_rec.graph.kg import load_kg  # noqa: E402
from coauthor_rec.models.kg_generators import KGIndex  # noqa: E402
from coauthor_rec.models.kg_ltr import GROUPS, build_pairs, cross_val_rank, feature_columns, folds  # noqa: E402

KG_GROUPS = [g for g in GROUPS if g != "coautoria"]          # relações além da coautoria
MAIN = ("R@10", "R@50", "NDCG@10", "Hits@10", "MRR")


def configs() -> dict[str, list[str]]:
    allg = list(GROUPS) + ["atividade"]
    c = {"LTR completo": allg, "LTR só coautoria": ["coautoria", "atividade"]}
    for g in KG_GROUPS + ["atividade", "coautoria"]:
        c[f"sem {g}"] = [x for x in allg if x != g]
    for g in KG_GROUPS:
        c[f"coautoria + {g}"] = ["coautoria", "atividade", g]
    return c


def evaluate(pairs: pd.DataFrame, score: np.ndarray, gt: dict, targets: list) -> pd.DataFrame:
    """Métricas por alvo para um escore sobre o conjunto fixo de candidatos."""
    d = pairs[["alvo", "cand", "rotulo"]].assign(s=score)
    out = []
    by = dict(tuple(d.groupby("alvo", sort=False)))
    for a in targets:
        rel = gt[a]
        g = by.get(a)
        if g is None:
            out.append({"alvo": a, **ranking_report([], 0, 0, rel)})
            continue
        order = g.sort_values("s", ascending=False, kind="stable")    # empate: ordem da união
        hits = set(order.loc[order["rotulo"] == 1, "cand"])
        # coautores novos fora do conjunto entram como marcadores nunca ranqueados: o recall
        # continua sobre TODOS os coautores novos do alvo
        relset = hits | {-(j + 1) for j in range(len(rel) - len(hits))}
        out.append({"alvo": a, **ranking_report(order["cand"].tolist(), len(hits), len(g), relset)})
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()
    t0 = time.time()
    bases = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = bases["bases"][args.base]
    ev = load_config("eval")
    set_seed(ev["seed"])
    cap = load_filters()["max_coauthors_per_work"]
    corpus = pd.read_parquet(resolve(prof["corpus"]), columns=["work_id", "author_id", "author_name",
                                                                "publication_date"])
    autores = pd.read_csv(resolve(f"data/processed/autores_{args.base}.csv"), index_col=0,
                          usecols=["canonical_id", "alvo"])
    P = build_protocol(corpus, autores.index[autores["alvo"]].tolist(), bases.get("split"), cap,
                       ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    del corpus
    kg = load_kg(resolve(f"data/processed/kg_{args.base}"))
    w = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract"])
    w = w[w["id"].isin(set(kg["wrote"]["work_id"]))].set_index("id")
    texts = (w["title"].fillna("") + ". " + w["abstract"].fillna("")).str.strip()
    del w
    idx = KGIndex(kg, cap, P.cutoff, texts=texts)
    targets = P.targets
    print(f"[{args.base}] {len(targets)} alvos; montando pares…", flush=True)
    pairs, reach = build_pairs(idx, kg, targets, P.train_graph, P.gt, batch=args.batch)
    print(f"[{args.base}] {len(pairs)} pares, {int(pairs['rotulo'].sum())} positivos "
          f"({time.time() - t0:.0f} s)", flush=True)

    # ---- ablação da geração (micro: soma de pares)
    n_rel = sum(len(P.gt[a]) for a in targets)
    gen = {c: round(float(reach[c].sum() / n_rel), 4) for c in reach.columns if c not in ("alvo", "n_relevantes")}

    # ---- ablação da ordenação
    fold_of = folds(targets, 5, ev["seed"])
    per, imp_gain, imp_shap = {}, None, None
    per["União RRF (sem aprendizado)"] = evaluate(pairs, pairs["rrf"].to_numpy(), P.gt, targets)
    for name, groups in configs().items():
        t = time.time()
        cols = feature_columns(groups)
        s, imp, sh = cross_val_rank(pairs, cols, fold_of, ev["seed"], want_shap=(name == "LTR completo"))
        per[name] = evaluate(pairs, s.to_numpy(), P.gt, targets)
        if name == "LTR completo":
            imp_gain, imp_shap = imp, sh
        print(f"[{args.base}] {name:28s} R@10 {per[name]['R@10'].mean() * 100:5.2f}  "
              f"R@50 {per[name]['R@50'].mean() * 100:5.2f}  NDCG@10 {per[name]['NDCG@10'].mean() * 100:5.2f} "
              f"({time.time() - t:.0f} s)", flush=True)

    def group_of(col):
        for g, gens in GROUPS.items():
            if any(col == x or col == f"{x}_pos" for x in gens):
                return g
        return "atividade"
    gain_by = imp_gain.groupby(group_of).sum().sort_values(ascending=False)
    shap_by = imp_shap.groupby(group_of).sum()
    shap_by = (shap_by / shap_by.sum()).sort_values(ascending=False)

    # ---- testes pareados
    tests = {}
    comps = [("LTR completo", "LTR só coautoria"), ("LTR completo", "União RRF (sem aprendizado)")]
    comps += [("LTR completo", f"sem {g}") for g in KG_GROUPS + ["atividade", "coautoria"]]
    comps += [(f"coautoria + {g}", "LTR só coautoria") for g in KG_GROUPS]
    alpha = bonferroni(0.05, len(comps))
    for a, b in comps:
        for met in ("R@50", "NDCG@10"):
            r = paired_test(per[a][met].to_numpy(), per[b][met].to_numpy())
            tests[f"{a} vs {b} | {met}"] = {**r, "significativo": bool(r["p_value"] is not None
                                                                        and r["p_value"] < alpha)}

    regimes = pd.Series(P.regimes)
    rows = []
    for name, d in per.items():
        rows.append(d.assign(modelo=name, regime=d["alvo"].map(regimes)))
    allp = pd.concat(rows, ignore_index=True)
    out_dir = resolve("runs/ablacao_kg")
    out_dir.mkdir(parents=True, exist_ok=True)
    allp.to_parquet(out_dir / f"{args.base}.parquet", index=False)
    summary = {name: {m: round(float(d[m].mean()), 4) for m in MAIN} for name, d in per.items()}
    by_reg = {reg: {name: {m: round(float(d[m].mean()), 4) for m in ("R@50", "NDCG@10")}
                    for name, d in allp[allp["regime"] == reg].groupby("modelo")}
              for reg in ("warm", "cool", "cold", "newcomer") if (allp["regime"] == reg).any()}
    res = {"base": args.base, "alvos": len(targets), "pares": int(len(pairs)),
           "positivos_no_conjunto": int(pairs["rotulo"].sum()), "pares_novos": n_rel,
           "alfa_bonferroni": alpha, "geracao_alcance1000": gen, "ordenacao": summary,
           "por_regime": by_reg, "importancia_ganho": gain_by.round(4).to_dict(),
           "importancia_shap": shap_by.round(4).to_dict(), "testes": tests,
           "tempo_s": round(time.time() - t0, 1)}
    (out_dir / f"{args.base}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[{args.base}] geração (alcance@1000 da união): {gen}", flush=True)
    print(f"[{args.base}] SHAP por grupo: {shap_by.round(3).to_dict()}", flush=True)
    print(f"[{args.base}] concluído em {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
