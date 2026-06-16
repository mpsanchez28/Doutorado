"""STUB — Grafo de Conhecimento heterogêneo (Tabela 8 / Seção 4.3.1).

Esqueleto da materialização do KG heterogêneo dirigido multi-relacional que alimentará
a GNN (PyTorch Geometric) em 2027. Definido agora para fixar o esquema e evitar
retrabalho. A implementação efetiva (preencher features e construir o HeteroData)
ocorre no ciclo do módulo relacional.

Entidades: Author, Paper, Institution, Venue, Concept.
Relações:
  WRITES           Author -> Paper
  CO_AUTHOR        Author <-> Author   (ponderada: weight, year)
  CITES            Paper  -> Paper     (restrita a citações intra-corpus)
  AFFILIATED_WITH  Author -> Institution
  PUBLISHED_IN     Paper  -> Venue
  HAS_TOPIC        Paper  -> Concept   (score >= 0.3; até 5 conceitos/artigo)
"""
from __future__ import annotations

from dataclasses import dataclass, field

NODE_TYPES = ("author", "paper", "institution", "venue", "concept")
EDGE_TYPES = (
    ("author", "writes", "paper"),
    ("author", "co_author", "author"),
    ("paper", "cites", "paper"),
    ("author", "affiliated_with", "institution"),
    ("paper", "published_in", "venue"),
    ("paper", "has_topic", "concept"),
)

# Parâmetros do esquema (Tabela 8).
HAS_TOPIC_MIN_SCORE = 0.3
HAS_TOPIC_MAX_PER_PAPER = 5


@dataclass
class HeteroGraphSpec:
    """Especificação do esquema; ponto único de verdade do KG heterogêneo."""
    node_types: tuple = NODE_TYPES
    edge_types: tuple = EDGE_TYPES
    has_topic_min_score: float = HAS_TOPIC_MIN_SCORE
    has_topic_max_per_paper: int = HAS_TOPIC_MAX_PER_PAPER
    notes: dict = field(default_factory=dict)


def build_hetero_data(*args, **kwargs):  # pragma: no cover
    """Materializa o KG em torch_geometric.data.HeteroData. (a implementar em 2027)"""
    raise NotImplementedError(
        "Materialização do HeteroData será implementada no ciclo do módulo relacional "
        "(GNN/PyG). O esquema já está fixado em HeteroGraphSpec."
    )
