"""Grafo de Conhecimento heterogêneo (Tabela 8 / Seção 4.3.1).

Materializa o KG heterogêneo dirigido multi-relacional que alimenta a GNN (PyTorch
Geometric). Respeita o corte temporal: quando ``work_ids`` é fornecido (tipicamente o
conjunto de treino T0), apenas esses artigos e as arestas por eles induzidas entram no
grafo — preservando a formulação de predição de links futuros.

Entidades: Author, Paper, Institution, Venue, Concept.
Relações:
  WRITES           Author -> Paper
  CO_AUTHOR        Author <-> Author   (ponderada: weight; simétrica)
  CITES            Paper  -> Paper     (restrita a citações intra-corpus)
  AFFILIATED_WITH  Author -> Institution
  PUBLISHED_IN     Paper  -> Venue
  HAS_TOPIC        Paper  -> Concept   (score >= 0.3; até 5 conceitos/artigo)

Features iniciais dos nós são bibliométricas/estruturais (placeholder). Os embeddings
textuais (CNN/BERT) substituem/concatenam às features de Paper/Author no módulo textual.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import pandas as pd

NODE_TYPES = ("author", "paper", "institution", "venue", "concept")
EDGE_TYPES = (
    ("author", "writes", "paper"),
    ("author", "co_author", "author"),
    ("paper", "cites", "paper"),
    ("author", "affiliated_with", "institution"),
    ("paper", "published_in", "venue"),
    ("paper", "has_topic", "concept"),
)

# Parâmetros do esquema (Tabela 8) — fonte única em configs/filters.yaml.
from ..config import load_filters as _load_filters
_F = _load_filters()
HAS_TOPIC_MIN_SCORE = _F.get("has_topic_min_score", 0.3)
HAS_TOPIC_MAX_PER_PAPER = _F.get("has_topic_max_per_paper", 5)


@dataclass
class HeteroGraphSpec:
    """Especificação do esquema; ponto único de verdade do KG heterogêneo."""
    node_types: tuple = NODE_TYPES
    edge_types: tuple = EDGE_TYPES
    has_topic_min_score: float = HAS_TOPIC_MIN_SCORE
    has_topic_max_per_paper: int = HAS_TOPIC_MAX_PER_PAPER
    notes: dict = field(default_factory=dict)


def _loads(value):
    """json.loads tolerante a NaN/None/strings vazias -> retorna [] ou {}."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return []


def _index_map(ids) -> dict:
    """Mapeia ids únicos -> índice inteiro contíguo (ordem estável)."""
    return {v: i for i, v in enumerate(dict.fromkeys(ids))}


def build_hetero_data(
    corpus_df: pd.DataFrame,
    works_raw_df: pd.DataFrame,
    work_ids=None,
    has_topic_min_score: float = HAS_TOPIC_MIN_SCORE,
    has_topic_max_per_paper: int = HAS_TOPIC_MAX_PER_PAPER,
    max_coauthors_per_work: int | None = None,
    enrich_path=None,
):
    """Constrói o ``HeteroData`` do KG.

    ``corpus_df``: corpus limpo (work_id, author_id, institution_ids, title, abstract,
    publication_date). ``works_raw_df``: works.csv cru (id, venue_id, concepts,
    referenced_works, cited_by_count). ``work_ids``: subconjunto de works (ex.: treino T0);
    se None, usa todos os works do corpus.

    Retorna ``(data, maps)`` onde ``maps[node_type]`` é dict id_OpenAlex -> índice.
    """
    import torch
    from torch_geometric.data import HeteroData

    df = corpus_df
    if work_ids is not None:
        work_ids = set(work_ids)
        df = df[df["work_id"].isin(work_ids)]
    paper_ids = set(df["work_id"].unique())

    raw = works_raw_df[works_raw_df["id"].isin(paper_ids)].copy()
    raw_by_id = raw.set_index("id")

    # ----- Índices dos nós -----
    author_map = _index_map(df["author_id"])
    paper_map = _index_map(df["work_id"].unique())

    inst_ids, venue_ids, concept_ids = [], [], []
    # instituições (do corpus limpo)
    for v in df["institution_ids"]:
        inst_ids.extend([i for i in _loads(v) if i])
    # venues e conceitos (do works cru)
    for vid in raw["venue_id"]:
        if isinstance(vid, str) and vid:
            venue_ids.append(vid)
    for c in raw["concepts"]:
        for item in _loads(c):
            if item.get("id") and item.get("score", 0) >= has_topic_min_score:
                concept_ids.append(item["id"])
    inst_map = _index_map(inst_ids)
    venue_map = _index_map(venue_ids)
    concept_map = _index_map(concept_ids)

    # ----- Arestas -----
    writes_s, writes_d = [], []
    affil = set()
    for wid, aid, insts in zip(df["work_id"], df["author_id"], df["institution_ids"]):
        if aid in author_map and wid in paper_map:
            writes_s.append(author_map[aid])
            writes_d.append(paper_map[wid])
        for i in _loads(insts):
            if i in inst_map and aid in author_map:
                affil.add((author_map[aid], inst_map[i]))

    # CO_AUTHOR ponderada (simétrica)
    from .coauthor import build_weighted_coauthor_edges
    co_edges = build_weighted_coauthor_edges(df, max_coauthors_per_work=max_coauthors_per_work)
    co_s, co_d, co_w = [], [], []
    for (a, b), meta in co_edges.items():
        if a in author_map and b in author_map:
            ia, ib = author_map[a], author_map[b]
            w = float(meta["weight"])
            co_s += [ia, ib]; co_d += [ib, ia]; co_w += [w, w]

    # PUBLISHED_IN, HAS_TOPIC, CITES (do works cru)
    pub_s, pub_d = [], []
    topic_s, topic_d = [], []
    cite_s, cite_d = [], []
    for pid in paper_ids:
        if pid not in raw_by_id.index:
            continue
        row = raw_by_id.loc[pid]
        venue = row.get("venue_id")
        if isinstance(venue, str) and venue in venue_map:
            pub_s.append(paper_map[pid]); pub_d.append(venue_map[venue])
        concepts = sorted(
            [c for c in _loads(row.get("concepts")) if c.get("id") and
             c.get("score", 0) >= has_topic_min_score],
            key=lambda c: c.get("score", 0), reverse=True,
        )[:has_topic_max_per_paper]
        for c in concepts:
            if c["id"] in concept_map:
                topic_s.append(paper_map[pid]); topic_d.append(concept_map[c["id"]])
        for ref in _loads(row.get("referenced_works")):
            if ref in paper_map:  # citação intra-corpus
                cite_s.append(paper_map[pid]); cite_d.append(paper_map[ref])

    # ----- Features dos nós -----
    # Author: [log1p(n_papers), log1p(grau_coautoria), log1p(citações_totais)]
    n_authors = len(author_map)
    a_papers = [0.0] * n_authors
    for s in writes_s:
        a_papers[s] += 1.0
    a_deg = [0.0] * n_authors
    for s in co_s:
        a_deg[s] += 1.0
    # citações por autor = soma de cited_by_count dos seus papers
    paper_cites = {}
    for pid in paper_ids:
        if pid in raw_by_id.index:
            cc = raw_by_id.loc[pid].get("cited_by_count")
            paper_cites[paper_map[pid]] = float(cc) if pd.notna(cc) else 0.0
    a_cit = [0.0] * n_authors
    for s, d in zip(writes_s, writes_d):
        a_cit[s] += paper_cites.get(d, 0.0)
    author_x = torch.tensor(
        [[math.log1p(a_papers[i]), math.log1p(a_deg[i]), math.log1p(a_cit[i])]
         for i in range(n_authors)], dtype=torch.float)

    # Paper: [log1p(citações), ano normalizado]
    def _year(pid):
        d = df[df["work_id"] == pid]["publication_date"]
        if len(d) == 0:
            return 2004
        y = pd.to_datetime(d.iloc[0], errors="coerce")
        return 2004 if pd.isna(y) else int(y.year)
    paper_years = {paper_map[p]: _year(p) for p in paper_ids}
    paper_x = torch.tensor(
        [[math.log1p(paper_cites.get(i, 0.0)), (paper_years.get(i, 2004) - 2004) / 30.0]
         for i in range(len(paper_map))], dtype=torch.float)

    data = HeteroData()
    data["author"].x = author_x
    data["author"].num_nodes = n_authors
    data["paper"].x = paper_x
    data["paper"].num_nodes = len(paper_map)
    for ntype, m in (("institution", inst_map), ("venue", venue_map), ("concept", concept_map)):
        data[ntype].num_nodes = len(m)
        data[ntype].x = torch.ones((len(m), 1), dtype=torch.float)  # placeholder

    def _ei(s, d):
        return torch.tensor([s, d], dtype=torch.long) if s else torch.empty((2, 0), dtype=torch.long)

    data["author", "writes", "paper"].edge_index = _ei(writes_s, writes_d)
    data["author", "co_author", "author"].edge_index = _ei(co_s, co_d)
    if co_w:
        data["author", "co_author", "author"].edge_attr = torch.tensor(co_w, dtype=torch.float).view(-1, 1)
    data["paper", "cites", "paper"].edge_index = _ei(cite_s, cite_d)
    aff_s = [a for a, _ in affil]; aff_d = [i for _, i in affil]
    data["author", "affiliated_with", "institution"].edge_index = _ei(aff_s, aff_d)
    data["paper", "published_in", "venue"].edge_index = _ei(pub_s, pub_d)
    data["paper", "has_topic", "concept"].edge_index = _ei(topic_s, topic_d)

    maps = {"author": author_map, "paper": paper_map, "institution": inst_map,
            "venue": venue_map, "concept": concept_map}

    # Enriquecimento GenAI (§4.3.3): atributos categóricos como novos nós/relações do KG.
    if enrich_path is not None:
        _attach_enrichment(data, maps, paper_map, enrich_path, torch)
    return data, maps


def _attach_enrichment(data, maps, paper_map, enrich_path, torch):
    """Adiciona nós ptype/contrib/style (paper_type, contribution, writing_style) e suas
    relações paper->has_* a partir do JSONL de enriquecimento (um registro por work_id)."""
    import json as _json

    enrich = {}
    with open(enrich_path, encoding="utf-8") as fh:
        for line in fh:
            r = _json.loads(line)
            enrich[r["work_id"]] = r

    specs = [("ptype", "paper_type", "has_ptype"),
             ("contrib", "contribution", "has_contrib"),
             ("style", "writing_style", "has_style")]
    for ntype, field, rel in specs:
        vocab = {}  # valor -> índice
        src, dst = [], []
        for wid, pidx in paper_map.items():
            r = enrich.get(wid)
            if not r:
                continue
            val = r.get(field)
            if not val:
                continue
            j = vocab.setdefault(val, len(vocab))
            src.append(pidx); dst.append(j)
        if not vocab:
            continue
        data[ntype].num_nodes = len(vocab)
        data[ntype].x = torch.ones((len(vocab), 1), dtype=torch.float)  # featless -> embedding
        ei = torch.tensor([src, dst], dtype=torch.long) if src else torch.empty((2, 0), dtype=torch.long)
        data["paper", rel, ntype].edge_index = ei
        maps[ntype] = vocab
