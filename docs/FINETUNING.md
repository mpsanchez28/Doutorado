# Fine-tuning do encoder científico (SciBERT/SPECTER) — guia de execução

Objetivo: ajustar o encoder para aproximar autores que **coautoram**, melhorando o sinal
textual usado pelo modelo vencedor (reranker de 2 etapas). É um modelo de 110M parâmetros
com dataset pequeno → **1 GPU, ~10–60 min**.

## Hardware
- **1 GPU de 16–24 GB** (T4 16GB mínimo; L4/A10G/A5000 24GB confortável). Não use Mac/MPS.
- Opções: **cluster da USP (SLURM)**, Google Colab Pro (L4/A100), ou cloud spot (RunPod/Vast/Lambda).

## Passo a passo
1. **Copie os dados** para a máquina GPU: `data/processed/corpus.parquet` e o repositório.
2. **Ambiente** (casar a roda CUDA da máquina):
   ```bash
   python -m venv .venv-gpu && source .venv-gpu/bin/activate
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   pip install -r requirements-gpu.txt && pip install -e .
   ```
3. **Gerar os pares de treino** (T0, sem vazamento) — pode rodar em CPU:
   ```bash
   PYTHONHASHSEED=0 python scripts/prep_finetune_pairs.py 100000
   # -> data/processed/finetune_pairs.jsonl
   ```
4. **Treinar** (GPU):
   ```bash
   python scripts/finetune_encoder.py --base allenai/scibert_scivocab_uncased \
       --out models/scibert-coauthor --epochs 1 --batch 32
   ```
   (SPECTER2: `--base allenai/specter2_base`.)
5. **Plugar o encoder ajustado** no projeto — em `src/coauthor_rec/text/encoders.py`, registre:
   ```python
   "scibert-ft": lambda: HFEncoder("models/scibert-coauthor", pooling="mean", label="scibert-ft"),
   ```
6. **Re-embedar e re-avaliar** (de volta no Mac ou na própria GPU):
   ```bash
   rm -f data/processed/text_emb/scibert.npz
   coauthor-rec text-compare --encoders scibert-ft --no-baseline   # re-gera o pooled
   PYTHONHASHSEED=0 python scripts/two_stage_eval.py               # mede o ganho do 2-etapas
   ```

## Colab (alternativa rápida)
```python
!git clone <repo> && cd coauthor-rec
!pip install -q sentence-transformers transformers accelerate
# subir data/processed/corpus.parquet para data/processed/
!PYTHONHASHSEED=0 python scripts/prep_finetune_pairs.py 100000
!python scripts/finetune_encoder.py --out models/scibert-coauthor --epochs 1 --batch 32
# baixar models/scibert-coauthor/ para usar localmente
```

## USP / SLURM
`sbatch scripts/finetune_slurm.sh` (ajuste partição/módulos do cluster no cabeçalho).

## O que esperar
Hipótese: o encoder ajustado melhora o recall do Texto/2-etapas, sobretudo em cool/cold,
por alinhar o espaço textual à tarefa de coautoria. Comparar `scibert-ft` × `scibert` no
`two_stage_eval.py` (com IC95% e significância) confirma ou refuta o ganho.
