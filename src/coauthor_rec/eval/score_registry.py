"""Registro de escores fora da amostra para a integração em duas etapas (ESPECIFICACAO §5.3, emenda E5).

Cada linha registra UM escore de um módulo (1ª etapa) para UM par numa janela:
  consulta, candidato        — o par (consulta = quem recebe a recomendação)
  instante                   — corte das features/grafo usados para produzir o escore (fim do ano)
  janela_inicio, janela_fim  — período (anos, inclusive) cujo desfecho o escore ajuda a prever
  rotulos_ajuste_inicio/fim  — período dos rótulos usados para AJUSTAR o módulo (pesos e escolhas)
  modulo                     — versão do módulo (hash de código, configuração e pesos)
  uso                        — "treino_2a_etapa" ou "teste"

Regras verificadas (por par/evento/janela — um par pode aparecer em janelas diferentes):
  1. o módulo não viu rótulos do período que o escore ajuda a prever:
     [rotulos_ajuste] ∩ [janela] = ∅;
  2. o módulo só usou rótulos conhecidos no instante de previsão: rotulos_ajuste_fim ≤ instante;
  3. features anteriores ao período previsto: instante < janela_inicio.
"""
from __future__ import annotations

import pandas as pd

COLS = ["consulta", "candidato", "instante", "janela_inicio", "janela_fim", "rotulos_ajuste_inicio",
        "rotulos_ajuste_fim", "modulo", "uso"]


def check_score_registry(reg: pd.DataFrame) -> dict:
    missing = [c for c in COLS if c not in reg.columns]
    if missing:
        raise ValueError(f"registro de escores sem colunas obrigatórias: {missing}")
    overlap = (reg["rotulos_ajuste_inicio"] <= reg["janela_fim"]) & (reg["janela_inicio"] <= reg["rotulos_ajuste_fim"])
    late = reg["rotulos_ajuste_fim"] > reg["instante"]
    future_feat = reg["instante"] >= reg["janela_inicio"]
    out = {"linhas": len(reg), "rotulos_do_modulo_sobrepoem_a_janela_prevista": int(overlap.sum()),
           "rotulos_do_modulo_posteriores_ao_instante": int(late.sum()),
           "features_nao_anteriores_a_janela": int(future_feat.sum())}
    out["ok"] = not (overlap.any() or late.any() or future_feat.any())
    return out
