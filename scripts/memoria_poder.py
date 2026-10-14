"""Memória reproduzível do cálculo de poder e precisão (ESPECIFICACAO_METODOLOGICA §4.5, emenda E4).

Reproduz e confere os números relatados (~3% e ~7% de poder; ~4.900 e ~2.500 alvos) e os separa em:
  (a) PODER para o efeito especificado δ, (b) PRECISÃO do intervalo, (c) frequência de rejeição sob
  o efeito OBSERVADO no protocolo histórico, (d) tamanho efetivo do teste sob H0 (calibração).

Unidade: pessoa-alvo. Métrica: R@50 na escala de 0 a 1 (proporção). "pp" = pontos percentuais
(proporção × 100). Δ_i = R@50(LambdaMART + KG)_i − R@50(LambdaMART só coautoria)_i, avaliação estrita.
Fonte da dispersão: diferenças por alvo do PROTOCOLO HISTÓRICO (runs/ltr_temporal/<base>.parquet;
corte 2021, horizonte 2022–2026, seleção original) — teste já consultado em 10–11/10/2026.
Métricas das reconstruções v2 NÃO são lidas; só as contagens de alvos dos relatórios (n).
H0: E[Δ] = 0; bilateral; família F1 com m = 4 testes (uma área cada); Bonferroni:
α_efetivo = 0,05/4 = 0,0125 por teste (IC de 98,75%).

Uso: python scripts/memoria_poder.py   →  runs/robustez/memoria_poder.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm, skew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

ALPHA, M = 0.05, 4
SEED, R, B = 20261014, 1000, 1000           # réplicas externas (amostras) e internas (bootstrap)
BASES = ["medicina", "computacao", "matematica", "economia"]
S1, S2 = "S1_20261014_econ_mat", "S2_20261014_comp_med"
N_V2 = {b: {"3 anos": f"reconstrucao_{b}_2021_v2_{snap}_coletado_h3", "completo": f"reconstrucao_{b}_2021_v2_{snap}_coletado_ate2026-10-08"}
        for b, snap in (("economia", S1), ("matematica", S1), ("computacao", S2), ("medicina", S2))}


def analytic(delta, sigma, n, alpha_eff):
    z = norm.ppf(1 - alpha_eff / 2)
    ncp = delta * np.sqrt(n) / sigma
    return {"z_critico": round(float(z), 4), "parametro_nao_central": round(float(ncp), 4),
            "poder": round(float(norm.cdf(ncp - z) + norm.cdf(-ncp - z)), 4),
            "n_para_80pct_poder": int(np.ceil(((z + norm.ppf(0.8)) * sigma / delta) ** 2)),
            "semiamplitude_esperada": round(float(z * sigma / np.sqrt(n)), 6)}


def simulate(diff, mean_target, n, alpha_eff, rng):
    """Fração de ICs percentil (bootstrap, nível 1 − α_efetivo) que excluem 0, com as diferenças
    históricas deslocadas para a média ``mean_target`` (forma da distribuição preservada)."""
    x = diff - diff.mean() + mean_target
    lo_q, hi_q = 100 * alpha_eff / 2, 100 * (1 - alpha_eff / 2)
    rej, hw = 0, []
    for _ in range(R):
        s = x[rng.integers(0, len(x), n)]
        m = s[rng.integers(0, n, (B, n))].mean(axis=1)
        lo, hi = np.percentile(m, [lo_q, hi_q])
        rej += (lo > 0) or (hi < 0)
        hw.append((hi - lo) / 2)
    p = rej / R
    return {"frequencia_rejeicao": round(p, 4), "erro_monte_carlo": round(float(np.sqrt(p * (1 - p) / R)), 4),
            "semiamplitude_mediana": round(float(np.median(hw)), 6)}


def calibration():
    """Conferência com B = 10.000 (o valor especificado em §4.6) nos cenários de n real e em Medicina n=310."""
    global B
    B = 10_000
    rng = np.random.default_rng(SEED + 1)
    a_eff = ALPHA / M
    res = {"bootstrap_interno": B, "replicas": R, "semente": SEED + 1, "cenarios": {}}
    for b, n in (("economia", 184), ("matematica", 221), ("medicina", 310), ("computacao", 310)):
        d = pd.read_parquet(resolve(f"runs/ltr_temporal/{b}.parquet"))
        x = d[d["modelo"] == "LTR completo"].set_index("alvo")["R@50"]
        y = d[d["modelo"] == "LTR só coautoria"].set_index("alvo")["R@50"].reindex(x.index)
        diff = (x - y).to_numpy()
        delta = 0.10 * float(y.mean())
        res["cenarios"][f"{b} n={n}"] = {"tamanho_H0": simulate(diff, 0.0, n, a_eff, rng),
                                         "poder_delta": simulate(diff, delta, n, a_eff, rng)}
        print(f"[calibração B=10.000] {b} n={n}: {res['cenarios'][f'{b} n={n}']}", flush=True)
    resolve("runs/robustez/memoria_poder_calibracao.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    if "--calibracao" in sys.argv:
        return calibration()
    rng = np.random.default_rng(SEED)
    a_eff = ALPHA / M
    out = {"descricao": __doc__.strip().splitlines()[0], "unidade": "pessoa-alvo", "escala": "R@50 em proporção (0–1); pp = ×100",
           "H0": "E[Δ] = 0", "alternativa": "bilateral", "teste": "IC percentil do bootstrap; rejeita se excluir 0 (aproximação analítica: z)",
           "familia": "F1: um contraste por área (4 áreas)", "m": M, "alfa_nominal": ALPHA, "alfa_efetivo_por_teste": a_eff,
           "nivel_IC": 1 - a_eff, "delta": "10% do R@50 médio do controle (LambdaMART só coautoria) no protocolo histórico, todos os alvos",
           "fonte_dispersao": "runs/ltr_temporal/<base>.parquet (protocolo histórico; teste já consultado)",
           "metricas_v2_acessadas": False, "simulacao": {"semente": SEED, "replicas": R, "bootstrap_interno": B},
           "premissas_e_limites": [
               "σ do protocolo histórico (outra seleção, horizonte 2022–2026, outro treino); o n e a variância da v2 podem diferir",
               "alvos independentes (o bootstrap de Poisson por pessoa trata só repetições de pessoa; aqui não há repetição)",
               "aproximação normal ignora zeros e assimetria; a simulação preserva a forma da distribuição histórica deslocada",
               "deslocar a distribuição supõe efeito aditivo constante (não verificado)"],
           "bases": {}}
    for b in BASES:
        d = pd.read_parquet(resolve(f"runs/ltr_temporal/{b}.parquet"))
        x = d[d["modelo"] == "LTR completo"].set_index("alvo")["R@50"]
        y = d[d["modelo"] == "LTR só coautoria"].set_index("alvo")["R@50"].reindex(x.index)
        diff = (x - y).to_numpy()
        ctrl = float(y.mean())
        delta = 0.10 * ctrl
        sigma = float(diff.std(ddof=1))
        r = {"n_historico": int(len(diff)), "controle_R50": round(ctrl, 6), "controle_R50_pp": round(100 * ctrl, 4),
             "delta": round(delta, 6), "delta_pp": round(100 * delta, 4),
             "delta_registrado_pp": {"ESPECIFICACAO": {"medicina": 0.35, "computacao": 0.55, "matematica": 0.94, "economia": 0.61}[b],
                                     "PROTOCOLO_e_precisao_t4": {"medicina": 0.35, "computacao": 0.56, "matematica": 0.94, "economia": 0.61}[b]},
             "sigma": round(sigma, 6), "sigma_pp": round(100 * sigma, 4), "media_historica": round(float(diff.mean()), 6),
             "fracao_zeros": round(float((diff == 0).mean()), 4), "assimetria": round(float(skew(diff)), 3),
             "cenarios": {}}
        ns = {}
        for h, folder in N_V2.get(b, {}).items():
            f = resolve(f"runs/robustez/t4/{folder}/relatorio.json")
            if f.exists():
                ns[f"v2 congelado {h}"] = json.loads(f.read_text())["corpus_local_parcial"]["protocolo"]["alvos"]
        for k in (160, 310):
            ns.setdefault(f"grade n={k}", k)
        for label, n in ns.items():
            r["cenarios"][label] = {"n": n, "analitico_F1": analytic(delta, sigma, n, a_eff),
                                    "analitico_sem_multiplicidade": analytic(delta, sigma, n, ALPHA),
                                    "sim_poder_delta": simulate(diff, delta, n, a_eff, rng),
                                    "sim_tamanho_H0": simulate(diff, 0.0, n, a_eff, rng),
                                    "sim_efeito_observado_historico": simulate(diff, diff.mean(), n, a_eff, rng),
                                    "meta_precisao_delta_sobre_2": round(delta / 2, 6)}
            c = r["cenarios"][label]
            print(f"[{b}] {label}: n={n} poder analítico {c['analitico_F1']['poder']:.3f} | sim {c['sim_poder_delta']['frequencia_rejeicao']:.3f}"
                  f"±{c['sim_poder_delta']['erro_monte_carlo']:.3f} | tamanho sob H0 {c['sim_tamanho_H0']['frequencia_rejeicao']:.3f} "
                  f"(nominal {a_eff}) | n80 {c['analitico_F1']['n_para_80pct_poder']} | semiampl {100 * c['analitico_F1']['semiamplitude_esperada']:.2f} pp",
                  flush=True)
        out["bases"][b] = r
    resolve("runs/robustez/memoria_poder.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("escrito runs/robustez/memoria_poder.json")


if __name__ == "__main__":
    main()
