"""Precisão esperada do contraste principal em amostras de alvos menores (docs/ROBUSTEZ_T1_T4.md §4.1).

Contraste principal (definido antes de qualquer resultado da reconstrução):
  Δ = R@50(LambdaMART + KG) − R@50(LambdaMART só coautoria), pareado por alvo, avaliação estrita.
Melhoria mínima relevante (δ): 10% relativos sobre o controle (R@50 médio do só coautoria na base).
Precisão desejada: semiamplitude do IC 95% de Δ ≤ δ/2 (o intervalo distingue δ de 0).

Estimativa: reamostra (com reposição) n alvos das diferenças pareadas JÁ disponíveis
(runs/ltr_temporal/, protocolo original, corte 2021) e mede a semiamplitude do IC 95% bootstrap
e a fração de reamostras em que o IC exclui 0. Também em subconjunto "corrigido" (auditoria).
Limitações (registradas na saída): diferenças vêm do protocolo ORIGINAL (seleção, horizonte
2022–2026 e treino diferentes dos protocolos corrigido e do T4); horizonte de 3 anos tende a ter
menos coautorias novas por alvo (mais zeros, outra variância); distribuição com muitos zeros;
a reamostragem trata os alvos como independentes.
Saída: runs/robustez/precisao.json. Uso: python scripts/precisao_t4.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from coauthor_rec.config import resolve  # noqa: E402

NS = (120, 160, 250, 310, 450)
REPS, BOOT = 400, 400


def ci_halfwidth(x: np.ndarray, rng) -> tuple[float, bool]:
    m = x[rng.integers(0, len(x), size=(BOOT, len(x)))].mean(axis=1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return (hi - lo) / 2, bool(lo > 0)


def main():
    cfg = yaml.safe_load(open(resolve("configs/bases.yaml")))
    rng = np.random.default_rng(0)
    out = {"contraste": "R@50(LTR completo) − R@50(LTR só coautoria), pareado por alvo, avaliação estrita",
           "delta_minimo": "10% relativo ao R@50 médio do LTR só coautoria (convertido em pp por base)",
           "justificativa_delta": "escolha a priori, não derivada dos dados: a menor melhoria considerada de interesse "
                                  "prático para um ranqueador (um acerto a mais a cada dez que o controle já obtém); "
                                  "sensibilidade a outros δ pode ser reportada",
           "precisao_desejada": "semiamplitude IC95 ≤ δ/2",
           "o_que_cada_numero_mede": {"semiamplitude_IC95": "PRECISÃO da estimativa (largura do intervalo), sem supor efeito",
                                      "frac_IC_exclui_0": "fração de reamostras com IC>0 sob o efeito OBSERVADO no protocolo anterior",
                                      "poder_aprox_para_delta": "fração de ICs que excluem 0 se o efeito verdadeiro fosse exatamente δ",
                                      "n_para_80pct_poder_normal": "aproximação normal; ignora a assimetria e os zeros"},
           "status": "planejamento APROXIMADO baseado no protocolo anterior (corte 2021, horizonte ~4,8 anos, seleção original)",
           "limitacoes": ["diferenças do protocolo ORIGINAL (seleção, horizonte 2022–2026, treino) — não do corrigido nem do T4",
                          "horizonte de 3 anos → menos coautorias novas por alvo; a variância pode mudar",
                          "distribuição com muitos zeros; IC por bootstrap percentil",
                          "alvos tratados como independentes (podem compartilhar coautores)"],
           "bases": {}}
    for b in cfg["gradiente"]:
        d = pd.read_parquet(resolve(f"runs/ltr_temporal/{b}.parquet"))
        x = d[d["modelo"] == "LTR completo"].set_index("alvo")["R@50"]
        y = d[d["modelo"] == "LTR só coautoria"].set_index("alvo")["R@50"].reindex(x.index)
        aud = resolve(f"runs/robustez/auditoria/elegibilidade_{b}.csv")
        subsets = {"todos": x.index}
        if aud.exists():
            a = pd.read_csv(aud).drop_duplicates("pessoa").set_index("pessoa")
            ok = (a["status_2021"] == "mantida") & (a["sorteio_ate_2021"] == True)  # noqa: E712
            subsets["corrigido"] = x.index[ok.reindex(x.index).fillna(False).to_numpy()]
        res = {}
        for sname, idx in subsets.items():
            diff = (x.loc[idx] - y.loc[idx]).to_numpy()
            delta = 0.10 * float(y.loc[idx].mean())
            sd = float(diff.std(ddof=1))
            n_req = int(np.ceil(((1.96 + 0.84) * sd / delta) ** 2)) if delta > 0 else None
            n_prec = int(np.ceil((1.96 * sd / (delta / 2)) ** 2)) if delta > 0 else None
            sim = {}
            for n in NS:
                hw, excl = zip(*(ci_halfwidth(diff[rng.integers(0, len(diff), n)], rng) for _ in range(REPS)))
                sim[n] = {"semiamplitude_IC95_mediana_pp": round(100 * float(np.median(hw)), 3),
                          "frac_IC_exclui_0": round(float(np.mean(excl)), 3),
                          "atinge_precisao": bool(np.median(hw) <= delta / 2)}
            nz = diff[diff != 0]
            dist_nz = {"n": int(len(nz)), "frac_positivas": round(float((nz > 0).mean()), 3) if len(nz) else None,
                       "quantis_pp": {q: round(100 * float(np.quantile(nz, q)), 2) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
                       if len(nz) else None,
                       "media_pp": round(100 * float(nz.mean()), 3) if len(nz) else None}
            # poder aproximado por reamostragem: desloca as diferenças para que a média seja δ e
            # mede a fração de ICs que excluem 0 (aproximação; o formato da distribuição é mantido)
            shifted = diff - diff.mean() + delta
            power = {}
            for n in (160, 310, 1000):
                excl = [ci_halfwidth(shifted[rng.integers(0, len(shifted), n)], rng)[1] for _ in range(REPS // 2)]
                power[n] = round(float(np.mean(excl)), 3)
            res[sname] = {"n_disponivel": int(len(diff)), "media_delta_pp": round(100 * float(diff.mean()), 3),
                          "diferencas_nao_nulas": dist_nz, "poder_aprox_para_delta_por_reamostragem": power,
                          "dp_delta_pp": round(100 * sd, 3), "fracao_delta_zero": round(float((diff == 0).mean()), 3),
                          "controle_R50_pp": round(100 * float(y.loc[idx].mean()), 3), "delta_minimo_pp": round(100 * delta, 3),
                          "n_para_80pct_poder_normal": n_req, "n_para_precisao_desejada_normal": n_prec,
                          "reamostragem": sim}
            print(f"[{b}:{sname}] Δ={res[sname]['media_delta_pp']:+.2f} pp, dp={res[sname]['dp_delta_pp']:.2f}, "
                  f"δ={res[sname]['delta_minimo_pp']:.2f} pp, zeros={res[sname]['fracao_delta_zero']:.0%}; "
                  f"n p/ precisão≈{n_prec}, n p/ 80% poder≈{n_req}; IC½ @120/160/250: "
                  f"{sim[120]['semiamplitude_IC95_mediana_pp']}/{sim[160]['semiamplitude_IC95_mediana_pp']}/"
                  f"{sim[250]['semiamplitude_IC95_mediana_pp']} pp; não nulas: {dist_nz['frac_positivas']} positivas, "
                  f"quantis {dist_nz['quantis_pp']}; poder(δ) @160/310/1000 {power}", flush=True)
        out["bases"][b] = res
    resolve("runs/robustez/precisao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("escrito runs/robustez/precisao.json")


if __name__ == "__main__":
    main()
