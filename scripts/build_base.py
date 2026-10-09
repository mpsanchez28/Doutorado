"""Constrói uma base temática de configs/bases.yaml de ponta a ponta. Gradiente da H3
(nível de campo): medicina | computacao | matematica | economia; legado: ia.

  1. VERIFICA os Concept IDs contra a API do OpenAlex (aborta se o display_name
     não bater com o esperado em configs/bases.yaml — evita coletar a área errada)
  2. COLETA (modo thematic; parada por AUTORES distintos — mesmo target_authors
     para as 3 bases, igualando o catálogo de recomendáveis; works variam por área) -> <raw_dir>/
  3. LIMPA + HIGIENIZA (filters.yaml; scripts/hygiene.py: ORCID, pessoa canônica,
     níveis A/B/C/X, vínculo institucional, elegibilidade E1–E8) -> corpus_<base>.parquet
  4. GATE de qualidade de rede (configs/corpus_gate.yaml) sobre o corpus higienizado
  5. AUDITORIA de veracidade dos autores (scripts/audit_authors.py — diagnóstico do bruto)

A base "ia" já coletada é reaproveitada (pula a coleta se raw_dir tiver os CSVs),
mas ATENÇÃO: os campos de veracidade (ORCID etc.) só existem em coletas feitas com
o coletor estendido — use --recollect para re-coletar a IA com os campos novos.

Uso (no Mac, com pyalex instalado e rede):
    PYTHONHASHSEED=0 python scripts/build_base.py medicina
    PYTHONHASHSEED=0 python scripts/build_base.py computacao
    PYTHONHASHSEED=0 python scripts/build_base.py all        # as 4 do gradiente
    PYTHONHASHSEED=0 python scripts/build_base.py ia --recollect   # legado
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys

import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import load_config, resolve  # noqa: E402
from coauthor_rec.collect.openalex import thematic_collect  # noqa: E402
from coauthor_rec.data.gate import evaluate_gate  # noqa: E402


def verify_concepts(concept_ids: list[str], expected: dict, mailto: str) -> None:
    """Confere cada Concept ID na API (polite pool). Aborta se o nome não bater."""
    import pyalex
    from pyalex import Concepts
    pyalex.config.email = mailto
    print("[verify] conferindo Concept IDs na API do OpenAlex…")
    for cid in concept_ids:
        c = Concepts()[cid]
        name = c.get("display_name")
        exp = expected.get(cid)
        marker = "ok" if (exp and name and name.lower() == exp.lower()) else "MISMATCH"
        print(f"  {cid}: '{name}' (esperado: '{exp}', nível {c.get('level')}, "
              f"{c.get('works_count'):,} works) [{marker}]")
        if marker == "MISMATCH":
            raise SystemExit(f"ABORTADO: {cid} devolveu '{name}', esperado '{exp}'. "
                             f"Corrija configs/bases.yaml antes de coletar.")


def build(base_key: str, recollect: bool, offline: bool = False) -> None:
    profiles = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    prof = profiles["bases"][base_key]
    collect_cfg = load_config("collect")
    eval_cfg = load_config("eval")
    raw_dir = resolve(prof["raw_dir"])
    print(f"\n===== BASE {base_key} — {prof['label']} =====")

    # ---- 1+2. verificação + coleta ----
    have_raw = (raw_dir / "authorships.csv").exists() and (raw_dir / "works.csv").exists()
    if have_raw and not recollect:
        print(f"[collect] {prof['raw_dir']} já existe — pulando coleta (use --recollect "
              f"para refazer com os campos de veracidade do autor).")
    else:
        verify_concepts(prof["concepts"], prof.get("expected_names", {}),
                        collect_cfg["api"]["mailto"])
        cfg = dict(collect_cfg)
        cfg["mode"] = "thematic"
        cfg["thematic"] = {"concept_ids": prof["concepts"],
                           "target_authors": profiles.get("target_authors"),
                           "target_works": profiles.get("target_works"),
                           "max_works": profiles.get("max_works")}
        stats = thematic_collect(cfg, raw_dir, verbose=True)
        print(f"[collect] {stats}")

    # ---- 3. limpeza + higienização de autores (ORCID, pessoa canônica, E1–E8) ----
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from hygiene import run as run_hygiene  # noqa: E402
    merged, _, _ = run_hygiene(base_key, offline=offline)

    # ---- 4. gate de rede ----
    gate = evaluate_gate(merged, load_config("corpus_gate"))
    print(f"[gate]  {'APROVADO' if gate['passed'] else 'REPROVADO'}")
    for k, (val, thr, ok) in gate["checks"].items():
        print(f"    {k:24s} {val} (mín {thr}) {'ok' if ok else 'FALHOU'}")
    out_dir = resolve(f"runs/{base_key}")
    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(gate, open(out_dir / "gate.json", "w"), indent=1, ensure_ascii=False,
              default=str)

    # ---- 5. auditoria de veracidade dos autores ----
    print("[audit] rodando auditoria de identidade dos autores…")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "audit_authors.py"),
                    "--raw-dir", prof["raw_dir"], "--base", base_key], check=True)


if __name__ == "__main__":
    profiles = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    ap = argparse.ArgumentParser()
    ap.add_argument("base", choices=list(profiles["bases"]) + ["all"],
                    help="'all' = bases do gradiente (gradiente: true), na ordem do YAML")
    ap.add_argument("--recollect", action="store_true",
                    help="re-coleta mesmo se raw_dir já existir")
    ap.add_argument("--offline", action="store_true",
                    help="higienização usa só o cache do ORCID (sem rede)")
    args = ap.parse_args()
    keys = profiles.get("gradiente") or [k for k, p in profiles["bases"].items()
                                         if p.get("gradiente")]
    keys = keys if args.base == "all" else [args.base]
    for k in keys:
        build(k, args.recollect, args.offline)
