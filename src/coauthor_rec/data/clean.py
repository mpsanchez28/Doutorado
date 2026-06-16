"""Limpeza e integração das tabelas (Seção 5.1.1).

Integra authorships + works por work_id, padroniza datas, remove nulos essenciais,
mantém inglês e ano >= corte, e deduplica. Inclui a reconstrução de abstract a partir
do abstract_inverted_index do OpenAlex (formato nativo da API).
"""
from __future__ import annotations

import pandas as pd

ESSENTIAL_COLS = ["author_id", "publication_date", "title", "abstract", "language"]


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Reconstrói o texto do abstract a partir do abstract_inverted_index do OpenAlex."""
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in positions)


def clean_and_merge(
    authorships_df: pd.DataFrame,
    works_df: pd.DataFrame,
    min_year: int = 2004,
    language: str = "en",
) -> pd.DataFrame:
    """Replica o pré-processamento do estudo inicial e retorna o dataframe integrado."""
    cols = ["id", "publication_date", "title", "abstract", "language"]
    merged = authorships_df.merge(
        works_df[[c for c in cols if c in works_df.columns]],
        left_on="work_id",
        right_on="id",
    )
    merged["publication_date"] = pd.to_datetime(merged["publication_date"], errors="coerce")
    merged = merged.dropna(subset=ESSENTIAL_COLS).drop(columns=["id"], errors="ignore")
    merged = merged[merged["language"] == language]
    merged = merged[merged["publication_date"].dt.year >= min_year]
    return merged.reset_index(drop=True)


def corpus_summary(merged_df: pd.DataFrame) -> dict:
    """Estatísticas descritivas (Tabela 11) usadas pelo gate e nos relatórios."""
    works = merged_df["work_id"].nunique()
    authors = merged_df["author_id"].nunique()
    abstract_cov = (
        merged_df.drop_duplicates("work_id")["abstract"].notna().mean()
        if works else 0.0
    )
    years = pd.to_datetime(merged_df["publication_date"], errors="coerce").dt.year
    return {
        "works": int(works),
        "authors": int(authors),
        "abstract_coverage": float(abstract_cov),
        "year_min": int(years.min()) if works else None,
        "year_max": int(years.max()) if works else None,
    }
