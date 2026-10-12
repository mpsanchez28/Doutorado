"""Embeddings SPECTER2 dos trabalhos de T0 de uma base (docs/TEXTO_SPECTER2.md).

SPECTER2 (Singh et al., 2023): SciBERT treinado por contraste em citações, com o adapter de
**proximidade** (``allenai/specter2``), o indicado para busca de artigos parecidos. Entrada no
formato do modelo: ``título [SEP] resumo``, até 512 tokens; vetor = token [CLS] (768 dims).

Roda num ambiente isolado (``.venv-specter2``), porque a biblioteca ``adapters`` exige um
``transformers`` mais novo que o do ambiente principal:

  .venv-specter2/bin/python scripts/embed_specter2.py economia [--batch 32] [--max-length 512]

Só trabalhos até o fim de T0 (os únicos que entram no KG). Retomável: grava blocos em
``data/processed/text_emb/specter2_<base>/parte_*.npz`` e, ao fim, junta tudo em
``data/processed/text_emb/specter2_<base>.npz`` (``ids``, ``emb`` float16 normalizado L2).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from coauthor_rec.config import resolve  # noqa: E402
from coauthor_rec.data.raw import load_raw_works  # noqa: E402

BASE_MODEL, ADAPTER = "allenai/specter2_base", "allenai/specter2"
CHUNK = 4096


def main():
    import torch
    from adapters import AutoAdapterModel
    from transformers import AutoTokenizer
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-length", type=int, default=512)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    prof = cfg["bases"][args.base]
    cut = int(cfg["split"]["t0_ate"])

    kg_works = set(pd.read_parquet(resolve(f"data/processed/kg_{args.base}/wrote.parquet"), columns=["work_id"])["work_id"])
    w = load_raw_works(resolve(prof["raw_dir"]), ["id", "title", "abstract", "publication_date"])
    w = w[w["id"].isin(kg_works)].sort_values("id").reset_index(drop=True)
    assert (pd.to_datetime(w["publication_date"], errors="coerce").dt.year <= cut).all()
    out_dir = resolve(f"data/processed/text_emb/specter2_{args.base}")
    out_dir.mkdir(parents=True, exist_ok=True)

    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoAdapterModel.from_pretrained(BASE_MODEL)
    model.load_adapter(ADAPTER, source="hf", load_as="proximity", set_active=True)
    model = model.to(device).eval()
    sep = tok.sep_token
    texts = (w["title"].fillna("") + sep + w["abstract"].fillna("")).tolist()
    print(f"[specter2:{args.base}] {len(texts)} trabalhos de T0, dispositivo {device}", flush=True)

    t0 = time.time()
    done = 0
    for c in range(0, len(texts), CHUNK):
        f = out_dir / f"parte_{c // CHUNK:05d}.npz"
        if f.exists():
            done += min(CHUNK, len(texts) - c)
            continue
        vecs = []
        for i in range(c, min(c + CHUNK, len(texts)), args.batch):
            enc = tok(texts[i:i + args.batch], padding=True, truncation=True, max_length=args.max_length,
                      return_tensors="pt", return_token_type_ids=False).to(device)
            with torch.no_grad():
                v = model(**enc).last_hidden_state[:, 0]
            vecs.append(torch.nn.functional.normalize(v, dim=1).float().cpu().numpy())
        np.savez(f, emb=np.concatenate(vecs).astype(np.float16))
        done += min(CHUNK, len(texts) - c)
        rate = done / max(time.time() - t0, 1e-6)
        print(f"[specter2:{args.base}] {done}/{len(texts)} ({rate:.0f}/s, faltam ~{(len(texts) - done) / max(rate, 1e-6) / 60:.0f} min)",
              flush=True)

    parts = sorted(out_dir.glob("parte_*.npz"))
    emb = np.concatenate([np.load(p)["emb"] for p in parts])
    assert len(emb) == len(texts), (len(emb), len(texts))
    np.savez(resolve(f"data/processed/text_emb/specter2_{args.base}.npz"), ids=w["id"].to_numpy(), emb=emb)
    print(f"[specter2:{args.base}] concluído: {emb.shape} em {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
