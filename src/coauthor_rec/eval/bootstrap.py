"""Bootstrap de Poisson por pessoa (docs/ESPECIFICACAO_METODOLOGICA.md §6).

Cada pessoa canônica recebe, em cada réplica b, UM peso w_pb ~ Poisson(1), aplicado a TODAS as
suas observações — em todas as áreas, cortes e horizontes. O peso é derivado de um hash estável
de (semente, pessoa, b): a mesma identidade recebe o mesmo peso mesmo quando as áreas são
processadas em chamadas separadas ou em ordens diferentes.

O que isto trata: a repetição da MESMA pessoa (como alvo) entre áreas, cortes e horizontes.
O que NÃO trata: dependência entre pessoas diferentes (coautores em comum, mesma instituição,
pares que compartilham candidatos, redes). Essa dependência residual é reportada à parte.
A ligação entre áreas depende de os identificadores canônicos coincidirem (ORCID ou o mesmo ID
de autor); pessoas sem identificador comum são tratadas como distintas.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def person_weights(persons, n_rep: int, seed: int = 0) -> pd.DataFrame:
    """Pesos Poisson(1) (pessoas × réplicas), estáveis por identidade."""
    rows = {}
    for p in pd.unique(pd.Series(list(persons), dtype=object)):
        h = int.from_bytes(hashlib.sha256(f"{seed}\x1f{p}".encode()).digest()[:8], "little")
        rows[p] = np.random.default_rng(h).poisson(1.0, n_rep)
    return pd.DataFrame.from_dict(rows, orient="index")


def poisson_bootstrap(df: pd.DataFrame, value: str, person: str = "pessoa", group: str = "area",
                      n_rep: int = 2000, seed: int = 0, level: float = 0.95,
                      agg_weights: dict | None = None) -> dict:
    """Média ponderada de ``value`` por grupo (área) e agregado, com IC percentil.

    Estimativa do grupo g na réplica b: Σ w_pb·x / Σ w_pb sobre as observações de g.
    Agregado: Σ_g a_g · estimativa_g, com a_g = ``agg_weights`` (padrão: pesos iguais, 1/nº de grupos).
    Réplicas em que um grupo fica com peso total 0 são descartadas (contadas em ``replicas_descartadas``).
    """
    d = df[[person, group, value]].dropna()
    W = person_weights(d[person], n_rep, seed).loc[d[person]].to_numpy(dtype=float)   # obs × réplicas
    x = d[value].to_numpy(dtype=float)
    groups = sorted(d[group].unique())
    a = agg_weights or {g: 1 / len(groups) for g in groups}
    lo_q, hi_q = 100 * (1 - level) / 2, 100 * (1 + level) / 2
    reps, out = {}, {"grupos": {}}
    for g in groups:
        m = (d[group] == g).to_numpy()
        den = W[m].sum(axis=0)
        reps[g] = np.where(den > 0, (W[m] * x[m, None]).sum(axis=0) / np.where(den > 0, den, 1), np.nan)
        out["grupos"][g] = {"estimativa": float(x[m].mean()), "n_obs": int(m.sum()),
                            "n_pessoas": int(d.loc[m, person].nunique())}
    ok = np.all([~np.isnan(reps[g]) for g in groups], axis=0)
    for g in groups:
        r = reps[g][ok]
        out["grupos"][g].update({"ic_inf": float(np.percentile(r, lo_q)), "ic_sup": float(np.percentile(r, hi_q))})
    agg = sum(a[g] * reps[g][ok] for g in groups)
    out["agregado"] = {"estimativa": float(sum(a[g] * out["grupos"][g]["estimativa"] for g in groups)),
                       "ic_inf": float(np.percentile(agg, lo_q)), "ic_sup": float(np.percentile(agg, hi_q)),
                       "pesos": a}
    multi = d.groupby(person)[group].nunique()
    out["pessoas_em_mais_de_um_grupo"] = int((multi > 1).sum())
    out["replicas"] = int(ok.sum())
    out["replicas_descartadas"] = int((~ok).sum())
    out["nivel"] = level
    return out
