"""Métricas *beyond-accuracy* (avaliação multidimensional — lacuna #5 da qualificação).

Ranqueamento (Precision/Recall/NDCG…) mede acurácia; estas métricas medem outras
dimensões da qualidade da recomendação, que a literatura aponta como negligenciadas:

- **Diversidade intra-lista (ILD@K)**: quão diferentes entre si são os coautores
  recomendados. ILD = 1 − similaridade média par-a-par (cosseno dos perfis SciBERT).
  Alta ILD = a lista cobre temas variados; baixa = recomenda "mais do mesmo".
- **Novidade@K**: quão fora do óbvio (long-tail) são os recomendados. Auto-informação
  média −log2 p(c), com p(c) = popularidade do autor c (grau de coautoria em T0
  normalizado). Alta novidade = recomenda autores pouco conectados (combate o viés de
  popularidade); baixa = recomenda hubs já conhecidos.
- **Cobertura de catálogo@K** (agregada, no script): fração dos autores do catálogo que
  chegam a ser recomendados a *algum* alvo — mede se o modelo explora o espaço ou colapsa
  num punhado de candidatos.

IMPORTANTE: estas métricas só têm sentido LIDAS JUNTO COM a acurácia. Um recomendador
aleatório é diverso e novo ao máximo e, ainda assim, inútil. Reporte-as ao lado do Recall.
"""
from __future__ import annotations

import math

import numpy as np


def intra_list_diversity(recommended: list, k: int, emb: np.ndarray, author_index: dict) -> float:
    """ILD@K = 1 − cosseno médio entre pares dos top-K recomendados (perfis textuais).

    ``emb`` deve estar L2-normalizado por linha (cosseno = produto interno). Considera
    apenas recomendados com embedding disponível; retorna 0.0 se houver menos de 2.
    """
    idxs = [author_index[a] for a in recommended[:k] if a in author_index]
    if len(idxs) < 2:
        return 0.0
    V = emb[idxs]
    S = V @ V.T                       # cossenos (emb normalizado)
    n = len(idxs)
    off = (S.sum() - np.trace(S)) / (n * (n - 1))   # média dos pares (exclui diagonal)
    return float(1.0 - off)


def novelty(recommended: list, k: int, popularity: dict) -> float:
    """Novidade@K = média de −log2 p(c) sobre os top-K (auto-informação).

    ``popularity[c] ∈ (0, 1]`` = popularidade do autor c (ex.: grau de coautoria T0 / N).
    Autores fora do dicionário recebem a menor popularidade observada (máx. novidade).
    """
    top = recommended[:k]
    if not top:
        return 0.0
    floor = min(popularity.values()) if popularity else 1.0
    acc = 0.0
    for c in top:
        p = popularity.get(c, floor)
        p = min(max(p, 1e-12), 1.0)
        acc += -math.log2(p)
    return acc / len(top)


def popularity_from_graph(train_graph: dict) -> dict:
    """p(c) = grau de coautoria de c em T0 / (nº de autores). Normaliza para (0, 1].

    ``train_graph[a]`` = conjunto de coautores de a em T0. Autores sem grau recebem
    popularidade mínima (1/N) — são os mais "novos"/long-tail.
    """
    n = max(len(train_graph), 1)
    pop = {}
    for a, coas in train_graph.items():
        pop[a] = max(len(coas), 1) / n
    return pop
