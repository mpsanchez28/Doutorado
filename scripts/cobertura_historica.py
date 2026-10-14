"""Matriz de cobertura histórica por base e etapa — DESCONHECIDO NÃO É ZERO (ESPECIFICACAO §3, emenda E1).

Para cada base e etapa (fase do desenho temporal), o universo de autores exigido e a janela exigida
são confrontados com o que foi CONSULTADO, por pessoa e ano:
  - semente (bruto)       : histórico das sementes, 2004–2026, já no bruto (coleta "seeded")
  - consultado, c/ registros / consultado, s/ registros : a pessoa estava num lote concluído que
                            cobria o ano (expansão original 2017–2021; lotes do T4 em estado.json);
                            "sem registros" = a consulta (área + idioma) não devolveu trabalho
  - não consultado        : nenhum lote cobriu (pessoa, ano) — NÃO significa zero publicações
  - pendente              : lote previsto e não concluído (coleta parcial ou interrompida)
  - excluído no processamento : havia registros, mas todos caíram na limpeza (resumo, idioma, ano)
Também mede, só com os trabalhos das sementes (histórico completo), quanto uma janela curta de
reconhecimento de colaborações anteriores transforma coautorias antigas em "novas" (proxy do efeito
sobre os rótulos das consultas que são candidatos, cujo histórico começa em 2017).
Nenhuma chamada a API. Nenhuma métrica de modelo é lida.

Uso: python scripts/cobertura_historica.py [bases…]  →  runs/robustez/t4/cobertura_historica.json (+ .csv)
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from coauthor_rec.collect.openalex import candidate_universe_at_cut  # noqa: E402
from coauthor_rec.config import load_config, load_filters, resolve  # noqa: E402
from coauthor_rec.data.clean import ESSENTIAL_COLS  # noqa: E402
from coletor_t4 import build_lots  # noqa: E402

J = 5
# etapas do desenho em discussão: (rótulo, corte das features, último ano de rótulo, componentes)
STAGES = [("teste 2021", 2021, 2021, "teste (KG ≤ 2021); rótulos das sementes 2022+ vêm do bruto"),
          ("treino final / validação (fase 2018)", 2018, 2021, "treino do LambdaMART; validação temporal; módulo neural da 2ª etapa (teste)"),
          ("treino de seleção / 1ª etapa neural (fase 2015)", 2015, 2018, "validação temporal 2015→2018; módulo neural da 1ª etapa")]
PILOT = [("piloto teste 2019", 2019, 2019, "piloto"), ("piloto treino (fase 2016)", 2016, 2019, "piloto")]
RATE_PILOT = 0.025        # piloto 2019: 818 créditos / 32.558 autor-anos consultados (1.560 × 5 + 12.379 × 2)


def years_of(s):
    return pd.to_datetime(s, errors="coerce").dt.year


def queried_years(base, cuts):
    """{autor: {ano: 'concluido'|'pendente'}} dos lotes do T4 (e da expansão original 2017–2021)."""
    q = defaultdict(dict)
    for c in cuts:
        d = resolve(f"data/robustez/t4/{base}_{c}")
        st = json.loads((d / "estado.json").read_text()) if (d / "estado.json").exists() else {"lotes_feitos": []}
        done = set(st.get("lotes_feitos", []))
        lots = []
        v1 = resolve(f"runs/robustez/t4/reconstrucao_{base}_{c}/lacunas.csv")
        if v1.exists():
            lots += build_lots(pd.read_csv(v1), c, J)
        v2 = resolve(f"runs/robustez/t4/reconstrucao_{base}_{c}_v2/lacunas.csv")
        if v2.exists():
            g = pd.read_csv(v2)
            asked = {x for t, ids, _, _ in lots if t in done for x in ids}
            g = g[~((g["situacao"] == "novo") & g["author_id"].isin(asked))]
            lots += build_lots(g, c, J, prefix="v2_")
        for tag, ids, d0, d1 in lots:
            status = "concluido" if tag in done or tag in st.get("ids_por_lote", {}) else "pendente"
            for y in range(int(d0[:4]), int(d1[:4]) + 1):
                for x in ids:
                    if q[x].get(y) != "concluido":
                        q[x][y] = status
    return q


def main():
    bases = sys.argv[1:] or ["economia", "matematica", "computacao", "medicina"]
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    cap = load_filters().get("max_coauthors_per_work")
    ev = load_config("eval")
    max_cand, tie = int(cfg.get("max_candidatos", 15000)), int(cfg["coleta"].get("seed", 42))
    led = {b: json.loads(resolve(f"runs/robustez/t4/coleta_{b}_2021/gasto.json").read_text()) for b in bases}
    out, rows = {"nota": __doc__.strip().splitlines()[0], "bases": {}}, []
    for b in bases:
        raw = resolve(cfg["bases"][b]["raw_dir"])
        seeds = pd.read_csv(raw / "seeds.csv")
        sa = pd.read_csv(raw / "authorships.csv", usecols=["work_id", "author_id"])
        sw = pd.read_csv(raw / "works.csv", usecols=["id", "publication_date"])
        wy = dict(zip(sw["id"], years_of(sw["publication_date"])))
        seeds["ano"] = seeds["seed_work_id"].map(wy)
        all_seeds = set(seeds["author_id"])
        orig = set(pd.read_csv(raw / "candidates.csv")["author_id"])
        cuts = [2021] + ([2019] if b == "economia" else [])
        q = queried_years(b, cuts)
        # pools com registros: expansão + T4 (autor, ano) com algum trabalho; e após a limpeza
        ca = pd.read_parquet(raw / "authorships_cand.parquet", columns=["work_id", "author_id"])
        cw = pd.read_parquet(raw / "works_cand.parquet")
        extra_a, extra_w = [], []
        for c in cuts:
            for p in sorted(resolve(f"data/robustez/t4/{b}_{c}").glob("auth_*.parquet")):
                a = pd.read_parquet(p)
                if len(a.columns):
                    extra_a.append(a[["work_id", "author_id"]])
            for p in sorted(resolve(f"data/robustez/t4/{b}_{c}").glob("works_*.parquet")):
                w = pd.read_parquet(p)
                if len(w.columns):
                    extra_w.append(w)
        A = pd.concat([ca, *extra_a], ignore_index=True).drop_duplicates()
        W = pd.concat([cw, *extra_w], ignore_index=True).drop_duplicates("id")
        A = A[A["work_id"].isin(set(W["id"]))]
        wy_all = dict(zip(W["id"], years_of(W["publication_date"])))
        A = A.assign(ano=A["work_id"].map(wy_all))
        has_rec = set(zip(A["author_id"], A["ano"]))
        ess = [c for c in ESSENTIAL_COLS if c in W.columns]                 # mesmas exigências da limpeza
        nonempty = W[ess].notna().all(axis=1) & W[ess].astype(str).apply(lambda col: col.str.strip() != "").all(axis=1)
        ok_w = set(W.loc[nonempty & (W["language"] == ev["split"]["language"])
                         & (years_of(W["publication_date"]) >= ev["split"]["min_year"]), "id"])
        has_kept = set(zip(A.loc[A["work_id"].isin(ok_w), "author_id"], A.loc[A["work_id"].isin(ok_w), "ano"]))
        q21 = queried_years(b, [2021])                  # taxa: gasto de 2021 / autor-anos consultados em 2021
        rate21 = led[b]["gasto_creditos"] / max(sum(1 for x in q21 for y in q21[x] if q21[x][y] == "concluido"), 1)
        res = {}
        for label, cp, last_label, comp in STAGES + (PILOT if b == "economia" else []):
            ids = set(seeds.loc[seeds["ano"] <= cp, "author_id"])
            u = set(candidate_universe_at_cut(sa, ids, cap, wy, cp, max_candidates=max_cand, seed=tie))
            feat_years = list(range(cp - J + 1, cp + 1))
            lab_years = list(range(cp + 1, last_label + 1)) if last_label > cp else []
            need = feat_years + lab_years
            full, gaps_ay, pend_ay = 0, 0, 0
            per_status = defaultdict(int)
            for x in u:
                if x in all_seeds:
                    per_status["semente (bruto)"] += 1
                    full += 1
                    continue
                cov = []
                for y in need:
                    s = "concluido" if (x in orig and 2017 <= y <= 2021) else q.get(x, {}).get(y)
                    cov.append(s)
                    if s is None:
                        gaps_ay += 1
                    elif s == "pendente":
                        pend_ay += 1
                if all(s == "concluido" for s in cov):
                    full += 1
                    recs = [(x, y) in has_rec for y in need]
                    kept_ = [(x, y) in has_kept for y in need]
                    if not any(recs):
                        per_status["consultado, sem registros na janela"] += 1
                    elif not any(kept_):
                        per_status["consultado, registros todos excluídos na limpeza"] += 1
                    else:
                        per_status["consultado, com registros"] += 1
                elif any(s == "pendente" for s in cov):
                    per_status["coleta pendente (parcial)"] += 1
                elif any(s == "concluido" for s in cov):
                    per_status["parcialmente consultado (anos fora da janela coletada)"] += 1
                else:
                    per_status["não consultado"] += 1
            r = {"corte_features": cp, "janela_features_exigida": f"{feat_years[0]}–{feat_years[-1]}",
                 "anos_de_rotulo_exigidos_para_consultas_candidato": f"{lab_years[0]}–{lab_years[-1]}" if lab_years else "—",
                 "sementes_da_fase": len(ids), "universo": len(u), "autores_cobertura_completa": full,
                 "fracao_cobertura_completa": round(full / max(len(u), 1), 4), "situacao_por_autor": dict(per_status),
                 "autor_anos_nao_consultados": gaps_ay, "autor_anos_pendentes": pend_ay,
                 "custo_incremental_creditos": [round(gaps_ay * rate21), round(gaps_ay * RATE_PILOT)],
                 "componentes": comp}
            res[label] = r
            rows.append({"base": b, "etapa": label, **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                                                       for k, v in r.items()}})
            print(f"[{b}] {label}: universo {len(u)}, completa {r['fracao_cobertura_completa']:.1%}, {dict(per_status)}; "
                  f"autor-anos não consultados {gaps_ay}, pendentes {pend_ay}; custo ~{r['custo_incremental_creditos']}", flush=True)
        # reconhecimento de colaborações anteriores com janela curta (só sementes: histórico completo)
        saw = sa.assign(ano=sa["work_id"].map(wy))
        team = saw.groupby("work_id")["author_id"].transform("nunique")
        saw = saw[team <= cap] if cap else saw
        rec = {}
        for cp, w0, last in ((2018, 2017, 2021), (2021, 2017, 2024)):
            ids = set(seeds.loc[seeds["ano"] <= cp, "author_id"])
            past_full, past_short, fut = defaultdict(set), defaultdict(set), defaultdict(set)
            by_work = saw.groupby("work_id")
            for wid, g in by_work:
                y = g["ano"].iloc[0]
                if pd.isna(y) or y > last:
                    continue
                au = set(g["author_id"])
                for s in au & ids:
                    other = au - {s}
                    if y <= cp:
                        past_full[s] |= other
                        if y >= w0:
                            past_short[s] |= other
                    else:
                        fut[s] |= other
            new_full = sum(len(fut[s] - past_full[s]) for s in ids)
            new_short = sum(len(fut[s] - past_short[s]) for s in ids)
            rec[f"corte {cp}, janela curta {w0}–{cp}, rótulos {cp + 1}–{last}"] = {
                "pares_novos_historico_completo": new_full, "pares_novos_janela_curta": new_short,
                "falsos_novos": new_short - new_full,
                "fracao_falsos_entre_os_novos_da_janela_curta": round((new_short - new_full) / max(new_short, 1), 4)}
        out["bases"][b] = {"etapas": res, "reconhecimento_colaboracoes_anteriores_proxy_sementes": rec,
                           "taxa_creditos_por_autor_ano_2021": round(rate21, 5),
                           "taxa_creditos_por_autor_ano_piloto_2019": RATE_PILOT}
        print(f"[{b}] reconhecimento (proxy): {rec}", flush=True)
    resolve("runs/robustez/t4/cobertura_historica.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    pd.DataFrame(rows).to_csv(resolve("runs/robustez/t4/cobertura_historica.csv"), index=False)
    print("escrito runs/robustez/t4/cobertura_historica.json")


if __name__ == "__main__":
    main()
