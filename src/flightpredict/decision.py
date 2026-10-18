"""DECISION basada en UTILIDAD (componente IBM 4): compara la utilidad esperada de alertar vs. no alertar."""
from __future__ import annotations

from dataclasses import dataclass

from .config import BETA_PER_MIN, COST_FALSE_ALARM

ALERTAR, NO_ALERTAR, REVISION = "ALERTAR", "NO_ALERTAR", "REVISION_MANUAL"


@dataclass
class Decision:
    flight_id: str
    action: str
    p_delay: float | None = None
    d_hat: float | None = None
    u_alert: float | None = None
    u_none: float = 0.0
    suggestion: str | None = None
    reason: str = ""


def utility_of_alert(p: float, d_hat: float) -> float:
    """U(alertar) = P * (BETA * duracion_esperada) - (1-P) * costo_falsa_alarma ;  U(no alertar) = 0.

    El 'umbral de probabilidad' del diseno es el punto de equilibrio P* = C_FA / (C_FA + BETA*d_hat):
    depende de la duracion esperada (un retraso largo justifica alertar con menos certeza)."""
    return p * BETA_PER_MIN * d_hat - (1 - p) * COST_FALSE_ALARM


def decide(flight_id: str, p: float, d_hat: float, est_carry: float) -> Decision:
    u = utility_of_alert(p, d_hat)
    if u > 0.0:
        big = d_hat >= 45 or (est_carry == est_carry and est_carry >= 30)
        sug = "REASIGNAR_TRIPULACION_Y_PUERTA" if big else "REASIGNAR_PUERTA"
        return Decision(flight_id, ALERTAR, p, d_hat, u, 0.0, sug, "U(alertar) > U(no alertar)")
    return Decision(flight_id, NO_ALERTAR, p, d_hat, u, 0.0, None, "U(alertar) <= U(no alertar)")
