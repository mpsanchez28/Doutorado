"""Geração seletiva em cascata (docs/GERACAO_SELETIVA.md) — treino temporal, numa base.

  conjunto ampliado = união dos top-1000 de cada gerador (~13 mil candidatos/alvo em Medicina)
  etapa 1 (pontual, LightGBM binário): nota cada candidato do conjunto ampliado → fica o top-1000
  etapa 2 (LambdaMART, a mesma do treino temporal): ordena esse top-1000

Treino no passado (KG 2018 → coautorias novas de 2019–2021), consultas = sementes + candidatos,
divididas em duas metades DISJUNTAS: A treina a etapa 1 (todos os positivos + 2% dos negativos);
B recebe o top-1000 escolhido pela etapa 1 e treina a etapa 2 — assim a etapa 2 aprende com
listas produzidas por um modelo que não viu aquelas consultas, como no teste.

Teste: KG 2021 → T1, mesmos alvos e gabarito (estrito e padrão) da linha de base.
Comparações: alcance@1000 da etapa 1 vs União RRF; resultado final vs LTR temporal sobre a
União RRF (runs/ltr_temporal) e vs a própria União RRF.

Uso: PYTHONHASHSEED=0 python scripts/cascade_eval.py economia [--batch 32] [--max-consultas 4000]
Saídas: runs/cascata/<base>.{json,parquet}
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

from ablation_kg import MAIN, evaluate  # noqa: E402
from temporal_ltr import TRAIN_CUTOFF, texts_for  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve, set_seed  # noqa: E402
from coauthor_rec.data.raw import load_raw_works  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.eval.stats import bonferroni, paired_test  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, load_kg  # noqa: E402
from coauthor_rec.models.kg_generators import KGIndex  # noqa: E402
from coauthor_rec.models.kg_ltr import (GROUPS, cascade_pairs, feature_columns, lgbm_params,  # noqa: E402
                                        stage1_params, train_apply)

KEEP = 1000
NEG_RATE = 0.02


def micro(reach: pd.DataFrame, col: str, denom) -> float:
    """Fração de pares; ``denom`` = coluna de ``reach`` ou total explícito (todos os alvos,
    inclusive os sem trabalho em T0 — o mesmo denominador da linha de base)."""
    d = reach[denom].sum() if isinstance(denom, str) else denom
    return round(float(reach[col].sum() / max(d, 1)), 4)


def main():
    import lightgbm as lgb
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-consultas", type=int, default=4000)
    args = ap.parse_args()
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

    # ---- consultas de treino (como no treino temporal), divididas em A (etapa 1) e B (etapa 2)
    seeds = set(au.index[au["is_seed"]])
    cand_oa = set(pd.read_csv(resolve(prof["raw_dir"]) / "candidates.csv", usecols=["author_id"])["author_id"])
    oa2can = corpus.drop_duplicates("author_id_openalex").set_index("author_id_openalex")["author_id"]
    cands = {oa2can[c] for c in cand_oa if c in oa2can.index} - seeds
    year = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
    Pin = build_protocol(corpus[year <= test_cut], seeds | cands, {"modo": "calendario", "t0_ate": TRAIN_CUTOFF},
                         cap, wr, cr)
    rng = np.random.default_rng(seed)
    q_seeds = [a for a in Pin.targets if a in seeds]
    q_cands = [a for a in Pin.targets if a not in seeds]
    room = max(args.max_consultas - len(q_seeds), 0)
    if len(q_cands) > room:
        q_cands = rng.choice(q_cands, size=room, replace=False).tolist()
    queries = np.array(sorted(q_seeds + q_cands))
    rng.shuffle(queries)
    half = len(queries) // 2
    qA, qB = sorted(queries[:half]), sorted(queries[half:])
    print(f"[{args.base}] consultas de treino: {len(queries)} (A={len(qA)} etapa 1, B={len(qB)} etapa 2)", flush=True)

    works_raw = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract", "venue_id", "referenced_works"])
    kg18 = build_kg_t0(corpus, works_raw, resolve(f"data/processed/enrich_{args.base}"), TRAIN_CUTOFF)
    idx = KGIndex(kg18, cap, TRAIN_CUTOFF, texts=texts_for(works_raw, kg18["wrote"]["work_id"]))

    # ---- etapa 1: treino em A (positivos + 2% dos negativos do conjunto ampliado)
    s1_cols = feature_columns(list(GROUPS) + ["atividade"]) + ["rrf", "rrf_pos"]
    trA, reachA = cascade_pairs(idx, kg18, qA, Pin.train_graph, Pin.gt, keep=KEEP, batch=args.batch,
                                neg_rate=NEG_RATE, seed=seed)
    stage1 = lgb.LGBMClassifier(**stage1_params(seed))
    stage1.fit(trA[s1_cols].to_numpy(np.float32), trA["rotulo"].to_numpy())
    s1_imp = pd.Series(stage1.booster_.feature_importance("gain"), index=s1_cols)
    print(f"[{args.base}] etapa 1 treinada: {len(trA)} pares ({int(trA['rotulo'].sum())} positivos) "
          f"({time.time() - t0:.0f} s)", flush=True)
    del trA

    # ---- etapa 2: pares de B = top-1000 da etapa 1
    trB, reachB = cascade_pairs(idx, kg18, qB, Pin.train_graph, Pin.gt, keep=KEEP, batch=args.batch,
                                stage1=stage1, stage1_cols=s1_cols)
    print(f"[{args.base}] treino da etapa 2: {len(trB)} pares, {int(trB['rotulo'].sum())} positivos; alcance@1000 "
          f"em B: RRF {micro(reachB, 'hits_rrf', 'n_relevantes')} → etapa 1 {micro(reachB, 'hits_etapa1', 'n_relevantes')} "
          f"({time.time() - t0:.0f} s)", flush=True)
    del idx, kg18, Pin
    gc.collect()

    # ---- teste (KG 2021)
    P = build_protocol(corpus[["work_id", "author_id", "author_name", "publication_date"]],
                       au.index[au["alvo"]].tolist(), bases.get("split"), cap, wr, cr)
    del corpus
    kg21 = load_kg(resolve(f"data/processed/kg_{args.base}"))
    idx = KGIndex(kg21, cap, P.cutoff, texts=texts_for(works_raw, kg21["wrote"]["work_id"]))
    del works_raw
    test, reach = cascade_pairs(idx, kg21, P.targets, P.train_graph, P.gt, keep=KEEP, batch=args.batch,
                                stage1=stage1, stage1_cols=s1_cols)
    del idx, kg21
    gc.collect()
    n_all = sum(len(P.gt[a]) for a in P.targets)
    n_t0 = sum(len(s) for s in P.gt_t0.values())
    gen = {"estrita": {"uniao_rrf@1000": micro(reach, "hits_rrf", n_all),
                       "etapa1@1000": micro(reach, "hits_etapa1", n_all),
                       "conjunto_ampliado": micro(reach, "hits_ampliado", n_all)},
           "padrao_T0": {"uniao_rrf@1000": micro(reach, "hits_rrf", n_t0),
                         "etapa1@1000": micro(reach, "hits_etapa1", n_t0),
                         "conjunto_ampliado": micro(reach, "hits_ampliado", n_t0)},
           "conjunto_ampliado_mediana": float(reach["conjunto_ampliado"].median()),
           "treino_B": {"uniao_rrf@1000": micro(reachB, "hits_rrf", "n_relevantes"),
                        "etapa1@1000": micro(reachB, "hits_etapa1", "n_relevantes")}}
    print(f"[{args.base}] geração no teste: {gen}", flush=True)

    # ---- etapa 2 e avaliação
    cols = feature_columns(list(GROUPS) + ["atividade"])
    tgt_t0 = sorted(P.gt_t0)
    per, per_t0 = {}, {}
    variants = {"Cascata: etapa 1 apenas": None,
                "Cascata: etapa 1 → LTR": cols,
                "Cascata: etapa 1 → LTR (+ nota da etapa 1)": cols + ["nota_etapa1"]}
    for name, c in variants.items():
        if c is None:
            sc = test["nota_etapa1"].to_numpy()
        else:
            sc, _, _ = train_apply(trB, test, c, seed, lgbm_params(seed))
            sc = sc.to_numpy()
        per[name] = evaluate(test, sc, P.gt, P.targets)
        per_t0[name] = evaluate(test, sc, P.gt_t0, tgt_t0)
        print(f"[{args.base}] {name:45s} R@10 {per[name]['R@10'].mean() * 100:5.2f}  R@50 "
              f"{per[name]['R@50'].mean() * 100:5.2f}  NDCG@10 {per[name]['NDCG@10'].mean() * 100:5.2f}  | padrão R@50 "
              f"{per_t0[name]['R@50'].mean() * 100:5.2f}", flush=True)

    # referências: LTR temporal sobre a União RRF e a própria União RRF (mesmos alvos)
    ref = {}
    for fname, store, tg in ((f"{args.base}.parquet", per, P.targets), (f"{args.base}_padrao_T0.parquet", per_t0, tgt_t0)):
        f = resolve(f"runs/ltr_temporal/{fname}")
        if f.exists():
            d = pd.read_parquet(f)
            for m, lab in (("LTR completo", "LTR temporal (União RRF → LTR)"),
                           ("União RRF (sem aprendizado)", "União RRF (sem aprendizado)")):
                store[lab] = d[d["modelo"] == m].set_index("alvo").reindex(tg).reset_index()
                ref[lab] = True
    best = "Cascata: etapa 1 → LTR"
    comps = [(best, "LTR temporal (União RRF → LTR)"), (best, "União RRF (sem aprendizado)"),
             ("Cascata: etapa 1 → LTR (+ nota da etapa 1)", "LTR temporal (União RRF → LTR)")]
    comps = [(a, b) for a, b in comps if a in per and b in per]
    alpha = bonferroni(0.05, 2 * len(comps))
    tests = {}
    for var, store in (("estrita", per), ("padrao_T0", per_t0)):
        for a, b in comps:
            for met in ("R@50", "NDCG@10"):
                r = paired_test(store[a][met].to_numpy(), store[b][met].to_numpy())
                tests[f"{var} | {a} vs {b} | {met}"] = {**r, "significativo": bool(r["p_value"] is not None
                                                                                    and r["p_value"] < alpha)}
    regimes = pd.Series(P.regimes)
    out_dir = resolve("runs/cascata")
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat([d.assign(modelo=n, avaliacao=v, regime=d["alvo"].map(regimes))
               for v, st in (("estrita", per), ("padrao_T0", per_t0)) for n, d in st.items()],
              ignore_index=True).to_parquet(out_dir / f"{args.base}.parquet", index=False)
    res = {"base": args.base, "consultas_treino": {"A_etapa1": len(qA), "B_etapa2": len(qB)},
           "taxa_negativos_etapa1": NEG_RATE, "geracao": gen, "alfa_bonferroni": alpha,
           "ordenacao": {v: {n: {m: round(float(d[m].mean()), 4) for m in MAIN} for n, d in st.items()}
                         for v, st in (("estrita", per), ("padrao_T0", per_t0))},
           "testes": tests,
           "etapa1_importancia": (s1_imp / s1_imp.sum()).sort_values(ascending=False).head(15).round(4).to_dict(),
           "tempo_s": round(time.time() - t0, 1)}
    (out_dir / f"{args.base}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[{args.base}] concluído em {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
