"""CLI do projeto.

Subcomandos:
  collect       — coleta snowball do OpenAlex (configs/collect.yaml)
  clean         — integra e limpa authorships+works -> data/processed/corpus.parquet
  gate          — aplica o gate de qualidade (configs/corpus_gate.yaml)
  run-baselines — treina e avalia baseline/oráculo/RF e grava relatório em runs/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .config import load_config, resolve, set_seed


def _load_corpus(processed_path: Path) -> pd.DataFrame:
    if processed_path.suffix == ".parquet":
        return pd.read_parquet(processed_path)
    return pd.read_csv(processed_path)


def cmd_collect(args) -> None:
    from .collect.openalex import collect
    cfg = load_config(args.config)
    if args.mode:  # override do modo definido no YAML
        cfg["mode"] = args.mode
    out = resolve(cfg["paths"]["raw_dir"])
    collect(cfg, out)


def cmd_clean(args) -> None:
    from .data.clean import clean_and_merge, corpus_summary
    raw = resolve(args.raw_dir)
    authorships = pd.read_csv(raw / "authorships.csv")
    works = pd.read_csv(raw / "works.csv")
    eval_cfg = load_config("eval")["split"]
    merged = clean_and_merge(authorships, works,
                             min_year=eval_cfg["min_year"],
                             language=eval_cfg["language"])
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out, index=False)
    print(f"[clean] corpus -> {out}")
    print(json.dumps(corpus_summary(merged), indent=2, ensure_ascii=False))


def cmd_gate(args) -> None:
    from .data.gate import evaluate_gate
    merged = _load_corpus(resolve(args.corpus))
    thresholds = load_config("corpus_gate")
    result = evaluate_gate(merged, thresholds)
    print(json.dumps(result["stats"], indent=2, ensure_ascii=False))
    print("\nGate de qualidade:")
    for name, (value, threshold, ok) in result["checks"].items():
        print(f"  [{'OK ' if ok else 'X  '}] {name}: {value} (mín. {threshold})")
    print(f"\n==> {'APROVADO' if result['passed'] else 'REPROVADO'}")
    if not result["passed"]:
        raise SystemExit(1)


def cmd_build_graph(args) -> None:
    import torch
    from .split.temporal import chronological_split
    from .graph.hetero import build_hetero_data

    eval_cfg = load_config("eval")
    merged = _load_corpus(resolve(args.corpus))
    works_raw = pd.read_csv(resolve(args.works_raw))

    if args.split == "train":  # grafo só com T0 (padrão p/ predição de links futuros)
        train_df, _ = chronological_split(merged, train_fraction=eval_cfg["split"]["train_fraction"])
        work_ids = set(train_df["work_id"])
    else:  # grafo com todo o corpus
        work_ids = None

    data, maps = build_hetero_data(merged, works_raw, work_ids=work_ids)
    print(data)
    print("\nNós:", {k: len(v) for k, v in maps.items()})
    print("Arestas:", {"->".join(et): data[et].edge_index.size(1) for et in data.edge_types})

    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"data": data, "maps": maps}, out)
    print(f"\n[build-graph] KG ({args.split}) -> {out}")


def cmd_run_baselines(args) -> None:
    from .split.temporal import chronological_split, build_ground_truth
    from .models.baseline import TopologyRecommender
    from .models.oracle import IdealTopologyRecommender
    from .models.hybrid_rf import HybridCoauthorRecommender
    from .eval.evaluate import evaluate_models
    from .report import format_full_report

    eval_cfg = load_config("eval")
    set_seed(eval_cfg["seed"])
    merged = _load_corpus(resolve(args.corpus))

    train_df, test_df = chronological_split(
        merged, train_fraction=eval_cfg["split"]["train_fraction"]
    )
    train_graph, ground_truth = build_ground_truth(train_df, test_df)
    print(f"[split] treino={train_df['work_id'].nunique()} works, "
          f"teste={test_df['work_id'].nunique()} works, "
          f"autores-alvo={len(ground_truth)}")

    baseline = TopologyRecommender().fit(train_df)
    oracle = IdealTopologyRecommender(baseline, ground_truth).fit(train_df)
    hybrid = HybridCoauthorRecommender().fit(train_df)

    regimes = eval_cfg["regimes"]
    results = evaluate_models(
        [baseline, oracle, hybrid], ground_truth, train_graph,
        k_values=eval_cfg["evaluation"]["k_values"],
        warm_min=regimes["warm_min_coauthors"],
        cool_min=regimes["cool_min_coauthors"],
    )

    report = format_full_report(results)
    print("\n" + report)
    run_dir = resolve(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.txt").write_text(report, encoding="utf-8")
    serializable = {m: {"overall": r["overall"], "by_regime": r["by_regime"],
                        "regime_counts": r["regime_counts"]}
                    for m, r in results.items()}
    (run_dir / "results.json").write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[run-baselines] resultados -> {run_dir}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="coauthor-rec")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("collect", help="coleta do OpenAlex (snowball | thematic | hybrid)")
    p.add_argument("--config", default="collect")
    p.add_argument("--mode", choices=["snowball", "thematic", "hybrid"], default=None,
                   help="sobrepõe o modo definido no YAML")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("clean", help="integra e limpa o corpus")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--out", default="data/processed/corpus.parquet")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("gate", help="aplica o gate de qualidade")
    p.add_argument("--corpus", default="data/processed/corpus.parquet")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("build-graph", help="materializa o KG heterogêneo (HeteroData)")
    p.add_argument("--corpus", default="data/processed/corpus.parquet")
    p.add_argument("--works-raw", default="data/raw/works.csv")
    p.add_argument("--split", choices=["train", "all"], default="train",
                   help="train = só T0 (predição de links futuros); all = corpus inteiro")
    p.add_argument("--out", default="data/processed/hetero_T0.pt")
    p.set_defaults(func=cmd_build_graph)

    p = sub.add_parser("run-baselines", help="treina e avalia os baselines")
    p.add_argument("--corpus", default="data/processed/corpus.parquet")
    p.add_argument("--out", default="runs/baselines")
    p.set_defaults(func=cmd_run_baselines)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
