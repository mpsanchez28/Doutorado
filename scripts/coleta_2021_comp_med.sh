#!/usr/bin/env bash
# Complementação de 2021 (universo v2) em Computação e depois Medicina, sob o teto TOTAL de 2.400
# créditos de 2021 (autorização de 14/10/2026). Controle global: antes de cada base, soma o gasto
# contado de TODAS as bases de 2021 e dá a esta base só o saldo menos uma MARGEM; uma base por vez
# (sem processos concorrentes). Retomável: lotes concluídos não são refeitos. O piloto de 2019
# (coleta_economia_2019, teto próprio) não entra nesta conta.
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
TETO_TOTAL=${TETO_TOTAL:-2400}
MARGEM=${MARGEM:-100}
gasto() { $PY -c "import json,os,sys; f='runs/robustez/t4/coleta_'+sys.argv[1]+'_2021/gasto.json'; print(json.load(open(f))['gasto_creditos'] if os.path.exists(f) else 0)" "$1"; }
for b in ${BASES:-computacao medicina}; do
  total=0; for x in economia matematica computacao medicina; do total=$((total + $(gasto $x))); done
  proprio=$(gasto $b); limite=$((proprio + TETO_TOTAL - MARGEM - total))
  echo "===== [$(date +%H:%M)] $b: gasto 2021 acumulado $total/$TETO_TOTAL; margem $MARGEM; limite desta base $limite (já gasto $proprio) ====="
  PYTHONHASHSEED=0 $PY -u scripts/coletor_t4.py $b --corte 2021 --limite $limite \
    --lacunas runs/robustez/t4/reconstrucao_${b}_2021_v2/lacunas.csv \
    --lacunas-anteriores runs/robustez/t4/reconstrucao_${b}_2021/lacunas.csv --prefixo v2_
  echo "===== $b exit $? ====="
  if [ "$b" = computacao ]; then   # lacunas de Medicina recalculadas com o cache e o saldo reais
    echo "===== [$(date +%H:%M)] inventário v2 de medicina antes da coleta ====="
    PYTHONHASHSEED=0 $PY -u scripts/reconstrucao_t4.py medicina --corte 2021 --n-sementes todas --sem-corpus | tail -2
  fi
done
total=0; for x in economia matematica computacao medicina; do total=$((total + $(gasto $x))); done
echo "===== [$(date +%H:%M)] gasto 2021 total: $total/$TETO_TOTAL créditos ====="
