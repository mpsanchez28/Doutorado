"""Verifica as credenciais e o orçamento das APIs externas, sem imprimir segredos.

  OpenAlex — com OPENALEX_API_KEY: consulta /rate-limit (saldo de créditos do dia);
             sem chave: avisa que o orçamento é 1.000 créditos/dia (insuficiente p/ uma base).
  ORCID    — faz uma leitura de teste (registro de exemplo oficial) com ou sem ORCID_TOKEN.

Uso: python scripts/check_apis.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from coauthor_rec.secrets import get_secret  # noqa: E402


def _req(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def main():
    key, tok = get_secret("OPENALEX_API_KEY"), get_secret("ORCID_TOKEN")
    print("=== OpenAlex ===")
    if key:
        st, hd, body = _req(f"https://api.openalex.org/rate-limit?api_key={key}")
        if st == 200:
            print("  chave OK — saldo:", json.dumps(json.loads(body), ensure_ascii=False)[:500])
        else:
            print(f"  chave RECUSADA (HTTP {st}): {body[:200]!r}")
    else:
        st, hd, _ = _req("https://api.openalex.org/works?per_page=1&select=id")
        print(f"  sem OPENALEX_API_KEY — orçamento sem chave: {hd.get('X-RateLimit-Limit')} créditos/dia, "
              f"restam {hd.get('X-RateLimit-Remaining')} (HTTP {st}). Uma base consome ~3 mil.")
    print("=== ORCID ===")
    h = {"Accept": "application/json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    st, _, _ = _req("https://pub.orcid.org/v3.0/0000-0002-1825-0097/record", h)
    modo = "com token (100 mil leituras/dia)" if tok else "anônimo (25 mil leituras/dia por IP)"
    print(f"  leitura de teste: HTTP {st} — {modo}"
          + ("" if st == 200 else " — 429/503 = cota ou limite de taxa atingido; 401 = token inválido"))


if __name__ == "__main__":
    main()
