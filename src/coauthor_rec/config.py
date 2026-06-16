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


def load_config(name: str) -> dict[str, Any]:
    """Carrega um YAML de configs/ pelo nome (com ou sem extensão)."""
    if not name.endswith((".yaml", ".yml")):
        name = f"{name}.yaml"
    path = CONFIGS_DIR / name if not os.path.isabs(name) else Path(name)
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def set_seed(seed: int) -> None:
    """Fixa seeds para reprodutibilidade (Python e NumPy)."""
    random.seed(seed)
    np.random.seed(seed)


def resolve(path: str | Path) -> Path:
    """Resolve um caminho relativo à raiz do projeto."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p
