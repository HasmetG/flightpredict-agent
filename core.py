"""Logica de la interfaz web de FlightPredict-Agent (sin dependencia de ningun framework de UI).

No reimplementa el agente: usa el mismo paquete `flightpredict`, el mismo simulador y el mismo scripts/run_tests.py.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import joblib
import numpy as np
import pandas as pd

from flightpredict.agent import FlightPredictAgent
from flightpredict.config import MODELS_DIR
from flightpredict.evaluation import run_stream
from flightpredict.logger import RunLogger
from flightpredict.memory import LongTermMemory
from flightpredict.simulator import AIRLINES, AIRPORTS, Profile, generate_flights

COLS = ["Hora simulada", "Vuelo", "Fase del ciclo", "Detalle"]
_ASSETS: dict = {}
_LOCK = threading.Lock()
SUITE_LOCK = threading.Lock()


def _retrain_from_scratch():
    from flightpredict.config import SEED_TRAIN
    from flightpredict.model import DelayModel
    from flightpredict.training import replay_features
    hist = generate_flights(Profile(name="historial", n_aircraft_days=8000, start_hour=(0.0, 16.0)), SEED_TRAIN)
    lm = LongTermMemory.from_history(hist)
    feats, delayed, dd = replay_features(hist, lm)
    return DelayModel().fit(feats, delayed, dd), lm, (feats, delayed, dd)


def assets() -> dict:
    """Carga el modelo entrenado; si el .joblib no coincide con la version de scikit-learn, reentrena una sola vez (~1 min)."""
    with _LOCK:
        if not _ASSETS:
            lm = LongTermMemory.load(MODELS_DIR / "long_term_memory.json")
            hf = pd.read_csv(MODELS_DIR / "history_features.csv.gz")
            base = (hf.drop(columns=["delayed", "dep_delay"]), hf.delayed.to_numpy(), hf.dep_delay.to_numpy())
            try:
                model = joblib.load(MODELS_DIR / "delay_model.joblib")
                _ASSETS["origen_modelo"] = "models/delay_model.joblib (entrenado con scripts/train.py)"
            except Exception as e:
                print("Reentrenando modelo:", repr(e), flush=True)
                model, lm, base = _retrain_from_scratch()
                _ASSETS["origen_modelo"] = "reentrenado al iniciar (el .joblib no era compatible con esta version de scikit-learn)"
            _ASSETS.update(model=model, lm=lm, base=base)
        return _ASSETS


def new_agent(logger):
    a = assets()
    return FlightPredictAgent(a["model"], a["lm"].clone(), a["base"], logger)


def _row(ts, fid, phase, d):
    ts = "" if ts in (None, "None") else str(ts)[:16].replace("T", " ")
    if phase == "percepcion":
        fc = d.get("forecast")
        det = (f"{d.get('origin')} -> {d.get('dest')} | salida prog. {str(d.get('sched_dep'))[:16].replace('T', ' ')} | "
               f"pronóstico: {'SIN DATO' if not fc else ('inválido' if isinstance(fc, dict) and fc.get('temp') == 999.0 else 'ok')}")
        return [ts, fid, "1 · PERCEPCIÓN", det]
    if phase == "decision":
        if d.get("action") == "REVISION_MANUAL":
            return [ts, fid, "2 · DECISIÓN", f"REVISION_MANUAL — {d.get('estado')} {d.get('problemas')}"]
        return [ts, fid, "2 · DECISIÓN",
                f"{d['action']} | P(retraso)={d['p_delay']:.2f} | duración esp.={d['d_hat']:.0f} min | "
                f"U(alertar)={d['u_alert']:+.2f} | antelación={d['lead_min']:.0f} min | clima imputado={d['wx_imputed']}"]
    if phase == "accion":
        return [ts, fid, "3 · ACCIÓN", f"{d.get('tipo')} {d.get('sugerencia') or ''}".strip()]
    if phase == "retroalimentacion":
        return [ts, fid, "4 · RESULTADO REAL", f"retraso real={d['retraso_real_min']:.0f} min | acierto={d['acierto']}"]
    return [ts, fid, phase.upper(), str(d)]


class CollectingLogger(RunLogger):
    """Igual que RunLogger (escribe el log JSONL.gz con marca de tiempo) y ademas guarda los eventos para mostrarlos."""

    def __init__(self, path, run_id, scenario):
        super().__init__(path, run_id, scenario, 0)
        self.rows = []

    def log(self, ts_sim, flight_id, phase, **d):
        super().log(ts_sim, flight_id, phase, **d)
        self.rows.append(_row(ts_sim, flight_id, phase, d))


def run_demo(tipico: bool, dias: int):
    """Demo sobre el simulador. Devuelve (DataFrame del log, resumen markdown, bytes del log .jsonl.gz)."""
    prof = Profile(n_aircraft_days=int(dias)) if tipico else Profile(
        n_aircraft_days=int(dias), corrupt_p=0.3, late_p=0.3, sensor_dropout_p=0.3)
    flights = generate_flights(prof, seed=2026)
    out = Path(tempfile.mkdtemp()) / "log_demo.jsonl.gz"
    logger = CollectingLogger(out, "demo", "tipico" if tipico else "falla")
    agent = new_agent(logger)
    df = run_stream(flights, agent, prof, np.random.default_rng(1))
    logger.close()
    counts = df.action.value_counts().to_dict()
    resumen = {"Vuelos procesados": len(df), **{k: int(v) for k, v in counts.items()},
               "Mensajes al sistema operativo (simulado)": len(agent.ops.outbox),
               "Excepciones (fallos de robustez)": int(df.crash.sum())}
    return pd.DataFrame(logger.rows, columns=COLS), resumen, out.read_bytes()


def run_manual(origin, dest, airline, sched_dep_txt, lead_h, has_fc, vis, wind, precip, temp, has_prev, prev_delay):
    """Un vuelo con entradas controladas por el usuario. Devuelve (decision, percepto, DataFrame del log, outbox)."""
    logger = CollectingLogger(None, "manual", "manual")
    agent = new_agent(logger)
    try:
        sd = datetime.fromisoformat(sched_dep_txt.strip())
        sd_s, now_s = sd.isoformat(), (sd - timedelta(hours=float(lead_h))).isoformat()
    except ValueError:                                  # fecha no interpretable: se la pasamos tal cual al agente
        sd_s, now_s, sd = sched_dep_txt, "2026-07-15T05:00:00", datetime(2026, 7, 15, 8, 30)
    raw = {"flight_id": "MANUAL-0001", "tail": "TMANUAL", "leg": 2 if has_prev else 1, "airline": airline,
           "origin": origin, "dest": dest, "sched_dep": sd_s, "prev_sched_arr": None, "now": now_s,
           "forecast": {"vis": float(vis), "wind": float(wind), "precip": float(precip), "temp": float(temp)} if has_fc else None}
    if has_prev:   # el tramo anterior de la misma aeronave salio con retraso -> estado interno (memoria de corto plazo)
        raw["prev_sched_arr"] = (sd - timedelta(minutes=55)).isoformat()
        agent.mem.update_from_outcome("TMANUAL", 1, float(prev_delay), sd - timedelta(hours=4))
    dec, percept = agent.step(raw)
    return dec, percept, pd.DataFrame(logger.rows, columns=COLS), json.dumps(agent.ops.outbox, indent=2, ensure_ascii=False, default=str)


class _Progress(io.TextIOBase):
    def __init__(self, cb, total=65):
        self.cb, self.total, self.n, self.buf = cb, total, 0, ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if "rep" in line and "acc=" in line:
                self.n += 1
                self.cb(self.n / self.total, f"{line.split(':')[0]}  ({self.n}/{self.total})")
        return len(s)


def _fmt_tabla(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["cumple"] = t["cumple"].map({True: "✅ Cumple", False: "❌ No cumple"})
    t = t[["medida", "formula", "umbral", "casos", "resultado", "cumple"]]
    t.columns = ["Medida", "Fórmula", "Umbral (fijado antes)", "Casos ejecutados", "Resultado obtenido", "¿Cumple?"]
    return t


def run_suite(progress_cb=lambda frac, text: None):
    """Ejecuta scripts/run_tests.py (13 escenarios x 5 repeticiones) escribiendo en una carpeta temporal.
    Devuelve (tabla, resumen por escenario, bytes del .zip con logs y CSV)."""
    import run_tests
    assets()
    tmp = Path(tempfile.mkdtemp())
    old = run_tests.RESULTS_DIR
    run_tests.RESULTS_DIR = tmp
    try:
        with contextlib.redirect_stdout(_Progress(progress_cb)):
            run_tests.main()
    finally:
        run_tests.RESULTS_DIR = old
    tabla = _fmt_tabla(pd.read_csv(tmp / "tabla_resultados.csv"))
    por_esc = pd.read_csv(tmp / "resumen_por_escenario.csv")
    zpath = tmp / "evidencia_pruebas.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in tmp.rglob("*"):
            if f.is_file() and f != zpath:
                z.write(f, f.relative_to(tmp))
    return tabla, por_esc, zpath.read_bytes()


def saved_results():
    return _fmt_tabla(pd.read_csv(ROOT / "results" / "tabla_resultados.csv")), pd.read_csv(ROOT / "results" / "resumen_por_escenario.csv")


def manual_markdown(dec, percept) -> str:
    if dec.action == "REVISION_MANUAL":
        return (f"### Decisión: `REVISION_MANUAL`\nEl agente **no emitió predicción** porque la percepción no pasó la validación.\n\n"
                f"- Estado: **{dec.reason}**\n- Se marcó el vuelo para revisión de un operador (sin excepción).")
    return (f"### Decisión: `{dec.action}`\n"
            f"- P(retraso ≥ 15 min) = **{dec.p_delay:.1%}**\n- Duración esperada si se retrasa = **{dec.d_hat:.0f} min**\n"
            f"- U(alertar) = P·β·d − (1−P)·C_FA = **{dec.u_alert:+.2f}** (U(no alertar) = 0)\n"
            f"- Antelación = {percept.lead_min:.0f} min · pronóstico imputado con climatología: **{percept.wx_imputed}**\n"
            f"- Sugerencia al operador: **{dec.suggestion or '—'}**")
