"""Treino TEMPORAL do re-ranqueador (docs/ABLACAO_KG.md §7) — nenhum rótulo do período de teste.

Na ablação por validação cruzada, os rótulos de treino vinham de T1 (de outros alvos). Aqui o
modelo aprende inteiramente no passado e é aplicado ao futuro:

  treino: KG cortado em 2018 → rótulos = coautorias novas de 2019–2021
          consultas = sementes ∪ candidatos (todos têm histórico completo em 2017–2021)
  teste:  KG cortado em 2021 → rótulos = coautorias novas de T1 (2022+), alvos elegíveis, M9
          (exatamente o conjunto e as métricas da ablação)

Incluir os candidatos como consultas multiplica os positivos de treino (eles não podem ser alvos
de avaliação porque o histórico deles depois de 2021 não foi coletado, mas em 2019–2021 está
completo). Configurações: as mesmas da ablação (completo, só coautoria, sem X, coautoria + X),
mais duas de sensibilidade: só sementes como consultas e hiperparâmetros padrão do LightGBM.

Uso: PYTHONHASHSEED=0 python scripts/temporal_ltr.py economia [--batch 32] [--max-consultas 3000]
Saídas: runs/ltr_temporal/<base>.{json,parquet}
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from ablation_kg import KG_GROUPS, MAIN, configs, evaluate  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve, set_seed  # noqa: E402
from coauthor_rec.data.raw import load_raw_works  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.eval.stats import bonferroni, paired_test  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, load_kg  # noqa: E402
from coauthor_rec.models.kg_generators import KGIndex, text_variant  # noqa: E402
from coauthor_rec.models.kg_ltr import GROUPS, build_pairs, feature_columns, lgbm_params, train_apply  # noqa: E402

TRAIN_CUTOFF = 2018


def texts_for(works_raw: pd.DataFrame, work_ids) -> pd.Series:
    w = works_raw[works_raw["id"].isin(set(work_ids))].set_index("id")
    return (w["title"].fillna("") + ". " + w["abstract"].fillna("")).str.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-consultas", type=int, default=3000)
    ap.add_argument("--texto", choices=["tfidf", "specter2", "ambos"], default="tfidf",
                    help="sinal textual: TF-IDF (padrão), SPECTER2 no lugar dele, ou os dois")
    args = ap.parse_args()
    gens, wemb = text_variant(args.texto, args.base)
    t0 = time.time()
    bases = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = bases["bases"][args.base]
    ev = load_config("eval")
    seed = ev["seed"]
    set_seed(seed)
    cap = load_filters()["max_coauthors_per_work"]
    wr, cr = ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"]
    corpus = pd.read_parquet(resolve(prof["corpus"]), columns=[
        "work_id", "author_id", "author_id_openalex", "author_name", "publication_date", "level", "author_position"])
    au = pd.read_csv(resolve(f"data/processed/autores_{args.base}.csv"), index_col=0,
                     usecols=["canonical_id", "alvo", "is_seed"])
    test_cut = int(bases["split"]["t0_ate"])

    # ---- consultas de treino: sementes ∪ candidatos (pessoa canônica)
    seeds = set(au.index[au["is_seed"]])
    cand_oa = set(pd.read_csv(resolve(prof["raw_dir"]) / "candidates.csv", usecols=["author_id"])["author_id"])
    oa2can = corpus.drop_duplicates("author_id_openalex").set_index("author_id_openalex")["author_id"]
    cands = {oa2can[c] for c in cand_oa if c in oa2can.index} - seeds
    year = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
    c21 = corpus[year <= test_cut]
    Pin = build_protocol(c21, seeds | cands, {"modo": "calendario", "t0_ate": TRAIN_CUTOFF}, cap, wr, cr)
    rng = np.random.default_rng(seed)
    q_seeds = [a for a in Pin.targets if a in seeds]
    q_cands = [a for a in Pin.targets if a not in seeds]
    room = max(args.max_consultas - len(q_seeds), 0)
    if len(q_cands) > room:
        q_cands = sorted(rng.choice(q_cands, size=room, replace=False).tolist())
    queries = sorted(q_seeds + q_cands)
    print(f"[{args.base}] treino {TRAIN_CUTOFF}→{TRAIN_CUTOFF + 1}–{test_cut}: {len(Pin.targets)} consultas com "
          f"coautoria nova ({len(q_seeds)} sementes, {len(Pin.targets) - len(q_seeds)} candidatos); "
          f"usadas {len(queries)}", flush=True)

    # ---- pares de treino (KG de 2018)
    works_raw = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract", "venue_id", "referenced_works"])
    kg18 = build_kg_t0(corpus, works_raw, resolve(f"data/processed/enrich_{args.base}"), TRAIN_CUTOFF)
    idx = KGIndex(kg18, cap, TRAIN_CUTOFF, texts=texts_for(works_raw, kg18["wrote"]["work_id"]), work_emb=wemb)
    train, _ = build_pairs(idx, kg18, queries, Pin.train_graph, Pin.gt, gens=gens, batch=args.batch)
    train["semente"] = train["alvo"].isin(seeds)
    del idx, kg18, Pin, c21
    gc.collect()
    print(f"[{args.base}] treino: {len(train)} pares, {int(train['rotulo'].sum())} positivos "
          f"({time.time() - t0:.0f} s)", flush=True)

    # ---- pares de teste (KG de 2021 — o mesmo da linha de base e da ablação)
    P = build_protocol(corpus[["work_id", "author_id", "author_name", "publication_date"]],
                       au.index[au["alvo"]].tolist(), bases.get("split"), cap, wr, cr)
    del corpus
    kg21 = load_kg(resolve(f"data/processed/kg_{args.base}"))
    idx = KGIndex(kg21, cap, P.cutoff, texts=texts_for(works_raw, kg21["wrote"]["work_id"]), work_emb=wemb)
    del works_raw
    test, _ = build_pairs(idx, kg21, P.targets, P.train_graph, P.gt, gens=gens, batch=args.batch)
    del idx, kg21
    gc.collect()
    print(f"[{args.base}] teste: {len(test)} pares, {int(test['rotulo'].sum())} positivos "
          f"({time.time() - t0:.0f} s)", flush=True)

    # ---- modelos
    tgt_t0 = sorted(P.gt_t0)                     # avaliação padrão: só coautores presentes em T0
    per = {"União RRF (sem aprendizado)": evaluate(test, test["rrf"].to_numpy(), P.gt, P.targets)}
    per_t0 = {"União RRF (sem aprendizado)": evaluate(test, test["rrf"].to_numpy(), P.gt_t0, tgt_t0)}
    shap = None
    runs = list(configs().items())
    runs += [("LTR completo — só sementes como consultas", list(GROUPS) + ["atividade"]),
             ("LTR completo — parâmetros padrão", list(GROUPS) + ["atividade"])]
    for name, groups in runs:
        t = time.time()
        cols = feature_columns(groups, gens)
        tr = train[train["semente"]] if "só sementes" in name else train
        params = None
        if "padrão" in name:
            params = {**lgbm_params(seed), "n_estimators": 400, "num_leaves": 31, "min_child_samples": 20,
                      "reg_lambda": 0.0}
        s, _, sh = train_apply(tr, test, cols, seed, params, want_shap=(name == "LTR completo"))
        if name == "LTR completo":
            shap = sh
        per[name] = evaluate(test, s.to_numpy(), P.gt, P.targets)
        per_t0[name] = evaluate(test, s.to_numpy(), P.gt_t0, tgt_t0)
        print(f"[{args.base}] {name:42s} R@10 {per[name]['R@10'].mean() * 100:5.2f}  "
              f"R@50 {per[name]['R@50'].mean() * 100:5.2f}  NDCG@10 {per[name]['NDCG@10'].mean() * 100:5.2f} "
              f"({time.time() - t:.0f} s)", flush=True)

    # comparação com a ablação por validação cruzada (mesmos alvos e candidatos)
    cv_f = resolve(f"runs/ablacao_kg/{args.base}.parquet")
    if cv_f.exists():
        cv = pd.read_parquet(cv_f)
        cv = cv[cv["modelo"] == "LTR completo"].set_index("alvo").reindex(P.targets).reset_index()
        per["LTR completo (validação cruzada)"] = cv

    def group_of(col):
        for g, gens in GROUPS.items():
            if any(col == x or col == f"{x}_pos" for x in gens):
                return g
        return "atividade"
    shap_by = shap.groupby(group_of).sum()
    shap_by = (shap_by / shap_by.sum()).sort_values(ascending=False)

    comps = [("LTR completo", "União RRF (sem aprendizado)"), ("LTR completo", "LTR só coautoria"),
             ("LTR completo", "LTR completo (validação cruzada)"),
             ("LTR completo", "LTR completo — só sementes como consultas")]
    comps += [("LTR completo", f"sem {g}") for g in KG_GROUPS + ["atividade", "coautoria"]]
    comps += [(f"coautoria + {g}", "LTR só coautoria") for g in KG_GROUPS]
    comps = [(a, b) for a, b in comps if a in per and b in per]
    alpha = bonferroni(0.05, len(comps))
    tests = {}
    for a, b in comps:
        for met in ("R@50", "NDCG@10"):
            r = paired_test(per[a][met].to_numpy(), per[b][met].to_numpy())
            tests[f"{a} vs {b} | {met}"] = {**r, "significativo": bool(r["p_value"] is not None and r["p_value"] < alpha)}

    comps_t0 = [("LTR completo", "União RRF (sem aprendizado)"), ("LTR completo", "LTR só coautoria")]
    comps_t0 += [(f"coautoria + {g}", "LTR só coautoria") for g in KG_GROUPS]
    alpha_t0 = bonferroni(0.05, len(comps_t0))
    tests_t0 = {}
    for a, b in comps_t0:
        for met in ("R@50", "NDCG@10"):
            r = paired_test(per_t0[a][met].to_numpy(), per_t0[b][met].to_numpy())
            tests_t0[f"{a} vs {b} | {met}"] = {**r, "significativo": bool(r["p_value"] is not None
                                                                          and r["p_value"] < alpha_t0)}
    regimes = pd.Series(P.regimes)
    allp = pd.concat([d.assign(modelo=n, regime=d["alvo"].map(regimes)) for n, d in per.items()], ignore_index=True)
    out_dir = resolve("runs/ltr_temporal" + ("" if args.texto == "tfidf" else f"_{args.texto}"))
    out_dir.mkdir(parents=True, exist_ok=True)
    allp.to_parquet(out_dir / f"{args.base}.parquet", index=False)
    pd.concat([d.assign(modelo=n, regime=d["alvo"].map(regimes)) for n, d in per_t0.items()],
              ignore_index=True).to_parquet(out_dir / f"{args.base}_padrao_T0.parquet", index=False)
    res = {"base": args.base, "texto": args.texto, "geradores": gens, "corte_treino": TRAIN_CUTOFF, "corte_teste": test_cut,
           "consultas_treino": {"sementes": len(q_seeds), "candidatos": len(q_cands)},
           "pares_treino": int(len(train)), "positivos_treino": int(train["rotulo"].sum()),
           "positivos_treino_sementes": int(train.loc[train["semente"], "rotulo"].sum()),
           "alvos_teste": len(P.targets), "pares_teste": int(len(test)), "positivos_teste": int(test["rotulo"].sum()),
           "alfa_bonferroni": alpha,
           "ordenacao": {n: {m: round(float(d[m].mean()), 4) for m in MAIN} for n, d in per.items()},
           "por_regime": {reg: {n: {m: round(float(d[m].mean()), 4) for m in ("R@50", "NDCG@10")}
                                for n, d in allp[allp["regime"] == reg].groupby("modelo")}
                          for reg in ("warm", "cool", "cold") if (allp["regime"] == reg).any()},
           "importancia_shap": shap_by.round(4).to_dict(), "testes": tests,
           "padrao_T0": {"alvos": len(tgt_t0), "alfa_bonferroni": alpha_t0, "testes": tests_t0,
                         "ordenacao": {n: {m: round(float(d[m].mean()), 4) for m in MAIN}
                                       for n, d in per_t0.items()}}, "tempo_s": round(time.time() - t0, 1)}
    (out_dir / f"{args.base}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[{args.base}] SHAP por grupo: {shap_by.round(3).to_dict()}", flush=True)
    print(f"[{args.base}] concluído em {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
