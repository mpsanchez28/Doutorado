"""T4 — reconstrução retrospectiva de UM corte, só com dados locais (docs/ROBUSTEZ_T1_T4.md §3.3).

"Retrospectiva pela data dos fatos, com metadados atuais": cada etapa da construção do corpus é
refeita usando apenas fatos datados até o corte c, mas os METADADOS (desambiguação, tópicos,
afiliações, ORCID) são os de hoje (limitações em §3.4). Parâmetros pré-registrados em
configs/robustez.yaml › t4.piloto. Nenhuma chamada a API.

Etapas:
  0. validação: ``select_candidates`` (a mesma função da expansão original) com os parâmetros
     originais reproduz o candidates.csv atual;
  1. sementes: as sorteadas por trabalho publicado ≤ c, primeiras N pela ordem de sorteio;
  2. elegibilidade E1–E8 recalculada com autorias ≤ c (ORCID: retrato atual);
  3. candidatos: ``select_candidates`` com essas sementes, laços ≤ c, teto de candidatos;
  4. lacunas de coleta: para cada candidato, os anos da janela (c−J+1 … c) sem histórico local;
     volume e custo estimados da coleta que falta;
  5. corpus local PARCIAL (sementes + o histórico de candidatos já disponível) → higienização →
     protocolo (corte c, rótulos em (c, c+H]) → KG validado — validação TÉCNICA do pipeline.
     Nenhum modelo é treinado e nenhuma métrica de desempenho é produzida.

Saídas: runs/robustez/t4/reconstrucao_<base>_<c>/ (sementes, elegibilidade, candidatos, lacunas,
relatório.json). Não altera dados existentes.
Uso: PYTHONHASHSEED=0 python scripts/reconstrucao_t4.py economia [--corte 2019] [--n-sementes todas|N]
        [--horizonte 3] [--sem-corpus] [--coletado data/robustez/t4/economia_2019]
  --sem-corpus  só etapas 0–4 (inventário; rápido, útil para o protocolo corrigido de 2021)
  --coletado    integra ao corpus da etapa 5 o histórico coletado pelo coletor do T4
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.collect.openalex import select_candidates  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import CRITERIA, author_table, authorship_levels, canonicalize, hygienize  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, validate_kg  # noqa: E402

PER_PAGE, IDS_PER_CALL = 200, 50


def years_of(df, col="publication_date"):
    return pd.to_datetime(df[col], errors="coerce").dt.year


def main():
    rob = yaml.safe_load(open(resolve("configs/robustez.yaml")))
    pil = rob["t4"]["piloto"]
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=pil["base"])
    ap.add_argument("--corte", type=int, default=int(pil["corte"]))
    ap.add_argument("--n-sementes", default=str(pil["n_sementes"]))
    ap.add_argument("--horizonte", type=int, default=int(pil["horizonte_anos"]))
    ap.add_argument("--sem-corpus", action="store_true")
    ap.add_argument("--coletado", default=None)
    ap.add_argument("--fim-rotulos", default=None,
                    help="data exata (AAAA-MM-DD) de fim dos rótulos; substitui o horizonte em anos")
    ap.add_argument("--modelo", action="store_true",
                    help="etapa 6: treino temporal + avaliação (validação técnica; métricas não interpretadas)")
    args = ap.parse_args()
    base, c, H = args.base, args.corte, args.horizonte
    J = int(pil["janela_candidatos_anos"])
    N = None if str(args.n_sementes).lower() == "todas" else int(args.n_sementes)
    t_start = time.time()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = cfg["bases"][base]
    raw = resolve(prof["raw_dir"])
    filt = load_filters()
    hcfg = filt.get("hygiene", {})
    cap = filt.get("max_coauthors_per_work")
    max_cand = int(cfg.get("max_candidatos", 15000))
    tie_seed = int(cfg["coleta"].get("seed", 42))
    ev = load_config("eval")
    tag = f"ate{args.fim_rotulos}" if args.fim_rotulos else f"h{H}"
    out = resolve(f"{rob['saida']}/t4/reconstrucao_{base}_{c}" + ("" if args.coletado is None else f"_coletado_{tag}"))
    out.mkdir(parents=True, exist_ok=True)
    rep = {"base": base, "corte": c, "rotulos": f"{c + 1}–{c + H}", "janela_candidatos": f"{c - J + 1}–{c}",
           "n_sementes_alvo": "todas" if N is None else N, "metadados": "atuais (OpenAlex/ORCID de hoje) — reconstrução retrospectiva pela data dos fatos"}

    seeds = pd.read_csv(raw / "seeds.csv")
    sa = pd.read_csv(raw / "authorships.csv", usecols=["work_id", "author_id", "author_orcid"])
    sw = pd.read_csv(raw / "works.csv", usecols=["id", "publication_date"])
    wyear = dict(zip(sw["id"], years_of(sw)))

    # 0. validação da seleção de candidatos (parâmetros originais)
    t0_orig = int(cfg["split"]["t0_ate"])
    orig = select_candidates(sa[["work_id", "author_id"]], set(seeds["author_id"]), cap, wyear, t0_orig,
                             max_candidates=max_cand, seed=tie_seed)
    cur = pd.read_csv(raw / "candidates.csv")["author_id"]
    rep["validacao_candidatos_originais"] = {"reproduz": set(orig) == set(cur), "recalculados": len(orig),
                                            "gravados": int(len(cur)), "diferenca": len(set(orig) ^ set(cur))}
    print(f"[{base}] validação: select_candidates reproduz candidates.csv? {rep['validacao_candidatos_originais']}", flush=True)

    # 1. sementes do corte
    seeds["ano_sorteio"] = seeds["seed_work_id"].map(wyear)
    sc = seeds[seeds["ano_sorteio"] <= c].sort_values("order")
    sc = sc if N is None else sc.head(N)
    rep["sementes"] = {"disponiveis_sorteio_ate_c": int((seeds["ano_sorteio"] <= c).sum()), "usadas": len(sc),
                       "sem_ano_de_sorteio": int(seeds["ano_sorteio"].isna().sum())}
    sc.to_csv(out / "sementes.csv", index=False)

    # 2. elegibilidade ≤ c (higienização refeita nos trabalhos dessas sementes; ORCID do cache)
    cache = resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
    full_auth = pd.read_csv(raw / "authorships.csv")
    works = pd.read_csv(raw / "works.csv")
    s_works = set(full_auth.loc[full_auth["author_id"].isin(set(sc["author_id"])), "work_id"])
    merged_s = clean_and_merge(full_auth[full_auth["work_id"].isin(s_works)], works,
                               min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    claims = {o: json.loads((cache / f"{o}.json").read_text()) for o in set(sc["author_orcid"].dropna())
              if (cache / f"{o}.json").exists()}
    df, _ = canonicalize(merged_s)
    df = authorship_levels(df, claims, hcfg.get("reject_name_mismatch", True))
    th = author_table(df[years_of(df) <= c], hcfg.get("author_criteria", {}), cap)
    canon = dict(zip(df["author_id"], df["canonical_id"]))
    sc = sc.assign(pessoa=[canon.get(a, f"orcid:{o}" if isinstance(o, str) else a)
                           for a, o in zip(sc["author_id"], sc["author_orcid"])])
    sc["elegivel_c"] = sc["pessoa"].map(th["eligible"]).fillna(False).astype(bool)
    sc["orcid_no_cache"] = sc["author_orcid"].isin(claims)
    sc["reprova_c"] = sc["pessoa"].map(lambda p: ",".join(k for k, _ in CRITERIA if p in th.index and not th.loc[p, k])
                                       if p in th.index else "sem publicação até o corte")
    sc.to_csv(out / "elegibilidade.csv", index=False)
    rep["elegibilidade_ate_c"] = {"elegiveis": int(sc["elegivel_c"].sum()),
                                  "indeterminadas_sem_orcid_no_cache": int((~sc["orcid_no_cache"]).sum()),
                                  "motivos": sc.loc[~sc["elegivel_c"], "reprova_c"].str.split(",").explode().value_counts().to_dict()}

    # 3. candidatos no corte (mesma função; laços ≤ c)
    cands, ties = select_candidates(sa[["work_id", "author_id"]], set(sc["author_id"]), cap, wyear, c,
                                    max_candidates=max_cand, seed=tie_seed, return_ties=True)
    pd.DataFrame({"author_id": cands, "laco_ate_c": [int(ties[x]) for x in cands]}).to_csv(out / "candidatos.csv", index=False)

    # 4. lacunas: anos da janela sem histórico local
    hist_from = c - J + 1
    have_window = set(range(2017, 2022))                  # janela coletada na expansão original
    cur_set = set(cur)
    need_years = [y for y in range(hist_from, c + 1)]
    new = [x for x in cands if x not in cur_set]
    old = [x for x in cands if x in cur_set]
    miss_old = [y for y in need_years if y not in have_window]
    ca = pd.read_parquet(raw / "authorships_cand.parquet", columns=["work_id", "author_id"])
    cw = pd.read_parquet(raw / "works_cand.parquet", columns=["id", "publication_date"])
    cy = dict(zip(cw["id"], years_of(cw)))
    per_cand_year = ca.assign(y=ca["work_id"].map(cy)).groupby("author_id")["work_id"].nunique().mean() / len(have_window)
    works_new = len(new) * len(need_years) * per_cand_year
    works_old = len(old) * len(miss_old) * per_cand_year
    calls_lists = math.ceil(len(new) / 50) + (math.ceil(len(old) / 50) if miss_old else 0) \
        + math.ceil((works_new + works_old) / PER_PAGE)
    calls_enrich = 2 * math.ceil((works_new + works_old) / IDS_PER_CALL)            # tópicos + instituições
    orc = pd.read_csv(raw / "authorships.csv", usecols=["author_id", "author_orcid"]).dropna().drop_duplicates("author_id")
    orc_new = orc[orc["author_id"].isin(set(new))]["author_orcid"].map(lambda o: str(o).rstrip("/").split("/")[-1])
    orcid_reads = int(sum(not (cache / f"{o}.json").exists() for o in orc_new))
    gaps = pd.DataFrame([{"author_id": x, "situacao": "novo", "anos_faltando": f"{hist_from}–{c}"} for x in new] +
                        ([{"author_id": x, "situacao": "ja_coletado", "anos_faltando": ",".join(map(str, miss_old))} for x in old]
                         if miss_old else []))
    gaps.to_csv(out / "lacunas.csv", index=False)
    rep["candidatos"] = {"total": len(cands), "ja_coletados": len(old), "novos": len(new),
                         "anos_faltando_para_ja_coletados": miss_old,
                         "cobertura_local_candidato_ano": round(1 - (len(new) * len(need_years) + len(old) * len(miss_old))
                                                                / max(len(cands) * len(need_years), 1), 4)}
    credits = calls_lists + calls_enrich
    rep["custo_estimado"] = {"trabalhos_a_coletar": int(works_new + works_old), "consultas_lista": calls_lists,
                             "consultas_enriquecimento": calls_enrich, "creditos_openalex": credits,
                             "usd_aprox": round(credits / 10000, 3), "leituras_orcid": orcid_reads,
                             "limite_proposto_creditos": int(math.ceil(credits * 2 / 100) * 100),
                             "nota": "média de trabalhos por candidato-ano da expansão original; ±50% de incerteza"}
    print(f"[{base}] corte {c}: {len(sc)} sementes, {rep['elegibilidade_ate_c']['elegiveis']} elegíveis ≤{c}; "
          f"{len(cands)} candidatos ({len(old)} já coletados, {len(new)} novos; faltam anos {miss_old} p/ os já coletados) "
          f"→ ~{rep['custo_estimado']['trabalhos_a_coletar']:,} trabalhos, ~{credits:,} créditos, {orcid_reads} leituras ORCID",
          flush=True)

    if args.sem_corpus:
        rep["tempo_s"] = round(time.time() - t_start, 1)
        (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
        print(f"escrito {out}/relatorio.json (sem corpus; {rep['tempo_s']} s)")
        return

    # 5. corpus local (PARCIAL, ou completo com --coletado) → higienização → protocolo → KG validado
    keep_seed_works = set(full_auth.loc[full_auth["author_id"].isin(set(sc["author_id"])), "work_id"])
    a_seed = full_auth[full_auth["work_id"].isin(keep_seed_works)]
    w_seed = works[works["id"].isin(keep_seed_works)]
    a_cand = pd.read_parquet(raw / "authorships_cand.parquet")
    w_cand = pd.read_parquet(raw / "works_cand.parquet")
    wc_year = years_of(w_cand)
    w_cand = w_cand[(wc_year >= hist_from) & (wc_year <= c)]
    a_cand = a_cand[a_cand["work_id"].isin(set(w_cand["id"])) &
                    a_cand["work_id"].isin(set(a_cand.loc[a_cand["author_id"].isin(set(cands)), "work_id"]))]
    w_cand = w_cand[w_cand["id"].isin(set(a_cand["work_id"]))]
    extra_a, extra_w = [], []
    if args.coletado:
        col = resolve(args.coletado)
        extra_a = [pd.read_parquet(p) for p in sorted(col.glob("auth_*.parquet"))]
        extra_w = [pd.read_parquet(p) for p in sorted(col.glob("works_*.parquet"))]
        rep["coletado"] = {"dir": str(args.coletado), "trabalhos": int(sum(len(x) for x in extra_w))}
    auth_c = pd.concat([a_seed, a_cand, *extra_a], ignore_index=True).drop_duplicates(["work_id", "author_id"])
    works_c = pd.concat([w_seed, w_cand, *extra_w], ignore_index=True).drop_duplicates("id")
    if args.fim_rotulos:                                                      # fim exato dos rótulos
        fim = pd.Timestamp(args.fim_rotulos)
        works_c = works_c[pd.to_datetime(works_c["publication_date"], errors="coerce") <= fim]
        rep["rotulos"] = f"{c + 1}-01-01 a {args.fim_rotulos}"
    else:
        works_c = works_c[years_of(works_c) <= c + H]                         # nada além do horizonte
        rep["rotulos"] = f"{c + 1}-01-01 a {c + H}-12-31"
    auth_c = auth_c[auth_c["work_id"].isin(set(works_c["id"]))]
    merged = clean_and_merge(auth_c, works_c, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    claims_all = {o: json.loads((cache / f"{o}.json").read_text())
                  for o in set(merged["author_orcid"].dropna()) if (cache / f"{o}.json").exists()}
    corpus_c, _, hrep = hygienize(merged, claims_all, hcfg, cap)
    rep["dependencias_metadados_atuais"] = temporal_dependencies(merged, claims_all, hcfg, c)
    alvos = sc.loc[sc["elegivel_c"], "pessoa"].tolist()
    P = build_protocol(corpus_c, alvos, {"modo": "calendario", "t0_ate": c}, cap,
                       ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    # 5b. enriquecimento SÓ a partir do cache (nenhuma chamada): tópicos, instituições, ORCID
    enrich_dir = out / "enrich"
    enrich_cov = enrich_offline(corpus_c, auth_c, sc, cands, enrich_dir)
    rep["enriquecimento_offline"] = enrich_cov
    kg = build_kg_t0(corpus_c, works_c, enrich_dir, c)
    pd.DataFrame({"alvo": P.targets, "regime": [P.regimes.get(a) for a in P.targets],
                  "n_coautores_novos": [len(P.gt[a]) for a in P.targets]}).to_csv(out / "alvos.csv", index=False)
    v = validate_kg(kg, c)
    leak = {"max_ano_fatos_kg": int(max(kg[r]["year"].max() for r in ("wrote", "atInstitution", "publishedIn", "cites")
                                        if len(kg[r]))),
            "max_ano_rotulos": int(years_of(P.test).max()), "min_ano_rotulos": int(years_of(P.test).min()),
            "candidatos_escolhidos_com_lacos_ate": c}
    rep["corpus_local_parcial"] = {"trabalhos": int(corpus_c["work_id"].nunique()), "pessoas": int(corpus_c["author_id"].nunique()),
                                   "protocolo": P.summary(), "kg_valido": v["valido"], "kg_violacoes": v["violacoes"],
                                   "kg_cobertura": v["cobertura"], "checagens_temporais": leak,
                                   "aviso": "parcial: falta o histórico dos candidatos listados em lacunas.csv; "
                                            "sem métricas de desempenho"}
    print(f"[{base}] corpus parcial: {rep['corpus_local_parcial']['trabalhos']:,} trabalhos; alvos {P.summary()['alvos']}; "
          f"KG válido={v['valido']}; checagens {leak}", flush=True)
    if args.modelo:
        rep["modelo"] = run_model(corpus_c, works_c, enrich_dir, sc, cands, P, c, H, cap, ev, out)
    rep["tempo_s"] = round(time.time() - t_start, 1)
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    print(f"escrito {out}/relatorio.json ({rep['tempo_s']} s)")


def temporal_dependencies(merged, claims, hcfg, c) -> dict:
    """Quanto da higienização do corpus reconstruído depende de evidência posterior ao corte ou
    de metadados atuais (registrado como limitação; nada é corrigido aqui)."""
    yr = years_of(merged)
    has = merged.dropna(subset=["author_orcid"])
    early = set(has.loc[years_of(has) <= c, "author_id"])
    late_only = set(has["author_id"]) - early
    df, _ = canonicalize(merged)
    df = authorship_levels(df, claims, hcfg.get("reject_name_mismatch", True))
    t0 = df[years_of(df) <= c]
    return {
        "author_ids_com_orcid_so_em_trabalhos_pos_corte": len(late_only),
        "autorias_T0_desses_author_ids (canonicalizadas por evidência pós-corte)":
            int(t0["author_id"].isin(late_only).sum()),
        "autorias_T0_total": int(len(t0)),
        "autorias_T0_nivel_A (reivindicação no ORCID ATUAL)": int((t0["level"] == "A").sum()),
        "autorias_T0_nivel_X (nomes atuais OpenAlex/ORCID)": int((t0["level"] == "X").sum()),
        "autorias_T0_I1 (afiliação no ORCID ATUAL)": int((t0["inst_level"] == "I1").sum()),
        "nota": "limpeza (resumo/idioma/campo), desambiguação de autores e tópicos também são metadados atuais",
    }


def enrich_offline(corpus, auth_raw, sc, cands, out_dir) -> dict:
    """Tabelas de enriquecimento do corpus reconstruído a partir do CACHE (como enrich_base.py,
    mas sem consultar a API). O que não está no cache fica de fora e é reportado."""
    from coauthor_rec.enrich import careers as CA
    from coauthor_rec.enrich import institutions as IN
    from coauthor_rec.enrich import topics as TO
    from coauthor_rec.enrich.openalex_cache import load_cache
    ecfg = yaml.safe_load(open(resolve("configs/enrich.yaml")))
    cache = resolve(ecfg["openalex"]["cache_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    wids = set(corpus["work_id"])
    wcache = load_cache(cache, "works")
    recs = {k: v for k, v in wcache.items() if k in wids}
    wt = TO.work_topics(recs)
    wt = wt[wt["work_id"].isin(wids)].reset_index(drop=True)
    TO.taxonomy(wt).to_parquet(out_dir / "taxonomy.parquet", index=False)
    wt.to_parquet(out_dir / "work_topics.parquet", index=False)
    icache = load_cache(cache, "institutions")
    raw_inst = {i for v in auth_raw["institution_ids"].dropna() for i in json.loads(v) if i}
    irecs = {k: v for k, v in icache.items() if k in raw_inst}
    inst = IN.institutions_table(irecs)
    parents = {p for ps in inst["parents"] for p in ps} - set(inst["institution_id"])
    irecs.update({k: v for k, v in icache.items() if k in parents})
    inst = IN.institutions_table(irecs)
    inst.to_parquet(out_dir / "institutions.parquet", index=False)
    IN.lineage_edges(inst).to_parquet(out_dir / "institution_lineage.parquet", index=False)
    IN.associated_edges(irecs).to_parquet(out_dir / "institution_associated.parquet", index=False)
    IN.author_institution_years(corpus).to_parquet(out_dir / "author_institution_years.parquet", index=False)
    cc = ecfg["careers"]
    persons = set(corpus.loc[corpus["author_id_openalex"].isin(set(sc["author_id"]) | set(cands)), "author_id"])
    persons = {p for p in persons if isinstance(p, str) and p.startswith("orcid:")}
    aff = CA.career_affiliations(sorted(persons), resolve(cc["orcid_cache_dir"]), cc["employment_sections"],
                                 cc["education_sections"])
    aff.to_parquet(out_dir / "author_affiliations_orcid.parquet", index=False)
    return {"trabalhos_com_topico_em_cache": round(wt["work_id"].nunique() / max(len(wids), 1), 4),
            "instituicoes_em_cache": round(len(set(inst["institution_id"]) & raw_inst) / max(len(raw_inst), 1), 4),
            "pessoas_com_vinculo_orcid": int(aff["author_id"].nunique()) if len(aff) else 0}


def run_model(corpus_c, works_c, enrich_dir, sc, cands, P, c, H, cap, ev, out) -> dict:
    """Etapa 6 — o pipeline do modelo principal sobre o corpus reconstruído (pré-registrado em
    configs/robustez.yaml › t4.piloto): treino temporal KG(c−3) → rótulos (c−3, c]; teste KG(c) →
    rótulos (c, c+H]. Validação TÉCNICA: grava métricas por alvo, mas o relatório não as interpreta."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from ablation_kg import evaluate
    from robustez_t1 import MODELS, sample_queries
    from temporal_ltr import texts_for
    from coauthor_rec.models.kg_generators import GENERATORS, KGIndex
    from coauthor_rec.models.kg_ltr import build_pairs, feature_columns, lgbm_params, train_apply
    lag = 3
    yr = years_of(corpus_c)
    seeds_c = set(corpus_c.loc[corpus_c["author_id_openalex"].isin(set(sc["author_id"])), "author_id"])
    cands_c = set(corpus_c.loc[corpus_c["author_id_openalex"].isin(set(cands)), "author_id"]) - seeds_c
    Pin = build_protocol(corpus_c[yr <= c], seeds_c | cands_c, {"modo": "calendario", "t0_ate": c - lag}, cap,
                         ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    queries = sample_queries(Pin.targets, seeds_c, 3000, 42)
    kg_tr = build_kg_t0(corpus_c, works_c, enrich_dir, c - lag)
    v_tr = validate_kg(kg_tr, c - lag)
    idx = KGIndex(kg_tr, cap, c - lag, texts=texts_for(works_c, kg_tr["wrote"]["work_id"]), verbose=False)
    train, _ = build_pairs(idx, kg_tr, queries, Pin.train_graph, Pin.gt, gens=GENERATORS, verbose=False)
    del idx
    kg_te = build_kg_t0(corpus_c, works_c, enrich_dir, c)
    idx = KGIndex(kg_te, cap, c, texts=texts_for(works_c, kg_te["wrote"]["work_id"]), verbose=False)
    test, _ = build_pairs(idx, kg_te, P.targets, P.train_graph, P.gt, gens=GENERATORS, verbose=False)
    tgt_t0 = sorted(P.gt_t0)
    # --- checagens temporais (a falha aborta): rótulos de teste não influenciam o treino
    tr_lab = years_of(Pin.test)
    te_lab = years_of(P.test)
    assert tr_lab.min() > c - lag and tr_lab.max() <= c, ("rótulos de treino fora de (c−3, c]", tr_lab.min(), tr_lab.max())
    assert te_lab.min() > c, ("rótulo de teste antes do corte", te_lab.min())
    assert v_tr["valido"] and validate_kg(kg_te, c)["valido"], "KG com fato posterior ao corte"
    assert int(kg_tr["wrote"]["year"].max()) <= c - lag and int(kg_te["wrote"]["year"].max()) <= c
    spec = {"rotulos_treino": f"{int(tr_lab.min())}–{int(tr_lab.max())}", "rotulos_teste": f"{int(te_lab.min())}–{int(te_lab.max())}",
            "kg_treino_ate": c - lag, "kg_teste_ate": c,
            "tfidf": {"ajuste_treino": f"textos dos trabalhos do KG ≤ {c - lag} ({kg_tr['wrote']['work_id'].nunique()} trabalhos)",
                      "ajuste_teste": f"textos dos trabalhos do KG ≤ {c} ({kg_te['wrote']['work_id'].nunique()} trabalhos)",
                      "nota": "vocabulário/IDF reajustados em cada KG, só com textos do passado daquele KG"},
            "negativos": "todos os candidatos do top-1000 da União RRF que não são coautores novos; grupos sem positivo saem do treino",
            "validacao": "nenhuma: sem parada antecipada nem busca de hiperparâmetros neste piloto",
            "hiperparametros": "fixos (models/kg_ltr.lgbm_params, semente 42) — escolhidos ANTES, na validação cruzada de "
                               "Economia do protocolo original (rótulos 2022+); ver ressalva em docs/ROBUSTEZ_T1_T4.md",
            "demais_transformacoes": "escores dos meta-caminhos e atributos de atividade calculados em cada KG; anos relativos ao corte; sem padronização"}
    rows = []
    rows.append(evaluate(test, test["rrf"].to_numpy(), P.gt, P.targets).assign(modelo="União RRF", avaliacao="estrita"))
    for name, groups in MODELS.items():
        sc_, _, _ = train_apply(train, test, feature_columns(groups, GENERATORS), 42, lgbm_params(42))
        rows.append(evaluate(test, sc_.to_numpy(), P.gt, P.targets).assign(modelo=name, avaliacao="estrita"))
        rows.append(evaluate(test, sc_.to_numpy(), P.gt_t0, tgt_t0).assign(modelo=name, avaliacao="padrao"))
    pd.concat(rows, ignore_index=True).to_parquet(out / "metricas_por_alvo.parquet", index=False)
    return {"kg_treino_valido": v_tr["valido"], "consultas_treino": len(queries),
            "rotulos_treino": f"{c - lag + 1}–{c}", "pares_treino": int(len(train)),
            "positivos_treino": int(train["rotulo"].sum()), "alvos_teste": len(P.targets),
            "pares_teste": int(len(test)), "positivos_teste": int(test["rotulo"].sum()),
            "metricas": "gravadas em metricas_por_alvo.parquet — NÃO interpretadas (piloto técnico)",
            "especificacao_e_checagens": spec}


if __name__ == "__main__":
    main()
