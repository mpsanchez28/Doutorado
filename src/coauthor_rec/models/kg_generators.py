"""Geradores de candidatos por meta-caminho do KG T0 (docs/LINHA_BASE.md).

Cada gerador é um meta-caminho da ontologia que liga um autor-alvo a outros autores, com um
escore. O mesmo objeto serve a dois papéis:

- **baseline**: ordenar os candidatos pelo próprio escore do meta-caminho;
- **oráculo**: o conjunto de candidatos (escore > 0) define o que o gerador ENXERGA. Um
  ranqueador perfeito restrito a ele acerta no máximo esse conjunto — é o teto do gerador.

Meta-caminhos (A = autor, W = trabalho, I = instituição, T = tópico, V = periódico, O =
organização ORCID):

=================  =====================================  ==================================
gerador            meta-caminho                            escore
=================  =====================================  ==================================
coautoria_cn       A–W–A–W–A (2 saltos)                    vizinhos em comum
coautoria_aa       idem                                    Adamic-Adar (Σ 1/log grau)
coautoria_ra       idem                                    Resource Allocation (Σ 1/grau)
ppr                passeio aleatório A–W–A com reinício    PageRank personalizado
instituicao        A–atInstitution–I–A                     Σ 1/log(tamanho de I)
org_mae            A–I–partOf*–I_raiz–I–A                  idem, na raiz da hierarquia
topico             A–W–hasTopic–T–W–A                      cosseno dos perfis de tópico
periodico          A–W–publishedIn–V–W–A                   Σ 1/log(tamanho de V)
citacao            A–W–cites–W–A (qualquer sentido)        nº de citações entre os dois
acoplamento        A–W–cites–R–cites–W–A                   referências em comum (normalizado)
ex_colegas         A–hasEmployment–O–A (períodos sobrep.)  nº de organizações em comum
texto_tfidf        A–W~W–A (similaridade de resumo)        cosseno TF-IDF médio
popularidade       —                                       grau em T0 (igual para todos)
=================  =====================================  ==================================

Os ``coautoria_*`` e o ``ppr`` usam só trabalhos dentro do teto de coautores (mesmo grafo do
gabarito). As relações semânticas usam todos os trabalhos de T0: um consórcio não gera
coautoria par a par, mas ainda informa tema, periódico e instituição.

Todos os escores são calculados para um LOTE de alvos de uma vez, com álgebra esparsa — é o
que torna viável Medicina (≈1 milhão de pessoas). Candidatos excluídos: o próprio alvo e os
coautores de T0 (a tarefa é prever coautorias NOVAS).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp

GENERATORS = ("coautoria_cn", "coautoria_aa", "coautoria_ra", "ppr", "instituicao", "org_mae",
              "topico", "periodico", "citacao", "acoplamento", "ex_colegas", "texto_tfidf",
              "popularidade")
# relações do KG além da coautoria (as que a ablação liga/desliga)
KG_RELATIONS = ("instituicao", "org_mae", "topico", "periodico", "citacao", "acoplamento",
                "ex_colegas")


def _incidence(rows, cols, row_index: dict, col_index: dict | None = None, values=None):
    """Matriz esparsa (len(row_index) × n_cols) a partir de pares (linha, coluna)."""
    if col_index is None:
        col_index = {c: i for i, c in enumerate(pd.unique(pd.Series(cols)))}
    r = pd.Series(rows).map(row_index)
    c = pd.Series(cols).map(col_index)
    ok = r.notna() & c.notna()
    v = np.ones(int(ok.sum()), dtype=np.float32) if values is None else np.asarray(values, np.float32)[ok.values]
    m = sp.csr_matrix((v, (r[ok].astype(int).values, c[ok].astype(int).values)),
                      shape=(len(row_index), len(col_index)), dtype=np.float32)
    m.sum_duplicates()
    return m, col_index


def _binarize(m):
    m = m.tocsr(copy=True)
    m.data[:] = 1.0
    return m


def _row_normalize(m):
    s = np.asarray(m.sum(axis=1)).ravel()
    s[s == 0] = 1.0
    return sp.diags(1.0 / s) @ m


class KGIndex:
    """Matrizes esparsas do KG T0 indexadas pelas pessoas de T0."""

    def __init__(self, kg: dict[str, pd.DataFrame], cap: int, cutoff: int, texts: pd.Series | None = None,
                 ppr_alpha: float = 0.15, ppr_iters: int = 20, verbose: bool = True):
        self.cutoff, self.verbose = cutoff, verbose
        self.ppr_alpha, self.ppr_iters = ppr_alpha, ppr_iters
        wrote = kg["wrote"]
        self.authors = np.array(sorted(wrote["author_id"].unique()))
        self.aidx = {a: i for i, a in enumerate(self.authors)}
        n = len(self.authors)

        # autor × trabalho (todos de T0) e só trabalhos dentro do teto (grafo de coautoria)
        self.AW, self.widx = _incidence(wrote["author_id"], wrote["work_id"], self.aidx)
        size = np.asarray(self.AW.sum(axis=0)).ravel()
        keep = sp.diags(((size >= 2) & (size <= cap)).astype(np.float32))
        self.AWc = (self.AW @ keep).tocsr()
        self.AWc.eliminate_zeros()
        self.AWcT = self.AWc.T.tocsr()
        self.degree = self._degrees()

        # instituição e organização-mãe (raiz da hierarquia)
        ai = kg["atInstitution"][["author_id", "institution_id"]].drop_duplicates()
        self.AI, _ = _incidence(ai["author_id"], ai["institution_id"], self.aidx)
        parent = kg["partOf"].groupby("child")["parent"].agg(list).to_dict()
        roots = ai["institution_id"].map(lambda i: self._root(i, parent))
        ar = pd.DataFrame({"a": ai["author_id"], "r": roots}).drop_duplicates()
        self.AR, _ = _incidence(ar["a"], ar["r"], self.aidx)

        # tópicos: perfil = Σ score dos tópicos dos trabalhos, normalizado (L2 para cosseno)
        ht = kg["hasTopic"]
        WT, _ = _incidence(ht["work_id"], ht["topic_id"], self.widx, values=ht["score"].values)
        self.AT = self._l2(self.AW @ WT)

        # periódico
        pv = kg["publishedIn"]
        WV, _ = _incidence(pv["work_id"], pv["venue_id"], self.widx)
        self.AV = _binarize(self.AW @ WV)

        # citação entre trabalhos do corpus (W × W) e referências em geral (W × R)
        ct = kg["cites"]
        inside = ct[ct["cited_id"].isin(self.widx)]
        self.WW, _ = _incidence(inside["work_id"], inside["cited_id"], self.widx, self.widx)
        self.WR, _ = _incidence(ct["work_id"], ct["cited_id"], self.widx)
        rcount = np.asarray(self.WR.sum(axis=0)).ravel()           # quantos trabalhos citam R
        self.WRw = (self.WR @ sp.diags(1.0 / np.log(1.0 + np.maximum(rcount, 1.0)))).tocsr()
        n_refs = np.asarray((self.AW @ self.WR).sum(axis=1)).ravel()
        self.ref_norm = np.sqrt(np.maximum(n_refs, 1.0)).astype(np.float32)

        # vínculos ORCID (ex-colegas): (autor, org, início, fim)
        emp = kg["hasEmployment"]
        self.emp = emp[emp["author_id"].isin(self.aidx)].copy()
        self.emp["end"] = self.emp["end"].fillna(cutoff)

        # texto: TF-IDF por trabalho; perfil do autor = média dos vetores dos trabalhos
        self.WX = None
        if texts is not None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            t = texts.reindex(list(self.widx)).fillna("")
            vec = TfidfVectorizer(sublinear_tf=True, min_df=2, max_df=0.5, stop_words="english",
                                  max_features=2 ** 17, dtype=np.float32)
            self.WX = vec.fit_transform(t.values).tocsr()
            self.AWn = _row_normalize(self.AW).tocsr()

        # tamanhos para Adamic-Adar de instituição/periódico
        self.inst_w = 1.0 / np.log(2.0 + np.asarray(self.AI.sum(axis=0)).ravel())
        self.root_w = 1.0 / np.log(2.0 + np.asarray(self.AR.sum(axis=0)).ravel())
        self.venue_w = 1.0 / np.log(2.0 + np.asarray(self.AV.sum(axis=0)).ravel())
        # PPR: passeio autor → trabalho → autor no grafo bipartido (com teto)
        self.P_aw = _row_normalize(self.AWc).tocsr()
        self.P_wa = _row_normalize(self.AWcT).tocsr()
        if verbose:
            print(f"[kg-index] {n} pessoas, {len(self.widx)} trabalhos, {self.AI.shape[1]} instituições, "
                  f"{self.AV.shape[1]} periódicos, {self.AT.shape[1]} tópicos, {self.WW.nnz} citações internas, "
                  f"{self.WR.shape[1]} obras referenciadas, {self.emp['author_id'].nunique()} pessoas com vínculo ORCID",
                  flush=True)

    # ------------------------------------------------------------------ utilitários
    @staticmethod
    def _root(i, parent, depth=0):
        ps = parent.get(i)
        if not ps or depth > 10:
            return i
        return KGIndex._root(ps[-1], parent, depth + 1)

    @staticmethod
    def _l2(m):
        m = m.tocsr()
        nrm = np.sqrt(np.asarray(m.multiply(m).sum(axis=1)).ravel())
        nrm[nrm == 0] = 1.0
        return (sp.diags(1.0 / nrm) @ m).tocsr()

    def _degrees(self, chunk: int = 20000) -> np.ndarray:
        """Nº de coautores distintos em T0 (grafo com teto), em blocos para caber na memória."""
        deg = np.zeros(self.AWc.shape[0], dtype=np.float32)
        for s in range(0, self.AWc.shape[0], chunk):
            m = _binarize(self.AWc[s:s + chunk] @ self.AWcT)
            has_self = np.asarray(m[np.arange(m.shape[0]), np.arange(s, s + m.shape[0])]).ravel() > 0
            deg[s:s + chunk] = np.diff(m.indptr) - has_self
        return deg

    def neighbors(self, rows) -> sp.csr_matrix:
        m = _binarize(self.AWc[rows] @ self.AWcT).tocoo()
        keep = m.col != np.asarray(rows)[m.row]              # tira o próprio alvo
        return sp.csr_matrix((m.data[keep], (m.row[keep], m.col[keep])), shape=m.shape)

    # ------------------------------------------------------------------ escores por lote
    def scores(self, name: str, rows: np.ndarray) -> np.ndarray:
        """Matriz densa (len(rows) × n_pessoas) de escores do gerador ``name``."""
        f = getattr(self, f"_s_{name}")
        out = f(rows)
        return np.asarray(out.todense() if sp.issparse(out) else out, dtype=np.float32)

    def _two_hop(self, rows, weight):
        N = self.neighbors(rows)                              # alvos × pessoas (vizinhos)
        U = np.unique(N.indices)
        if len(U) == 0:
            return sp.csr_matrix((len(rows), len(self.authors)), dtype=np.float32)
        CU = _binarize(self.AWc[U] @ self.AWcT)               # vizinhos × pessoas
        w = weight(self.degree[U])
        return N[:, U] @ sp.diags(w.astype(np.float32)) @ CU

    def _s_coautoria_cn(self, rows):
        return self._two_hop(rows, lambda d: np.ones_like(d))

    def _s_coautoria_aa(self, rows):
        return self._two_hop(rows, lambda d: 1.0 / np.log(np.maximum(d, 2.0)))

    def _s_coautoria_ra(self, rows):
        return self._two_hop(rows, lambda d: 1.0 / np.maximum(d, 1.0))

    def _s_ppr(self, rows):
        n = len(self.authors)
        E = np.zeros((n, len(rows)), dtype=np.float32)
        E[rows, np.arange(len(rows))] = 1.0
        X = E.copy()
        a = self.ppr_alpha
        for _ in range(self.ppr_iters):
            X = (1 - a) * (self.P_wa.T @ (self.P_aw.T @ X)) + a * E
        return X.T

    def _s_instituicao(self, rows):
        return self.AI[rows] @ sp.diags(self.inst_w.astype(np.float32)) @ self.AI.T

    def _s_org_mae(self, rows):
        return self.AR[rows] @ sp.diags(self.root_w.astype(np.float32)) @ self.AR.T

    def _s_topico(self, rows):
        return self.AT[rows] @ self.AT.T

    def _s_periodico(self, rows):
        return self.AV[rows] @ sp.diags(self.venue_w.astype(np.float32)) @ self.AV.T

    def _s_citacao(self, rows):
        aw = self.AW[rows]
        out = (aw @ self.WW) @ self.AW.T                     # alvo cita
        out = out + (aw @ self.WW.T) @ self.AW.T             # alvo é citado
        return out

    def _s_acoplamento(self, rows):
        q = self.AW[rows] @ self.WRw                         # alvos × obras referenciadas
        s = np.asarray(((q @ self.WR.T) @ self.AW.T).todense(), dtype=np.float32)
        return s / self.ref_norm[rows][:, None] / self.ref_norm[None, :]

    def _s_ex_colegas(self, rows):
        out = np.zeros((len(rows), len(self.authors)), dtype=np.float32)
        if not len(self.emp):
            return out
        tg = pd.DataFrame({"author_id": self.authors[rows], "k": np.arange(len(rows))})
        mine = self.emp.merge(tg, on="author_id")
        if not len(mine):
            return out
        pair = mine.merge(self.emp, on="org_key", suffixes=("", "_o"))
        pair = pair[(pair["author_id_o"] != pair["author_id"])
                    & (pair["start"] <= pair["end_o"]) & (pair["start_o"] <= pair["end"])]
        pair = pair.drop_duplicates(["k", "author_id_o", "org_key"])
        cnt = pair.groupby(["k", "author_id_o"]).size().reset_index(name="n")
        out[cnt["k"].values, cnt["author_id_o"].map(self.aidx).values] = cnt["n"].values
        return out

    def _s_texto_tfidf(self, rows):
        if self.WX is None:
            return np.zeros((len(rows), len(self.authors)), dtype=np.float32)
        q = self.AWn[rows] @ self.WX                         # alvos × termos (perfil médio)
        sw = self.WX @ q.T                                   # trabalhos × alvos
        return (self.AWn @ sw).T

    def _s_popularidade(self, rows):
        return np.tile(self.degree, (len(rows), 1))


def rank_candidates(scores: np.ndarray, exclude: list[set[int]], tiebreak: np.ndarray,
                    top: int = 1000) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Para cada linha: (top-``top`` índices por escore, desempate por ``tiebreak``) e o conjunto
    completo de candidatos com escore > 0 (o que o gerador alcança). Exclui ``exclude[i]``."""
    ranked, pools = [], []
    for i in range(scores.shape[0]):
        s = scores[i].copy()
        ex = np.fromiter(exclude[i], dtype=np.int64) if exclude[i] else np.empty(0, np.int64)
        s[ex] = 0.0
        pool = np.flatnonzero(s > 0)
        pools.append(pool)
        if len(pool) > top:                                  # mantém todos os empatados no corte
            kth = np.partition(s[pool], len(pool) - top)[len(pool) - top]
            cand = pool[s[pool] >= kth]
        else:
            cand = pool
        order = np.lexsort((-tiebreak[cand], -s[cand]))      # escore ↓, depois grau ↓
        ranked.append(cand[order][:top])
    return ranked, pools
