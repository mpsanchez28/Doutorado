#!/usr/bin/env bash
# Universo v2 (docs/REVISAO_CONSISTENCIA_PROTOCOLOS.md A0): repetição do piloto 2019 (reprodutibilidade)
# e reconstrução de 2021 em Economia e Matemática, dois horizontes separados. Só dados locais.
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
echo "===== [$(date +%H:%M)] piloto economia 2019 v2 — repetição ====="
PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py economia --corte 2019 --n-sementes todas \
  --coletado data/robustez/t4/economia_2019 --horizonte 3 --modelo; echo "===== piloto exit $? ====="
for b in ${BASES:-economia matematica}; do
  for h in "--fim-rotulos 2026-10-08" "--horizonte 3"; do
    echo "===== [$(date +%H:%M)] $b 2021 $h ====="
    PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py $b --corte 2021 --n-sementes todas \
      --coletado data/robustez/t4/${b}_2021 $h --modelo; echo "===== $b $h exit $? ====="
  done
done
echo "===== [$(date +%H:%M)] concluído ====="
