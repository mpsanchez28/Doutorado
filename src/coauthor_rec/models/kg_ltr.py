"""Re-ranqueador aprendido (LambdaMART) sobre os meta-caminhos do KG — base da ablação.

Arquitetura em duas etapas:

1. **Geração**: candidatos = top-``pool`` da União RRF dos geradores (``kg_generators``). O
   conjunto é FIXO em todas as configurações da ablação, de modo que a ablação de atributos
   mede só o ganho de ORDENAÇÃO de cada relação (o ganho de GERAÇÃO é medido à parte, pelo
   Alcance@1000 da união sem a relação).
2. **Ordenação**: LightGBM ``lambdarank`` com um grupo por alvo, otimizando diretamente a
   ordem da lista (Burges, 2010), em vez de classificar pares isolados como o RF anterior.

Atributos por par (alvo, candidato), em grupos que a ablação liga e desliga:

==============  ==============================================================
grupo           atributos
==============  ==============================================================
coautoria       escore e posição de vizinhos comuns, Adamic-Adar, RA, PageRank
instituicao     idem para mesma instituição e mesma organização-mãe
topico          idem para tópicos
periodico       idem para periódico
citacao         idem para citação direta e acoplamento bibliográfico
ex_colegas      idem para ex-colegas ORCID
texto           idem para TF-IDF
atividade       grau, nº de trabalhos, anos desde o primeiro/último trabalho (alvo e candidato)
==============  ==============================================================

Tudo vem do KG T0 — nenhum atributo usa informação posterior ao corte.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .kg_generators import GENERATORS, KGIndex, rank_candidates

GROUPS = {
    "coautoria": ["coautoria_cn", "coautoria_aa", "coautoria_ra", "ppr"],
    "instituicao": ["instituicao", "org_mae"],
    "topico": ["topico"],
    "periodico": ["periodico"],
    "citacao": ["citacao", "acoplamento"],
    "ex_colegas": ["ex_colegas"],
    "texto": ["texto_tfidf", "texto_specter2"],
}
# anos RELATIVOS ao corte do KG ("há quantos anos"): o mesmo atributo significa o mesmo num KG
# de 2018 (treino temporal) e num de 2021 (teste)
ACTIVITY = ["grau_alvo", "trab_alvo", "anos_desde_ultimo_alvo", "grau_cand", "trab_cand",
            "anos_desde_primeiro_cand", "anos_desde_ultimo_cand"]
RRF_K = 60
NO_RANK = 2000            # posição atribuída a quem não está no top-1000 do gerador


def feature_columns(groups, gens=None) -> list[str]:
    """Colunas dos ``groups``; com ``gens``, só as dos geradores efetivamente calculados
    (ex.: ``texto_specter2`` só existe quando há embeddings da base)."""
    cols = []
    for g in groups:
        if g == "atividade":
            cols += ACTIVITY
        else:
            for gen in GROUPS[g]:
                if gens is None or gen in gens:
                    cols += [f"{gen}", f"{gen}_pos"]
    return cols


def activity_table(kg: dict, idx: KGIndex) -> dict[str, np.ndarray]:
    w = kg["wrote"]
    by = w.groupby("author_id")["year"].agg(["size", "min", "max"]).reindex(idx.authors)
    c = float(idx.cutoff)
    return {"trab": by["size"].fillna(0).to_numpy(np.float32),
            "desde_primeiro": (c - by["min"].fillna(c)).to_numpy(np.float32),
            "desde_ultimo": (c - by["max"].fillna(c)).to_numpy(np.float32)}


def _pair_features(idx: KGIndex, act: dict, S: dict, R: dict, gens, i: int, r: int,
                   cand: np.ndarray, rrf_vals: np.ndarray, rel_i: np.ndarray) -> dict:
    """Atributos dos pares (alvo da linha ``i`` do lote, cada candidato em ``cand``)."""
    order = np.lexsort((-idx.degree[cand], -rrf_vals))           # posição na união RRF
    rrf_pos = np.empty(len(cand), dtype=np.float32)
    rrf_pos[order] = np.arange(1, len(cand) + 1)
    f = {"cand": cand, "rrf": rrf_vals, "rrf_pos": rrf_pos}
    for g in gens:
        if g == "popularidade":
            continue
        f[g] = S[g][i, cand]
        pos = np.full(len(cand), NO_RANK, dtype=np.float32)
        _, ia, ib = np.intersect1d(cand, R[g][i], return_indices=True)
        pos[ia] = ib + 1
        f[f"{g}_pos"] = pos
    f.update({"grau_alvo": idx.degree[r], "trab_alvo": act["trab"][r],
              "anos_desde_ultimo_alvo": act["desde_ultimo"][r],
              "grau_cand": idx.degree[cand], "trab_cand": act["trab"][cand],
              "anos_desde_primeiro_cand": act["desde_primeiro"][cand],
              "anos_desde_ultimo_cand": act["desde_ultimo"][cand]})
    f["rotulo"] = np.isin(cand, rel_i).astype(np.int8)
    return f


def build_pairs(idx: KGIndex, kg: dict, targets: list, train_graph: dict, gt: dict,
                gens=GENERATORS, pool: int = 1000, top: int = 1000, batch: int = 32,
                union_groups=None, verbose: bool = True):
    """Monta a tabela de pares (alvo, candidato) com atributos e rótulo.

    Retorna (pares, alcance_uniao): ``pares`` tem uma linha por candidato do pool de cada alvo;
    ``alcance_uniao`` mede, por alvo, os acertos no top-``pool`` da união e da união SEM cada
    grupo (ablação da GERAÇÃO).
    """
    act = activity_table(kg, idx)
    union = [g for g in gens if g != "popularidade"]
    groups_ = union_groups or {k: v for k, v in GROUPS.items()}
    variants = {"todos": union, **{f"sem_{k}": [g for g in union if g not in v] for k, v in groups_.items()}}
    in_t0 = [a for a in targets if a in idx.aidx]
    frames, reach = [], []
    n = len(idx.authors)
    for b in range(0, len(in_t0), batch):
        tb = in_t0[b:b + batch]
        rows = np.array([idx.aidx[a] for a in tb])
        exclude = [{idx.aidx[c] for c in train_graph.get(a, ()) if c in idx.aidx} | {idx.aidx[a]} for a in tb]
        S, R = {}, {}
        for g in gens:
            S[g] = idx.scores(g, rows)
            R[g], _ = rank_candidates(S[g], exclude, idx.degree, top=top)
        rel = [np.array([idx.aidx[c] for c in gt.get(a, ()) if c in idx.aidx], dtype=np.int64) for a in tb]
        for i, a in enumerate(tb):
            # ablação da geração: alcance do top-pool da união com e sem cada grupo
            rr = {"alvo": a, "n_relevantes": len(gt.get(a, ()))}
            for vname, vg in variants.items():
                score = np.zeros(n, dtype=np.float32)
                for g in vg:
                    score[R[g][i]] += 1.0 / (RRF_K + np.arange(1, len(R[g][i]) + 1))
                cand = np.flatnonzero(score > 0)
                cand = cand[np.lexsort((-idx.degree[cand], -score[cand]))][:pool]
                rr[vname] = int(np.isin(rel[i], cand).sum())
                if vname == "todos":
                    pool_i, rrf_i = cand, score[cand]
            reach.append(rr)
            if len(pool_i) == 0:
                continue
            f = _pair_features(idx, act, S, R, gens, i, rows[i], pool_i, rrf_i, rel[i])
            f["alvo"] = a
            frames.append(pd.DataFrame(f))
        del S
        if verbose:
            print(f"[ltr] pares: {b + len(tb)}/{len(in_t0)} alvos", flush=True)
    pairs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return pairs, pd.DataFrame(reach)


def cascade_pairs(idx: KGIndex, kg: dict, targets: list, train_graph: dict, gt: dict,
                  gens=GENERATORS, top: int = 1000, keep: int = 1000, batch: int = 32,
                  stage1=None, stage1_cols=None, neg_rate: float | None = None, seed: int = 42,
                  verbose: bool = True):
    """Geração seletiva em cascata (docs/GERACAO_SELETIVA.md).

    Conjunto ampliado por alvo = união dos top-``top`` de TODOS os geradores (inclusive
    popularidade) — em Medicina, ~13 mil candidatos. Dois modos:

    - ``neg_rate``: devolve os pares do conjunto ampliado com todos os positivos e uma fração
      ``neg_rate`` dos negativos (treino da etapa 1, pontual);
    - ``stage1``: modelo já treinado; pontua o conjunto ampliado e devolve os ``keep`` melhores
      (o conjunto que a etapa 2 ordena), com a coluna ``nota_etapa1``.

    ``alcance`` (por alvo): acertos no conjunto ampliado, no top-``keep`` da União RRF e no
    top-``keep`` da etapa 1 — a comparação decisiva da geração.
    """
    act = activity_table(kg, idx)
    union = [g for g in gens if g != "popularidade"]
    in_t0 = [a for a in targets if a in idx.aidx]
    rng = np.random.default_rng(seed)
    frames, reach = [], []
    n = len(idx.authors)
    for b in range(0, len(in_t0), batch):
        tb = in_t0[b:b + batch]
        rows = np.array([idx.aidx[a] for a in tb])
        exclude = [{idx.aidx[c] for c in train_graph.get(a, ()) if c in idx.aidx} | {idx.aidx[a]} for a in tb]
        S, R = {}, {}
        for g in gens:
            S[g] = idx.scores(g, rows)
            R[g], _ = rank_candidates(S[g], exclude, idx.degree, top=top)
        rel = [np.array([idx.aidx[c] for c in gt.get(a, ()) if c in idx.aidx], dtype=np.int64) for a in tb]
        for i, a in enumerate(tb):
            score = np.zeros(n, dtype=np.float32)
            for g in union:
                score[R[g][i]] += 1.0 / (RRF_K + np.arange(1, len(R[g][i]) + 1))
            wide = np.unique(np.concatenate([R[g][i] for g in gens]))
            rr = {"alvo": a, "n_relevantes": len(gt.get(a, ())), "conjunto_ampliado": len(wide),
                  "hits_ampliado": int(np.isin(rel[i], wide).sum())}
            rrf_top = wide[np.lexsort((-idx.degree[wide], -score[wide]))][:keep]
            rr["hits_rrf"] = int(np.isin(rel[i], rrf_top).sum())
            if len(wide) == 0:
                reach.append(rr)
                continue
            f = pd.DataFrame(_pair_features(idx, act, S, R, gens, i, rows[i], wide, score[wide], rel[i]))
            f.insert(0, "alvo", a)
            if stage1 is not None:
                f["nota_etapa1"] = stage1.predict(f[stage1_cols].to_numpy(np.float32), raw_score=True)
                f = f.sort_values(["nota_etapa1", "rrf"], ascending=False, kind="stable").head(keep)
                rr["hits_etapa1"] = int(f["rotulo"].sum())
            elif neg_rate is not None:
                f = f[(f["rotulo"] == 1) | (rng.random(len(f)) < neg_rate)]
            reach.append(rr)
            frames.append(f.reset_index(drop=True))
        del S
        if verbose:
            print(f"[cascata] {b + len(tb)}/{len(in_t0)} alvos", flush=True)
    pairs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return pairs, pd.DataFrame(reach)


def stage1_params(seed: int = 42) -> dict:
    """Etapa 1 (pontual): classificador binário regularizado como o da etapa 2."""
    return dict(objective="binary", n_estimators=300, learning_rate=0.05, num_leaves=15,
                min_child_samples=200, reg_lambda=5.0, subsample=0.8, subsample_freq=1,
                colsample_bytree=0.8, random_state=seed, verbose=-1, n_jobs=8)


def folds(targets, k: int = 5, seed: int = 42) -> dict:
    """Partição dos alvos em ``k`` dobras (embaralhamento reprodutível)."""
    rng = np.random.default_rng(seed)
    t = np.array(sorted(targets))
    rng.shuffle(t)
    return {a: i % k for i, a in enumerate(t)}


def lgbm_params(seed: int = 42) -> dict:
    """Hiperparâmetros FIXOS em todas as bases e configurações da ablação.

    Positivos são raros (≈0,2% dos pares; ~400 por dobra de treino em Economia): com os valores
    padrão (400 árvores de 31 folhas, 20 amostras por folha) o modelo sobreajustava e ficava
    ABAIXO da União RRF sem aprendizado (NDCG@10 3,27 vs 3,71 em Economia). Árvores rasas, folhas
    com ≥200 pares e regularização L2 corrigem isso (4,02). Escolhidos em Economia entre 4
    variantes (padrão; regularizado lambdarank; regularizado binário; truncamento 1000) e
    mantidos nas outras bases — docs/ABLACAO_KG.md."""
    return dict(objective="lambdarank", n_estimators=200, learning_rate=0.05, num_leaves=7,
                min_child_samples=200, reg_lambda=5.0, subsample=0.8, subsample_freq=1,
                colsample_bytree=0.8, lambdarank_truncation_level=100, random_state=seed,
                verbose=-1, n_jobs=8)


def cross_val_rank(pairs: pd.DataFrame, cols: list[str], fold_of: dict, seed: int = 42,
                   want_shap: bool = False):
    """Treina/aplica o LambdaMART por dobra de alvos. Retorna (escores, importâncias, shap).

    ``escores``: Series alinhada a ``pairs`` com o escore previsto (fora da dobra de treino).
    """
    import lightgbm as lgb
    fold = pairs["alvo"].map(fold_of).to_numpy()
    pred = np.zeros(len(pairs), dtype=np.float64)
    gain = np.zeros(len(cols))
    shap = np.zeros(len(cols))
    n_shap = 0
    for k in sorted(set(fold)):
        tr, te = fold != k, fold == k
        dtr = pairs[tr]
        sizes = dtr.groupby("alvo", sort=False).size()
        # LightGBM exige linhas contíguas por grupo: pares já estão ordenados por alvo
        m = lgb.LGBMRanker(**lgbm_params(seed))
        m.fit(dtr[cols].to_numpy(np.float32), dtr["rotulo"].to_numpy(), group=sizes.to_numpy())
        X = pairs.loc[te, cols].to_numpy(np.float32)
        pred[te] = m.predict(X)
        gain += m.booster_.feature_importance("gain")
        if want_shap:
            c = m.predict(X, pred_contrib=True)[:, :-1]
            shap += np.abs(c).sum(axis=0)
            n_shap += len(X)
    imp = pd.Series(gain / gain.sum() if gain.sum() else gain, index=cols)
    sh = pd.Series(shap / max(n_shap, 1), index=cols) if want_shap else None
    return pd.Series(pred, index=pairs.index), imp, sh


def train_apply(train: pd.DataFrame, test: pd.DataFrame, cols: list[str], seed: int = 42,
                params: dict | None = None, want_shap: bool = False):
    """Treina UM LambdaMART em ``train`` (ex.: KG de 2018 → rótulos 2019–2021) e aplica em ``test``
    (KG de 2021 → T1). Retorna (escores de ``test``, importância por ganho, |SHAP| médio)."""
    import lightgbm as lgb
    tr = train[train.groupby("alvo", sort=False)["rotulo"].transform("max") > 0]   # grupos sem positivo não ensinam
    m = lgb.LGBMRanker(**(params or lgbm_params(seed)))
    m.fit(tr[cols].to_numpy(np.float32), tr["rotulo"].to_numpy(),
          group=tr.groupby("alvo", sort=False).size().to_numpy())
    X = test[cols].to_numpy(np.float32)
    gain = m.booster_.feature_importance("gain")
    imp = pd.Series(gain / gain.sum() if gain.sum() else gain, index=cols)
    sh = pd.Series(np.abs(m.predict(X, pred_contrib=True)[:, :-1]).mean(axis=0), index=cols) if want_shap else None
    return pd.Series(m.predict(X), index=test.index), imp, sh
