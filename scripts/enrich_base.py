"""Enriquecimento de uma base — camadas 1–3 + ontologia (docs/ENRIQUECIMENTO.md).

Etapas:
  1. Semântica temática  — Topics de cada trabalho (hierarquia + score), perfil do autor
  2. Instituições        — ROR, tipo, país, hierarquia, Wikidata; vínculo autor×inst×ano
  3. Trajetórias         — vínculos e formação do ORCID (cache), ex-colegas sem vazamento
  4. Diagnóstico de sinal — para pares que viraram coautoria em T1 vs pares aleatórios:
                            frequência de cada relação nova (lift), só com informação de T0
  5. Ontologia           — amostra do KG em RDF/Turtle, validada contra a TBox + SPARQL

Entradas: corpus higienizado (data/processed/corpus_<base>.parquet) ou, com
``--provisional``, o corpus apenas limpo (para validar o pipeline antes da higienização).
A busca no OpenAlex usa TODOS os trabalhos/instituições do bruto (superconjunto) e fica em
cache — não precisa ser refeita após a higienização.

Saídas: data/processed/enrich_<base>/*.parquet, kg_sample.ttl; runs/<base>/enrich.json.
Uso:  PYTHONHASHSEED=0 python scripts/enrich_base.py economia [--provisional]
"""
from __future__ import annotations

import argparse, json, os, sys, time

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.enrich import careers as CA  # noqa: E402
from coauthor_rec.enrich import institutions as IN  # noqa: E402
from coauthor_rec.enrich import topics as TO  # noqa: E402
from coauthor_rec.enrich.openalex_cache import fetch_by_ids  # noqa: E402
from coauthor_rec.split.temporal import build_ground_truth, chronological_split  # noqa: E402


def _jl(v):
    try:
        out = json.loads(v) if isinstance(v, str) and v else []
        return out if isinstance(out, list) else []
    except ValueError:
        return []


def load_corpus(base: str, prof: dict, provisional: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(corpus usado nos produtos, autorias brutas, works brutos)."""
    raw = resolve(prof["raw_dir"])
    auth = pd.read_csv(raw / "authorships.csv")
    works = pd.read_csv(raw / "works.csv")
    hyg = resolve(prof["corpus"])
    if hyg.exists() and resolve(f"runs/{base}/hygiene.json").exists():
        return pd.read_parquet(hyg), auth, works
    if not provisional:
        raise SystemExit(f"corpus higienizado de {base} ausente — rode a higienização ou use --provisional")
    ev = load_config("eval")
    return clean_and_merge(auth, works, ev["split"]["min_year"], ev["split"]["language"]), auth, works


def targets_for(base: str, prof: dict, corpus: pd.DataFrame) -> list[str]:
    """Alvos de avaliação: sementes ∩ elegíveis (higienizado) ou sementes (provisório)."""
    autores = resolve(f"data/processed/autores_{base}.csv")
    if autores.exists() and "author_id_openalex" in corpus.columns:
        t = pd.read_csv(autores, index_col=0)
        return sorted(t.index[t["alvo"]].tolist())
    seeds = pd.read_csv(resolve(prof["raw_dir"]) / "seeds.csv")
    return sorted(set(seeds["author_id"]) & set(corpus["author_id"]))


def signal_diagnostic(corpus, wt, inst, aiy, aff, targets, cap, train_fraction, seed=42) -> dict:
    """Lift de cada relação: P(relação | par que vira coautoria em T1) / P(relação | par aleatório).
    Todas as relações calculadas só com informação até o fim de T0 (sem vazamento)."""
    tr, te = chronological_split(corpus, train_fraction=train_fraction)
    tg, gt = build_ground_truth(tr, te, max_coauthors_per_work=cap)
    cutoff = int(pd.to_datetime(tr["publication_date"]).dt.year.max())
    t0_people = sorted(set(tr["author_id"]))
    rng = np.random.default_rng(seed)

    # perfis e vínculos de T0
    prof = TO.author_profile(tr, wt, "subfield")
    sub = {a: dict(zip(g["unit"], g["weight"])) for a, g in prof.groupby("author_id")}
    top = {a: max(d, key=d.get) for a, d in sub.items()}
    aiy0 = aiy[aiy["work_id"].isin(set(tr["work_id"]))]
    inst_of = aiy0.groupby("author_id")["institution_id"].agg(set).to_dict()
    it = inst.set_index("institution_id")
    root = {i: (it.loc[i, "parents"][-1] if it.loc[i, "parents"] else i) for i in it.index}
    ctry = {i: it.loc[i, "country"] for i in it.index}
    roots_of = {a: {root.get(i, i) for i in s} for a, s in inst_of.items()}
    ctry_of = {a: {ctry[i] for i in s if isinstance(ctry.get(i), str)} for a, s in inst_of.items()}
    colleagues = CA.ExColleagueIndex(aff) if len(aff) else None
    has_career = set(aff.loc[(aff["kind"] == "employment") & aff["start"].notna(), "author_id"])

    def cos(a, b):
        da, db = sub.get(a), sub.get(b)
        if not da or not db:
            return None
        num = sum(w * db.get(k, 0) for k, w in da.items())
        return num / (np.sqrt(sum(w * w for w in da.values())) * np.sqrt(sum(w * w for w in db.values())))

    feats = {"mesmo_subcampo_principal": lambda a, b: (top[a] == top[b]) if a in top and b in top else None,
             "similaridade_subcampos>0,5": lambda a, b: (c > 0.5) if (c := cos(a, b)) is not None else None,
             "mesma_instituicao": lambda a, b: bool(inst_of[a] & inst_of[b]) if a in inst_of and b in inst_of else None,
             "mesma_org_mae": lambda a, b: bool(roots_of[a] & roots_of[b]) if a in roots_of and b in roots_of else None,
             "mesmo_pais": lambda a, b: bool(ctry_of[a] & ctry_of[b]) if ctry_of.get(a) and ctry_of.get(b) else None,
             "ex_colegas_orcid": (lambda a, b: bool(colleagues.shared(a, b, cutoff))
                                  if colleagues and a in has_career and b in has_career else None)}
    pos, neg = [], []
    tset = [t for t in targets if t in gt]
    for a in tset:
        for b in gt[a]:
            pos.append((a, b))
        excl = tg.get(a, set()) | gt[a] | {a}
        need = len(gt[a])
        while need:
            b = t0_people[rng.integers(len(t0_people))]
            if b not in excl:
                neg.append((a, b)); need -= 1
    out = {"alvos_com_coautoria_nova": len(tset), "pares_positivos": len(pos),
           "pares_aleatorios": len(neg), "ano_corte_T0": cutoff, "relacoes": {}}
    for name, f in feats.items():
        vp = [v for v in (f(a, b) for a, b in pos) if v is not None]
        vn = [v for v in (f(a, b) for a, b in neg) if v is not None]
        pp, pn = (np.mean(vp) if vp else float("nan")), (np.mean(vn) if vn else float("nan"))
        out["relacoes"][name] = {"P_coautoria_nova": round(float(pp), 4), "P_aleatorio": round(float(pn), 4),
                                 "lift": round(float(pp / pn), 2) if pn and pn > 0 else None,
                                 "cobertura_pares": round(len(vp) / max(len(pos), 1), 4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--provisional", action="store_true",
                    help="usa o corpus apenas limpo se o higienizado ainda não existir")
    ap.add_argument("--skip-ontology", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    cfg = yaml.safe_load(open(os.path.join(ROOT, "configs", "enrich.yaml")))
    prof = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))["bases"][args.base]
    oa, filt, ev = cfg["openalex"], load_filters(), load_config("eval")
    out = resolve(f"data/processed/enrich_{args.base}")
    out.mkdir(parents=True, exist_ok=True)
    corpus, auth, works = load_corpus(args.base, prof, args.provisional)
    provisional = "author_id_openalex" not in corpus.columns
    rep = {"base": args.base, "provisorio": provisional, "corpus_trabalhos": int(corpus["work_id"].nunique()),
           "corpus_pessoas": int(corpus["author_id"].nunique())}
    print(f"[enrich:{args.base}] corpus {'PROVISÓRIO (não higienizado)' if provisional else 'higienizado'}: "
          f"{rep['corpus_trabalhos']} trabalhos / {rep['corpus_pessoas']} pessoas", flush=True)

    # ---- 1. semântica temática
    recs = fetch_by_ids("works", works["id"], cfg["topics"]["select"], resolve(oa["cache_dir"]), oa["mailto"],
                        oa["batch_size"], oa["requests_per_second"], oa["workers"])
    wt = TO.work_topics(recs)
    wt = wt[wt["work_id"].isin(set(corpus["work_id"]))].reset_index(drop=True)
    TO.taxonomy(wt).to_parquet(out / "taxonomy.parquet", index=False)
    wt.to_parquet(out / "work_topics.parquet", index=False)
    kw = TO.work_keywords(recs)
    kw[kw["work_id"].isin(set(corpus["work_id"]))].to_parquet(out / "work_keywords.parquet", index=False)
    TO.author_profile(corpus, wt, "subfield").to_parquet(out / "author_subfields.parquet", index=False)
    rep["camada1_topicos"] = TO.coverage(wt, corpus["work_id"].nunique(), prof.get("fields"))
    print(f"[enrich] camada 1: {rep['camada1_topicos']}", flush=True)

    # ---- 2. instituições
    aiy = IN.author_institution_years(corpus)
    raw_inst = {i for v in auth["institution_ids"] for i in _jl(v) if i}
    irecs = fetch_by_ids("institutions", raw_inst, cfg["institutions"]["select"], resolve(oa["cache_dir"]),
                         oa["mailto"], oa["batch_size"], oa["requests_per_second"], oa["workers"])
    inst = IN.institutions_table(irecs)
    # ancestrais fora do corpus também entram (para fechar a hierarquia)
    missing_par = {p for ps in inst["parents"] for p in ps} - set(inst["institution_id"])
    if missing_par:
        irecs.update(fetch_by_ids("institutions", missing_par, cfg["institutions"]["select"],
                                  resolve(oa["cache_dir"]), oa["mailto"], oa["batch_size"],
                                  oa["requests_per_second"], oa["workers"]))
        inst = IN.institutions_table(irecs)
    inst.to_parquet(out / "institutions.parquet", index=False)
    IN.lineage_edges(inst).to_parquet(out / "institution_lineage.parquet", index=False)
    IN.associated_edges(irecs).to_parquet(out / "institution_associated.parquet", index=False)
    aiy.to_parquet(out / "author_institution_years.parquet", index=False)
    rep["camada2_instituicoes"] = IN.coverage(inst, aiy, len(corpus))
    print(f"[enrich] camada 2: { {k: v for k, v in rep['camada2_instituicoes'].items() if k != 'tipos'} }", flush=True)

    # ---- 3. trajetórias (ORCID)
    cc = cfg["careers"]
    if provisional:   # corpus sem pessoa canônica: usa o ORCID declarado na autoria
        persons = {f"orcid:{o}" for o in corpus["author_orcid"].dropna().unique()}
        canon = corpus.dropna(subset=["author_orcid"]).assign(cid="orcid:" + corpus["author_orcid"].dropna())
        id_map = dict(zip(canon["cid"], canon["author_id"]))
    else:
        persons = {p for p in corpus["author_id"] if isinstance(p, str) and p.startswith("orcid:")}
        id_map = {p: p for p in persons}
    aff = CA.career_affiliations(sorted(persons), resolve(cc["orcid_cache_dir"]),
                                 cc["employment_sections"], cc["education_sections"])
    aff["author_id"] = aff["author_id"].map(id_map).fillna(aff["author_id"])   # alinha ao corpus
    aff.to_parquet(out / "author_affiliations_orcid.parquet", index=False)
    CA.career_summary(aff).to_parquet(out / "author_careers.parquet")
    cached = sum((resolve(cc["orcid_cache_dir"]) / f"{p[6:]}.json").exists() for p in persons)
    rep["camada3_trajetorias"] = {**CA.coverage(aff, len(persons)),
                                  "orcids_no_cache": round(cached / max(len(persons), 1), 4)}
    print(f"[enrich] camada 3: {rep['camada3_trajetorias']}", flush=True)

    # ---- 4. diagnóstico de sinal (só informação de T0)
    targets = targets_for(args.base, prof, corpus)
    rep["diagnostico_sinal"] = signal_diagnostic(corpus, wt, inst, aiy, aff, targets,
                                                 filt.get("max_coauthors_per_work"),
                                                 ev["split"]["train_fraction"], ev["seed"])
    print(f"[enrich] diagnóstico de sinal (lift = P(relação|coautoria nova)/P(relação|aleatório)):", flush=True)
    for k, v in rep["diagnostico_sinal"]["relacoes"].items():
        print(f"    {k:28s} {v}", flush=True)

    # ---- 5. ontologia: amostra RDF validada
    if not args.skip_ontology:
        from rdflib import Graph
        from coauthor_rec.graph import ontology as ON
        oc = cfg["ontology"]
        rng = np.random.default_rng(oc["sample_seed"])
        samp = sorted(rng.choice(targets, min(oc["sample_targets"], len(targets)), replace=False).tolist())
        cutoff = rep["diagnostico_sinal"]["ano_corte_T0"]
        g = ON.build_sample_graph(corpus, samp, wt, inst, aff, CA.ExColleagueIndex(aff), cutoff,
                                  filt.get("max_coauthors_per_work") or 50)
        g.serialize(out / "kg_sample.ttl", format="turtle")
        rep["ontologia"] = {"amostra_alvos": len(samp),
                            **ON.validate(g, Graph().parse(resolve(oc["tbox"]))),
                            "consultas": ON.run_queries(g, focus=samp)}
        print(f"[enrich] ontologia: {rep['ontologia']['triplas']} triplas, não declaradas: "
              f"{rep['ontologia']['nao_declaradas']}", flush=True)

    rep["segundos"] = round(time.time() - t0)
    resolve(f"runs/{args.base}").mkdir(parents=True, exist_ok=True)
    resolve(f"runs/{args.base}/enrich.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    print(f"[enrich:{args.base}] concluído em {rep['segundos']} s -> {out} · runs/{args.base}/enrich.json")


if __name__ == "__main__":
    main()
