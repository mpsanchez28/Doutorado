"""Credenciais de APIs externas: variável de ambiente ou ``.env`` do projeto (gitignored).

  OPENALEX_API_KEY  chave gratuita (openalex.org/settings/api): 10× o orçamento diário de
                    créditos do acesso sem chave (desde fev/2026, 1.000 créditos/dia sem chave)
  ORCID_TOKEN       token /read-public de um cliente da API pública do ORCID: 100 mil
                    leituras/dia por cliente (anônimo: 25 mil/dia por IP)

Nunca versionar nem colar essas credenciais em conversas ou logs.
"""
from __future__ import annotations

import os
from pathlib import Path

_ENV = Path(__file__).resolve().parents[2] / ".env"


def get_secret(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val.strip()
    if _ENV.exists():
        for line in _ENV.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None
