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
Uso: PYTHONHASHSEED=0 python scripts/reconstrucao_t4.py economia
"""
from __future__ import annotations

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
    base = sys.argv[1] if len(sys.argv) > 1 else pil["base"]
    c, H, J, N = int(pil["corte"]), int(pil["horizonte_anos"]), int(pil["janela_candidatos_anos"]), int(pil["n_sementes"])
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
    out = resolve(f"{rob['saida']}/t4/reconstrucao_{base}_{c}")
    out.mkdir(parents=True, exist_ok=True)
    rep = {"base": base, "corte": c, "rotulos": f"{c + 1}–{c + H}", "janela_candidatos": f"{c - J + 1}–{c}",
           "n_sementes_alvo": N, "metadados": "atuais (OpenAlex/ORCID de hoje) — reconstrução retrospectiva pela data dos fatos"}

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
    sc = seeds[seeds["ano_sorteio"] <= c].sort_values("order").head(N)
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

    # 5. corpus local PARCIAL → higienização → protocolo → KG validado (validação técnica)
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
    auth_c = pd.concat([a_seed, a_cand], ignore_index=True).drop_duplicates(["work_id", "author_id"])
    works_c = pd.concat([w_seed, w_cand], ignore_index=True).drop_duplicates("id")
    wy_c = years_of(works_c)
    works_c = works_c[wy_c <= c + H]                                          # nada além do horizonte
    auth_c = auth_c[auth_c["work_id"].isin(set(works_c["id"]))]
    merged = clean_and_merge(auth_c, works_c, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    claims_all = {o: json.loads((cache / f"{o}.json").read_text())
                  for o in set(merged["author_orcid"].dropna()) if (cache / f"{o}.json").exists()}
    corpus_c, _, hrep = hygienize(merged, claims_all, hcfg, cap)
    alvos = sc.loc[sc["elegivel_c"], "pessoa"].tolist()
    P = build_protocol(corpus_c, alvos, {"modo": "calendario", "t0_ate": c}, cap,
                       ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    kg = build_kg_t0(corpus_c, works_c.assign(venue_id=None, referenced_works="[]")
                     if "venue_id" not in works_c else works_c, resolve(f"data/processed/enrich_{base}"), c)
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
    rep["tempo_s"] = round(time.time() - t_start, 1)
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    print(f"escrito {out}/relatorio.json ({rep['tempo_s']} s)")


if __name__ == "__main__":
    main()
