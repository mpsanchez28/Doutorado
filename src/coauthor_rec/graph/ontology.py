"""Ontologia do KG: exportação de uma amostra em RDF (ABox) conforme a TBox
``configs/ontology/coauthor-rec.ttl``, validação e consultas SPARQL de demonstração.

A amostra parte de autores-alvo sorteados e inclui seus trabalhos, os coautores desses
trabalhos, as autorias (com níveis de evidência), as coautorias reificadas, os tópicos com
a hierarquia SKOS, as instituições (com ROR, tipo, país, hierarquia e Wikidata) e as
trajetórias ORCID — com ``owl:sameAs`` para ORCID, DOI, ROR e Wikidata.
"""
from __future__ import annotations

import itertools
import json
import re

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, FOAF, OWL, PROV, RDF, RDFS, SKOS, XSD

CR = Namespace("https://github.com/mpsanchez28/Doutorado/ontology#")
KG = Namespace("https://github.com/mpsanchez28/Doutorado/kg/")
SCHEMA = Namespace("https://schema.org/")
SRC_OPENALEX = URIRef("https://openalex.org")
SRC_ORCID = URIRef("https://orcid.org")


def _u(kind: str, ident) -> URIRef:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(ident))
    return KG[f"{kind}/{safe}"]


def _jl(v) -> list:
    if isinstance(v, list):
        return v
    try:
        out = json.loads(v) if isinstance(v, str) and v else []
        return out if isinstance(out, list) else []
    except ValueError:
        return []


def _year(v):
    return Literal(int(v), datatype=XSD.gYear) if v is not None and not pd.isna(v) else None


def build_sample_graph(corpus: pd.DataFrame, targets: list[str], wt: pd.DataFrame,
                       inst: pd.DataFrame, aff: pd.DataFrame | None = None,
                       colleagues=None, cutoff: int | None = None,
                       max_coauthors: int = 50) -> Graph:
    """Monta o grafo RDF da vizinhança dos ``targets`` (pessoas canônicas)."""
    g = Graph()
    for p, ns in (("cr", CR), ("kg", KG), ("schema", SCHEMA), ("foaf", FOAF), ("skos", SKOS),
                  ("dcterms", DCTERMS), ("prov", PROV), ("owl", OWL)):
        g.bind(p, ns)

    works = set(corpus.loc[corpus["author_id"].isin(set(targets)), "work_id"])
    sub = corpus[corpus["work_id"].isin(works)]
    people = set(sub["author_id"])
    years = pd.to_datetime(sub["publication_date"], errors="coerce").dt.year

    # --- pessoas
    for pid, grp in sub.groupby("author_id"):
        a = _u("author", pid)
        g.add((a, RDF.type, CR.Author))
        name = grp["author_name"].dropna()
        if len(name):
            g.add((a, FOAF.name, Literal(name.iloc[0])))
        if pid.startswith("orcid:"):
            g.add((a, CR.orcid, Literal(pid[6:])))
            g.add((a, OWL.sameAs, URIRef(f"https://orcid.org/{pid[6:]}")))
        for oa in grp.get("author_id_openalex", pd.Series(dtype=str)).dropna().unique():
            g.add((a, CR.openalexId, Literal(oa)))
            g.add((a, OWL.sameAs, URIRef(f"https://openalex.org/{oa}")))

    # --- trabalhos e autorias
    first = sub.drop_duplicates("work_id").set_index("work_id")
    for wid, row in first.iterrows():
        w = _u("work", wid)
        g.add((w, RDF.type, CR.Work))
        g.add((w, CR.openalexId, Literal(wid)))
        g.add((w, OWL.sameAs, URIRef(f"https://openalex.org/{wid}")))
        if isinstance(row.get("title"), str):
            g.add((w, DCTERMS.title, Literal(row["title"])))
        y = pd.to_datetime(row.get("publication_date"), errors="coerce")
        if not pd.isna(y):
            g.add((w, CR.year, _year(y.year)))
        if isinstance(row.get("doi"), str):
            g.add((w, CR.doi, Literal(row["doi"])))
            g.add((w, OWL.sameAs, URIRef(f"https://doi.org/{row['doi']}")))
        g.add((w, PROV.wasDerivedFrom, SRC_OPENALEX))
    for r in sub.itertuples(index=False):
        w, a = _u("work", r.work_id), _u("author", r.author_id)
        s = _u("authorship", f"{r.work_id}_{r.author_id}")
        g.add((s, RDF.type, CR.Authorship))
        g.add((w, CR.hasAuthorship, s))
        g.add((s, CR.agent, a))
        g.add((a, CR.wrote, w))
        if getattr(r, "level", None):
            g.add((s, CR.evidenceLevel, Literal(r.level)))
        if getattr(r, "inst_level", None):
            g.add((s, CR.institutionLevel, Literal(r.inst_level)))
        if isinstance(getattr(r, "author_position", None), str):
            g.add((s, CR.authorPosition, Literal(r.author_position)))
        for i in _jl(getattr(r, "institution_ids", None)):
            g.add((s, CR.atInstitution, _u("institution", i)))
            g.add((a, CR.affiliatedWith, _u("institution", i)))
        if getattr(r, "level", None) == "A":
            g.add((s, PROV.wasDerivedFrom, SRC_ORCID))

    # --- coautorias reificadas (trabalhos dentro do teto)
    pairs: dict[tuple, list] = {}
    for wid, grp in sub.groupby("work_id"):
        ids = sorted(set(grp["author_id"]))
        if 1 < len(ids) <= max_coauthors:
            yr = pd.to_datetime(grp["publication_date"].iloc[0], errors="coerce")
            lv = dict(zip(grp["author_id"], grp.get("level", pd.Series(["C"] * len(grp), index=grp.index))))
            for a, b in itertools.combinations(ids, 2):
                pairs.setdefault((a, b), []).append((None if pd.isna(yr) else yr.year,
                                                     max(lv.get(a, "C"), lv.get(b, "C"))))
    for (a, b), occ in pairs.items():
        ua, ub = _u("author", a), _u("author", b)
        g.add((ua, CR.coAuthorWith, ub))
        c = _u("coauthorship", f"{a}__{b}")
        g.add((c, RDF.type, CR.CoAuthorship))
        g.add((c, CR.between, ua))
        g.add((c, CR.between, ub))
        g.add((c, CR.weight, Literal(len(occ), datatype=XSD.integer)))
        ys = [y for y, _ in occ if y]
        if ys:
            g.add((c, CR.firstYear, _year(min(ys))))
        g.add((c, CR.evidenceLevel, Literal(max(l for _, l in occ))))   # menor confiança

    # --- tópicos com hierarquia SKOS
    wts = wt[wt["work_id"].isin(works)]
    for r in wts.itertuples(index=False):
        w, t = _u("work", r.work_id), _u("topic", r.topic_id)
        g.add((w, CR.hasTopic, t))
        ta = _u("topicassignment", f"{r.work_id}_{r.topic_id}")
        g.add((ta, RDF.type, CR.TopicAssignment))
        g.add((w, CR.topicAssignment, ta))
        g.add((ta, CR.topic, t))
        g.add((ta, CR.score, Literal(round(r.score, 4), datatype=XSD.decimal)))
    for r in wts.drop_duplicates("topic_id").itertuples(index=False):
        chain = [("topic", r.topic_id, r.topic, CR.Topic), ("subfield", r.subfield_id, r.subfield, CR.Subfield),
                 ("field", r.field_id, r.field, CR.Field), ("domain", r.domain_id, r.domain, CR.Domain)]
        for (k1, i1, n1, c1), nxt in itertools.zip_longest(chain, chain[1:]):
            u = _u(k1, i1)
            g.add((u, RDF.type, c1))
            g.add((u, SKOS.prefLabel, Literal(n1)))
            g.add((u, SKOS.inScheme, CR.TopicScheme))
            if nxt:
                g.add((u, CR.broader, _u(nxt[0], nxt[1])))

    # --- instituições
    used = {i for v in sub["institution_ids"] for i in _jl(v)}
    it = inst.set_index("institution_id")
    for iid in used | {p for i in used if i in it.index for p in it.loc[i, "parents"]}:
        u = _u("institution", iid)
        g.add((u, RDF.type, CR.Institution))
        if iid not in it.index:
            continue
        r = it.loc[iid]
        if isinstance(r["name"], str):
            g.add((u, SCHEMA.name, Literal(r["name"])))
        if isinstance(r["ror"], str):
            g.add((u, CR.ror, Literal(r["ror"])))
            g.add((u, OWL.sameAs, URIRef(f"https://ror.org/{r['ror']}")))
        if isinstance(r["wikidata"], str):
            g.add((u, OWL.sameAs, URIRef(f"http://www.wikidata.org/entity/{r['wikidata']}")))
        if isinstance(r["type"], str):
            g.add((u, CR.institutionType, Literal(r["type"])))
        if isinstance(r["country"], str):
            cu = _u("country", r["country"])
            g.add((u, CR.locatedIn, cu))
            g.add((cu, RDF.type, CR.Country))
        for p in r["parents"]:
            g.add((u, CR.partOf, _u("institution", p)))

    # --- trajetórias ORCID (até o corte) e ex-colegas
    if aff is not None and len(aff):
        ror_to_inst = {r: i for i, r in zip(inst["institution_id"], inst["ror"]) if isinstance(r, str)}
        inst_uris = {_u("institution", v) for v in ror_to_inst.values()}
        a2 = aff[aff["author_id"].isin(people)]
        if cutoff is not None:
            a2 = a2[a2["start"].isna() | (a2["start"] <= cutoff)]
        for n, r in enumerate(a2.itertuples(index=False)):
            node = _u(r.kind, f"{r.author_id}_{n}")
            g.add((node, RDF.type, CR.Employment if r.kind == "employment" else CR.Education))
            g.add((_u("author", r.author_id), CR.hasEmployment if r.kind == "employment"
                   else CR.hasEducation, node))
            orgu = (_u("institution", ror_to_inst[r.ror]) if isinstance(r.ror, str) and r.ror in ror_to_inst
                    else _u("org", r.org_key))
            if orgu not in inst_uris:
                g.add((orgu, RDF.type, FOAF.Organization))
                if isinstance(r.org_name, str):
                    g.add((orgu, SCHEMA.name, Literal(r.org_name)))
            g.add((node, CR.organization, orgu))
            for prop, val in ((CR.startYear, r.start), (CR.endYear, r.end)):
                lit = _year(val)
                if lit is not None:
                    g.add((node, prop, lit))
            g.add((node, PROV.wasDerivedFrom, SRC_ORCID))
        if colleagues is not None:
            orcid_people = sorted(p for p in people if p.startswith("orcid:"))
            for a, b in itertools.combinations(orcid_people, 2):
                if colleagues.shared(a, b, cutoff):
                    g.add((_u("author", a), CR.exColleagueOf, _u("author", b)))
    return g


def validate(abox: Graph, tbox: Graph) -> dict:
    """Toda classe e propriedade do namespace ``cr:`` usada na ABox deve estar na TBox."""
    declared = {s for s in tbox.subjects() if str(s).startswith(str(CR))}
    used_cls = {o for o in abox.objects(None, RDF.type) if str(o).startswith(str(CR))}
    used_prop = {p for p in abox.predicates() if str(p).startswith(str(CR))}
    return {"triplas": len(abox),
            "classes_usadas": len(used_cls), "propriedades_usadas": len(used_prop),
            "nao_declaradas": sorted(str(x) for x in (used_cls | used_prop) - declared)}


QUERIES = {
    "instancias_por_classe": """
        SELECT ?classe (COUNT(?s) AS ?n) WHERE { ?s a ?classe .
          FILTER(STRSTARTS(STR(?classe), STR(cr:))) } GROUP BY ?classe ORDER BY DESC(?n)""",
    # Parte de autores FOCO (VALUES ?a) — o motor SPARQL do rdflib faz junções em Python puro;
    # sem âncora, coautores × trabalhos × tópicos explode em amostras de dezenas de milhares
    # de triplas.
    "coautores_que_compartilham_subcampo": """
        SELECT ?a ?b ?subcampo (COUNT(DISTINCT ?w) AS ?trabalhos) WHERE {
          VALUES ?a { %FOCO% }
          ?a cr:coAuthorWith ?b . ?a cr:wrote ?w . ?w cr:hasTopic ?t . ?t cr:broader ?sf .
          ?sf skos:prefLabel ?subcampo .
          FILTER EXISTS { ?b cr:wrote ?w2 . ?w2 cr:hasTopic ?t2 . ?t2 cr:broader ?sf }
        } GROUP BY ?a ?b ?subcampo ORDER BY DESC(?trabalhos) LIMIT 5""",
    "coautores_ex_colegas": """
        SELECT (COUNT(*) AS ?n) WHERE { ?a cr:coAuthorWith ?b . ?a cr:exColleagueOf ?b .
          FILTER(STR(?a) < STR(?b)) }""",
    "autorias_por_nivel_de_evidencia": """
        SELECT ?nivel (COUNT(?s) AS ?n) WHERE { ?s a cr:Authorship ; cr:evidenceLevel ?nivel }
        GROUP BY ?nivel ORDER BY ?nivel""",
    "instituicoes_com_hierarquia": """
        SELECT ?filha ?mae WHERE { ?i cr:partOf ?p . ?i schema:name ?filha . ?p schema:name ?mae }
        LIMIT 5""",
}


def run_queries(g: Graph, focus: list[str] | None = None, max_focus: int = 3) -> dict:
    """Executa as consultas de demonstração. ``focus`` = pessoas canônicas usadas como âncora
    nas consultas de vizinhança (as primeiras ``max_focus``)."""
    ns = {"cr": CR, "skos": SKOS, "schema": SCHEMA}
    if focus:
        foco = " ".join(f"<{_u('author', p)}>" for p in focus[:max_focus])
    else:
        com_coautor = sorted({a for a in g.subjects(CR.coAuthorWith, None)}, key=str)
        foco = " ".join(f"<{a}>" for a in com_coautor[:max_focus])
    out = {}
    for name, q in QUERIES.items():
        rows = g.query(q.replace("%FOCO%", foco), initNs=ns)
        out[name] = [[str(v).split("/")[-1].split("#")[-1] if isinstance(v, URIRef) else
                      (v.toPython() if v is not None else None) for v in row] for row in rows]
    return out
