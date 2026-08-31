"""Avaliação das variantes do 2 etapas após o diagnóstico de alcance (text_reach).

Variantes:
  A. 2-stage atual (m_text=100, fill_to_k=False, fallback=True)  -> deve REPRODUZIR
     os números publicados (validação da réplica do protocolo)
  B. 2-stage m_text=200
  C. 2-stage fill_to_k=True (cauda adaptativa até K), fallback=True
  D. 2-stage fill_to_k=True, fallback=False
Referências: Texto (SciBERT), Híbrido RF.

Significância: Wilcoxon pareado (per-author) das variantes vs A, vs Texto e vs RF em
R@10 / R@200 / NDCG@10, α com Bonferroni. Também diff das listas top-10 em cold
(anomalia R@10 0,19 vs 1,14 do texto).

Uso: PYTHONHASHSEED=0 python scripts/two_stage_v2_eval.py
"""
import json, os, sys
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from coauthor_rec.config import load_config, set_seed
from coauthor_rec.data.clean import clean_and_merge
from coauthor_rec.split.temporal import chronological_split, build_ground_truth
from coauthor_rec.eval.evaluate import evaluate_models
from coauthor_rec.models.hybrid_rf import HybridCoauthorRecommender
from coauthor_rec.models.text_sim import TextSimilarityRecommender
from coauthor_rec.models.two_stage import TwoStageReranker

print("PYTHONHASHSEED =", os.environ.get("PYTHONHASHSEED", "(não fixado!)"))
EVAL = load_config("eval"); set_seed(EVAL["seed"])
CAP = EVAL["graph"]["max_coauthors_per_work"]; KS = EVAL["evaluation"]["k_values"]
ROOT = os.path.join(os.path.dirname(__file__), "..")

# corpus (a partir dos CSVs brutos, réplica validada: 13.924 works / 45.732 autores)
auth = pd.read_csv(f"{ROOT}/data/raw_ai/authorships.csv")
works = pd.read_csv(f"{ROOT}/data/raw_ai/works.csv")
merged = clean_and_merge(auth, works, min_year=EVAL["split"]["min_year"],
                         language=EVAL["split"]["language"])
print(f"corpus: {merged['work_id'].nunique()} works / {merged['author_id'].nunique()} autores")

train_df, test_df = chronological_split(merged, train_fraction=EVAL["split"]["train_fraction"])
train_graph, gt = build_ground_truth(train_df, test_df, max_coauthors_per_work=CAP)
t0 = set(train_df["author_id"])
gt = {a: v for a, v in gt.items() if a in t0}
print(f"alvos T0-ativos: {len(gt)}")

# embedding textual de autor (média SciBERT dos works de T0), catálogo = autores de T0
blob = np.load(f"{ROOT}/data/processed/text_emb/scibert.npz", allow_pickle=True)
emb, wids = blob["emb"].astype(np.float32), blob["work_ids"]
wpos = {w: i for i, w in enumerate(wids)}
authors = sorted(t0); author_map = {a: i for i, a in enumerate(authors)}
A = np.zeros((len(authors), emb.shape[1]), np.float32); cnt = np.zeros(len(authors), np.float32)
for aid, wid in zip(train_df["author_id"], train_df["work_id"]):
    j = wpos.get(wid)
    if j is not None:
        A[author_map[aid]] += emb[j]; cnt[author_map[aid]] += 1
A /= np.clip(cnt, 1.0, None)[:, None]

print("Treinando modelos…")
models = [
    TextSimilarityRecommender(A, author_map, name="Text (SciBERT)"),
    HybridCoauthorRecommender(max_coauthors_per_work=CAP).fit(train_df),
    TwoStageReranker(A, author_map, max_coauthors_per_work=CAP, m_text=100,
                     name="2st-A atual (m=100)").fit(train_df),
    TwoStageReranker(A, author_map, max_coauthors_per_work=CAP, m_text=200,
                     name="2st-B m=200").fit(train_df),
    TwoStageReranker(A, author_map, max_coauthors_per_work=CAP, m_text=100, fill_to_k=True,
                     name="2st-C fill-to-K").fit(train_df),
    TwoStageReranker(A, author_map, max_coauthors_per_work=CAP, m_text=100, fill_to_k=True,
                     popularity_fallback=False, name="2st-D fill-to-K sem fallback").fit(train_df),
]

print("Avaliando…")
res = evaluate_models(models, gt, train_graph, k_values=KS,
                      warm_min=EVAL["regimes"]["warm_min_coauthors"],
                      cool_min=EVAL["regimes"]["cool_min_coauthors"],
                      t0_authors=t0, show_progress=False)

# ---- tabela ----
print(f"\n{'modelo':32s} | {'R@10':>6} {'R@50':>6} {'R@200':>6} | {'NDCG@10':>8} | "
      f"{'cold R@10':>9} {'cold R@200':>10} | {'cool R@200':>10} | {'warm R@200':>10}")
for m in models:
    r = res[m.name]
    o = r["overall"]; c = r["by_regime"]["cold"]; co = r["by_regime"]["cool"]; w = r["by_regime"]["warm"]
    print(f"{m.name:32s} | {100*o[10]['R']:6.2f} {100*o[50]['R']:6.2f} {100*o[200]['R']:6.2f} | "
          f"{100*o[10]['NDCG']:8.2f} | {100*c[10]['R']:9.2f} {100*c[200]['R']:10.2f} | "
          f"{100*co[200]['R']:10.2f} | {100*w[200]['R']:10.2f}")

# ---- significância pareada (Wilcoxon), variantes vs referências ----
def paired(name_a, name_b, metric, k):
    key = {"R": "R", "NDCG": "NDCG"}[metric]
    xa = np.array(res[name_a]["per_author"][k][key]); xb = np.array(res[name_b]["per_author"][k][key])
    d = xa - xb
    if np.allclose(d, 0):
        return {"diff_pp": 0.0, "p": 1.0}
    stat, p = wilcoxon(xa, xb, zero_method="zsplit")
    return {"diff_pp": float(100 * d.mean()), "p": float(p)}

tests = {}
pairs = [("2st-B m=200", "2st-A atual (m=100)"), ("2st-C fill-to-K", "2st-A atual (m=100)"),
         ("2st-D fill-to-K sem fallback", "2st-A atual (m=100)"),
         ("2st-C fill-to-K", "Text (SciBERT)"), ("2st-C fill-to-K", "Hybrid (Graph + RandomForest)")]
metrics = [("R", 10), ("R", 200), ("NDCG", 10)]
alpha = 0.05 / (len(pairs) * len(metrics))
print(f"\nWilcoxon pareado (α Bonferroni = {alpha:.4g}):")
for a, b in pairs:
    for met, k in metrics:
        t = paired(a, b, met, k)
        tests[f"{a} vs {b} | {met}@{k}"] = t
        sig = "*" if t["p"] < alpha else " "
        print(f"  {a:30s} vs {b:28s} {met}@{k:<4} Δ={t['diff_pp']:+6.2f}pp  p={t['p']:.3g} {sig}")

# ---- diff cold: por que o 2 etapas atual perde do texto no topo? ----
cold_authors = [a for a in gt if len(train_graph.get(a, set())) == 0]
text_m, twoA = models[0], models[2]
same10 = mismatches = 0
example = None
for a in cold_authors:
    r1 = [x for x in text_m.recommend(a, top_n=600) if x not in train_graph.get(a, set())][:10]
    r2 = [x for x in twoA.recommend(a, top_n=600) if x not in train_graph.get(a, set())][:10]
    if r1 == r2:
        same10 += 1
    else:
        mismatches += 1
        if example is None:
            example = {"author": a, "text10": r1, "twostage10": r2}
print(f"\ncold (n={len(cold_authors)}): top-10 idêntico ao texto em {same10}; diferente em {mismatches}")
if example:
    print("exemplo de divergência:", json.dumps(example, ensure_ascii=False)[:400])

out = {"protocol": {"seed": EVAL["seed"], "cap": CAP, "n_targets": len(gt),
                    "hashseed": os.environ.get("PYTHONHASHSEED")},
       "results": {m.name: {"overall": {k: res[m.name]["overall"][k] for k in KS},
                            "by_regime": {r: {k: res[m.name]["by_regime"][r][k] for k in KS}
                                          for r in ["warm", "cool", "cold"]}} for m in models},
       "significance": tests,
       "cold_top10_diff": {"identical": same10, "different": mismatches, "example": example}}
os.makedirs(f"{ROOT}/runs/two_stage_v2", exist_ok=True)
json.dump(out, open(f"{ROOT}/runs/two_stage_v2/results.json", "w"), indent=1)
print("\nsalvo em runs/two_stage_v2/results.json")
