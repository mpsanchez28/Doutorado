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


def raw_stats(key: str, prof: dict) -> dict | None:
    """Totais da coleta e funil dos filtros de artigo (bruto → corpus limpo), para toda base
    que já tem dados brutos — independe da higienização."""
    from coauthor_rec.config import load_filters
    raw = resolve(prof["raw_dir"])
    if not (raw / "works.csv").exists():
        return None
    f = load_filters()
    from coauthor_rec.data.raw import load_raw
    a, w = load_raw(raw, usecols_auth=["work_id", "author_id"],
                    usecols_works=["id", "publication_date", "title", "abstract", "language"])
    ex = _json(resolve(f"runs/{key}/expand.json")) or {}
    seeds = pd.read_csv(raw / "seeds.csv") if (raw / "seeds.csv").exists() else None
    cj = _json(resolve(f"runs/{key}/collect.json")) or {}
    year = pd.to_datetime(w["publication_date"], errors="coerce").dt.year
    steps, m = [("trabalhos coletados (bruto)", pd.Series(True, index=w.index))], pd.Series(True, index=w.index)
    for label, cond in [(f"idioma = {f.get('language', 'en')}", w["language"] == f.get("language", "en")),
                        (f"ano ≥ {f.get('min_year', 2004)}", year >= f.get("min_year", 2004)),
                        ("com título", w["title"].notna()),
                        ("com abstract", w["abstract"].notna()),
                        ("com ≥1 autor identificado", w["id"].isin(set(a.dropna(subset=["author_id"])["work_id"])))]:
        m = m & cond
        steps.append((label, m.copy()))
    funnel = [{"etapa": lab, "restantes": int(s.sum()), "removidos_isolado": int((~cond).sum()) if i else 0}
              for i, ((lab, s), cond) in enumerate(zip(steps, [steps[0][1]] + [
                  w["language"] == f.get("language", "en"), year >= f.get("min_year", 2004),
                  w["title"].notna(), w["abstract"].notna(),
                  w["id"].isin(set(a.dropna(subset=["author_id"])["work_id"]))]))]
    status = ("higienizada" if resolve(f"runs/{key}/hygiene.json").exists()
              else "coletada" + (" + expandida" if ex else "") + " — higienização pendente")
    return {"label": prof["label"], "status": status,
            "collected_at": (cj.get("collected_at") or "")[:10] or
            dt.datetime.fromtimestamp((raw / "works.csv").stat().st_mtime).strftime("%Y-%m-%d"),
            "seeds": len(seeds) if seeds is not None else None,
            "works": len(w), "authorships": len(a), "authors": int(a["author_id"].nunique()),
            "no_author": int(a["author_id"].isna().sum()),
            "sample_seeds": cj.get("sample_seeds_used"), "funnel": funnel,
            "candidates": ex.get("candidates"), "works_cand": ex.get("works_cand")}


def collect_base(key: str, prof: dict) -> dict | None:
    raw = resolve(prof["raw_dir"])
    hyg = _json(resolve(f"runs/{key}/hygiene.json"))
    if not hyg or not (raw / "works.csv").exists():
        return None
    from coauthor_rec.data.raw import load_raw
    auth, works = load_raw(raw, usecols_auth=["work_id", "author_id"], usecols_works=["id", "publication_date"])
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
    raws = {k: raw_stats(k, prof["bases"][k]) for k in order}
    L += ["## 1. Total de registros coletados", "",
          "| Base | Status | Coletada em | Sementes | Candidatos expandidos | Trabalhos | (dos quais, só dos candidatos) | Autorias | Autores distintos | Autorias sem autor identificado |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in order:
        r = raws[k]
        if r is None:
            L.append(f"| {prof['bases'][k]['label']} | não coletada | — | — | — | — | — | — | — | — |")
            continue
        L.append(f"| {r['label']} | {r['status']} | {r['collected_at']} | {num(r['seeds'])} | "
                 f"{num(r['candidates'])} | {num(r['works'])} | {num(r['works_cand'])} | "
                 f"{num(r['authorships'])} | {num(r['authors'])} | {num(r['no_author'])} "
                 f"({pct(r['no_author'], r['authorships'])}) |")
    have = [k for k in order if raws[k]]
    tot = lambda f: sum(raws[k][f] for k in have)   # noqa: E731
    if len(have) > 1:
        L.append(f"| **Total** | | | {num(sum(raws[k]['seeds'] or 0 for k in have))} | "
                 f"{num(sum(raws[k]['candidates'] or 0 for k in have))} | {num(tot('works'))} | "
                 f"{num(sum(raws[k]['works_cand'] or 0 for k in have))} | "
                 f"{num(tot('authorships'))} | {num(tot('authors'))} | {num(tot('no_author'))} |")

    if have:
        L += ["", "### 1.1 Funil dos critérios de inclusão de artigos (bruto → corpus limpo)", "",
              "Aplicação sequencial dos critérios de `configs/filters.yaml`; entre parênteses, quantos "
              "trabalhos cada critério removeria isoladamente.", "",
              "| Etapa | " + " | ".join(raws[k]["label"] for k in have) + " |",
              "|---|" + "---:|" * len(have)]
        for i, row in enumerate(raws[have[0]]["funnel"]):
            cells = []
            for k in have:
                fr = raws[k]["funnel"][i]
                base_n = raws[k]["funnel"][0]["restantes"]
                cells.append(f"{num(fr['restantes'])} ({pct(fr['restantes'], base_n)})" + (
                    f" · −{num(fr['removidos_isolado'])} isol." if i else ""))
            L.append(f"| {row['etapa']} | " + " | ".join(cells) + " |")

    pending = [prof["bases"][k]["label"] for k, d in data.items() if not d]
    if pending:
        L += ["", f"**Higienização ainda não concluída:** {', '.join(pending)} — as seções 2 a 6 "
                  "aparecem quando a base for higienizada.", ""]
    if not done:
        open(resolve("docs/RESULTADOS_BASES.md"), "w").write("\n".join(L) + "\n")
        print(f"-> docs/RESULTADOS_BASES.md (coleta de {len(have)} base(s); nenhuma higienizada ainda)")
        return

    L += ["", "## 2. Corpus higienizado e densidade", "",
          "| Base | Trabalhos | Pessoas | Autores/trabalho (média · mediana) | Trabalhos de 1 autor | Trabalhos > 50 autores | Período |",
          "|---|---:|---:|---:|---:|---:|---|"]
    for d in done:
        L.append(f"| {d['label']} | {num(d['works'])} | {num(d['persons'])} | "
                 f"{d['dens_mean']:.2f} · {d['dens_median']:.0f} | {d['solo']:.1%} | {d['big']} | {d['years']} |")
    obs = [d["key"] for d in sorted(done, key=lambda d: -d["dens_mean"])]
    polos = prof.get("gradiente_polos") or {}
    rank = {"alto": 0, "intermediario": 1, "baixo": 2}
    if len(done) >= 2:
        # A H3 afirma uma ordem entre POLOS (alto > intermediário > baixo); dentro de um polo
        # (Matemática ≈ Economia) a ordem não é afirmada.
        seq = [rank.get(polos.get(k), i) for i, k in enumerate(obs)]
        ok = all(a <= b for a, b in zip(seq, seq[1:]))
        dens = ", ".join(f"{d['key']} {d['dens_mean']:.2f} ({polos.get(d['key'], '?')})"
                         for d in sorted(done, key=lambda d: -d["dens_mean"]))
        L += ["", f"**Gradiente de densidade (por polo):** {dens} → "
                  f"{'**confirmado** — a ordem entre polos se mantém' if ok else '**DIVERGE entre polos — investigar**'}."]

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
                if not v or v.get("P_coautoria_nova") is None or v["P_coautoria_nova"] != v["P_coautoria_nova"]:
                    cells.append("—")
                elif v.get("lift") is None:      # 0% entre os pares aleatórios: lift não definido
                    cells.append(f"∞ ({v['P_coautoria_nova']:.1%} vs 0%; cob. {v['cobertura_pares']:.0%})")
                else:
                    cells.append(f"{v['lift']}× ({v['P_coautoria_nova']:.0%} vs {v['P_aleatorio']:.0%}; "
                                 f"cob. {v['cobertura_pares']:.0%})")
            L.append(f"| {r} | " + " | ".join(cells) + " |")

    out = resolve("docs/RESULTADOS_BASES.md")
    out.write_text("\n".join(L) + "\n")
    print(f"-> {out} ({len(done)} base(s) concluída(s); pendentes: {pending or 'nenhuma'})")


if __name__ == "__main__":
    main()
