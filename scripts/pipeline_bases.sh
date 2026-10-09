#!/usr/bin/env bash
# Encadeia, para as 4 bases do gradiente, as etapas que seguem a coleta + expansão:
#   higienização (ORCID, pessoa canônica, E1–E8) + gate de rede + auditoria  → build_base.py
#   enriquecimento (camadas 1–3, diagnóstico de sinal, amostra RDF)          → enrich_base.py
#   relatório consolidado                                                     → report_bases.py
# Uma base que falha não interrompe as demais (o código de saída fica no log).
# Uso: bash scripts/pipeline_bases.sh [log_da_expansao_para_esperar]
set -u
cd "$(dirname "$0")/.."
PY=/Users/marcos.sanchez/anaconda3/bin/python3
WAIT_LOG="${1:-}"
if [ -n "$WAIT_LOG" ]; then
  echo "[pipeline] aguardando a expansão terminar ($WAIT_LOG)…"
  until grep -q "medicina terminou" "$WAIT_LOG" 2>/dev/null; do sleep 30; done
  echo "[pipeline] expansão concluída: $(grep -c 'terminou (exit 0)' "$WAIT_LOG")/4 bases com sucesso"
fi
for b in economia matematica computacao medicina; do
  echo "===== [$(date +%H:%M)] higienização: $b ====="
  PYTHONHASHSEED=0 $PY -u scripts/build_base.py "$b"; echo "===== higienização $b: exit $? ====="
  echo "===== [$(date +%H:%M)] enriquecimento: $b ====="
  PYTHONHASHSEED=0 $PY -u scripts/enrich_base.py "$b"; echo "===== enriquecimento $b: exit $? ====="
done
$PY scripts/report_bases.py
echo "===== [$(date +%H:%M)] pipeline concluído ====="
