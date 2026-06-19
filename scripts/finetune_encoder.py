"""Fine-tuning contrastivo do encoder científico (RODAR EM GPU).

Ajusta o SciBERT/SPECTER para aproximar perfis de autores que coautoram (positivos), com
sentence-transformers + MultipleNegativesRankingLoss (negativos = demais do lote). Lê os
pares gerados por prep_finetune_pairs.py e salva o modelo ajustado.

Uso (em GPU):
  python scripts/finetune_encoder.py \
      --pairs data/processed/finetune_pairs.jsonl \
      --base allenai/scibert_scivocab_uncased \
      --out models/scibert-coauthor --epochs 1 --batch 32

Depois, plugue no projeto apontando o HFEncoder para --out (ver docs/FINETUNING.md).
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/processed/finetune_pairs.jsonl")
    ap.add_argument("--base", default="allenai/scibert_scivocab_uncased")
    ap.add_argument("--out", default="models/scibert-coauthor")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-5)
    args = ap.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer, InputExample, losses, models
    from torch.utils.data import DataLoader

    dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"device={dev} | base={args.base}")

    # SciBERT não é um modelo sentence-transformers: monta Transformer + pooling médio.
    word = models.Transformer(args.base, max_seq_length=args.max_len)
    pool = models.Pooling(word.get_word_embedding_dimension(), pooling_mode_mean_tokens=True)
    model = SentenceTransformer(modules=[word, pool], device=dev)

    examples = []
    with open(args.pairs, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            examples.append(InputExample(texts=[d["anchor"], d["positive"]]))
    print(f"pares de treino: {len(examples)}")

    loader = DataLoader(examples, shuffle=True, batch_size=args.batch, drop_last=True)
    loss = losses.MultipleNegativesRankingLoss(model)
    warmup = int(len(loader) * args.epochs * 0.1)
    model.fit(train_objectives=[(loader, loss)], epochs=args.epochs, warmup_steps=warmup,
              optimizer_params={"lr": args.lr}, use_amp=(dev == "cuda"),
              show_progress_bar=True, output_path=args.out)
    print(f"[finetune] modelo salvo em {args.out}")


if __name__ == "__main__":
    main()
