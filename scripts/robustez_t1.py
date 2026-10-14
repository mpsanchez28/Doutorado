"""T1 — robustez do MODELO PRINCIPAL a sementes aleatórias (docs/ROBUSTEZ_T1_T4.md §2).

Modelo principal (inalterado): LambdaMART, treino temporal (KG 2018 → coautorias novas de
2019–2021, consultas = sementes + até 3.000 candidatos sorteados), aplicado ao top-1000 da
União RRF no KG de 2021, texto TF-IDF. Este script NÃO altera o modelo: reutiliza as mesmas
funções (``build_pairs``, ``train_apply``, ``lgbm_params``) e só controla, por fora, as duas
fontes de aleatoriedade:

  semente de CONSULTAS — sorteio dos candidatos usados como consultas de treino
  semente do LIGHTGBM  — subamostragem de linhas/colunas (random_state)

Modos (configs/robustez.yaml): ``ambos`` (as duas variam juntas), ``consultas`` e ``lightgbm``
(uma varia, a outra fica na referência 42). A rodada (42, 42) reproduz o resultado histórico
(runs/ltr_temporal/<base>.json) — verificação de fidelidade do executor.

Uso: PYTHONHASHSEED=0 python scripts/robustez_t1.py economia [--sementes 0 1 2] [--modos ambos]
Saídas: runs/robustez/t1/<base>.{json,parquet}
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

from ablation_kg import evaluate  # noqa: E402
from temporal_ltr import TRAIN_CUTOFF, texts_for  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.raw import load_raw_works  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.eval.stats import paired_test  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, load_kg, validate_kg  # noqa: E402
from coauthor_rec.models.kg_generators import GENERATORS, KGIndex  # noqa: E402
from coauthor_rec.models.kg_ltr import GROUPS, build_pairs, feature_columns, lgbm_params, train_apply  # noqa: E402

METRICS = ("R@10", "R@50", "NDCG@10", "Hits@10")
MODELS = {"LTR completo": list(GROUPS) + ["atividade"], "LTR só coautoria": ["coautoria", "atividade"]}


def sample_queries(pin_targets: list, seeds: set, max_q: int, seed: int) -> list:
    """Idêntico ao sorteio de scripts/temporal_ltr.py (mesma ordem de chamadas ao gerador)."""
    rng = np.random.default_rng(seed)
    q_seeds = [a for a in pin_targets if a in seeds]
    q_cands = [a for a in pin_targets if a not in seeds]
    room = max(max_q - len(q_seeds), 0)
    if len(q_cands) > room:
        q_cands = sorted(rng.choice(q_cands, size=room, replace=False).tolist())
    return sorted(q_seeds + q_cands)


def bootstrap_ci(x: np.ndarray, n: int, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def check(report: dict, what: str) -> None:
    """Aborta se o KG tiver fato posterior ao corte ou violar a ontologia (validate_kg)."""
    if not report["valido"]:
        raise SystemExit(f"[vazamento/consistência] {what}: {report['violacoes']}")
    print(f"[checagem] {what}: válido, nenhum fato posterior ao corte", flush=True)


def group_of(col: str) -> str:
    for g, gens in GROUPS.items():
        if any(col == x or col == f"{x}_pos" for x in gens):
            return g
    return "atividade"


def main():
    rob = yaml.safe_load(open(resolve("configs/robustez.yaml")))
    t1 = rob["t1"]
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--sementes", type=int, nargs="*", default=t1["sementes"])
    ap.add_argument("--modos", nargs="*", default=t1["modos"])
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()
    ref = int(t1["semente_referencia"])
    t0 = time.time()
    bases = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = bases["bases"][args.base]
    ev = load_config("eval")
    cap = load_filters()["max_coauthors_per_work"]
    wr, cr = ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"]
    test_cut = int(bases["split"]["t0_ate"])

    # rodadas: (modo, semente de consultas, semente do LightGBM); a referência sempre entra
    runs = [("referencia", ref, ref)]
    for m in args.modos:
        for s in args.sementes:
            runs.append((m, s if m in ("ambos", "consultas") else ref, s if m in ("ambos", "lightgbm") else ref))

    corpus = pd.read_parquet(resolve(prof["corpus"]), columns=[
        "work_id", "author_id", "author_id_openalex", "author_name", "publication_date", "level", "author_position"])
    au = pd.read_csv(resolve(f"data/processed/autores_{args.base}.csv"), index_col=0,
                     usecols=["canonical_id", "alvo", "is_seed"])
    seeds = set(au.index[au["is_seed"]])
    cand_oa = set(pd.read_csv(resolve(prof["raw_dir"]) / "candidates.csv", usecols=["author_id"])["author_id"])
    oa2can = corpus.drop_duplicates("author_id_openalex").set_index("author_id_openalex")["author_id"]
    cands = {oa2can[c] for c in cand_oa if c in oa2can.index} - seeds
    year = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
    Pin = build_protocol(corpus[year <= test_cut], seeds | cands, {"modo": "calendario", "t0_ate": TRAIN_CUTOFF},
                         cap, wr, cr)
    P = build_protocol(corpus[["work_id", "author_id", "author_name", "publication_date"]],
                       au.index[au["alvo"]].tolist(), bases.get("split"), cap, wr, cr)
    works_raw = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract", "venue_id", "referenced_works"])

    # ---- teste: montado UMA vez (não depende de semente)
    kg21 = load_kg(resolve(f"data/processed/kg_{args.base}"))
    check(validate_kg(kg21, P.cutoff), f"KG de teste ({P.cutoff})")
    idx = KGIndex(kg21, cap, P.cutoff, texts=texts_for(works_raw, kg21["wrote"]["work_id"]))
    test, _ = build_pairs(idx, kg21, P.targets, P.train_graph, P.gt, gens=GENERATORS, batch=args.batch, verbose=False)
    del idx, kg21
    gc.collect()
    tgt_t0 = sorted(P.gt_t0)
    rrf = {"estrita": evaluate(test, test["rrf"].to_numpy(), P.gt, P.targets),
           "padrao": evaluate(test, test["rrf"].to_numpy(), P.gt_t0, tgt_t0)}
    print(f"[{args.base}] teste: {len(test)} pares ({time.time() - t0:.0f} s)", flush=True)

    # ---- treino: KG de 2018; pares remontados só quando muda o sorteio de consultas
    kg18 = build_kg_t0(corpus, works_raw, resolve(f"data/processed/enrich_{args.base}"), TRAIN_CUTOFF)
    check(validate_kg(kg18, TRAIN_CUTOFF), f"KG de treino ({TRAIN_CUTOFF})")
    # rótulos de treino só de (2018, 2021]; teste só depois de 2021
    assert Pin.cutoff == TRAIN_CUTOFF and P.cutoff == test_cut, (Pin.cutoff, P.cutoff)
    assert pd.to_datetime(Pin.test["publication_date"]).dt.year.max() <= test_cut, "rótulo de treino após o corte de teste"
    assert pd.to_datetime(P.test["publication_date"]).dt.year.min() > test_cut, "teste antes do corte"
    idx18 = KGIndex(kg18, cap, TRAIN_CUTOFF, texts=texts_for(works_raw, kg18["wrote"]["work_id"]), verbose=False)
    del corpus, works_raw
    gc.collect()
    train_cache: dict[int, pd.DataFrame] = {}
    rows, summary = [], []
    for mode, qs, ls in runs:
        t = time.time()
        if qs not in train_cache:
            train_cache.clear()
            q = sample_queries(Pin.targets, seeds, int(t1["max_consultas"]), qs)
            train_cache[qs], _ = build_pairs(idx18, kg18, q, Pin.train_graph, Pin.gt, gens=GENERATORS,
                                             batch=args.batch, verbose=False)
        train = train_cache[qs]
        rec = {"modo": mode, "semente_consultas": qs, "semente_lightgbm": ls,
               "positivos_treino": int(train["rotulo"].sum())}
        per = {}
        for name, groups in MODELS.items():
            cols = feature_columns(groups, GENERATORS)
            s, _, sh = train_apply(train, test, cols, ls, lgbm_params(ls), want_shap=(name == "LTR completo"))
            per[name] = {"estrita": evaluate(test, s.to_numpy(), P.gt, P.targets),
                         "padrao": evaluate(test, s.to_numpy(), P.gt_t0, tgt_t0)}
            if sh is not None:
                g = sh.groupby(group_of).sum()
                rec.update({f"shap_{k}": float(v) for k, v in (g / g.sum()).items()})
            for av, d in per[name].items():
                for m in METRICS:
                    rec[f"{name}|{av}|{m}"] = float(d[m].mean())
                rows.append(d.assign(base=args.base, modelo=name, avaliacao=av, modo=mode,
                                     semente_consultas=qs, semente_lightgbm=ls))
        for av in ("estrita", "padrao"):
            a = per["LTR completo"][av]["R@50"].to_numpy()
            for other, d in (("só coautoria", per["LTR só coautoria"][av]), ("União RRF", rrf[av])):
                r = paired_test(a, d["R@50"].to_numpy())
                rec[f"C|{av}|completo vs {other}|delta"] = float(r["mean_diff"])
                rec[f"C|{av}|completo vs {other}|p"] = float(r["p_value"])
            lo, hi = bootstrap_ci(a, int(t1["bootstrap"]))
            rec[f"IC95|{av}|R@50"] = [lo, hi]
        summary.append(rec)
        print(f"[{args.base}] {mode:10s} consultas={qs:<3d} lightgbm={ls:<3d} "
              f"R@50 {rec['LTR completo|estrita|R@50'] * 100:5.2f}  NDCG@10 {rec['LTR completo|estrita|NDCG@10'] * 100:5.2f}  "
              f"Δ vs só coautoria {rec['C|estrita|completo vs só coautoria|delta'] * 100:+.2f} "
              f"(p={rec['C|estrita|completo vs só coautoria|p']:.1e})  ({time.time() - t:.0f} s)", flush=True)

    # ---- fidelidade: a referência (42, 42) deve reproduzir o histórico
    hist_f = resolve(f"runs/ltr_temporal/{args.base}.json")
    fidelity = None
    if hist_f.exists():
        h = json.loads(hist_f.read_text())["ordenacao"]["LTR completo"]
        r0 = summary[0]
        fidelity = {m: {"historico": h[m], "reproduzido": round(r0[f"LTR completo|estrita|{m}"], 4)}
                    for m in ("R@10", "R@50", "NDCG@10")}
        fidelity["reproduz"] = all(abs(v["historico"] - v["reproduzido"]) < 1e-3 for v in fidelity.values()
                                   if isinstance(v, dict))
        print(f"[{args.base}] fidelidade ao histórico: {fidelity}", flush=True)

    # ---- agregação por modo (sem a referência): média, dp, CV e estabilidade das conclusões
    df = pd.DataFrame(summary)
    agg = {}
    alpha = 0.05
    for mode, d in df[df["modo"] != "referencia"].groupby("modo"):
        a = {}
        for c in [c for c in df.columns if c.startswith("LTR ")]:
            mu, sd = float(d[c].mean()), float(d[c].std(ddof=1)) if len(d) > 1 else 0.0
            a[c] = {"media": round(mu, 4), "dp": round(sd, 4), "cv": round(sd / mu, 4) if mu else None}
        for av in ("estrita", "padrao"):
            for other in ("só coautoria", "União RRF"):
                dl, pv = d[f"C|{av}|completo vs {other}|delta"], d[f"C|{av}|completo vs {other}|p"]
                a[f"{av}: completo > {other}"] = {"positivo": int((dl > 0).sum()), "significativo": int(((dl > 0) & (pv < alpha)).sum()),
                                                  "n": int(len(d))}
        agg[mode] = a
    out = resolve(f"{rob['saida']}/t1")
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(rows, ignore_index=True).to_parquet(out / f"{args.base}.parquet", index=False)
    (out / f"{args.base}.json").write_text(json.dumps(
        {"base": args.base, "rodadas": summary, "agregado": agg, "fidelidade": fidelity,
         "nota": "p-valores sem correção; a correção de Bonferroni entra na consolidação (Fase 4)",
         "tempo_s": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1, default=float))
    print(f"[{args.base}] concluído em {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
