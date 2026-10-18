"""Entorno simulado (sustituye al sistema operativo de la aerolinea, al servicio meteorologico y al historial BTS).

Genera rotaciones de aeronaves (3-5 tramos por dia) con un proceso estocastico de retrasos que incluye:
congestion por aeropuerto, efecto de aerolinea, hora del dia, clima, estacionalidad, retrasos en cadena
(propagacion del retraso del tramo anterior de la misma aeronave) e incidentes ocultos que el agente no observa.
El agente NUNCA ve el clima real (solo un pronostico con error) ni el retraso del tramo anterior si este aun no ha salido.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from .config import MIN_TURNAROUND

CONGESTION = {"ORD": 0.65, "JFK": 0.60, "ATL": 0.55, "SFO": 0.55, "DFW": 0.45, "BOS": 0.45, "DEN": 0.40,
              "LAX": 0.35, "MIA": 0.30, "CLT": 0.25, "SEA": 0.20, "MSP": 0.15, "MCO": 0.15, "PHX": 0.10,
              "LAS": 0.10, "ANC": 0.05, "BZN": 0.00, "MSO": 0.00}
AIRLINE_EFFECT = {"AA": 0.15, "DL": -0.10, "UA": 0.20, "WN": 0.05, "B6": 0.30, "NK": 0.35, "AS": -0.15,
                  "F9": 0.25, "XP": 0.10}
RARE_AIRPORTS = ["ANC", "BZN", "MSO"]
RARE_AIRLINES = ["XP"]
HUBS = ["ORD", "JFK", "ATL", "SFO", "DFW", "BOS"]
AIRPORTS = list(CONGESTION)
AIRLINES = list(AIRLINE_EFFECT)
# efecto de la hora del dia (0-23)
HOUR_EFFECT = np.array([-0.6] * 6 + [-0.3] * 4 + [0.0] * 5 + [0.45] * 4 + [0.7] * 4 + [0.2])
INTERCEPT = -3.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class Profile:
    """Parametros de un escenario del entorno."""
    name: str = "base"
    n_aircraft_days: int = 75
    start_hour: tuple = (5.0, 12.0)
    airport_weights: dict | None = None
    airline_weights: dict | None = None
    p_storm: float = 0.04
    month: int | None = None
    cong_scale: float = 1.0
    base_shift: float = 0.0
    airport_extra: dict = field(default_factory=dict)
    incident_p: float = 0.03
    incident_mean: float = 50.0
    # fallas que se inyectan en los registros que recibe el agente (no en la fisica del entorno)
    sensor_dropout_p: float = 0.0
    corrupt_p: float = 0.0
    late_p: float = 0.0


def _weights(names, override, rare, rare_w=0.05):
    if override:
        w = np.array([override.get(n, 0.0) for n in names], dtype=float)
    else:
        w = np.array([rare_w if n in rare else 1.0 for n in names], dtype=float)
    return w / w.sum()


def _weather(rng, storm: bool):
    if storm:
        return rng.uniform(0.5, 4.0), max(0.0, rng.normal(30, 6)), rng.exponential(8.0)
    vis = float(np.clip(rng.normal(12, 3), 0.5, 16))
    wind = float(rng.gamma(2, 4))
    precip = 0.0 if rng.random() < 0.8 else float(rng.exponential(2.0))
    return vis, wind, precip


def _severity(vis, wind, precip) -> float:
    return float(np.clip(0.35 * np.clip(1 - vis / 10, 0, 1) + 0.35 * np.clip(wind / 40, 0, 1)
                         + 0.3 * np.clip(precip / 10, 0, 1), 0, 1))


def generate_flights(profile: Profile, seed: int) -> pd.DataFrame:
    """Genera los vuelos (verdad terreno incluida) de un escenario, ordenados por hora programada."""
    rng = np.random.default_rng(seed)
    ap_w = _weights(AIRPORTS, profile.airport_weights, RARE_AIRPORTS)
    al_w = _weights(AIRLINES, profile.airline_weights, RARE_AIRLINES)
    rows, counter = [], 0
    for d in range(profile.n_aircraft_days):
        tail = f"T{seed % 10000:04d}{d:05d}"
        month = profile.month or int(rng.integers(1, 13))
        day = datetime(2026, month, int(rng.integers(1, 28)))
        airline = str(rng.choice(AIRLINES, p=al_w))
        origin = str(rng.choice(AIRPORTS, p=ap_w))
        sched_dep = day + timedelta(hours=float(rng.uniform(*profile.start_hour)))
        prev_sched_arr, prev_arr_delay = None, 0.0
        for leg in range(1, int(rng.integers(3, 6)) + 1):
            dest = origin
            while dest == origin:
                dest = str(rng.choice(AIRPORTS, p=ap_w))
            if leg > 1:
                sched_dep = prev_sched_arr + timedelta(minutes=int(rng.integers(40, 75)))
            slack = None if prev_sched_arr is None else (sched_dep - prev_sched_arr).total_seconds() / 60
            carry = 0.0 if slack is None else max(0.0, prev_arr_delay + MIN_TURNAROUND - slack)
            dur = int(rng.integers(80, 250))
            sched_arr = sched_dep + timedelta(minutes=dur)
            storm = rng.random() < profile.p_storm
            vis, wind, precip = _weather(rng, storm)
            sev = _severity(vis, wind, precip)
            temp = 15 + 12 * np.sin((month - 4) / 12 * 2 * np.pi) + rng.normal(0, 4)
            season = 0.3 if month in (6, 7, 8, 12) else (0.2 if month in (1, 2) else 0.0)
            z = (INTERCEPT + HOUR_EFFECT[sched_dep.hour]
                 + profile.cong_scale * (1.5 * CONGESTION[origin] + 0.4 * CONGESTION[dest])
                 + profile.airport_extra.get(origin, 0.0) + AIRLINE_EFFECT[airline]
                 + 2.2 * sev + season + profile.base_shift + 0.15 * (leg - 1))
            if rng.random() < _sigmoid(z):
                other = 5.0 + rng.exponential(22.0 + 40.0 * sev)
            else:
                other = rng.uniform(-8, 4)
            if rng.random() < profile.incident_p:          # incidente oculto: el agente no lo observa
                other += rng.exponential(profile.incident_mean)
            dep_delay = max(-10.0, carry + other)
            arr_delay = max(-15.0, dep_delay + rng.normal(-4, 9))
            counter += 1
            rows.append(dict(
                flight_id=f"{seed}-{counter:06d}", tail=tail, leg=leg, airline=airline, origin=origin, dest=dest,
                sched_dep=sched_dep, sched_arr=sched_arr, prev_sched_arr=prev_sched_arr, month=month,
                vis=vis, wind=wind, precip=precip, temp=temp, wx_sev=sev,
                f_vis=max(0.1, vis * float(np.exp(rng.normal(0, 0.15)))),
                f_wind=max(0.0, wind + rng.normal(0, 3)),
                f_precip=max(0.0, precip * float(np.exp(rng.normal(0, 0.3)))
                             + (rng.exponential(0.3) if rng.random() < 0.05 else 0.0)),
                f_temp=temp + rng.normal(0, 1.5),
                dep_delay=dep_delay, arr_delay=arr_delay, delayed=bool(dep_delay >= 15),
                actual_dep=sched_dep + timedelta(minutes=float(dep_delay))))
            prev_sched_arr, prev_arr_delay, origin = sched_arr, arr_delay, dest
    return pd.DataFrame(rows).sort_values("sched_dep").reset_index(drop=True)


def make_raw(row, now: datetime, forecast: dict | None) -> dict:
    """Registro crudo que el sistema operativo de la aerolinea entrega al agente (sin verdad terreno)."""
    return {"flight_id": row.flight_id, "tail": row.tail, "leg": int(row.leg), "airline": row.airline,
            "origin": row.origin, "dest": row.dest, "sched_dep": row.sched_dep.isoformat(),
            "prev_sched_arr": None if pd.isna(row.prev_sched_arr) else row.prev_sched_arr.isoformat(),
            "now": now.isoformat(), "forecast": forecast}


def forecast_of(row) -> dict:
    return {"vis": float(row.f_vis), "wind": float(row.f_wind), "precip": float(row.f_precip),
            "temp": float(row.f_temp)}
