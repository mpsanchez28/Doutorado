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
  3. candidatos: ``candidate_universe_at_cut`` — gerado SÓ pelos trabalhos das sementes do corte,
     laços ≤ c, teto de candidatos (a mesma regra de ``select_candidates``). Verificado por
     ``check_candidate_universe``; comparado com a versão v1 (defeituosa: usava os trabalhos de
     TODAS as 1.000 sementes para gerar o universo — ver docs/REVISAO_CONSISTENCIA_PROTOCOLOS.md A0);
  4. lacunas de coleta: para cada candidato, os anos da janela (c−J+1 … c) sem histórico local;
     volume e custo estimados da coleta que falta;
  5. corpus local PARCIAL (sementes + o histórico de candidatos já disponível) → higienização →
     protocolo (corte c, rótulos em (c, c+H]) → KG validado — validação TÉCNICA do pipeline.
     Nenhum modelo é treinado e nenhuma métrica de desempenho é produzida.

Saídas: runs/robustez/t4/reconstrucao_<base>_<c>_v2[_coletado_<rótulos>]/ (sementes, elegibilidade,
candidatos, comparação com o universo v1, lacunas, relatório.json). As pastas sem ``_v2`` são da
versão v1 (universo defeituoso), preservadas e marcadas INVALIDO.json. Não altera dados existentes.
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

from coauthor_rec.collect.openalex import (candidate_universe_at_cut, check_candidate_universe,  # noqa: E402
                                           select_candidates)
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import CRITERIA, author_table, authorship_levels, canonicalize, hygienize  # noqa: E402
from coauthor_rec.eval.protocol import build_protocol  # noqa: E402
from coauthor_rec.graph.kg import build_kg_t0, validate_kg  # noqa: E402

PER_PAGE, IDS_PER_CALL = 200, 50
VERSAO = "v2"          # v2: universo de candidatos gerado só pelas sementes do corte (v1 era defeituoso)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from coletor_t4 import queried_ids  # noqa: E402


def orcid_fingerprint(claims: dict) -> dict:
    """Impressão digital dos registros ORCID usados (o cache é compartilhado e cresce entre execuções)."""
    import hashlib
    h = hashlib.sha256(json.dumps(claims, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"registros": len(claims), "sha256": h}


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
    ap.add_argument("--fase-treino", action="store_true",
                    help="monta e grava os conjuntos da fase de treino (sem treinar modelo)")
    ap.add_argument("--janela-hist", type=int, default=None,
                    help="anos de histórico dos candidatos (W) em TODAS as fases; padrão: configs/robustez.yaml (5)")
    ap.add_argument("--defasagem", type=int, default=None,
                    help="defasagem da fase de treino (rótulos de treino em (c−d, c]); padrão: configs/robustez.yaml (3)")
    ap.add_argument("--snapshot", default=None,
                    help="cópia congelada (data/snapshots/<id>): TODAS as entradas são lidas dela, verificada antes; "
                         "nenhum cache global é consultado")
    args = ap.parse_args()
    base, c, H = args.base, args.corte, args.horizonte
    J = int(args.janela_hist or pil["janela_candidatos_anos"])
    lag = int(args.defasagem or rob["t4"]["defasagem_treino"])
    N = None if str(args.n_sementes).lower() == "todas" else int(args.n_sementes)
    t_start = time.time()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = cfg["bases"][base]
    raw = resolve(prof["raw_dir"])
    snap = None
    if args.snapshot:                                   # entradas congeladas (ESPECIFICACAO §2, emenda E2)
        snap = resolve(args.snapshot)
        snap_info = check_snapshot_inputs(snap)
        raw = snap / "raw" / base
        if args.coletado:
            args.coletado = str(snap / "t4" / f"{base}_{c}")
    filt = load_filters()
    hcfg = filt.get("hygiene", {})
    cap = filt.get("max_coauthors_per_work")
    max_cand = int(cfg.get("max_candidatos", 15000))
    tie_seed = int(cfg["coleta"].get("seed", 42))
    ev = load_config("eval")
    tag = f"ate{args.fim_rotulos}" if args.fim_rotulos else f"h{H}"
    snap_tag = (f"_{snap.name}" if snap else "") + (f"_W{J}L{lag}" if (args.janela_hist or args.defasagem) else "")
    out = resolve(f"{rob['saida']}/t4/reconstrucao_{base}_{c}_{VERSAO}{snap_tag}" + ("" if args.coletado is None else f"_coletado_{tag}"))
    out.mkdir(parents=True, exist_ok=True)
    rep = {"janela_hist_candidatos_anos": J, "defasagem_treino": lag, "versao_universo": VERSAO, "base": base, "corte": c, "rotulos": f"{c + 1}–{c + H}", "janela_candidatos": f"{c - J + 1}–{c}",
           "n_sementes_alvo": "todas" if N is None else N, "metadados": "atuais (OpenAlex/ORCID de hoje) — reconstrução retrospectiva pela data dos fatos"}
    if snap:
        rep["entradas_congeladas"] = snap_info

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
    cache = snap / "orcid" if snap else resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
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
    rep["orcid_usado_na_elegibilidade"] = orcid_fingerprint(claims)
    rep["elegibilidade_ate_c"] = {"elegiveis": int(sc["elegivel_c"].sum()),
                                  "indeterminadas_sem_orcid_no_cache": int((~sc["orcid_no_cache"]).sum()),
                                  "motivos": sc.loc[~sc["elegivel_c"], "reprova_c"].str.split(",").explode().value_counts().to_dict()}

    # 3. candidatos no corte: SÓ os trabalhos das sementes do corte geram o universo (laços ≤ c).
    #    Sementes elegíveis (alvos) e universo de candidatos são conjuntos distintos: o universo é
    #    gerado por TODAS as sementes do corte (como no protocolo original, em que as 1.000 sementes
    #    geram o universo e só as elegíveis são alvos); sementes fora do corte podem ser candidatas.
    cut_ids = set(sc["author_id"])
    cands, ties = candidate_universe_at_cut(sa[["work_id", "author_id"]], cut_ids, cap, wyear, c,
                                            max_candidates=max_cand, seed=tie_seed, return_ties=True)
    chk = check_candidate_universe(cands, sa, cut_ids, cap, wyear, c, all_seeds=set(seeds["author_id"]))
    assert chk["ok"], ("universo de candidatos usa fato ou semente não permitidos pelo corte", chk)
    v1 = set(select_candidates(sa[["work_id", "author_id"]], cut_ids, cap, wyear, c, max_candidates=max_cand, seed=tie_seed))
    excl = set(seeds["author_id"]) - cut_ids
    rep["universo_candidatos"] = {
        "regra": "coautores, em trabalhos ≤ c com equipe ≤ teto, das sementes do corte; exclui só as sementes do corte; "
                 "teto de candidatos por laço (nº de trabalhos ≤ c em comum), desempate com semente fixa",
        "sementes_que_geram_o_universo": len(cut_ids), "sementes_elegiveis_alvos_potenciais": int(sc["elegivel_c"].sum()),
        "verificacao": chk,
        "comparacao_v1_defeituosa": {"v1": len(v1), "v2": len(cands), "comuns": len(v1 & set(cands)),
                                      "so_em_v1": len(v1 - set(cands)), "so_em_v2": len(set(cands) - v1),
                                      "sementes_fora_do_corte_em_v1": len(v1 & excl),
                                      "sementes_fora_do_corte_em_v2": len(set(cands) & excl)}}
    pd.DataFrame({"author_id": cands, "laco_ate_c": [int(ties[x]) for x in cands]}).to_csv(out / "candidatos.csv", index=False)
    pd.DataFrame({"author_id": sorted(v1 | set(cands))}).assign(
        em_v1=lambda d: d["author_id"].isin(v1), em_v2=lambda d: d["author_id"].isin(set(cands)),
        semente_fora_do_corte=lambda d: d["author_id"].isin(excl)).to_csv(out / "comparacao_universo_v1_v2.csv", index=False)
    print(f"[{base}] universo v2: {len(cands)} candidatos (v1 defeituoso: {len(v1)}; comuns {len(v1 & set(cands))}); "
          f"verificação {chk}", flush=True)

    # 4. lacunas: anos da janela sem histórico local
    hist_from = c - J + 1
    have_window = set(range(2017, 2022))                  # janela coletada na expansão original
    cur_set = set(cur)
    need_years = [y for y in range(hist_from, c + 1)]
    data_dir = snap / "t4" / f"{base}_{c}" if snap else resolve(args.coletado or f"data/robustez/t4/{base}_{c}")
    prev_gaps = [snap / "t4" / f"{base}_{c}" / "lacunas_v1.csv" if snap else
                 resolve(f"{rob['saida']}/t4/reconstrucao_{base}_{c}/lacunas.csv")]       # lacunas v1
    asked_new = queried_ids(data_dir, prev_gaps, c, J, "novo")
    asked_years = queried_ids(data_dir, prev_gaps, c, J, "anos")
    new_all = [x for x in cands if x not in cur_set]
    new = [x for x in new_all if x not in asked_new]                       # ainda não consultados
    old_all = [x for x in cands if x in cur_set]
    miss_old = [y for y in need_years if y not in have_window]
    old = [x for x in old_all if x not in asked_years] if miss_old else old_all
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
                         if miss_old else []), columns=["author_id", "situacao", "anos_faltando"])
    gaps.to_csv(out / "lacunas.csv", index=False)
    got = set()
    for f_ in sorted(data_dir.glob("auth_*.parquet")):                     # lote vazio: arquivo sem colunas
        got |= set(pd.read_parquet(f_).get("author_id", pd.Series(dtype=str)))
    led_f = resolve(f"{rob['saida']}/t4/coleta_{base}_{c}/gasto.json")
    spent_prev = json.loads(led_f.read_text())["gasto_creditos"] if led_f.exists() else 0
    rep["candidatos"] = {"total": len(cands), "ja_coletados_na_expansao_original": len(old_all),
                         "novos_vs_expansao_original": len(new_all),
                         "novos_ja_consultados_em_coleta_anterior": len(new_all) - len(new),
                         "novos_ja_consultados_com_trabalho_na_area": len(set(new_all) & asked_new & got),
                         "novos_a_consultar": len(new),
                         "anos_faltando_para_ja_coletados": miss_old,
                         "ja_coletados_com_anos_a_consultar": len(old) if miss_old else 0,
                         "cobertura_local_candidato_ano": round(1 - (len(new) * len(need_years) + (len(old) if miss_old else 0) * len(miss_old))
                                                                / max(len(cands) * len(need_years), 1), 4),
                         "gasto_anterior_desta_base_creditos": spent_prev}
    asked_n = len(asked_new)
    rep["custo_empirico"] = {"creditos_por_candidato_consultado": round(spent_prev / asked_n, 4) if asked_n else None,
                             "creditos_estimados_para_os_novos_a_consultar": round(len(new) * spent_prev / asked_n) if asked_n else None,
                             "nota": "custo real médio da coleta anterior desta base (listas + enriquecimento, com o "
                                     "aproveitamento de cache observado); só referência"}
    credits = calls_lists + calls_enrich
    rep["custo_estimado"] = {"trabalhos_a_coletar": int(works_new + works_old), "consultas_lista": calls_lists,
                             "consultas_enriquecimento": calls_enrich, "creditos_openalex": credits,
                             "usd_aprox": round(credits / 10000, 3), "leituras_orcid": orcid_reads,
                             "limite_proposto_creditos": int(math.ceil(credits * 2 / 100) * 100),
                             "nota": "média de trabalhos por candidato-ano da expansão original; ±50% de incerteza"}
    print(f"[{base}] corte {c}: {len(sc)} sementes, {rep['elegibilidade_ate_c']['elegiveis']} elegíveis ≤{c}; "
          f"{len(cands)} candidatos ({len(old_all)} da expansão original, {len(new_all)} novos, dos quais {len(new)} ainda não "
          f"consultados; faltam anos {miss_old} p/ os já coletados) "
          f"→ ~{rep['custo_estimado']['trabalhos_a_coletar']:,} trabalhos, ~{credits:,} créditos, {orcid_reads} leituras ORCID",
          flush=True)

    if args.sem_corpus:
        rep["tempo_s"] = round(time.time() - t_start, 1)
        (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
        print(f"escrito {out}/relatorio.json (sem corpus; {rep['tempo_s']} s)")
        return

    # 5. corpus local (PARCIAL, ou completo com --coletado) → higienização → protocolo → KG validado
    a_cand_all = pd.read_parquet(raw / "authorships_cand.parquet")
    w_cand_all = pd.read_parquet(raw / "works_cand.parquet")
    extra_a, extra_w = [], []
    if args.coletado:
        col = resolve(args.coletado)
        extra_a = [pd.read_parquet(p) for p in sorted(col.glob("auth_*.parquet"))]
        extra_w = [pd.read_parquet(p) for p in sorted(col.glob("works_*.parquet"))]
        rep["coletado"] = {"dir": str(args.coletado), "trabalhos_na_pasta": int(sum(len(x) for x in extra_w)),
                           "nota": "só entram trabalhos (na janela) de candidatos do universo v2"}
    pools = (full_auth, works, pd.concat([a_cand_all, *extra_a], ignore_index=True),
             pd.concat([w_cand_all, *extra_w], ignore_index=True), set(seeds["author_id"]))
    if args.fim_rotulos:                                                      # fim exato dos rótulos
        auth_c, works_c = compose_corpus(*pools, cut_ids, set(cands), hist_from, c, label_end=pd.Timestamp(args.fim_rotulos))
        rep["rotulos"] = f"{c + 1}-01-01 a {args.fim_rotulos}"
    else:                                                                     # nada além do horizonte
        auth_c, works_c = compose_corpus(*pools, cut_ids, set(cands), hist_from, c, label_end=pd.Timestamp(f"{c + H}-12-31"))
        rep["rotulos"] = f"{c + 1}-01-01 a {c + H}-12-31"
    merged = clean_and_merge(auth_c, works_c, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    claims_all = {o: json.loads((cache / f"{o}.json").read_text())
                  for o in set(merged["author_orcid"].dropna()) if (cache / f"{o}.json").exists()}
    corpus_c, _, hrep = hygienize(merged, claims_all, hcfg, cap)
    rep["orcid_usado_na_higienizacao"] = orcid_fingerprint(claims_all)
    rep["dependencias_metadados_atuais"] = temporal_dependencies(merged, claims_all, hcfg, c)
    alvos = sc.loc[sc["elegivel_c"], "pessoa"].tolist()
    P = build_protocol(corpus_c, alvos, {"modo": "calendario", "t0_ate": c}, cap,
                       ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    # 5a. fase de TREINO (só com --modelo): sementes, universo, corpus e transformações do PRÓPRIO
    #     corte de treino c−3 (nenhum laço posterior a c−3 escolhe consultas ou candidatos)
    phase = None
    if args.modelo or args.fase_treino:
        phase = training_phase(seeds, sc, sa, wyear, pools, c, lag, J, cap,
                               max_cand, tie_seed, cands, hcfg, cache, ev)
    # 5b. enriquecimento SÓ a partir do cache (nenhuma chamada): tópicos, instituições, ORCID
    enrich_dir = out / "enrich"
    caches = load_enrich_caches(snap)                      # lido uma vez; tabelas separadas por corpus
    enrich_cov = enrich_offline(corpus_c, auth_c, sc["author_id"], cands, enrich_dir, caches, orcid_dir=cache)
    if phase is not None:
        phase["enrich_dir"] = out / "enrich_treino"
        phase["relatorio"]["enriquecimento_offline"] = enrich_offline(
            phase["corpus"], phase["auth"], phase["seeds"], phase["universo"], phase["enrich_dir"], caches,
            orcid_dir=cache)
    del caches
    rep["enriquecimento_offline"] = enrich_cov
    kg = build_kg_t0(corpus_c, works_c, enrich_dir, c)
    pd.DataFrame({"alvo": P.targets, "regime": [P.regimes.get(a) for a in P.targets],
                  "n_coautores_novos": [len(P.gt[a]) for a in P.targets]}).to_csv(out / "alvos.csv", index=False)
    write_sets(out, sc, cands, P, corpus_c, "teste")
    if phase is not None:
        rep["fase_de_treino"] = phase["relatorio"]
        write_phase_sets(out, phase, c, cap, ev)
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
        rep["modelo"] = run_model(corpus_c, works_c, enrich_dir, sc, cands, P, c, H, cap, ev, out, phase)
    rep["tempo_s"] = round(time.time() - t_start, 1)
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    print(f"escrito {out}/relatorio.json ({rep['tempo_s']} s)")


def compose_corpus(full_auth, works, cand_auth, cand_works, all_seeds, seed_ids, cand_ids, hist_from, hist_to, label_end):
    """Autorias e trabalhos do corpus de um corte: TODOS os trabalhos das sementes indicadas (bruto)
    e, dos candidatos indicados, só os trabalhos na janela [hist_from, hist_to] que os incluem
    (expansão original + coleta do T4). Candidatos que são sementes de outro sorteio/corte (``all_seeds``)
    têm o histórico no BRUTO — nunca entram na fila de coleta — e ele é usado na mesma janela.
    Nada depois de ``label_end``."""
    sw_ = set(full_auth.loc[full_auth["author_id"].isin(set(seed_ids)), "work_id"])
    cw = cand_works.drop_duplicates("id")
    y = years_of(cw)
    cw = cw[(y >= hist_from) & (y <= hist_to)]
    keep = set(cand_auth.loc[cand_auth["author_id"].isin(set(cand_ids)) & cand_auth["work_id"].isin(set(cw["id"])), "work_id"])
    seed_cands = set(cand_ids) & set(all_seeds)
    rw = works[works["id"].isin(set(full_auth.loc[full_auth["author_id"].isin(seed_cands), "work_id"]))]
    ry = years_of(rw)
    keep_raw = set(rw.loc[(ry >= hist_from) & (ry <= hist_to), "id"]) - sw_
    auth = pd.concat([full_auth[full_auth["work_id"].isin(sw_ | keep_raw)], cand_auth[cand_auth["work_id"].isin(keep)]],
                     ignore_index=True).drop_duplicates(["work_id", "author_id"])
    wk = pd.concat([works[works["id"].isin(sw_ | keep_raw)], cw[cw["id"].isin(keep)]], ignore_index=True).drop_duplicates("id")
    wk = wk[pd.to_datetime(wk["publication_date"], errors="coerce") <= label_end]
    return auth[auth["work_id"].isin(set(wk["id"]))], wk


def training_phase(seeds, sc, sa, wyear, pools, c, lag, J, cap, max_cand, tie_seed, cands_c, hcfg, cache, ev) -> dict:
    """Exemplos de TREINO no corte c' = c − lag, cada etapa com o PRÓPRIO corte:
    sementes = as do corte c sorteadas por trabalho ≤ c' (as sorteadas por trabalho em (c', c]
    foram escolhidas por atividade posterior a c'); universo = coautores DESSAS sementes com laço
    ≤ c' (mesma regra e teto); histórico dos candidatos na janela [c'−J+1, c'] — limitado ao que
    está coletado (registrado) — e trabalhos até c para os rótulos (c', c]."""
    cp = c - lag
    s_ph = sc[sc["ano_sorteio"] <= cp]
    ids_ph = set(s_ph["author_id"])
    u_ph = candidate_universe_at_cut(sa[["work_id", "author_id"]], ids_ph, cap, wyear, cp,
                                     max_candidates=max_cand, seed=tie_seed)
    chk = check_candidate_universe(u_ph, sa, ids_ph, cap, wyear, cp, all_seeds=set(seeds["author_id"]))
    assert chk["ok"], ("universo da fase de treino usa fato ou semente não permitidos", chk)
    assert int(s_ph["ano_sorteio"].max()) <= cp
    full_auth, works, cand_auth, cand_works, all_seeds = pools
    auth, wk = compose_corpus(*pools, ids_ph, set(u_ph), cp - J + 1, c,
                              label_end=pd.Timestamp(f"{c}-12-31"))
    merged = clean_and_merge(auth, wk, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    claims = {o: json.loads((cache / f"{o}.json").read_text())
              for o in set(merged["author_orcid"].dropna()) if (cache / f"{o}.json").exists()}
    corpus, _, _ = hygienize(merged, claims, hcfg, cap)
    have = set(cand_auth.loc[cand_auth["work_id"].isin(set(cand_works["id"])), "author_id"]) | (set(u_ph) & set(all_seeds))
    cy = years_of(cand_works.drop_duplicates("id"))
    yrs_have = sorted({int(y) for y in cy.dropna().unique()})
    window = list(range(cp - J + 1, cp + 1))
    rep = {"corte_treino": cp, "rotulos": f"{cp + 1}–{c}", "sementes_do_corte_c": len(sc),
           "sementes_da_fase (sorteio ≤ c')": len(s_ph), "universo_da_fase": len(u_ph),
           "universo_da_fase_fora_do_universo_do_teste": len(set(u_ph) - set(cands_c)),
           "universo_da_fase_com_algum_trabalho_coletado": len(set(u_ph) & have),
           "universo_da_fase_que_sao_sementes (histórico do bruto)": len(set(u_ph) & set(all_seeds)),
           "verificacao_universo": chk,
           "janela_historico_desejada": f"{window[0]}–{window[-1]}",
           "anos_da_janela_sem_coleta_de_candidatos": [y for y in window if y not in yrs_have],
           "laco_maximo_usado_para_escolher_consultas_e_candidatos": cp}
    print(f"[fase de treino {cp}] {rep}", flush=True)
    return {"corpus": corpus, "works": wk, "auth": auth, "seeds": ids_ph, "universo": u_ph, "relatorio": rep}


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


def check_snapshot_inputs(snap) -> dict:
    """Verifica a cópia congelada (hashes) e exige configurações idênticas às do repositório.
    Divergência ou ausência → falha explícita (nunca consulta que mude os dados)."""
    from coauthor_rec.data.snapshot import SnapshotError, sha256_file, verify_snapshot
    info = verify_snapshot(snap)
    diff = [f.name for f in sorted((snap / "configs").glob("*.yaml"))
            if sha256_file(f) != sha256_file(resolve(f"configs/{f.name}"))]
    if diff:
        raise SnapshotError(f"configurações do repositório diferem das congeladas: {diff}")
    man = json.loads((snap / "MANIFEST.json").read_text())
    return {"snapshot": snap.name, "criado_em": info["criado_em"], "sha256_combinado": info["sha256_combinado"],
            "meta": man.get("meta", {})}


def load_enrich_caches(snap=None) -> dict:
    from coauthor_rec.enrich.openalex_cache import load_cache
    cache = snap / "openalex" if snap else resolve(yaml.safe_load(open(resolve("configs/enrich.yaml")))["openalex"]["cache_dir"])
    return {"works": load_cache(cache, "works"), "institutions": load_cache(cache, "institutions")}


def write_sets(out, sc, cands, P, corpus, label):
    """Conjuntos derivados, para comparação entre versões: sementes/elegibilidade (já gravadas),
    universo (candidatos.csv), alvos e gabarito (pares alvo–coautor novo, após M9, e se alcançável em T0)."""
    rows = [(a, b, b in P.gt_t0.get(a, set())) for a in P.targets for b in sorted(P.gt[a])]
    pd.DataFrame(rows, columns=["alvo", "coautor_novo", "presente_em_T0"]).to_csv(out / f"gabarito_{label}.csv", index=False)


def write_phase_sets(out, phase, c, cap, ev):
    from robustez_t1 import sample_queries
    corpus_tr = phase["corpus"]
    yr = years_of(corpus_tr)
    seeds_tr = set(corpus_tr.loc[corpus_tr["author_id_openalex"].isin(phase["seeds"]), "author_id"])
    cands_tr = set(corpus_tr.loc[corpus_tr["author_id_openalex"].isin(set(phase["universo"])), "author_id"]) - seeds_tr
    cp = phase["relatorio"]["corte_treino"]
    Pin = build_protocol(corpus_tr[yr <= c], seeds_tr | cands_tr, {"modo": "calendario", "t0_ate": cp}, cap,
                         ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    queries = sample_queries(Pin.targets, seeds_tr, 3000, 42)
    pd.DataFrame({"consulta": queries, "e_semente_da_fase": [q in seeds_tr for q in queries],
                  "n_coautores_novos": [len(Pin.gt[q]) for q in queries]}).to_csv(out / "consultas_treino.csv", index=False)
    pd.DataFrame({"author_id": sorted(phase["universo"])}).to_csv(out / "universo_treino.csv", index=False)
    phase["relatorio"]["consultas"] = {"total": len(queries), "sementes": len(set(queries) & seeds_tr),
                                       "candidatos": len(set(queries) - seeds_tr),
                                       "positivos": int(sum(len(Pin.gt[q]) for q in queries))}


def enrich_offline(corpus, auth_raw, seed_ids, cands, out_dir, caches, orcid_dir=None) -> dict:
    """Tabelas de enriquecimento de UM corpus reconstruído a partir do CACHE (como enrich_base.py,
    mas sem consultar a API). O que não está no cache fica de fora e é reportado."""
    from coauthor_rec.enrich import careers as CA
    from coauthor_rec.enrich import institutions as IN
    from coauthor_rec.enrich import topics as TO
    ecfg = yaml.safe_load(open(resolve("configs/enrich.yaml")))
    out_dir.mkdir(parents=True, exist_ok=True)
    wids = set(corpus["work_id"])
    wcache = caches["works"]
    recs = {k: v for k, v in wcache.items() if k in wids}
    wt = TO.work_topics(recs)
    wt = wt[wt["work_id"].isin(wids)].reset_index(drop=True)
    TO.taxonomy(wt).to_parquet(out_dir / "taxonomy.parquet", index=False)
    wt.to_parquet(out_dir / "work_topics.parquet", index=False)
    icache = caches["institutions"]
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
    persons = set(corpus.loc[corpus["author_id_openalex"].isin(set(seed_ids) | set(cands)), "author_id"])
    persons = {p for p in persons if isinstance(p, str) and p.startswith("orcid:")}
    aff = CA.career_affiliations(sorted(persons), orcid_dir or resolve(cc["orcid_cache_dir"]), cc["employment_sections"],
                                 cc["education_sections"])
    aff.to_parquet(out_dir / "author_affiliations_orcid.parquet", index=False)
    return {"trabalhos_com_topico_em_cache": round(wt["work_id"].nunique() / max(len(wids), 1), 4),
            "instituicoes_em_cache": round(len(set(inst["institution_id"]) & raw_inst) / max(len(raw_inst), 1), 4),
            "pessoas_com_vinculo_orcid": int(aff["author_id"].nunique()) if len(aff) else 0}


def run_model(corpus_c, works_c, enrich_dir, sc, cands, P, c, H, cap, ev, out, phase) -> dict:
    """Etapa 6 — o pipeline do modelo principal sobre o corpus reconstruído (pré-registrado em
    configs/robustez.yaml › t4.piloto): treino temporal KG(c−3) → rótulos (c−3, c] sobre o corpus
    da FASE DE TREINO (sementes, universo e laços ≤ c−3; ver ``training_phase``); teste KG(c) →
    rótulos (c, c+H]. Validação TÉCNICA: grava métricas por alvo, mas o relatório não as interpreta."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from ablation_kg import evaluate
    from robustez_t1 import MODELS, sample_queries
    from temporal_ltr import texts_for
    from coauthor_rec.models.kg_generators import GENERATORS, KGIndex
    from coauthor_rec.models.kg_ltr import build_pairs, feature_columns, lgbm_params, train_apply
    lag = c - phase["relatorio"]["corte_treino"]
    corpus_tr, works_tr = phase["corpus"], phase["works"]
    yr = years_of(corpus_tr)
    seeds_tr = set(corpus_tr.loc[corpus_tr["author_id_openalex"].isin(phase["seeds"]), "author_id"])
    cands_tr = set(corpus_tr.loc[corpus_tr["author_id_openalex"].isin(set(phase["universo"])), "author_id"]) - seeds_tr
    Pin = build_protocol(corpus_tr[yr <= c], seeds_tr | cands_tr, {"modo": "calendario", "t0_ate": c - lag}, cap,
                         ev["regimes"]["warm_min_coauthors"], ev["regimes"]["cool_min_coauthors"])
    queries = sample_queries(Pin.targets, seeds_tr, 3000, 42)
    assert set(queries) <= seeds_tr | cands_tr, "consulta de treino fora das sementes/universo da fase"
    kg_tr = build_kg_t0(corpus_tr, works_tr, phase["enrich_dir"], c - lag)
    v_tr = validate_kg(kg_tr, c - lag)
    idx = KGIndex(kg_tr, cap, c - lag, texts=texts_for(works_tr, kg_tr["wrote"]["work_id"]), verbose=False)
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
    spec = {"fase_de_treino": phase["relatorio"],
            "consultas_treino_sementes_da_fase": len(set(queries) & seeds_tr),
            "consultas_treino_candidatos_da_fase": len(set(queries) - seeds_tr),
            "rotulos_treino": f"{int(tr_lab.min())}–{int(tr_lab.max())}", "rotulos_teste": f"{int(te_lab.min())}–{int(te_lab.max())}",
            "kg_treino_ate": c - lag, "kg_teste_ate": c,
            "tfidf": {"ajuste_treino": f"textos dos trabalhos do KG ≤ {c - lag} ({kg_tr['wrote']['work_id'].nunique()} trabalhos)",
                      "ajuste_teste": f"textos dos trabalhos do KG ≤ {c} ({kg_te['wrote']['work_id'].nunique()} trabalhos)",
                      "nota": "vocabulário/IDF reajustados em cada KG, só com textos do passado daquele KG"},
            "negativos": "todos os candidatos do top-1000 da União RRF que não são coautores novos; grupos sem positivo saem do treino",
            "validacao": "nenhuma: sem parada antecipada nem busca de hiperparâmetros nesta execução técnica",
            "hiperparametros": "fixos (models/kg_ltr.lgbm_params, semente 42) — escolhidos ANTES, na validação cruzada de "
                               "Economia do protocolo original (rótulos 2022+); ver ressalva em docs/ROBUSTEZ_T1_T4.md",
            "demais_transformacoes": "escores dos meta-caminhos e atributos de atividade calculados em cada KG; anos relativos ao corte; sem padronização"}
    # compatibilidade treino × teste: o modelo NÃO recebe vetores TF-IDF; recebe o cosseno entre perfis
    # (escalar) e a posição do candidato na lista daquele gerador. Quantis nos dois conjuntos.
    comp = {}
    for col in ("texto_tfidf", "texto_tfidf_pos", "coautoria_aa", "ppr", "topico", "grau_cand", "anos_desde_ultimo_cand"):
        if col in train and col in test:
            q = lambda x: {k: round(float(x.quantile(k)), 4) for k in (0.5, 0.9, 0.99)}
            comp[col] = {"treino": q(train[col]), "teste": q(test[col]),
                         "treino_entre_positivos": q(train.loc[train["rotulo"] == 1, col])}
    spec["compatibilidade_atributos"] = comp
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
