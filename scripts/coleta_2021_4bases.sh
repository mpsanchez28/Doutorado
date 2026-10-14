#!/usr/bin/env bash
# Coleta das lacunas da reconstrução de 2021 nas 4 bases sob um TETO TOTAL (docs/PROTOCOLO_CORRIGIDO_2021.md §6).
# Cada base recebe como limite: o que ela já gastou + (TETO_TOTAL − gasto somado de todas as bases),
# de modo que a soma nunca ultrapassa o teto. Retomável (o coletor pula lotes feitos).
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
TETO_TOTAL=${TETO_TOTAL:-2400}
gasto() {  # gasto contado de uma base (0 se ainda não começou)
  $PY -c "import json,os,sys; f='runs/robustez/t4/coleta_'+sys.argv[1]+'_2021/gasto.json'; print(json.load(open(f))['gasto_creditos'] if os.path.exists(f) else 0)" "$1"
}
for b in ${BASES:-economia matematica computacao medicina}; do
  total=0; for x in economia matematica computacao medicina; do total=$((total + $(gasto $x))); done
  proprio=$(gasto $b); limite=$((proprio + TETO_TOTAL - total))
  echo "===== [$(date +%H:%M)] $b: gasto total até aqui $total/$TETO_TOTAL; limite desta base $limite ====="
  PYTHONHASHSEED=0 $PY -u scripts/coletor_t4.py $b --corte 2021 --limite $limite; echo "===== $b exit $? ====="
done
total=0; for x in economia matematica computacao medicina; do total=$((total + $(gasto $x))); done
echo "===== gasto total final: $total/$TETO_TOTAL créditos ====="
