"""Higienização de autores: garante a cadeia PESSOA → AUTORIA → TRABALHO → INSTITUIÇÃO
→ COAUTORIA antes de qualquer modelagem. Método e justificativa: docs/HIGIENIZACAO.md.

Etapas (critérios em configs/filters.yaml › hygiene):
  1. Pessoa canônica — ORCID quando existe (funde author_ids fragmentados do OpenAlex);
     author_id com >1 ORCID = identidade fundida (conflito).
  2. Nível de evidência de cada AUTORIA (autor×trabalho):
       A  ORCID + DOI do trabalho reivindicado no registro ORCID da pessoa
       B  ORCID declarado na publicação (metadata do editor), não reivindicado
       C  sem ORCID; author_id resolvido e nome consistente
       X  rejeitada: conflito de identidade ou nome do artigo incompatível
     ORCID cujo registro lista nomes incompatíveis com o autor rebaixa A/B → C.
  3. Vínculo autor–instituição de cada autoria:
       I1 instituição confirmada no ORCID (ROR, ou nome+país, com ano compatível)
       I2 instituição identificada por ROR no OpenAlex (não confirmada no ORCID)
       I3 sem instituição identificada
  4. Coautoria — só entre autorias não rejeitadas e ≥ min_edge_level; confiança da
     aresta = menor nível das duas pontas (graph usa o corpus higienizado).
  5. Elegibilidade do autor como alvo/semente (E1–E8) + funil de atrito.

Nada aqui acessa a rede: os claims do ORCID entram prontos (data/orcid.py).
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict

import pandas as pd

LEVELS = ("A", "B", "C", "X")
RANK = {lv: i for i, lv in enumerate(LEVELS)}
PARTICLES = {"de", "da", "do", "dos", "das", "di", "du", "del", "della", "la", "le",
             "van", "von", "der", "den", "ten", "ter", "y", "e", "al", "el", "bin", "ibn"}


# --------------------------------------------------------------------------- #
# Nomes
# --------------------------------------------------------------------------- #
def normalize_name(name) -> str:
    """casefold, sem acentos, pontuação de nome vira espaço, espaços colapsados."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    for ch in ".,-'’()":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _tokens(name) -> set[str]:
    return {t for t in normalize_name(name).split() if len(t) >= 2 and t not in PARTICLES}


def names_compatible(a, b) -> bool | None:
    """True se os nomes compartilham ao menos um token significativo (≥2 letras, não
    partícula) — tolera iniciais, ordem invertida e acentos. None se algum faltar."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return None
    return bool(ta & tb)


def _jlist(v) -> list:
    if isinstance(v, list):
        return v
    if not isinstance(v, str) or not v:
        return []
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else []
    except ValueError:
        return []


# --------------------------------------------------------------------------- #
# 1. Pessoa canônica
# --------------------------------------------------------------------------- #
def canonicalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Adiciona ``canonical_id`` (``orcid:<ORCID>`` ou author_id) e ``id_conflict``."""
    df = df.copy()
    has_orcid = "author_orcid" in df.columns
    orcids_of = (df.dropna(subset=["author_orcid"]).groupby("author_id")["author_orcid"]
                 .agg(lambda s: set(s)) if has_orcid else pd.Series(dtype=object))
    conflict = {a for a, s in orcids_of.items() if len(s) > 1}
    canon = {a: f"orcid:{next(iter(s))}" for a, s in orcids_of.items() if len(s) == 1}
    df["id_conflict"] = df["author_id"].isin(conflict)
    df["canonical_id"] = df["author_id"].map(canon).fillna(df["author_id"])
    ids_per_orcid = (pd.Series(canon).reset_index().groupby(0)["index"].nunique()
                     if canon else pd.Series(dtype=int))
    stats = {
        "author_ids": int(df["author_id"].nunique()),
        "persons_canonical": int(df.loc[~df["id_conflict"], "canonical_id"].nunique()),
        "orcids": int(len(ids_per_orcid)),
        "orcids_fragmented": int((ids_per_orcid > 1).sum()),
        "author_ids_merged": int(ids_per_orcid[ids_per_orcid > 1].sum()) if len(ids_per_orcid) else 0,
        "author_ids_conflict": len(conflict),
        "orcid_available": bool(has_orcid),
    }
    return df, stats


# --------------------------------------------------------------------------- #
# 2–3. Nível de evidência da autoria e do vínculo institucional
# --------------------------------------------------------------------------- #
def _affil_index(claims: dict) -> dict:
    """Pré-processa as afiliações de cada ORCID: RORs e (nome normalizado, país)."""
    idx = {}
    for o, c in (claims or {}).items():
        affs = c.get("affiliations") or []
        idx[o] = [(a.get("ror"), normalize_name(a.get("name")), (a.get("country") or "").upper(),
                   a.get("start"), a.get("end")) for a in affs]
    return idx


def _year_ok(year, start, end, tol=1) -> bool:
    if year is None:
        return True
    if start and year < start - tol:
        return False
    if end and year > end + tol:
        return False
    return True


def authorship_levels(df: pd.DataFrame, claims: dict | None = None,
                      reject_name_mismatch: bool = True) -> pd.DataFrame:
    """Adiciona ``level`` (A/B/C/X), ``inst_level`` (I1/I2/I3) e as evidências usadas."""
    claims = claims or {}
    affil = _affil_index(claims)
    df = df.copy()
    years = pd.to_datetime(df["publication_date"], errors="coerce").dt.year
    out_level, out_inst, out_claimed, out_name_ok, out_orcid_name = [], [], [], [], []
    col = lambda c: df[c] if c in df.columns else pd.Series([None] * len(df), index=df.index)
    for orcid, doi, name, raw, conflict, rors, inames, ctry, yr in zip(
            col("author_orcid"), col("doi"), col("author_name"), col("raw_author_name"),
            df["id_conflict"], col("institution_rors"), col("institution_names"),
            col("countries"), years):
        orcid = orcid if isinstance(orcid, str) and orcid else None
        c = claims.get(orcid) if orcid else None
        name_ok = names_compatible(name, raw)
        claimed = bool(c and c.get("exists") and isinstance(doi, str)
                       and doi.lower() in set(c.get("dois") or []))
        orcid_name_ok = None
        if c and c.get("exists") and c.get("names"):
            orcid_name_ok = any(names_compatible(name, n) for n in c["names"])

        if conflict or (reject_name_mismatch and name_ok is False):
            level = "X"
        elif orcid and orcid_name_ok is not False:
            level = "A" if claimed else "B"
        else:
            level = "C"          # sem ORCID, ou ORCID cujo nome não confirma a pessoa

        rr = {str(r) for r in _jlist(rors)}
        inst = "I3"
        if rr:
            inst = "I2"
        if orcid and orcid in affil:
            nn = {normalize_name(n) for n in _jlist(inames) if n}
            cc = {str(x).upper() for x in _jlist(ctry) if x}
            y = None if pd.isna(yr) else int(yr)
            for a_ror, a_name, a_cty, st, en in affil[orcid]:
                if not _year_ok(y, st, en):
                    continue
                if (a_ror and a_ror in rr) or (a_name and a_name in nn and (not cc or a_cty in cc)):
                    inst = "I1"
                    break
        out_level.append(level); out_inst.append(inst); out_claimed.append(claimed)
        out_name_ok.append(name_ok); out_orcid_name.append(orcid_name_ok)
    df["level"], df["inst_level"], df["doi_claimed"] = out_level, out_inst, out_claimed
    df["name_ok"], df["orcid_name_ok"] = out_name_ok, out_orcid_name
    return df


# --------------------------------------------------------------------------- #
# 5. Elegibilidade do autor (E1–E8) e funil
# --------------------------------------------------------------------------- #
CRITERIA = [
    ("E1_orcid", "possui ORCID (identidade verificável)"),
    ("E2_sem_conflito", "sem ORCIDs conflitantes no mesmo author_id"),
    ("E3_reivindicado", "≥ min_claimed_works trabalhos reivindicados no ORCID"),
    ("E4_instituicao", "≥ min_works_with_ror autorias com instituição identificada"),
    ("E5_atividade", "≥ min_works trabalhos na área"),
    ("E6_plausivel", "produtividade e multiafiliação plausíveis por ano"),
    ("E7_nome", "nome consistente entre artigo, OpenAlex e ORCID"),
    ("E8_equipe", "≥1 trabalho dentro do teto de coautores (gera aresta)"),
]


def _n_components(lists: list[list[str]]) -> int:
    """Nº de grupos de instituições: une as que aparecem juntas em alguma lista."""
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for lst in lists:
        for i in lst:
            find(i)
        for a, b in zip(lst, lst[1:]):
            parent[find(a)] = find(b)
    return len({find(x) for x in parent})


def author_table(df: pd.DataFrame, crit: dict, max_coauthors: int | None) -> pd.DataFrame:
    """Uma linha por pessoa canônica com as métricas, os critérios E1–E8 e ``eligible``."""
    df = df.copy()
    df["year"] = pd.to_datetime(df["publication_date"], errors="coerce").dt.year
    team = df.groupby("work_id")["author_id"].nunique()
    df["team_size"] = df["work_id"].map(team)
    ok = df[df["level"] != "X"]

    g_all = df.groupby("canonical_id")
    g = ok.groupby("canonical_id")
    t = pd.DataFrame(index=pd.Index(sorted(df["canonical_id"].unique()), name="canonical_id"))
    t["author_name"] = g_all["author_name"].agg(lambda s: s.dropna().iloc[0] if s.notna().any() else None)
    t["has_orcid"] = t.index.str.startswith("orcid:")
    t["id_conflict"] = g_all["id_conflict"].any()
    t["n_works"] = g["work_id"].nunique()
    t["n_claimed"] = ok[ok["level"] == "A"].groupby("canonical_id")["work_id"].nunique()
    t["n_with_ror"] = ok[ok["inst_level"].isin(["I1", "I2"])].groupby("canonical_id")["work_id"].nunique()
    t["n_inst_confirmed"] = ok[ok["inst_level"] == "I1"].groupby("canonical_id")["work_id"].nunique()
    t["max_works_per_year"] = (ok.drop_duplicates(["canonical_id", "work_id"])
                               .groupby(["canonical_id", "year"]).size().groupby(level=0).max())

    # E6 — grupos de afiliação por ano: instituições co-listadas numa MESMA autoria são
    # um grupo (multiafiliação legítima: univ.+hospital+instituto). Grupos DESCONEXOS no
    # mesmo ano indicam pessoas distintas fundidas sob um id.
    groups_year = defaultdict(list)
    for cid, yr, blob in zip(ok["canonical_id"], ok["year"],
                             ok["institution_ids"] if "institution_ids" in ok else [None] * len(ok)):
        insts = [i for i in _jlist(blob) if i]
        if insts:
            groups_year[(cid, yr)].append(insts)
    miy = defaultdict(int)
    for (cid, _), lists in groups_year.items():
        miy[cid] = max(miy[cid], _n_components(lists))
    t["max_inst_same_year"] = pd.Series(miy)
    t["name_mismatch_rate"] = g_all.apply(
        lambda s: float(((s["name_ok"] == False) | (s["orcid_name_ok"] == False)).mean()))  # noqa: E712
    cap = max_coauthors or float("inf")
    t["small_team"] = ok.groupby("canonical_id")["team_size"].min() <= cap
    t = t.fillna({"n_works": 0, "n_claimed": 0, "n_with_ror": 0, "n_inst_confirmed": 0,
                  "max_works_per_year": 0, "max_inst_same_year": 0, "small_team": False})

    t["E1_orcid"] = t["has_orcid"] | (not crit.get("require_orcid", True))
    t["E2_sem_conflito"] = ~t["id_conflict"] | (not crit.get("forbid_id_conflict", True))
    t["E3_reivindicado"] = t["n_claimed"] >= crit.get("min_claimed_works", 1)
    t["E4_instituicao"] = t["n_with_ror"] >= crit.get("min_works_with_ror", 1)
    t["E5_atividade"] = t["n_works"] >= crit.get("min_works", 2)
    t["E6_plausivel"] = ((t["max_works_per_year"] <= crit.get("max_works_per_year", 30)) &
                         (t["max_inst_same_year"] <= crit.get("max_institutions_same_year", 3)))
    t["E7_nome"] = t["name_mismatch_rate"] <= crit.get("max_name_mismatch_rate", 0.0)
    t["E8_equipe"] = t["small_team"] | (not crit.get("require_small_team_work", True))
    t["eligible"] = t[[c for c, _ in CRITERIA]].all(axis=1)
    return t


def funnel(t: pd.DataFrame) -> list[dict]:
    """Atrito sequencial E1→E8 (quantos restam após cada critério) + reprovação isolada."""
    rows, mask = [{"etapa": "pessoas canônicas", "restantes": int(len(t))}], pd.Series(True, index=t.index)
    for c, desc in CRITERIA:
        mask &= t[c]
        rows.append({"etapa": f"{c} — {desc}", "restantes": int(mask.sum()),
                     "reprovam_isolado": int((~t[c]).sum())})
    return rows


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def hygienize(merged: pd.DataFrame, claims: dict | None, cfg: dict,
              max_coauthors: int | None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Aplica a higienização completa.

    Retorna (corpus_higienizado, tabela_de_autores, relatório). No corpus, ``author_id``
    passa a ser a pessoa canônica (original em ``author_id_openalex``), autorias X e abaixo
    de ``min_edge_level`` saem, e cada (work, pessoa) aparece uma vez.
    """
    df, canon_stats = canonicalize(merged)
    df = authorship_levels(df, claims, cfg.get("reject_name_mismatch", True))
    table = author_table(df, cfg.get("author_criteria", {}), max_coauthors)

    min_lv = cfg.get("min_edge_level", "C")
    keep = df["level"].map(RANK) <= RANK[min_lv]
    corpus = (df[keep].rename(columns={"author_id": "author_id_openalex"})
              .rename(columns={"canonical_id": "author_id"})
              .drop_duplicates(["work_id", "author_id"]).reset_index(drop=True))

    lv = df["level"].value_counts().reindex(LEVELS, fill_value=0)
    il = df.loc[df["level"] != "X", "inst_level"].value_counts().reindex(["I1", "I2", "I3"], fill_value=0)
    report = {
        "canonicalizacao": canon_stats,
        "autorias": {"total": int(len(df)), **{f"nivel_{k}": int(v) for k, v in lv.items()}},
        "vinculo_institucional": {k: int(v) for k, v in il.items()},
        "min_edge_level": min_lv,
        "corpus_higienizado": {"autorias": int(len(corpus)), "works": int(corpus["work_id"].nunique()),
                               "pessoas": int(corpus["author_id"].nunique())},
        "funil_elegibilidade": funnel(table),
        "elegiveis": int(table["eligible"].sum()),
        "criterios": cfg.get("author_criteria", {}),
    }
    return corpus, table, report
