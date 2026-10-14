#!/usr/bin/env bash
# Reconstrução de 2021 (protocolo corrigido) nas 4 bases, dois horizontes SEPARADOS
# (docs/PROTOCOLO_CORRIGIDO_2021.md §3, §6). Espera a coleta terminar. Não toca a referência histórica.
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
until grep -q "gasto total final" runs/robustez/t4/coleta_2021_4bases.log 2>/dev/null; do sleep 30; done
for b in ${BASES:-economia matematica computacao medicina}; do
  for h in "--fim-rotulos 2026-10-08" "--horizonte 3"; do
    echo "===== [$(date +%H:%M)] $b $h ====="
    PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py $b --corte 2021 --n-sementes todas \
      --coletado data/robustez/t4/${b}_2021 $h --modelo; echo "===== $b $h exit $? ====="
  done
done
echo "===== [$(date +%H:%M)] reconstrução 2021 concluída ====="
