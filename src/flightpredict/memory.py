"""MEMORIA (componente IBM 3): corto plazo (estado por aeronave) y largo plazo (historial, climatologia, retroalimentacion)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class AircraftMemory:
    """Memoria de corto plazo: ultimo estado conocido de cada aeronave en la jornada (parte 'basada en modelo')."""

    def __init__(self):
        self.state = {}

    def update_from_outcome(self, tail, leg, dep_delay, actual_dep):
        self.state[tail] = {"leg": int(leg), "dep_delay": float(dep_delay), "actual_dep": actual_dep}

    def context(self, tail, leg):
        s = self.state.get(tail)
        if s is None:
            return {"last_delay": float("nan"), "last_is_prev": False}
        return {"last_delay": s["dep_delay"], "last_is_prev": s["leg"] == int(leg) - 1}


class LongTermMemory:
    """Memoria de largo plazo: climatologia para imputar, tasas historicas de vuelos similares y buffer de retroalimentacion."""

    def __init__(self, clim=None, clim_global=None, rates=None, base_rate=0.2):
        self.clim = clim or {}
        self.clim_global = clim_global or {"vis": 12.0, "wind": 8.0, "precip": 0.0, "temp": 15.0}
        self.rates = rates or {}
        self.base_rate = base_rate
        self.feedback = []          # muestras etiquetadas: (features, delayed, dep_delay)

    @classmethod
    def from_history(cls, hist: pd.DataFrame):
        clim = {}
        for (o, m), g in hist.groupby(["origin", "month"]):
            clim[f"{o}|{m}"] = {"vis": float(g.f_vis.median()), "wind": float(g.f_wind.median()),
                                "precip": float(g.f_precip.median()), "temp": float(g.f_temp.median())}
        glob = {"vis": float(hist.f_vis.median()), "wind": float(hist.f_wind.median()),
                "precip": float(hist.f_precip.median()), "temp": float(hist.f_temp.median())}
        h = hist.assign(hour=hist.sched_dep.dt.hour // 6)
        rates = {f"{o}|{b}": float(g.delayed.mean()) for (o, b), g in h.groupby(["origin", "hour"])}
        return cls(clim, glob, rates, float(hist.delayed.mean()))

    def climatology(self, origin, month):
        return dict(self.clim.get(f"{origin}|{month}", self.clim_global))

    def similar_flights_rate(self, origin, hour):
        """Paso 'consultar historial de vuelos similares' del plan: tasa historica de retraso en origen y franja."""
        return self.rates.get(f"{origin}|{hour // 6}", self.base_rate)

    def clone(self):
        return LongTermMemory(self.clim, self.clim_global, self.rates, self.base_rate)

    def save(self, path: Path):
        Path(path).write_text(json.dumps({"clim": self.clim, "clim_global": self.clim_global,
                                          "rates": self.rates, "base_rate": self.base_rate}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["clim"], d["clim_global"], d["rates"], d["base_rate"])
