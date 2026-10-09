"""Camada 3 — trajetórias de carreira a partir do registro ORCID (cache da higienização).

Para cada pessoa canônica com ORCID: vínculos profissionais e formação declarados, com
organização, país e período. Deles derivam-se (i) um resumo de carreira (nº de
empregadores, países, ano da última formação concluída como aproximação do início da
carreira independente) e (ii) a relação **ex-colegas**: duas pessoas com vínculo na mesma
organização em períodos sobrepostos — preditor clássico de colaboração.

**Controle de vazamento:** o ORCID é uma fotografia do presente. Toda consulta recebe um
``cutoff`` (ano do corte T0) e só considera vínculos iniciados até ele; períodos em aberto
são truncados no corte.

Identidade da organização (``org_key``): ROR quando o ORCID traz; senão o identificador
desambiguado do próprio ORCID (RINGGOLD/GRID/FUNDREF — consistente entre registros); senão
nome normalizado + país.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ..data.hygiene import normalize_name


def org_key(aff: dict) -> str | None:
    if aff.get("ror"):
        return f"ror:{aff['ror']}"
    if aff.get("other_id"):
        return aff["other_id"]
    n = normalize_name(aff.get("name"))
    return f"name:{n}|{(aff.get('country') or '').upper()}" if n else None


def career_affiliations(person_ids, cache_dir: str | Path, employment_sections,
                        education_sections) -> pd.DataFrame:
    """Uma linha por vínculo declarado no ORCID, para as pessoas ``orcid:<id>`` do corpus."""
    cache = Path(cache_dir)
    emp, edu = set(employment_sections), set(education_sections)
    rows = []
    for pid in person_ids:
        if not isinstance(pid, str) or not pid.startswith("orcid:"):
            continue
        f = cache / f"{pid[6:]}.json"
        if not f.exists():
            continue
        c = json.loads(f.read_text())
        for a in c.get("affiliations") or []:
            kind = "employment" if a["section"] in emp else "education" if a["section"] in edu else None
            if not kind:
                continue
            rows.append({"author_id": pid, "kind": kind, "section": a["section"],
                         "org_key": org_key(a), "org_name": a.get("name"),
                         "country": (a.get("country") or "").upper() or None,
                         "ror": a.get("ror"), "start": a.get("start"), "end": a.get("end")})
    return pd.DataFrame(rows, columns=["author_id", "kind", "section", "org_key", "org_name",
                                       "country", "ror", "start", "end"])


def career_summary(aff: pd.DataFrame, cutoff: int | None = None) -> pd.DataFrame:
    """Resumo por pessoa, usando só vínculos iniciados até ``cutoff`` (se dado)."""
    a = aff if cutoff is None else aff[aff["start"].isna() | (aff["start"] <= cutoff)]
    e = a[a["kind"] == "employment"]
    d = a[a["kind"] == "education"]
    s = pd.DataFrame(index=pd.Index(sorted(aff["author_id"].unique()), name="author_id"))
    s["n_empregadores"] = e.groupby("author_id")["org_key"].nunique()
    s["n_paises"] = a.groupby("author_id")["country"].nunique()
    s["primeiro_emprego"] = e.groupby("author_id")["start"].min()
    ends = d["end"] if cutoff is None else d["end"].where(d["end"] <= cutoff)
    s["ultima_formacao"] = ends.groupby(d["author_id"]).max()
    return s.fillna({"n_empregadores": 0, "n_paises": 0})


class ExColleagueIndex:
    """Índice organização → [(pessoa, início, fim)] para consultar ex-colegas por par."""

    def __init__(self, aff: pd.DataFrame, kinds=("employment",), tolerance: int = 0):
        self.tol = tolerance
        self.by_org = defaultdict(list)
        self.orgs_of = defaultdict(set)
        sub = aff[aff["kind"].isin(kinds) & aff["org_key"].notna()]
        sub = sub[sub["start"].notna() | sub["end"].notna()]     # período desconhecido: fora
        for p, k, s, e in zip(sub["author_id"], sub["org_key"], sub["start"], sub["end"]):
            s = None if pd.isna(s) else int(s)
            e = None if pd.isna(e) else int(e)
            self.by_org[k].append((p, s, e))
            self.orgs_of[p].add(k)

    def _period(self, s, e, cutoff):
        lo = s if s is not None else (e if e is not None else 0)
        hi = e if e is not None else (cutoff if cutoff is not None else 9999)
        if cutoff is not None:
            if lo > cutoff:
                return None                                      # começou depois do corte
            hi = min(hi, cutoff)
        return lo, hi

    def shared(self, a: str, b: str, cutoff: int | None = None) -> list[str]:
        """Organizações em que ``a`` e ``b`` estiveram ao mesmo tempo (até o ``cutoff``)."""
        out = []
        for k in self.orgs_of.get(a, set()) & self.orgs_of.get(b, set()):
            pa = [self._period(s, e, cutoff) for p, s, e in self.by_org[k] if p == a]
            pb = [self._period(s, e, cutoff) for p, s, e in self.by_org[k] if p == b]
            if any(x and y and min(x[1], y[1]) - max(x[0], y[0]) >= -self.tol
                   for x in pa for y in pb):
                out.append(k)
        return out


def coverage(aff: pd.DataFrame, n_orcid_persons: int) -> dict:
    per = aff.groupby("author_id")
    emp = aff[aff["kind"] == "employment"]
    return {
        "pessoas_com_orcid": int(n_orcid_persons),
        "com_algum_vinculo": round(per.ngroups / max(n_orcid_persons, 1), 4),
        "com_emprego_datado": round(emp[emp["start"].notna()]["author_id"].nunique()
                                    / max(n_orcid_persons, 1), 4),
        "com_formacao_concluida": round(aff[(aff["kind"] == "education") & aff["end"].notna()]
                                        ["author_id"].nunique() / max(n_orcid_persons, 1), 4),
        "org_key_por_ror": round(float(aff["org_key"].str.startswith("ror:").mean()), 4) if len(aff) else 0,
        "org_key_por_id_orcid": round(float(aff["org_key"].str.match(r"^[A-Z]+:").mean()), 4) if len(aff) else 0,
        "vinculos": int(len(aff)),
    }
