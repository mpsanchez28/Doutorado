#!/bin/bash
#SBATCH --job-name=ft-scibert-coauthor
#SBATCH --partition=gpu            # ajuste ao nome da partição GPU do cluster (USP)
#SBATCH --gres=gpu:1               # 1 GPU (16-24 GB basta)
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=ft_%j.log

# Template SLURM para fine-tuning do encoder no cluster da USP.
set -euo pipefail
module load python/3.10 cuda/12.1 2>/dev/null || true   # ajuste aos módulos do cluster

cd "$SLURM_SUBMIT_DIR"
python -m venv .venv-gpu && source .venv-gpu/bin/activate
pip install --quiet -r requirements-gpu.txt

# 1) gerar os pares (CPU) — pode rodar fora do nó GPU
PYTHONHASHSEED=0 python scripts/prep_finetune_pairs.py 100000
# 2) treinar (GPU)
python scripts/finetune_encoder.py --base allenai/scibert_scivocab_uncased \
    --out models/scibert-coauthor --epochs 1 --batch 32
echo "OK: modelo em models/scibert-coauthor"
