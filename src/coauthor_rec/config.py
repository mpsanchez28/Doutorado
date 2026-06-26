"""Carregamento de configs YAML e utilitários de caminho/seed."""
from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Raiz do projeto = dois níveis acima de src/coauthor_rec/.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"


def load_filters() -> dict[str, Any]:
    """Critérios de inclusão/exclusão (fonte única: configs/filters.yaml)."""
    path = CONFIGS_DIR / "filters.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _apply_filters(base: str, cfg: dict, f: dict) -> dict:
    """Sobrepõe os filtros canônicos na estrutura esperada por cada config."""
    if base == "eval":
        cfg.setdefault("graph", {})["max_coauthors_per_work"] = f.get("max_coauthors_per_work")
        cfg.setdefault("split", {})["min_year"] = f.get("min_year")
        cfg["split"]["language"] = f.get("language")
    elif base == "collect":
        cfg["filters"] = {"from_publication_year": f.get("min_year"), "languages": [f.get("language")]}
        cfg.setdefault("thematic", {})["concept_ids"] = f.get("concepts")
        cfg["thematic"]["min_concept_score"] = f.get("has_topic_min_score")
    return cfg


def load_config(name: str) -> dict[str, Any]:
    """Carrega um YAML de configs/ pelo nome (com ou sem extensão).

    Para 'eval' e 'collect', os critérios de filtros.yaml são sobrepostos (fonte única).
    """
    base = name[:-5] if name.endswith((".yaml", ".yml")) else name
    fname = base if base.endswith((".yaml", ".yml")) else f"{base}.yaml"
    path = CONFIGS_DIR / fname if not os.path.isabs(fname) else Path(fname)
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    f = load_filters()
    if f and base in ("eval", "collect"):
        cfg = _apply_filters(base, cfg, f)
    return cfg


def set_seed(seed: int) -> None:
    """Fixa seeds para reprodutibilidade (Python e NumPy)."""
    random.seed(seed)
    np.random.seed(seed)


def resolve(path: str | Path) -> Path:
    """Resolve um caminho relativo à raiz do projeto."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p
