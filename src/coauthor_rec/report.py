"""Formatação de tabelas de resultados (estilo Tabelas 12/13 da qualificação)."""
from __future__ import annotations


def format_metrics_table(per_k: dict, title: str = "") -> str:
    """Renderiza uma tabela K x métricas (%) em texto monoespaçado."""
    lines = []
    if title:
        lines.append(title)
    header = f"{'K':>5} {'P(%)':>8} {'R(%)':>8} {'F1(%)':>8} {'MRR(%)':>8} {'NDCG(%)':>9} {'MAP(%)':>8}"
    lines.append(header)
    lines.append("-" * len(header))
    for k in sorted(per_k):
        m = per_k[k]
        lines.append(
            f"{k:>5} {m['P']*100:>8.2f} {m['R']*100:>8.2f} {m['F1']*100:>8.2f} "
            f"{m['MRR']*100:>8.2f} {m['NDCG']*100:>9.2f} {m['MAP']*100:>8.2f}"
        )
    return "\n".join(lines)


def format_full_report(results: dict) -> str:
    """Relatório completo: por modelo, geral + por regime + contagem de autores."""
    blocks = []
    for model_name, res in results.items():
        blocks.append("=" * 72)
        blocks.append(f"MODELO: {model_name}")
        counts = res.get("regime_counts", {})
        blocks.append(f"Autores-alvo por regime: {counts}")
        blocks.append(format_metrics_table(res["overall"], "\n[Geral]"))
        for regime in ("warm", "cool", "cold"):
            if regime in res["by_regime"]:
                blocks.append(format_metrics_table(
                    res["by_regime"][regime], f"\n[Regime: {regime}]"
                ))
    return "\n".join(blocks)
