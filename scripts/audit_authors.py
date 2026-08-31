"""Higienização / auditoria de veracidade dos dados de autor (fase pós-limpeza).

Verifica a qualidade da identidade dos autores no corpus ANTES da modelagem:

  1. Cobertura de ORCID           — % de autores com ORCID (identidade verificável)
  2. Homônimos                    — nomes normalizados compartilhados por >1 author_id
  3. Fragmentação (candidatos a merge) — mesmo nome + coautor OU instituição em comum
                                    em IDs diferentes (possível pessoa dividida)
  4. Divergência de nome          — raw_author_name (como está no artigo) muito
                                    diferente do display_name canônico do OpenAlex
  5. Afiliações inconsistentes    — autor com muitas instituições distintas no mesmo ano
  6. Produtividade implausível    — autor com works/ano acima do plausível (possível
                                    identidade fundida pelo OpenAlex)
  7. Amostra para verificação manual — CSV com N autores aleatórios + URLs
                                    (OpenAlex/ORCID) para conferência humana/BRCris

Nada é corrigido automaticamente: o resultado é um RELATÓRIO (runs/<base>/audit.json,
runs/<base>/audit_sample.csv) e um veredito de gate de identidade, com limiares
configuráveis abaixo. Campos de veracidade (author_orcid, raw_author_name, countries)
existem em coletas feitas após a extensão do coletor; em CSVs antigos os checks que
dependem deles são reportados como "indisponível" em vez de falhar.

Uso: PYTHONHASHSEED=0 python scripts/audit_authors.py --raw-dir data/raw_ai --base ia
"""
from __future__ import annotations

import argparse, json, os, sys, unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from coauthor_rec.config import load_config
from coauthor_rec.data.clean import clean_and_merge

# ---- limiares do gate de identidade (recalibráveis) ----
THRESH = {
    "min_orcid_author_coverage": 0.25,   # % mínima de autores com ORCID
    "max_homonym_author_rate": 0.05,     # % máxima de autores envolvidos em homonímia
    "max_merge_candidate_rate": 0.02,    # % máxima de autores em pares candidatos a merge
    "max_implausible_rate": 0.005,       # % máxima de autores com produtividade implausível
    "works_per_year_implausible": 30,    # works/ano no corpus acima disso = implausível
    "max_institutions_same_year": 3,     # instituições distintas no mesmo ano acima disso = flag
    "sample_size": 200,                  # amostra p/ verificação manual
}


def normalize_name(name: str) -> str:
    """casefold + remove acentos + colapsa espaços (não colapsa iniciais)."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().replace(".", " ").split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw_ai")
    ap.add_argument("--base", default=None, help="rótulo da base (p/ runs/<base>/)")
    args = ap.parse_args()
    root = os.path.join(os.path.dirname(__file__), "..")
    base = args.base or os.path.basename(args.raw_dir.rstrip("/"))
    out_dir = os.path.join(root, "runs", base)
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(42)

    EVAL = load_config("eval")
    auth = pd.read_csv(os.path.join(root, args.raw_dir, "authorships.csv"))
    works = pd.read_csv(os.path.join(root, args.raw_dir, "works.csv"))
    m = clean_and_merge(auth, works, min_year=EVAL["split"]["min_year"],
                        language=EVAL["split"]["language"])
    m["year"] = pd.to_datetime(m["publication_date"]).dt.year
    n_authors = m["author_id"].nunique()
    print(f"[audit:{base}] corpus limpo: {m.work_id.nunique()} works / {n_authors} autores")

    report: dict = {"base": base, "raw_dir": args.raw_dir, "thresholds": THRESH,
                    "works": int(m.work_id.nunique()), "authors": int(n_authors), "checks": {}}
    has = lambda c: c in m.columns and m[c].notna().any()

    # ---- 1. ORCID ----
    if has("author_orcid"):
        per_author = m.groupby("author_id")["author_orcid"].apply(lambda s: s.notna().any())
        cov = float(per_author.mean())
        report["checks"]["orcid_coverage"] = {
            "value": round(cov, 4), "min": THRESH["min_orcid_author_coverage"],
            "passed": cov >= THRESH["min_orcid_author_coverage"]}
    else:
        report["checks"]["orcid_coverage"] = {"value": None, "passed": None,
            "note": "coluna author_orcid ausente — re-coletar com o coletor estendido"}

    # ---- 2. homônimos ----
    name_of = m.drop_duplicates("author_id").set_index("author_id")["author_name"]
    norm = name_of.map(normalize_name)
    by_name = defaultdict(list)
    for aid, nm in norm.items():
        if nm:
            by_name[nm].append(aid)
    homonym_groups = {nm: ids for nm, ids in by_name.items() if len(ids) > 1}
    homonym_authors = sum(len(v) for v in homonym_groups.values())
    rate = homonym_authors / n_authors
    report["checks"]["homonyms"] = {
        "groups": len(homonym_groups), "authors_involved": homonym_authors,
        "rate": round(rate, 4), "max": THRESH["max_homonym_author_rate"],
        "passed": rate <= THRESH["max_homonym_author_rate"],
        "examples": [{"name": nm, "ids": ids[:5]}
                     for nm, ids in sorted(homonym_groups.items(),
                                           key=lambda kv: -len(kv[1]))[:10]]}

    # ---- 3. fragmentação: mesmo nome + vizinhança/instituição em comum ----
    coa = defaultdict(set)
    for _, grp in m.groupby("work_id"):
        aids = grp["author_id"].tolist()
        if 1 < len(aids) <= 50:
            for a in aids:
                coa[a].update(x for x in aids if x != a)
    inst_of = defaultdict(set)
    if has("institution_ids"):
        for aid, blob in zip(m["author_id"], m["institution_ids"].fillna("[]")):
            try:
                inst_of[aid].update(json.loads(blob))
            except Exception:
                pass
    merge_cands = []
    for nm, ids in homonym_groups.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                shared_co = coa[a] & coa[b]
                shared_inst = inst_of[a] & inst_of[b]
                if shared_co or shared_inst:
                    merge_cands.append({"name": nm, "id_a": a, "id_b": b,
                                        "shared_coauthors": len(shared_co),
                                        "shared_institutions": len(shared_inst)})
    mc_authors = len({x for c in merge_cands for x in (c["id_a"], c["id_b"])})
    mc_rate = mc_authors / n_authors
    report["checks"]["merge_candidates"] = {
        "pairs": len(merge_cands), "authors_involved": mc_authors,
        "rate": round(mc_rate, 4), "max": THRESH["max_merge_candidate_rate"],
        "passed": mc_rate <= THRESH["max_merge_candidate_rate"],
        "examples": merge_cands[:15]}

    # ---- 4. divergência raw_author_name × display_name ----
    if has("raw_author_name"):
        sub = m.dropna(subset=["raw_author_name"])
        div = (sub["raw_author_name"].map(normalize_name)
               != sub["author_name"].map(normalize_name)).mean()
        report["checks"]["name_divergence"] = {"authorship_rate": round(float(div), 4),
            "note": "divergência esperada p/ iniciais/ordem; útil como indicador relativo entre bases"}
    else:
        report["checks"]["name_divergence"] = {"value": None,
            "note": "raw_author_name ausente — re-coletar com o coletor estendido"}

    # ---- 5. afiliações inconsistentes no mesmo ano ----
    if has("institution_ids"):
        rows = []
        for (aid, yr), blobs in m.groupby(["author_id", "year"])["institution_ids"]:
            insts = set()
            for b in blobs.fillna("[]"):
                try:
                    insts.update(json.loads(b))
                except Exception:
                    pass
            if len(insts) > THRESH["max_institutions_same_year"]:
                rows.append({"author_id": aid, "year": int(yr), "institutions": len(insts)})
        flagged = len({r["author_id"] for r in rows})
        report["checks"]["multi_affiliation_same_year"] = {
            "authors_flagged": flagged, "rate": round(flagged / n_authors, 4),
            "examples": rows[:10],
            "note": "multiafiliação real existe; acima do limiar é indício de identidade fundida"}

    # ---- 6. produtividade implausível ----
    wpy = m.drop_duplicates(["author_id", "work_id"]).groupby(["author_id", "year"]).size()
    impl = wpy[wpy > THRESH["works_per_year_implausible"]]
    impl_authors = impl.index.get_level_values(0).nunique()
    impl_rate = impl_authors / n_authors
    report["checks"]["implausible_productivity"] = {
        "authors": int(impl_authors), "rate": round(impl_rate, 4),
        "max": THRESH["max_implausible_rate"],
        "passed": impl_rate <= THRESH["max_implausible_rate"],
        "top": [{"author_id": a, "year": int(y), "works": int(n)}
                for (a, y), n in impl.sort_values(ascending=False).head(10).items()]}

    # ---- 7. amostra para verificação manual (ORCID/BRCris/Lattes) ----
    uniq = m.drop_duplicates("author_id")[
        [c for c in ["author_id", "author_name", "author_orcid"] if c in m.columns]]
    sample = uniq.iloc[rng.choice(len(uniq), size=min(THRESH["sample_size"], len(uniq)),
                                  replace=False)].copy()
    sample["openalex_url"] = "https://openalex.org/" + sample["author_id"]
    if "author_orcid" in sample.columns:
        sample["orcid_url"] = sample["author_orcid"].map(
            lambda o: f"https://orcid.org/{o}" if isinstance(o, str) else "")
    sample["n_works_no_corpus"] = sample["author_id"].map(
        m.drop_duplicates(["author_id", "work_id"]).groupby("author_id").size())
    sample["verificado_ok"] = ""   # preencher manualmente (S/N/observação)
    sample_path = os.path.join(out_dir, "audit_sample.csv")
    sample.to_csv(sample_path, index=False)

    # ---- veredito ----
    applicable = [c["passed"] for c in report["checks"].values()
                  if isinstance(c, dict) and c.get("passed") is not None]
    report["passed"] = all(applicable) if applicable else None
    report["n_checks_applicable"] = len(applicable)
    json.dump(report, open(os.path.join(out_dir, "audit.json"), "w"),
              indent=1, ensure_ascii=False)

    print(f"\n[audit:{base}] veredito: "
          f"{'APROVADO' if report['passed'] else 'REPROVADO' if report['passed'] is False else 'INCOMPLETO'}"
          f" ({len(applicable)} checks aplicáveis)")
    for name, c in report["checks"].items():
        if isinstance(c, dict):
            status = {True: "ok", False: "FALHOU", None: "n/d"}[c.get("passed")]
            val = c.get("value", c.get("rate", c.get("authorship_rate", "")))
            print(f"  {name:28s} {status:7s} {val}")
    print(f"\n[audit:{base}] relatório: runs/{base}/audit.json · amostra manual: runs/{base}/audit_sample.csv")


if __name__ == "__main__":
    main()
