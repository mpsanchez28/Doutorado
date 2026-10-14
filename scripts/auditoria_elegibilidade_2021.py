"""Auditoria da elegibilidade das sementes com dados até 31/12/2021 (docs/AUDITORIA_SELECAO.md §4).

Refaz, só com dados locais (bruto + cache do ORCID; nenhuma chamada paga), a higienização dos
trabalhos das sementes e recalcula os critérios E1–E8 em duas versões:

  atual     — todos os anos (deve REPRODUZIR a elegibilidade gravada em autores_<base>.csv;
              é a validação da própria auditoria);
  ate_2021  — só autorias com publicação ≤ 2021 (E5 atividade, E4 instituição, E6
              plausibilidade, E7 nome, E8 equipe e E3 reivindicação passam a olhar só esse período).

Classificação de cada semente no corte de 2021:
  mantida        — elegível com dados ≤ 2021 (E1/E3 continuam dependendo do retrato ATUAL do
                   ORCID: existência do iD e reivindicações — mantida *condicionalmente*);
  excluída       — reprova algum critério calculável só com dados ≤ 2021 (anota quais);
  indeterminada  — sem registro ORCID no cache (E3/E7-ORCID não avaliáveis).
Cruzada com o ano do trabalho pelo qual a semente foi sorteada (≤ 2021 × > 2021).

Saídas: runs/robustez/auditoria/elegibilidade_<base>.csv (uma linha por semente) e
        runs/robustez/auditoria/elegibilidade.json (resumo). Não altera nenhum dado existente.
Uso: PYTHONHASHSEED=0 python scripts/auditoria_elegibilidade_2021.py [bases…]
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402
from coauthor_rec.data.hygiene import CRITERIA, author_table, authorship_levels, canonicalize  # noqa: E402
from coauthor_rec.data.raw import load_raw  # noqa: E402

CUT = 2021
HIST_CRIT = ["E3_reivindicado", "E4_instituicao", "E5_atividade", "E6_plausivel", "E7_nome", "E8_equipe"]


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    filt = load_filters()
    hcfg, crit = filt.get("hygiene", {}), filt.get("hygiene", {}).get("author_criteria", {})
    cap = filt.get("max_coauthors_per_work")
    ev = load_config("eval")
    cache = resolve(hcfg.get("orcid_api", {}).get("cache_dir", "data/cache/orcid"))
    out_dir = resolve("runs/robustez/auditoria")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = json.loads((out_dir / "elegibilidade.json").read_text()) if (out_dir / "elegibilidade.json").exists() else {}
    for b in sys.argv[1:] or cfg["gradiente"]:
        t0 = time.time()
        raw = resolve(cfg["bases"][b]["raw_dir"])
        seeds = pd.read_csv(raw / "seeds.csv")
        auth, works = load_raw(raw)
        seed_works = set(auth.loc[auth["author_id"].isin(set(seeds["author_id"])), "work_id"])
        auth = auth[auth["work_id"].isin(seed_works)]                 # trabalhos das sementes (todos os coautores)
        merged = clean_and_merge(auth, works, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
        orcids = set(seeds["author_orcid"].dropna())
        claims = {o: json.loads((cache / f"{o}.json").read_text()) for o in orcids if (cache / f"{o}.json").exists()}
        df, _ = canonicalize(merged)
        df = authorship_levels(df, claims, hcfg.get("reject_name_mismatch", True))
        canon = dict(zip(df["author_id"], df["canonical_id"]))
        seeds["pessoa"] = [canon.get(a, f"orcid:{o}" if isinstance(o, str) else a)
                           for a, o in zip(seeds["author_id"], seeds["author_orcid"])]
        year = pd.to_datetime(df["publication_date"], errors="coerce").dt.year
        t_now = author_table(df, crit, cap)
        t_hist = author_table(df[year <= CUT], crit, cap)

        # ano do trabalho sorteado
        wy = pd.to_datetime(works.drop_duplicates("id").set_index("id")["publication_date"], errors="coerce").dt.year
        full = raw / "works_full.csv"
        if full.exists():
            wf = pd.read_csv(full, usecols=["id", "publication_date"]).drop_duplicates("id").set_index("id")["publication_date"]
            wy = wy.combine_first(pd.to_datetime(wf, errors="coerce").dt.year)
        seeds["ano_sorteio"] = seeds["seed_work_id"].map(wy)

        stored = pd.read_csv(resolve(f"data/processed/autores_{b}.csv"), index_col=0, usecols=["canonical_id", "eligible", "alvo"])
        rows = []
        for _, s in seeds.iterrows():
            p = s["pessoa"]
            now = t_now.loc[p] if p in t_now.index else None
            hist = t_hist.loc[p] if p in t_hist.index else None
            r = {"semente": s["author_id"], "pessoa": p, "ordem": int(s["order"]), "ano_sorteio": s["ano_sorteio"],
                 "sorteio_ate_2021": bool(s["ano_sorteio"] <= CUT) if pd.notna(s["ano_sorteio"]) else None,
                 "orcid_no_cache": isinstance(s["author_orcid"], str) and s["author_orcid"] in claims,
                 "elegivel_gravado": bool(stored["eligible"].get(p, False)), "alvo_gravado": bool(stored["alvo"].get(p, False)),
                 "elegivel_atual_recalc": bool(now["eligible"]) if now is not None else False,
                 "trabalhos_ate_2021": int(hist["n_works"]) if hist is not None else 0,
                 "trabalhos_total": int(now["n_works"]) if now is not None else 0}
            if hist is None:
                r["elegivel_2021"], r["reprova_2021"] = False, "sem publicação até 2021"
            else:
                fails = [c for c, _ in CRITERIA if not bool(hist[c])]
                r["elegivel_2021"], r["reprova_2021"] = (not fails), ",".join(fails)
            if not r["orcid_no_cache"]:
                r["status_2021"] = "indeterminada"
            else:
                r["status_2021"] = "mantida" if r["elegivel_2021"] else "excluída"
            rows.append(r)
        d = pd.DataFrame(rows)
        d.to_csv(out_dir / f"elegibilidade_{b}.csv", index=False)

        rep = d["elegivel_atual_recalc"] == d["elegivel_gravado"]
        crosstab = pd.crosstab(d["status_2021"], d["sorteio_ate_2021"].map({True: "sorteio ≤2021", False: "sorteio >2021"}))
        failing = d.loc[d["status_2021"] == "excluída", "reprova_2021"].str.split(",").explode().value_counts()
        summary[b] = {
            "sementes": len(d), "reproducao_elegibilidade_gravada": round(float(rep.mean()), 4),
            "divergencias_reproducao": int((~rep).sum()),
            "elegiveis_gravados": int(d["elegivel_gravado"].sum()), "alvos_gravados_entre_sementes": int(d["alvo_gravado"].sum()),
            "status_2021": d["status_2021"].value_counts().to_dict(),
            "status_x_sorteio": {k: {kk: int(vv) for kk, vv in v.items()} for k, v in crosstab.to_dict(orient="index").items()},
            "elegiveis_gravados_que_saem_em_2021": int((d["elegivel_gravado"] & (d["status_2021"] == "excluída")).sum()),
            "inelegiveis_gravados_que_entram_em_2021": int((~d["elegivel_gravado"] & (d["status_2021"] == "mantida")).sum()),
            "motivos_exclusao_2021": failing.to_dict(),
            "corrigidos_2021": int(((d["status_2021"] == "mantida") & (d["sorteio_ate_2021"] == True)).sum()),  # noqa: E712
        }
        print(f"[{b}] reprodução {summary[b]['reproducao_elegibilidade_gravada']:.1%} | status 2021 {summary[b]['status_2021']} | "
              f"elegíveis que saem {summary[b]['elegiveis_gravados_que_saem_em_2021']} | motivos {summary[b]['motivos_exclusao_2021']} | "
              f"mantidas e sorteadas ≤2021: {summary[b]['corrigidos_2021']} ({time.time() - t0:.0f} s)", flush=True)
        (out_dir / "elegibilidade.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
