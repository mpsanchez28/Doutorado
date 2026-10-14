#!/usr/bin/env bash
# Recalcula elegibilidade, identidades, universos e conjuntos (teste e fase de treino) de Economia e
# Matemática SÓ com a cópia congelada S1 (sem treinar modelo; nenhuma seleção). ESPECIFICACAO, emenda E2.
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
S=data/snapshots/S1_20261014_econ_mat
run() { echo "===== [$(date +%H:%M)] $* ====="; PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py "$@" --n-sementes todas --snapshot $S --fase-treino; echo "===== exit $? ====="; }
run economia --corte 2019 --coletado x --horizonte 3
for b in economia matematica; do
  run $b --corte 2021 --coletado x --horizonte 3
  run $b --corte 2021 --coletado x --fim-rotulos 2026-10-08
done
echo "===== [$(date +%H:%M)] concluído ====="
