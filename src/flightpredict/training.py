"""Entrenamiento: reproduce el flujo del agente sobre el historial para construir caracteristicas consistentes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .memory import AircraftMemory
from .perception import FEATURES, extract_features, perceive
from .simulator import forecast_of, make_raw
from .agent import FlightPredictAgent


def replay_features(flights: pd.DataFrame, long_memory):
    """Recorre los vuelos en orden cronologico (salidas reales antes que predicciones) con la misma percepcion y memoria."""
    ev = []
    for i, r in enumerate(flights.itertuples()):
        ev.append((FlightPredictAgent.trigger_time(r.sched_dep), 1, i))
        ev.append((r.actual_dep, 0, i))
    ev.sort(key=lambda e: (e[0], e[1]))
    mem, rows = AircraftMemory(), {}
    tuples = list(flights.itertuples())
    for t, kind, i in ev:
        r = tuples[i]
        if kind == 0:
            mem.update_from_outcome(r.tail, r.leg, r.dep_delay, r.actual_dep)
        else:
            raw = make_raw(r, FlightPredictAgent.trigger_time(r.sched_dep), forecast_of(r))
            p, status, _ = perceive(raw, long_memory)
            rows[i] = extract_features(p, mem)
    feats = pd.DataFrame([rows[i] for i in range(len(tuples))])[FEATURES]
    return feats, flights.delayed.to_numpy(), flights.dep_delay.to_numpy()
