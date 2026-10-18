"""Ejecucion de un escenario completo (flujo cronologico de eventos) y calculo de metricas."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .agent import FlightPredictAgent
from .config import LEAD_MIN
from .decision import ALERTAR, REVISION
from .simulator import Profile, forecast_of, make_raw

CORRUPTIONS = ["aeropuerto_desconocido", "aerolinea_nula", "origen_igual_destino", "fecha_invalida", "sin_tail"]


def _corrupt(raw: dict, rng):
    mode = str(rng.choice(CORRUPTIONS))
    if mode == "aeropuerto_desconocido":
        raw["origin"] = "ZZZ"
    elif mode == "aerolinea_nula":
        raw["airline"] = None
    elif mode == "origen_igual_destino":
        raw["dest"] = raw["origin"]
    elif mode == "fecha_invalida":
        raw["sched_dep"] = "no-es-una-fecha"
    else:
        raw["tail"] = ""
    return mode


def run_stream(flights: pd.DataFrame, agent: FlightPredictAgent, profile: Profile, rng, retrain_every=None):
    tuples = list(flights.itertuples())
    ev = []
    meta = {}
    for i, r in enumerate(tuples):
        late = rng.random() < profile.late_p
        now = (r.sched_dep - timedelta(minutes=float(rng.uniform(10, 170)))) if late \
            else FlightPredictAgent.trigger_time(r.sched_dep)
        meta[i] = {"late": late, "now": now}
        ev.append((now, 1, i))
        ev.append((r.actual_dep, 0, i))
    ev.sort(key=lambda e: (e[0], e[1]))
    out, since_retrain = {}, 0
    for t, kind, i in ev:
        r = tuples[i]
        if kind == 0:
            before = len(agent.feedback)
            agent.receive_outcome(r.flight_id, r.tail, r.leg, r.dep_delay, r.actual_dep)
            since_retrain += len(agent.feedback) - before
            if retrain_every and since_retrain >= retrain_every:
                agent.retrain()
                since_retrain = 0
            continue
        fc = forecast_of(r)
        dropped = False
        if rng.random() < profile.sensor_dropout_p:
            dropped = True
            fc = None if rng.random() < 0.5 else {"vis": -99.0, "wind": -1.0, "precip": -5.0, "temp": 999.0}
        raw = make_raw(r, meta[i]["now"], fc)
        corrupted = None
        if rng.random() < profile.corrupt_p:
            corrupted = _corrupt(raw, rng)
        crash, dec, percept = False, None, None
        try:
            dec, percept = agent.step(raw)
        except Exception as e:                      # una excepcion es un fallo de robustez
            crash = True
            agent.log.log(meta[i]["now"], r.flight_id, "excepcion", error=repr(e))
        out[i] = {"flight_id": r.flight_id, "sched_dep": r.sched_dep, "actual_delayed": bool(r.delayed),
                  "dep_delay": float(r.dep_delay), "late_record": meta[i]["late"], "sensor_dropped": dropped,
                  "corruption": corrupted, "crash": crash,
                  "action": None if dec is None else dec.action,
                  "p_delay": None if dec is None else dec.p_delay,
                  "d_hat": None if dec is None else dec.d_hat,
                  "lead_min": None if percept is None else percept.lead_min,
                  "wx_imputed": None if percept is None else percept.wx_imputed}
    return pd.DataFrame([out[i] for i in range(len(tuples))])


def classification_metrics(df: pd.DataFrame) -> dict:
    d = df[df.action.isin([ALERTAR, "NO_ALERTAR"])]
    if len(d) == 0:
        return {"n": 0, "accuracy": np.nan, "recall": np.nan, "precision": np.nan, "f1": np.nan,
                "base_rate": np.nan, "baseline_acc": np.nan, "alert_rate": np.nan}
    y, yh = d.actual_delayed.to_numpy(), (d.action == ALERTAR).to_numpy()
    tp, fp, fn = int((y & yh).sum()), int((~y & yh).sum()), int((y & ~yh).sum())
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if tp and prec == prec and rec == rec else 0.0
    base = float(y.mean())
    return {"n": int(len(d)), "accuracy": float((y == yh).mean()), "recall": rec, "precision": prec, "f1": f1,
            "base_rate": base, "baseline_acc": max(base, 1 - base), "alert_rate": float(yh.mean())}
