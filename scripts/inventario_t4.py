"""T4 — inventário para a RECONSTRUÇÃO HISTÓRICA do corpus em cada corte (docs/ROBUSTEZ_T1_T4.md §3).

Só lê dados locais (nenhuma consulta às APIs). Para cada base e corte c:

1. Seleção histórica das sementes: o sorteio original é UNIFORME entre os trabalhos da área
   (2004+), sem limite superior de ano. Condicionando ao trabalho sorteado ter ano ≤ c, as
   sementes resultantes são uma amostra uniforme dos trabalhos ≤ c — a seleção que teria sido
   feita no corte (ressalvas: ORCID e metadados são o retrato de hoje; ver §3.4 do doc).
2. Elegibilidade histórica: atividade na área até c (≥ 2 trabalhos ≤ c, E5 histórico) e
   ≥ 1 coautoria nova em (c, c+H] (alvo avaliável).
3. Universo de candidatos no corte: coautores dessas sementes em trabalhos ≤ c (teto de
   coautores), priorizados pelo laço ≤ c, até o teto de candidatos; janela de histórico
   (c−J+1 … c). Compara com o que já foi coletado (candidatos atuais, histórico 2017–2021).
4. Custo estimado da coleta que falta (créditos OpenAlex, leituras ORCID).

Saídas: runs/robustez/t4/inventario.json e tabela impressa.
Uso: PYTHONHASHSEED=0 python scripts/inventario_t4.py [bases…]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_filters, resolve  # noqa: E402

PER_PAGE = 200              # página máxima da API de listas
WORKS_PER_ID_CALL = 50      # enriquecimento: filtro openalex:ID1|…|ID50


def main():
    rob = yaml.safe_load(open(resolve("configs/robustez.yaml")))
    t4 = rob["t4"]
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    cap = load_filters()["max_coauthors_per_work"]
    H, last = int(t4["horizonte_anos"]), int(t4["ultimo_ano_completo"])
    J = int(cfg.get("janela_candidatos_anos", 5))
    max_cand = int(cfg.get("max_candidatos", 15000))
    bases = sys.argv[1:] or cfg["gradiente"]
    out = {}
    for b in bases:
        t0 = time.time()
        prof = cfg["bases"][b]
        raw = resolve(prof["raw_dir"])
        corpus = pd.read_parquet(resolve(prof["corpus"]), columns=["work_id", "author_id", "author_id_openalex",
                                                                    "author_orcid", "publication_date"])
        corpus["year"] = pd.to_datetime(corpus["publication_date"], errors="coerce").dt.year
        oa2can = corpus.drop_duplicates("author_id_openalex").set_index("author_id_openalex")["author_id"]
        seeds = pd.read_csv(raw / "seeds.csv")
        seeds["pessoa"] = seeds["author_id"].map(oa2can)
        wy = pd.concat([pd.read_csv(raw / f, usecols=["id", "publication_date"])
                        for f in ("works.csv", "works_full.csv") if (raw / f).exists()]).drop_duplicates("id")
        wy = wy.set_index("id")["publication_date"].pipe(pd.to_datetime, errors="coerce").dt.year
        seeds["ano_sorteio"] = seeds["seed_work_id"].map(wy)
        cand_now = set(oa2can.reindex(pd.read_csv(raw / "candidates.csv")["author_id"]).dropna())
        seed_works = set(pd.read_csv(raw / "works.csv", usecols=["id"])["id"])

        # coautorias por trabalho (teto de coautores), uma vez
        size = corpus.groupby("work_id")["author_id"].transform("nunique")
        small = corpus[size <= cap]
        all_seed_people = set(seeds["pessoa"].dropna())
        with_seed = set(small.loc[small["author_id"].isin(all_seed_people), "work_id"])
        small = small[small["work_id"].isin(with_seed)]                   # só trabalhos com alguma semente
        by_work = small.groupby("work_id")["author_id"].agg(list)
        work_year = small.drop_duplicates("work_id").set_index("work_id")["year"]
        n_works_cand_now = corpus[corpus["author_id"].isin(cand_now) & ~corpus["work_id"].isin(seed_works)]["work_id"].nunique()
        works_per_cand_year = n_works_cand_now / max(len(cand_now), 1) / J
        orcid_rate = corpus.drop_duplicates("author_id")["author_orcid"].notna().mean()

        res = {"sementes": len(seeds), "sementes_sem_ano_de_sorteio": int(seeds["ano_sorteio"].isna().sum()),
               "ano_sorteio": seeds["ano_sorteio"].value_counts().sort_index().astype(int).to_dict(),
               "cortes": {}}
        for c in t4["cortes"]:
            if c + H > last:
                res["cortes"][c] = {"viavel": False}
                continue
            s_c = seeds[(seeds["ano_sorteio"] <= c) & seeds["pessoa"].notna()]
            ps = set(s_c["pessoa"])
            mine = corpus[corpus["author_id"].isin(ps)]
            act = mine[mine["year"] <= c].groupby("author_id")["work_id"].nunique()
            active = set(act[act >= 2].index)
            # coautores ≤ c (passado) e em (c, c+H] (futuro) das sementes ativas
            past, fut = defaultdict(set), defaultdict(set)
            tie = Counter()
            for w, authors in by_work.items():
                y = work_year.get(w)
                if y is None or y > c + H:
                    continue
                inside = [a for a in authors if a in active]
                if not inside:
                    continue
                for s in inside:
                    for o in authors:
                        if o == s:
                            continue
                        if y <= c:
                            past[s].add(o)
                            tie[o] += 1
                        else:
                            fut[s].add(o)
            new = {s: fut[s] - past[s] for s in active}
            evaluable = [s for s in active if new[s]]
            universe = {o for s in active for o in past[s]} - active
            ranked = sorted(universe, key=lambda o: -tie[o])[:max_cand]
            in_now = [o for o in ranked if o in cand_now]
            hist_from = c - J + 1
            # anos da janela (hist_from … c) fora do histórico já coletado dos candidatos (2017–2021)
            missing_years = sum(1 for y in range(hist_from, c + 1) if not 2017 <= y <= 2021)
            # custo: candidatos novos (janela inteira) + atuais (só os anos que faltam)
            new_c = len(ranked) - len(in_now)
            works_new = new_c * J * works_per_cand_year
            works_extra = len(in_now) * missing_years * works_per_cand_year
            works_total = works_new + works_extra
            credits_lists = math.ceil(len(ranked) / 50) + math.ceil(works_total / PER_PAGE)
            credits_enrich = math.ceil(works_total / WORKS_PER_ID_CALL) * 2      # tópicos + instituições (aprox.)
            res["cortes"][c] = {
                "viavel": True, "janela_teste": f"{c + 1}–{c + H}", "janela_historico_candidatos": f"{hist_from}–{c}",
                "sementes_sorteadas_ate_c": len(s_c), "sementes_ativas_ate_c": len(active),
                "alvos_avaliaveis": len(evaluable), "coautorias_novas": int(sum(len(new[s]) for s in evaluable)),
                "universo_candidatos": len(universe), "candidatos_no_teto": len(ranked),
                "ja_coletados": len(in_now), "a_coletar": new_c, "anos_faltando_para_ja_coletados": missing_years,
                "trabalhos_a_coletar_est": int(works_total),
                "creditos_openalex_est": int(credits_lists + credits_enrich),
                "leituras_orcid_est": int(new_c * orcid_rate),
            }
            r = res["cortes"][c]
            print(f"[{b}] corte {c}: sementes sorteadas ≤c {r['sementes_sorteadas_ate_c']}, ativas {r['sementes_ativas_ate_c']}, "
                  f"avaliáveis {r['alvos_avaliaveis']} ({r['coautorias_novas']} coautorias novas) | candidatos: "
                  f"{r['candidatos_no_teto']} (já coletados {r['ja_coletados']}, a coletar {r['a_coletar']}, "
                  f"+{missing_years} ano(s) para os já coletados) | ~{r['trabalhos_a_coletar_est']:,} trabalhos, "
                  f"~{r['creditos_openalex_est']:,} créditos, ~{r['leituras_orcid_est']:,} ORCID", flush=True)
        res["trabalhos_por_candidato_ano"] = round(works_per_cand_year, 3)
        res["fracao_com_orcid"] = round(float(orcid_rate), 3)
        out[b] = res
        print(f"[{b}] {time.time() - t0:.0f} s", flush=True)
    dest = resolve(f"{rob['saida']}/t4")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "inventario.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=int))
    print(f"escrito {dest / 'inventario.json'}")


if __name__ == "__main__":
    main()
