"""Métricas estruturais do KG heterogêneo.

Calcula estatísticas de nós, arestas e da rede de coautoria (densidade, grau,
componentes conexas, clustering) e a cobertura das demais relações. Saída em dict
serializável (JSON), consumida pela CLI ``graph-stats``.
"""
from __future__ import annotations

import numpy as np


def _rel_key(edge_type) -> str:
    return "__".join(edge_type)


def compute_graph_stats(data, clustering_sample: int | None = 2000, seed: int = 42) -> dict:
    """Calcula métricas estruturais de um ``HeteroData``.

    ``clustering_sample``: nº de nós amostrados para o clustering médio (caro em grafos
    grandes); None usa todos os nós.
    """
    import networkx as nx

    nodes = {nt: int(data[nt].num_nodes) for nt in data.node_types}
    edges = {_rel_key(et): int(data[et].edge_index.size(1)) for et in data.edge_types}

    stats: dict = {"nodes": nodes, "edges": edges}

    # ---- Rede de coautoria (relação simétrica) ----
    co = ("author", "co_author", "author")
    if co in data.edge_types and data[co].edge_index.numel() > 0:
        na = nodes["author"]
        ei = data[co].edge_index.numpy()
        deg = np.bincount(ei[0], minlength=na)
        undirected = int(ei.shape[1] // 2)
        density = (2 * undirected) / (na * (na - 1)) if na > 1 else 0.0

        G = nx.Graph()
        G.add_nodes_from(range(na))
        src, dst = ei
        G.add_edges_from((int(u), int(v)) for u, v in zip(src, dst) if u < v)
        components = list(nx.connected_components(G))
        giant = max(components, key=len) if components else set()

        if clustering_sample and na > clustering_sample:
            rng = np.random.default_rng(seed)
            sample = rng.choice(na, size=clustering_sample, replace=False).tolist()
            clustering = nx.average_clustering(G, nodes=sample)
            clustering_note = f"amostra de {clustering_sample} nós"
        else:
            clustering = nx.average_clustering(G)
            clustering_note = "todos os nós"

        stats["coauthor_network"] = {
            "authors": na,
            "undirected_edges": undirected,
            "density": round(float(density), 6),
            "degree_mean": round(float(deg.mean()), 2),
            "degree_median": int(np.median(deg)),
            "degree_max": int(deg.max()),
            "isolated_authors": int((deg == 0).sum()),
            "isolated_fraction": round(float((deg == 0).mean()), 4),
            "connected_components": len(components),
            "giant_component_size": len(giant),
            "giant_component_fraction": round(len(giant) / na, 4) if na else 0.0,
            "avg_clustering": round(float(clustering), 4),
            "avg_clustering_note": clustering_note,
        }

    # ---- Cobertura das demais relações ----
    npaper = nodes.get("paper", 0)
    na = nodes.get("author", 0)
    cov: dict = {}

    def _count(et):
        return data[et].edge_index.size(1) if et in data.edge_types else 0

    def _src_unique(et):
        if et in data.edge_types and data[et].edge_index.numel() > 0:
            return len(set(data[et].edge_index[0].tolist()))
        return 0

    writes = ("author", "writes", "paper")
    if na and npaper:
        cov["papers_per_author"] = round(_count(writes) / na, 2)
        cov["authors_per_paper"] = round(_count(writes) / npaper, 2)
    ht = ("paper", "has_topic", "concept")
    if npaper:
        cov["concepts_per_paper"] = round(_count(ht) / npaper, 2)
        cov["pct_papers_with_topic"] = round(_src_unique(ht) / npaper, 4)
        cov["pct_papers_with_venue"] = round(_src_unique(("paper", "published_in", "venue")) / npaper, 4)
        cit = ("paper", "cites", "paper")
        cov["intra_corpus_citations"] = _count(cit)
        cov["pct_papers_citing"] = round(_src_unique(cit) / npaper, 4)
    if na:
        cov["pct_authors_with_institution"] = round(
            _src_unique(("author", "affiliated_with", "institution")) / na, 4)
    stats["relation_coverage"] = cov

    return stats
