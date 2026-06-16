"""Geração de embeddings textuais de artigos e agregação por autor (§4.4.1).

Cada artigo é representado por (título + abstract); o embedding do autor é a média dos
embeddings dos seus artigos no período considerado (T0). A agregação por média é o ponto
de partida da proposta (pode evoluir para ponderação temporal/atenção).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def paper_texts(corpus_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Retorna (work_ids, textos) com um texto 'título. abstract' por artigo único."""
    papers = corpus_df.drop_duplicates("work_id")[["work_id", "title", "abstract"]]
    work_ids, texts = [], []
    for wid, title, abstract in zip(papers["work_id"], papers["title"], papers["abstract"]):
        title = "" if pd.isna(title) else str(title)
        abstract = "" if pd.isna(abstract) else str(abstract)
        work_ids.append(wid)
        texts.append((title + ". " + abstract).strip())
    return work_ids, texts


def author_embeddings(
    corpus_df: pd.DataFrame,
    paper_emb: np.ndarray,
    work_ids: list[str],
) -> tuple[np.ndarray, dict]:
    """Agrega embeddings de artigos em embeddings de autor (média).

    Retorna (matriz [n_autores, d], dict author_id -> índice da linha).
    """
    wpos = {w: i for i, w in enumerate(work_ids)}
    authors = list(dict.fromkeys(corpus_df["author_id"]))
    aidx = {a: i for i, a in enumerate(authors)}
    dim = paper_emb.shape[1]

    acc = np.zeros((len(authors), dim), dtype=np.float64)
    cnt = np.zeros(len(authors), dtype=np.float64)
    for aid, wid in zip(corpus_df["author_id"], corpus_df["work_id"]):
        wp = wpos.get(wid)
        if wp is None:
            continue
        acc[aidx[aid]] += paper_emb[wp]
        cnt[aidx[aid]] += 1
    cnt = np.clip(cnt, 1.0, None)
    return (acc / cnt[:, None]).astype(np.float32), aidx
