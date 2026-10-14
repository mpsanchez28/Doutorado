"""Registro de escores da integração em duas etapas: checagem por par, evento e janela."""
import pandas as pd
import pytest

from coauthor_rec.eval.score_registry import check_score_registry


def _row(**kw):
    base = dict(consulta="A", candidato="B", instante=2018, janela_inicio=2019, janela_fim=2021,
                rotulos_ajuste_inicio=2016, rotulos_ajuste_fim=2018, modulo="m1", uso="treino_2a_etapa")
    base.update(kw)
    return base


def test_temporal_out_of_sample_chronology_passes():
    reg = pd.DataFrame([
        _row(),                                                                    # M1 (fase 2015) pontua a fase 2018
        _row(instante=2021, janela_inicio=2022, janela_fim=2024, rotulos_ajuste_inicio=2019,
             rotulos_ajuste_fim=2021, modulo="m2", uso="teste"),                  # M2 (fase 2018) pontua o teste
    ])
    assert check_score_registry(reg)["ok"]


def test_same_pair_in_another_window_is_legitimate():
    reg = pd.DataFrame([_row(), _row(instante=2021, janela_inicio=2022, janela_fim=2024, rotulos_ajuste_inicio=2019,
                                     rotulos_ajuste_fim=2021, modulo="m2", uso="teste")])
    assert reg[["consulta", "candidato"]].duplicated().any() and check_score_registry(reg)["ok"]


def test_module_fitted_on_the_predicted_window_is_rejected():
    reg = pd.DataFrame([_row(rotulos_ajuste_inicio=2019, rotulos_ajuste_fim=2021)])   # mesmos rótulos da 2ª etapa
    r = check_score_registry(reg)
    assert not r["ok"] and r["rotulos_do_modulo_sobrepoem_a_janela_prevista"] == 1
    assert r["rotulos_do_modulo_posteriores_ao_instante"] == 1


def test_missing_columns_fail():
    with pytest.raises(ValueError):
        check_score_registry(pd.DataFrame([{"consulta": "A"}]))
