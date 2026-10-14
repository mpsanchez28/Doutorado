#!/usr/bin/env bash
# Conjuntos (teste e fase de treino) de Computação e Medicina SÓ com a cópia congelada S2 (sem treinar
# modelo; nenhuma seleção). Medicina está INCOMPLETA (enriquecimento pendente): conjuntos válidos,
# KG com cobertura de tópicos parcial. ESPECIFICACAO, emenda E2.
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
S=data/snapshots/S2_20261014_comp_med
for b in computacao medicina; do
  for h in "--horizonte 3" "--fim-rotulos 2026-10-08"; do
    echo "===== [$(date +%H:%M)] $b $h ====="
    PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py $b --corte 2021 --n-sementes todas --snapshot $S --coletado x $h --fase-treino
    echo "===== exit $? ====="
  done
done
echo "===== [$(date +%H:%M)] concluído ====="
