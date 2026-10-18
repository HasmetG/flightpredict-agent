"""PERCEPCION: validacion, imputacion y extraccion de caracteristicas (componente IBM 1: percepcion y manejo de entradas)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .config import LEAD_MIN, MIN_TURNAROUND
from .simulator import AIRLINES, AIRPORTS

OK, INVALID, INSUFFICIENT_WINDOW = "OK", "ENTRADA_INVALIDA", "VENTANA_INSUFICIENTE"
WX_RANGES = {"vis": (0.0, 50.0), "wind": (0.0, 200.0), "precip": (0.0, 500.0), "temp": (-60.0, 60.0)}
REQUIRED = ["flight_id", "tail", "airline", "origin", "dest", "sched_dep", "now"]


@dataclass
class Percept:
    flight_id: str
    tail: str
    leg: int
    airline: str
    origin: str
    dest: str
    sched_dep: datetime
    now: datetime
    lead_min: float
    slack_min: float | None
    wx: dict
    wx_imputed: bool
    issues: list = field(default_factory=list)


def _parse(ts):
    return ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))


def perceive(raw: dict, long_memory) -> tuple[Percept | None, str, list]:
    """Devuelve (percepto|None, estado, problemas). Nunca lanza excepcion por datos defectuosos."""
    issues = []
    if not isinstance(raw, dict):
        return None, INVALID, ["registro_no_es_dict"]
    for k in REQUIRED:
        if raw.get(k) in (None, ""):
            issues.append(f"falta_{k}")
    if issues:
        return None, INVALID, issues
    if raw["origin"] not in AIRPORTS or raw["dest"] not in AIRPORTS:
        issues.append("aeropuerto_desconocido")
    if raw["airline"] not in AIRLINES:
        issues.append("aerolinea_desconocida")
    if raw["origin"] == raw["dest"]:
        issues.append("origen_igual_destino")
    try:
        sched_dep, now = _parse(raw["sched_dep"]), _parse(raw["now"])
    except (ValueError, TypeError):
        issues.append("fecha_no_interpretable")
    if issues:
        return None, INVALID, issues
    lead = (sched_dep - now).total_seconds() / 60
    if lead <= 0:
        return None, INVALID, ["hora_programada_en_el_pasado"]
    if lead < LEAD_MIN:
        return None, INSUFFICIENT_WINDOW, [f"antelacion_{lead:.0f}_min_menor_a_{LEAD_MIN}"]
    slack = None
    if raw.get("prev_sched_arr"):
        try:
            slack = (sched_dep - _parse(raw["prev_sched_arr"])).total_seconds() / 60
        except (ValueError, TypeError):
            issues.append("prev_sched_arr_no_interpretable")
    wx, imputed = _clean_weather(raw.get("forecast"), raw["origin"], sched_dep.month, long_memory, issues)
    return Percept(raw["flight_id"], raw["tail"], int(raw.get("leg") or 1), raw["airline"], raw["origin"],
                   raw["dest"], sched_dep, now, lead, slack, wx, imputed, issues), OK, issues


def _clean_weather(fc, origin, month, long_memory, issues):
    """Si el pronostico falta o es fisicamente imposible, se imputa con la climatologia (memoria de largo plazo)."""
    ok = isinstance(fc, dict)
    if ok:
        for k, (lo, hi) in WX_RANGES.items():
            v = fc.get(k)
            if not isinstance(v, (int, float)) or not (lo <= v <= hi) or v != v:
                ok = False
    if ok:
        return {k: float(fc[k]) for k in WX_RANGES}, False
    issues.append("pronostico_ausente_o_invalido_imputado")
    return long_memory.climatology(origin, month), True


FEATURES = ["hour", "dow", "month", "origin", "dest", "airline", "leg", "slack_min", "last_delay",
            "last_is_prev", "est_carry", "wx_vis", "wx_wind", "wx_precip", "wx_temp"]


def extract_features(p: Percept, aircraft_memory) -> dict:
    """Combina percepcion actual + estado interno de la aeronave (modelo del entorno no observable)."""
    ctx = aircraft_memory.context(p.tail, p.leg)
    last, is_prev = ctx["last_delay"], ctx["last_is_prev"]
    est_carry = float("nan")
    if is_prev and p.slack_min is not None and last == last:
        est_carry = max(0.0, last - 4 - (p.slack_min - MIN_TURNAROUND))
    return {"hour": p.sched_dep.hour, "dow": p.sched_dep.weekday(), "month": p.sched_dep.month,
            "origin": p.origin, "dest": p.dest, "airline": p.airline, "leg": p.leg,
            "slack_min": float("nan") if p.slack_min is None else p.slack_min,
            "last_delay": last, "last_is_prev": float(is_prev), "est_carry": est_carry,
            "wx_vis": p.wx["vis"], "wx_wind": p.wx["wind"], "wx_precip": p.wx["precip"], "wx_temp": p.wx["temp"]}
