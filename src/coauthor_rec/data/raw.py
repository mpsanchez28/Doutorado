"""Leitura do bruto de uma base: coleta das sementes + expansão dos candidatos.

A coleta ``seeded`` grava ``authorships.csv``/``works.csv`` (sementes e seus históricos
completos). A expansão grava ``authorships_cand.parquet``/``works_cand.parquet`` (histórico dos
candidatos — coautores das sementes — até o fim de T0). Aqui as duas partes são unidas e
deduplicadas, de modo que limpeza, higienização, enriquecimento e relatórios vejam um único
bruto. Bases sem expansão continuam funcionando (só a primeira parte).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw(raw_dir: str | Path, usecols_auth=None, usecols_works=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = Path(raw_dir)
    auth = [pd.read_csv(raw / "authorships.csv", usecols=usecols_auth)]
    works = [pd.read_csv(raw / "works.csv", usecols=usecols_works)]
    if (raw / "works_cand.parquet").exists():
        auth.append(pd.read_parquet(raw / "authorships_cand.parquet", columns=usecols_auth))
        works.append(pd.read_parquet(raw / "works_cand.parquet", columns=usecols_works))
    elif (raw / "works_cand.csv").exists():
        auth.append(pd.read_csv(raw / "authorships_cand.csv", usecols=usecols_auth))
        works.append(pd.read_csv(raw / "works_cand.csv", usecols=usecols_works))
    a = pd.concat(auth, ignore_index=True)
    w = pd.concat(works, ignore_index=True).drop_duplicates("id")
    if {"work_id", "author_id"} <= set(a.columns):
        a = a.drop_duplicates(["work_id", "author_id"])
    return a.reset_index(drop=True), w.reset_index(drop=True)


def has_expansion(raw_dir: str | Path) -> bool:
    raw = Path(raw_dir)
    return (raw / "works_cand.parquet").exists() or (raw / "works_cand.csv").exists()
