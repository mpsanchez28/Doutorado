"""Protocolo de avaliação das bases do gradiente (docs/LINHA_BASE.md).

Reúne num só lugar o que todos os modelos precisam ver igual:

- **corte** por ano civil (``split_for_base``; T0 ≤ 2021) e teto de coautores por artigo;
- **verdade fundamental** C_new(a) = coautores de a em T1 que não eram coautores em T0;
- **alvos** = sementes elegíveis (``alvo`` em ``autores_<base>.csv``) com ≥1 coautoria nova;
- **regimes** warm/cool/cold/newcomer pelo nº de coautores em T0;
- **M9** (docs/HIGIENIZACAO.md): pares (alvo, coautor novo) em que o coautor novo tem o mesmo
  nome normalizado de um coautor de T0 do alvo — provável identidade fragmentada no OpenAlex
  (uma colaboração antiga que parece nova). Saem do gabarito; a versão sem a regra é mantida
  para a análise de sensibilidade.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

from ..data.hygiene import normalize_name
from ..split.temporal import build_ground_truth, split_for_base
from .regimes import classify_authors


@dataclass
class Protocol:
    train: pd.DataFrame
    test: pd.DataFrame
    cutoff: int
    train_graph: dict
    gt_raw: dict                       # gabarito sem M9
    gt: dict                           # gabarito com M9 (o oficial)
    targets: list                      # alvos com ≥1 coautoria nova (após M9)
    regimes: dict
    t0_authors: set
    m9_pairs: set = field(default_factory=set)

    def summary(self) -> dict:
        n_raw = sum(len(self.gt_raw[a]) for a in self.gt_raw)
        n = sum(len(self.gt[a]) for a in self.targets)
        reach = sum(b in self.t0_authors for a in self.targets for b in self.gt[a])
        by = defaultdict(int)
        for a in self.targets:
            by[self.regimes[a]] += 1
        return {"corte_T0": self.cutoff, "alvos": len(self.targets), "alvos_por_regime": dict(by),
                "pares_novos_sem_M9": n_raw, "pares_M9_removidos": len(self.m9_pairs),
                "pares_novos": n, "pares_alcancaveis_em_T0": reach,
                "fracao_inalcancavel": round(1 - reach / max(n, 1), 4)}


def m9_suspects(train_graph: dict, gt: dict, names: dict) -> set:
    """Pares (a, b) com b ∈ C_new(a) e algum nome normalizado de b igual ao de um coautor de
    a em T0. ``names``: pessoa → conjunto de nomes normalizados."""
    out = set()
    for a, new in gt.items():
        old_names = set()
        for c in train_graph.get(a, ()):
            old_names |= names.get(c, set())
        if not old_names:
            continue
        for b in new:
            if names.get(b, set()) & old_names:
                out.add((a, b))
    return out


def build_protocol(corpus: pd.DataFrame, eligible_targets, base_split: dict | None, cap: int,
                   warm_min: int = 5, cool_min: int = 1, apply_m9: bool = True) -> Protocol:
    tr, te = split_for_base(corpus, base_split)
    cutoff = int(pd.to_datetime(tr["publication_date"]).dt.year.max())
    train_graph, gt_all = build_ground_truth(tr, te, max_coauthors_per_work=cap)
    eligible = set(eligible_targets)
    gt_raw = {a: s for a, s in gt_all.items() if a in eligible}

    names = defaultdict(set)
    for pid, n in zip(corpus["author_id"], corpus["author_name"]):
        nn = normalize_name(n)
        if nn:
            names[pid].add(nn)
    m9 = m9_suspects(train_graph, gt_raw, names)
    gt = {}
    for a, s in gt_raw.items():
        keep = {b for b in s if (a, b) not in m9} if apply_m9 else set(s)
        if keep:
            gt[a] = keep
    t0 = set(tr["author_id"])
    targets = sorted(gt)
    regimes = classify_authors(train_graph, targets, warm_min, cool_min, t0_authors=t0)
    return Protocol(tr, te, cutoff, train_graph, gt_raw, gt, targets, regimes, t0, m9)
