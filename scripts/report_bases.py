"""Gera docs/RESULTADOS_BASES.md — números finais de coleta e higienização por base, para
a seção 9 de docs/METODOLOGIA_DADOS.md (e a tese). Lê só artefatos já produzidos:

  <raw_dir>/{authorships,works,seeds}.csv     coleta
  data/processed/corpus_<base>.parquet        corpus higienizado
  data/processed/autores_<base>.csv           critérios E1–E8 por pessoa
  runs/<base>/{hygiene,gate,audit}.json       relatórios

Bases ainda não concluídas aparecem como "em coleta". Uso:
    python scripts/report_bases.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

CRIT = ["E1_orcid", "E2_sem_conflito", "E3_reivindicado", "E4_instituicao",
        "E5_atividade", "E6_plausivel", "E7_nome", "E8_equipe"]


def _json(path):
    return json.loads(path.read_text()) if path.exists() else None


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "—"


def num(x):
    import numbers
    if x is None:
        return "—"
    if isinstance(x, numbers.Integral):
        return f"{int(x):,}".replace(",", ".")
    return x


def collect_base(key: str, prof: dict) -> dict | None:
    raw = resolve(prof["raw_dir"])
    hyg = _json(resolve(f"runs/{key}/hygiene.json"))
    if not hyg or not (raw / "works.csv").exists():
        return None
    auth = pd.read_csv(raw / "authorships.csv", usecols=["work_id", "author_id"])
    works = pd.read_csv(raw / "works.csv", usecols=["id", "publication_date"])
    seeds = pd.read_csv(raw / "seeds.csv") if (raw / "seeds.csv").exists() else None
    corpus = pd.read_parquet(resolve(prof["corpus"]), columns=["work_id", "author_id",
                                                               "publication_date"])
    team = corpus.groupby("work_id")["author_id"].nunique()
    years = pd.to_datetime(corpus["publication_date"]).dt.year
    autores = pd.read_csv(resolve(f"data/processed/autores_{key}.csv"), index_col=0)
    sem = autores[autores["is_seed"]] if "is_seed" in autores else autores
    return {
        "key": key, "label": prof["label"], "hyg": hyg,
        "gate": _json(resolve(f"runs/{key}/gate.json")),
        "audit": _json(resolve(f"runs/{key}/audit.json")),
        "raw_works": len(works), "raw_authorships": len(auth),
        "raw_authors": int(auth["author_id"].nunique()),
        "seeds": len(seeds) if seeds is not None else None,
        "works": int(corpus["work_id"].nunique()), "persons": int(corpus["author_id"].nunique()),
        "dens_mean": float(team.mean()), "dens_median": float(team.median()),
        "solo": float((team == 1).mean()), "big": int((team > 50).sum()),
        "years": f"{int(years.min())}–{int(years.max())}",
        "seed_pass": {c: float(sem[c].mean()) for c in CRIT if c in sem},
        "n_seed_persons": int(len(sem)),
        "targets": int(autores["alvo"].sum()) if "alvo" in autores else int(autores["eligible"].sum()),
        "collected_at": dt.datetime.fromtimestamp((raw / "works.csv").stat().st_mtime).strftime("%d/%m/%Y"),
    }


def main():
    prof = yaml.safe_load(open(os.path.join(ROOT, "configs", "bases.yaml")))
    order = prof.get("gradiente") or list(prof["bases"])
    data = {k: collect_base(k, prof["bases"][k]) for k in order}
    done = [d for d in data.values() if d]
    L = ["# Resultados da coleta e higienização das bases",
         "",
         f"> Gerado por `scripts/report_bases.py` em {dt.datetime.now():%d/%m/%Y %H:%M}. "
         "Métodos: `docs/METODOLOGIA_DADOS.md`.",
         ""]
    pending = [prof["bases"][k]["label"] for k, d in data.items() if not d]
    if pending:
        L += [f"**Em coleta / ainda sem relatório:** {', '.join(pending)}.", ""]
    if not done:
        open(resolve("docs/RESULTADOS_BASES.md"), "w").write("\n".join(L) + "\n")
        print("nenhuma base concluída ainda"); return

    L += ["## 1. Coleta", "",
          "| Base | Coletada em | Sementes | Trabalhos (bruto) | Autorias (bruto) | Autores (bruto) | Autorias sem autor |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for d in done:
        h = d["hyg"]
        L.append(f"| {d['label']} | {d['collected_at']} | {num(d['seeds'])} | {num(d['raw_works'])} | "
                 f"{num(d['raw_authorships'])} | {num(d['raw_authors'])} | "
                 f"{num(h['autorias_sem_author_id'])} ({pct(h['autorias_sem_author_id'], h['autorias_brutas'])}) |")

    L += ["", "## 2. Corpus higienizado e densidade", "",
          "| Base | Trabalhos | Pessoas | Autores/trabalho (média · mediana) | Trabalhos de 1 autor | Trabalhos > 50 autores | Período |",
          "|---|---:|---:|---:|---:|---:|---|"]
    for d in done:
        L.append(f"| {d['label']} | {num(d['works'])} | {num(d['persons'])} | "
                 f"{d['dens_mean']:.2f} · {d['dens_median']:.0f} | {d['solo']:.1%} | {d['big']} | {d['years']} |")
    obs = [d["key"] for d in sorted(done, key=lambda d: -d["dens_mean"])]
    exp = [k for k in order if k in obs]
    if len(done) >= 2:
        ok = obs == exp
        L += ["", f"**Gradiente de densidade:** observado {' > '.join(obs)}; esperado "
                  f"{' > '.join(exp)} → {'**confirmado**' if ok else '**DIVERGE — investigar**'}."]

    L += ["", "## 3. Identidade: níveis de evidência e vínculo institucional", "",
          "| Base | A (reivindicada) | B (ORCID declarado) | C (sem ORCID) | X (rejeitada) | I1 (confirmado no ORCID) | I2 (ROR) | I3 (sem inst.) | ORCIDs fragmentados fundidos |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for d in done:
        a, v, c = d["hyg"]["autorias"], d["hyg"]["vinculo_institucional"], d["hyg"]["canonicalizacao"]
        t, vt = a["total"], sum(v.values())
        L.append(f"| {d['label']} | {pct(a['nivel_A'], t)} | {pct(a['nivel_B'], t)} | {pct(a['nivel_C'], t)} | "
                 f"{pct(a['nivel_X'], t)} | {pct(v['I1'], vt)} | {pct(v['I2'], vt)} | {pct(v['I3'], vt)} | "
                 f"{num(c['orcids_fragmented'])} ({num(c['author_ids_merged'])} ids) |")

    L += ["", "## 4. Elegibilidade das sementes (E1–E8) e autores-alvo", "",
          "| Base | Sementes (pessoas) | " + " | ".join(c.split("_")[0] for c in CRIT) + " | **Alvos** |",
          "|---|---:|" + "---:|" * len(CRIT) + "---:|"]
    for d in done:
        sp = d["seed_pass"]
        L.append(f"| {d['label']} | {num(d['n_seed_persons'])} | " +
                 " | ".join(f"{sp.get(c, float('nan')):.0%}" for c in CRIT) +
                 f" | **{num(d['targets'])}** ({pct(d['targets'], d['n_seed_persons'])}) |")
    L += ["", "Critérios: E1 ORCID · E2 sem conflito · E3 trabalho reivindicado · E4 instituição · "
              "E5 ≥2 trabalhos · E6 plausibilidade · E7 nome · E8 equipe ≤ teto."]

    L += ["", "## 5. Funil de elegibilidade (todas as pessoas)", ""]
    for d in done:
        L += [f"**{d['label']}**", "", "| Etapa | Restantes | Reprovam isolado |", "|---|---:|---:|"]
        for r in d["hyg"]["funil_elegibilidade"]:
            L.append(f"| {r['etapa']} | {num(r['restantes'])} | {num(r.get('reprovam_isolado', '—'))} |")
        L.append("")

    L += ["## 6. Gate de rede e auditoria", "",
          "| Base | Gate | Trabalhos | Autores | Peso médio coautoria | Pares peso ≥3 | Abstract | Auditoria |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    for d in done:
        g = d["gate"] or {}
        ch = g.get("checks", {})
        val = lambda k: ch.get(k, ["—"])[0]
        au = d["audit"] or {}
        L.append(f"| {d['label']} | {'aprovado' if g.get('passed') else 'reprovado'} | {num(val('works'))} | "
                 f"{num(val('authors'))} | {val('mean_coauthor_weight')} | {num(val('pairs_weight_ge_3'))} | "
                 f"{val('abstract_coverage')} | {'aprovada' if au.get('passed') else 'reprovada' if au.get('passed') is False else '—'} |")
    # ---- 7. enriquecimento (camadas 1–3), quando já rodado
    enr = {k: _json(resolve(f"runs/{k}/enrich.json")) for k in order}
    enr = {k: v for k, v in enr.items() if v}
    if enr:
        L += ["", "## 7. Enriquecimento (camadas 1–3)", "",
              "| Base | Corpus | Trabalhos com tópico | Tópicos/trabalho | Tópico principal no campo da base | "
              "Instituições | com ROR | com ancestral | Pessoas ORCID com vínculo | com emprego datado |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for k, e in enr.items():
            c1, c2, c3 = e.get("camada1_topicos", {}), e.get("camada2_instituicoes", {}), e.get("camada3_trajetorias", {})
            L.append(f"| {prof['bases'][k]['label']} | {'provisório' if e.get('provisorio') else 'higienizado'} | "
                     f"{c1.get('cobertura', 0):.1%} | {c1.get('topicos_por_trabalho_media', '—')} | "
                     f"{c1.get('primario_no_campo_da_base') if c1.get('primario_no_campo_da_base') is None else format(c1['primario_no_campo_da_base'], '.1%')} | "
                     f"{num(c2.get('instituicoes'))} | {c2.get('com_ror', 0):.1%} | {c2.get('com_ancestral', 0):.1%} | "
                     f"{c3.get('com_algum_vinculo', 0):.1%} | {c3.get('com_emprego_datado', 0):.1%} |")
        L += ["", "**Diagnóstico de sinal** — lift = P(relação | coautoria nova em T1) ÷ P(relação | par "
                  "aleatório), relações calculadas só com T0 (`docs/ENRIQUECIMENTO.md` §5):", ""]
        rel = sorted({r for e in enr.values() for r in e.get("diagnostico_sinal", {}).get("relacoes", {})})
        L += ["| Relação | " + " | ".join(prof["bases"][k]["label"] for k in enr) + " |",
              "|---|" + "---:|" * len(enr)]
        for r in rel:
            cells = []
            for e in enr.values():
                v = e.get("diagnostico_sinal", {}).get("relacoes", {}).get(r)
                cells.append("—" if not v or v.get("lift") is None else
                             f"{v['lift']}× ({v['P_coautoria_nova']:.0%} vs {v['P_aleatorio']:.0%}; cob. {v['cobertura_pares']:.0%})")
            L.append(f"| {r} | " + " | ".join(cells) + " |")

    out = resolve("docs/RESULTADOS_BASES.md")
    out.write_text("\n".join(L) + "\n")
    print(f"-> {out} ({len(done)} base(s) concluída(s); pendentes: {pending or 'nenhuma'})")


if __name__ == "__main__":
    main()
