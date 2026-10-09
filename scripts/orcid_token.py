"""Obtém o token /read-public da API pública do ORCID e o grava no .env — sem imprimi-lo.

Pré-requisito: no .env do projeto (fora do git), as credenciais do cliente público
registrado em orcid.org → Developer Tools:

    ORCID_CLIENT_ID=APP-XXXXXXXXXXXXXXXX
    ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Uso:
    python3 scripts/orcid_token.py            # ORCID de produção
    python3 scripts/orcid_token.py --sandbox  # se as credenciais foram criadas no sandbox
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from coauthor_rec.secrets import _ENV, get_secret  # noqa: E402


def clean(v: str | None) -> str | None:
    return v.strip().strip('"').strip("'") if v else v


def save_token(token: str, env: Path = _ENV) -> None:
    lines = env.read_text().splitlines() if env.exists() else []
    lines = [ln for ln in lines if not ln.strip().startswith("ORCID_TOKEN=")]
    lines.append(f"ORCID_TOKEN={token}")
    env.write_text("\n".join(lines) + "\n")
    os.chmod(env, 0o600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", action="store_true")
    args = ap.parse_args()
    cid, sec = clean(get_secret("ORCID_CLIENT_ID")), clean(get_secret("ORCID_CLIENT_SECRET"))
    if not cid or not sec:
        sys.exit("Faltam ORCID_CLIENT_ID e/ou ORCID_CLIENT_SECRET no .env (veja o cabeçalho deste script).")
    if cid.upper().startswith("APP-APP-"):
        print("aviso: client_id com 'APP-' duplicado — corrigindo para a forma APP-XXXX…")
        cid = cid[4:]
    if not re.fullmatch(r"APP-[A-Z0-9]{16}", cid):
        print(f"aviso: client_id fora do formato esperado (APP- + 16 caracteres): começa com {cid[:8]!r}…, "
              f"{len(cid)} caracteres")
    host = "sandbox.orcid.org" if args.sandbox else "orcid.org"
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "scope": "/read-public",
                                   "grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(f"https://{host}/oauth/token", data=data,
                                 headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")[:300]
        print(f"ERRO HTTP {e.code} em {host}: {err}")
        if e.code in (400, 401):
            print("→ client_id/secret não reconhecidos. Confira: (1) copiou exatamente, sem espaços;"
                  " (2) o secret é o da MESMA aplicação; (3) se registrou em sandbox.orcid.org,"
                  " rode com --sandbox.")
        sys.exit(1)
    tok = body.get("access_token")
    if not tok:
        sys.exit(f"Resposta sem access_token: {sorted(body)}")
    save_token(tok)
    anos = (body.get("expires_in") or 0) / 31_536_000
    print(f"OK — token /read-public salvo no .env como ORCID_TOKEN (válido por ~{anos:.0f} anos; "
          f"escopo {body.get('scope')}). O token não foi impresso.")


if __name__ == "__main__":
    main()
