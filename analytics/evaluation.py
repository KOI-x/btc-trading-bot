from __future__ import annotations


def evaluar_vs_hold(estrategia: float, hold: float) -> tuple[str, str]:
    """Compara el resultado de la estrategia contra holdear."""
    if hold == 0:
        return "igual", "Sin valor de referencia para hold"
    diff_pct = (estrategia - hold) / hold * 100
    if diff_pct > 0:
        return "mejor", f"Tu estrategia supera al hold en un {diff_pct:.0f}%"
    if diff_pct < 0:
        return "peor", f"Tu estrategia rinde un {-diff_pct:.0f}% menos que holdear"
    return "igual", "La estrategia rinde lo mismo que holdear"
