"""Linha de base + família de oráculos por meta-caminho do KG, numa base do gradiente.

Etapas:
  1. protocolo (corte T0 ≤ 2021, gabarito com teto de coautores, alvos elegíveis, regimes, M9);
  2. KG T0 materializado e validado → data/processed/kg_<base>/ (uma tabela por relação);
  3. para cada gerador (meta-caminho): ranking top-1000 de cada alvo e conjunto alcançado;
     mais a UNIÃO dos geradores por Reciprocal Rank Fusion;
  4. métricas por alvo — como baseline (ordem do próprio escore) e como oráculo (reordenação
     perfeita do conjunto do gerador) —, com e sem M9 → runs/linha_base/<base>.{json,parquet}.

Uso: PYTHONHASHSEED=0 python scripts/baseline_oracle.py economia [--batch 32] [--no-text]
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
from coauthor_rec.eval.metrics import ranking_report as per_target_metrics  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, save_kg, validate_kg  # noqa: E402
from coauthor_rec.models.kg_generators import GENERATORS, KGIndex, rank_candidates  # noqa: E402

TOP = 1000
RRF_K = 60
# a união junta os meta-caminhos; popularidade fica de fora (alcança todo mundo, não é caminho)
UNION = tuple(g for g in GENERATORS if g != "popularidade")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--no-text", action="store_true", help="pula o gerador TF-IDF")
    args = ap.parse_args()
    t_start = time.time()
    bases = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = bases["bases"][args.base]
    ev = load_config("eval")
    set_seed(ev["seed"])
    cap = load_filters()["max_coauthors_per_work"]

    cols = ["work_id", "author_id", "author_name", "publication_date", "level", "author_position"]
    corpus = pd.read_parquet(resolve(prof["corpus"]), columns=cols)
    autores = pd.read_csv(resolve(f"data/processed/autores_{args.base}.csv"), index_col=0,
                          usecols=["canonical_id", "alvo"])
    eligible = autores.index[autores["alvo"]].tolist()
    print(f"[{args.base}] corpus {corpus['work_id'].nunique()} trabalhos / {corpus['author_id'].nunique()} "
          f"pessoas; {len(eligible)} alvos elegíveis", flush=True)

    # 1. protocolo
    P = build_protocol(corpus, eligible, bases.get("split"), cap,
                       ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    summ = P.summary()
    print(f"[{args.base}] protocolo: {json.dumps(summ, ensure_ascii=False)}", flush=True)

    # 2. KG T0
    # texto e metadados vêm dos works brutos (1 linha por trabalho; no corpus o resumo se repete
    # a cada autoria — ~4 milhões de cópias em Medicina)
    works_raw = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract", "venue_id",
                                                          "referenced_works"])
    kg = build_kg_t0(corpus, works_raw, resolve(f"data/processed/enrich_{args.base}"), P.cutoff)
    manifest = validate_kg(kg, P.cutoff)
    save_kg(kg, resolve(f"data/processed/kg_{args.base}"), manifest)
    print(f"[{args.base}] KG T0: válido={manifest['valido']} {manifest['relacoes']}", flush=True)
    for v in manifest["violacoes"]:
        print(f"  VIOLAÇÃO: {v}", flush=True)
    texts = None
    if not args.no_text:
        w0 = works_raw[works_raw["id"].isin(set(kg["wrote"]["work_id"]))].set_index("id")
        texts = (w0["title"].fillna("") + ". " + w0["abstract"].fillna("")).str.strip()
    del works_raw
    t0 = time.time()
    idx = KGIndex(kg, cap, P.cutoff, texts=texts)
    print(f"[{args.base}] índice do KG em {time.time() - t0:.0f} s", flush=True)
    gens = [g for g in GENERATORS if not (args.no_text and g == "texto_tfidf")]
    union = [g for g in UNION if g in gens]

    # 3. ranking por gerador, em lotes de alvos
    variants = {"com_M9": P.gt, "sem_M9": P.gt_raw}
    all_targets = sorted(set(P.gt_raw))                 # superset (sem M9)
    in_t0 = [a for a in all_targets if a in idx.aidx]
    rows_out = []
    timing = {g: 0.0 for g in gens + ["uniao_rrf"]}
    authors = idx.authors
    for b in range(0, len(in_t0), args.batch):
        batch = in_t0[b:b + args.batch]
        rows = np.array([idx.aidx[a] for a in batch])
        exclude = [{idx.aidx[c] for c in P.train_graph.get(a, ()) if c in idx.aidx} | {idx.aidx[a]}
                   for a in batch]
        rrf = np.zeros((len(batch), len(authors)), dtype=np.float32)
        union_pool = np.zeros((len(batch), len(authors)), dtype=bool)
        rel_idx = {var: [np.array([idx.aidx[c] for c in gt.get(a, ()) if c in idx.aidx], dtype=np.int64)
                         for a in batch] for var, gt in variants.items()}
        for g in gens:
            t = time.time()
            S = idx.scores(g, rows)
            ranked, pools = rank_candidates(S, exclude, idx.degree, top=TOP)
            del S
            for i, a in enumerate(batch):
                ids = authors[ranked[i]].tolist()
                if g in union:
                    rrf[i, ranked[i]] += 1.0 / (RRF_K + np.arange(1, len(ranked[i]) + 1))
                    union_pool[i, pools[i]] = True
                for var, gt in variants.items():
                    if a not in gt:
                        continue
                    rel = gt[a]
                    hits = int(np.isin(rel_idx[var][i], pools[i], assume_unique=True).sum())
                    m = per_target_metrics(ids, hits, len(pools[i]), rel)
                    rows_out.append({"alvo": a, "regime": P.regimes.get(a, "?"), "gerador": g,
                                     "variante": var, **m})
            timing[g] += time.time() - t
        t = time.time()
        ranked, _ = rank_candidates(rrf, exclude, idx.degree, top=TOP)
        for i, a in enumerate(batch):
            ids = authors[ranked[i]].tolist()
            for var, gt in variants.items():
                if a not in gt:
                    continue
                rel = gt[a]
                hits = int(union_pool[i, rel_idx[var][i]].sum())
                m = per_target_metrics(ids, hits, int(union_pool[i].sum()), rel)
                rows_out.append({"alvo": a, "regime": P.regimes.get(a, "?"), "gerador": "uniao_rrf",
                                 "variante": var, **m})
        timing["uniao_rrf"] += time.time() - t
        print(f"[{args.base}] alvos {b + len(batch)}/{len(in_t0)} ({time.time() - t_start:.0f} s)", flush=True)

    # alvos sem nenhum trabalho em T0 (newcomers): nada a recomendar — contam como zero
    for a in sorted(set(all_targets) - set(in_t0)):
        for g in gens + ["uniao_rrf"]:
            for var, gt in variants.items():
                if a in gt:
                    m = per_target_metrics([], 0, 0, gt[a])
                    rows_out.append({"alvo": a, "regime": P.regimes.get(a, "newcomer"), "gerador": g,
                                     "variante": var, **m})

    # 4. agregação
    df = pd.DataFrame(rows_out)
    out_dir = resolve("runs/linha_base")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / f"{args.base}.parquet", index=False)
    metric_cols = [c for c in df.columns if c not in ("alvo", "regime", "gerador", "variante")]
    agg = {}
    for var, d in df.groupby("variante"):
        agg[var] = {"geral": d.groupby("gerador")[metric_cols].mean().round(4).to_dict(orient="index")}
        for reg, dr in d.groupby("regime"):
            agg[var][reg] = {"n": int(dr["alvo"].nunique()),
                             **dr.groupby("gerador")[metric_cols].mean().round(4).to_dict(orient="index")}
    res = {"base": args.base, "protocolo": summ, "kg": manifest, "geradores": gens, "uniao": union,
           "parametros": {"top": TOP, "rrf_k": RRF_K, "teto_coautores": cap, "ppr_alpha": idx.ppr_alpha,
                          "ppr_iter": idx.ppr_iters, "lote": args.batch},
           "tempo_s": {k: round(v, 1) for k, v in timing.items()},
           "tempo_total_s": round(time.time() - t_start, 1), "resultados": agg}
    (out_dir / f"{args.base}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    g = agg["com_M9"]["geral"]
    print(f"\n[{args.base}] com M9 — {summ['alvos']} alvos", flush=True)
    print(f"{'gerador':16s} {'R@10':>6s} {'R@50':>6s} {'NDCG10':>7s} {'alc@1000':>8s} {'alc.total':>9s} "
          f"{'conj.med':>9s}", flush=True)
    for gname in gens + ["uniao_rrf"]:
        r = g[gname]
        print(f"{gname:16s} {r['R@10']*100:6.2f} {r['R@50']*100:6.2f} {r['NDCG@10']*100:7.2f} "
              f"{r['alcance@1000']*100:8.2f} {r['alcance']*100:9.2f} {r['tamanho_conjunto']:9.0f}",
              flush=True)
    print(f"[{args.base}] concluído em {time.time() - t_start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
