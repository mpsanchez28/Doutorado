"""Piloto do enriquecimento GenAI: roda OpenAI e Claude num pequeno conjunto de abstracts
e compara a concordância dos atributos extraídos. Uso: python scripts/enrich_pilot.py [N]
"""
import json
import sys
from pathlib import Path

import pandas as pd

from coauthor_rec.config import resolve
from coauthor_rec.text.embed import paper_texts
from coauthor_rec.text.enrich import enrich_papers, PAPER_TYPES, CONTRIBUTIONS, STYLES

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30

merged = pd.read_parquet(resolve("data/processed/corpus.parquet"))
work_ids, texts = paper_texts(merged)
work_ids, texts = work_ids[:N], texts[:N]
print(f"Piloto em {N} abstracts × 2 provedores…")

oa = {r["work_id"]: r for r in enrich_papers(texts, work_ids, "openai")}
cl = {r["work_id"]: r for r in enrich_papers(texts, work_ids, "anthropic")}

# concordância por campo categórico
fields = ["paper_type", "contribution", "writing_style"]
agree = {f: 0 for f in fields}
for wid in work_ids:
    for f in fields:
        if oa[wid][f] == cl[wid][f]:
            agree[f] += 1
print("\n=== Concordância OpenAI × Claude ===")
for f in fields:
    print(f"  {f:14s}: {agree[f]}/{N} ({agree[f]/N*100:.0f}%)")

print("\n=== Exemplos (5) ===")
for wid in work_ids[:5]:
    print(f"\n{wid}: {texts[work_ids.index(wid)][:90]}…")
    for name, src in (("OpenAI", oa), ("Claude", cl)):
        r = src[wid]
        print(f"  {name:7s} type={r['paper_type']:14s} contrib={r['contribution']:12s} "
              f"style={r['writing_style']:15s} methods={r['methods']} topic='{r['topic']}'")

# distribuições
print("\n=== Distribuição de paper_type ===")
for name, src in (("OpenAI", oa), ("Claude", cl)):
    from collections import Counter
    c = Counter(src[w]["paper_type"] for w in work_ids)
    print(f"  {name}: {dict(c)}")

out = resolve("runs/enrich_pilot.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"openai": list(oa.values()), "anthropic": list(cl.values()),
                           "agreement": agree, "n": N}, indent=2, ensure_ascii=False))
print(f"\n-> {out}")
