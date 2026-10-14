"""Reconciliação das contagens da amostra do piloto T4 (docs/ROBUSTEZ_T1_T4.md §3.4).

Fluxo, por semente: sementes brutas (seeds.csv) → trabalho de sorteio ≤ corte → presença no
corpus higienizado ATUAL → elegibilidade E1–E8 com autorias ≤ corte → alvo avaliável
(≥ 1 coautoria nova no horizonte, após M9). Explica 596→628 (inventário × reconstrução) e
189→246 (500 primeiras × todas). Separa inelegibilidade comprovada de ausência de dados no
cache do ORCID. Só lê arquivos locais.
Uso: python scripts/reconciliacao_piloto_t4.py [economia] [--corte 2019]
Saída: runs/robustez/t4/reconciliacao_<base>_<c>.csv e .json
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import load_config, resolve  # noqa: E402
from coauthor_rec.data.clean import clean_and_merge  # noqa: E402


def main():
    base = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "economia"
    c = int(sys.argv[sys.argv.index("--corte") + 1]) if "--corte" in sys.argv else 2019
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    raw = resolve(cfg["bases"][base]["raw_dir"])
    ev = load_config("eval")
    rec = resolve(f"runs/robustez/t4/reconstrucao_{base}_{c}")
    seeds = pd.read_csv(raw / "seeds.csv")
    works = pd.read_csv(raw / "works.csv")
    wyear = dict(zip(works["id"], pd.to_datetime(works["publication_date"], errors="coerce").dt.year))
    seeds["ano_sorteio"] = seeds["seed_work_id"].map(wyear)
    corpus = pd.read_parquet(resolve(cfg["bases"][base]["corpus"]), columns=["author_id_openalex", "author_id"])
    in_corpus = set(corpus["author_id_openalex"])
    el = pd.read_csv(rec / "elegibilidade.csv")
    alvos_f = resolve(f"runs/robustez/t4/reconstrucao_{base}_{c}_coletado_h3/alvos.csv")
    alvos = set(pd.read_csv(alvos_f)["alvo"]) if alvos_f.exists() else None

    # por que uma semente sorteada ≤ c não está no corpus higienizado atual
    auth = pd.read_csv(raw / "authorships.csv")
    sa = auth[auth["author_id"].isin(set(seeds["author_id"]))]
    after_clean = clean_and_merge(sa, works, min_year=ev["split"]["min_year"], language=ev["split"]["language"])
    n_raw = sa.groupby("author_id")["work_id"].nunique()
    n_clean = after_clean.groupby("author_id")["work_id"].nunique()

    d = seeds[["author_id", "author_orcid", "order", "seed_work_id", "ano_sorteio"]].copy()
    d["etapa1_sorteio_ate_c"] = d["ano_sorteio"] <= c
    d["etapa2_no_corpus_higienizado_atual"] = d["author_id"].isin(in_corpus)
    d["trabalhos_brutos"] = d["author_id"].map(n_raw).fillna(0).astype(int)
    d["trabalhos_apos_limpeza"] = d["author_id"].map(n_clean).fillna(0).astype(int)

    def why_absent(r):
        if r["etapa2_no_corpus_higienizado_atual"]:
            return ""
        if r["trabalhos_apos_limpeza"] == 0:
            return "todas as autorias removidas na limpeza (sem resumo/título/idioma)"
        return "autorias restantes rejeitadas na higienização (nível X)"
    d["motivo_fora_do_corpus"] = d.apply(why_absent, axis=1)
    e = el.set_index("author_id")
    d["no_conjunto_reconstruido"] = d["author_id"].isin(e.index)
    d["entre_as_500_primeiras"] = d["author_id"].isin(set(el.sort_values("order").head(500)["author_id"]))
    d["elegivel_ate_c"] = d["author_id"].map(e["elegivel_c"]).fillna(False).astype(bool)
    d["orcid_no_cache"] = d["author_id"].map(e["orcid_no_cache"])
    d["reprova_ate_c"] = d["author_id"].map(e["reprova_c"]).fillna("")

    def status(r):
        if not r["etapa1_sorteio_ate_c"]:
            return "fora: sorteada por trabalho > corte"
        if r["elegivel_ate_c"]:
            return "elegível ≤ corte"
        if r["orcid_no_cache"] is False or r["orcid_no_cache"] == 0:
            return "indeterminada: registro ORCID ausente do cache (E3/E7 não avaliáveis)"
        return "inelegível comprovada ≤ corte"
    d["status_elegibilidade"] = d.apply(status, axis=1)
    pessoa = dict(zip(el["author_id"], el["pessoa"]))
    if alvos is not None:
        d["alvo_avaliavel"] = d["author_id"].map(pessoa).isin(alvos) & d["elegivel_ate_c"]
    d.to_csv(resolve(f"runs/robustez/t4/reconciliacao_{base}_{c}.csv"), index=False)

    s1 = d[d["etapa1_sorteio_ate_c"]]
    out = {
        "sementes_brutas": int(len(d)),
        "sorteadas_por_trabalho_ate_c": int(len(s1)),
        "das_quais_no_corpus_higienizado_atual (= '596' do inventário)": int(s1["etapa2_no_corpus_higienizado_atual"].sum()),
        "das_quais_fora_do_corpus_atual (628 − 596)": int((~s1["etapa2_no_corpus_higienizado_atual"]).sum()),
        "motivos_fora_do_corpus": s1.loc[~s1["etapa2_no_corpus_higienizado_atual"], "motivo_fora_do_corpus"].value_counts().to_dict(),
        "status_elegibilidade_ate_c": s1["status_elegibilidade"].value_counts().to_dict(),
        "elegiveis_entre_as_500_primeiras (versão anterior)": int((s1["entre_as_500_primeiras"] & s1["elegivel_ate_c"]).sum()),
        "elegiveis_entre_as_128_seguintes": int((~s1["entre_as_500_primeiras"] & s1["elegivel_ate_c"]).sum()),
        "motivos_de_inelegibilidade_comprovada": s1.loc[s1["status_elegibilidade"] == "inelegível comprovada ≤ corte", "reprova_ate_c"]
            .str.split(",").explode().value_counts().to_dict(),
        "elegiveis_fora_do_corpus_atual": int((s1["elegivel_ate_c"] & ~s1["etapa2_no_corpus_higienizado_atual"]).sum()),
    }
    if alvos is not None:
        out["alvos_avaliaveis"] = int(d["alvo_avaliavel"].sum())
        out["elegiveis_sem_coautoria_nova_no_horizonte"] = int((s1["elegivel_ate_c"] & ~d.loc[s1.index, "alvo_avaliavel"]).sum())
    resolve(f"runs/robustez/t4/reconciliacao_{base}_{c}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
