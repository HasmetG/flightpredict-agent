"""Demo en vivo: muestra el ciclo percepcion -> decision -> accion desde cero.
Uso:  python scripts/demo.py --escenario tipico      (vuelos normales)
      python scripts/demo.py --escenario falla       (entradas invalidas, ventana < 3 h y sensor sin dato)"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import joblib
import numpy as np
import pandas as pd

from flightpredict.agent import FlightPredictAgent
from flightpredict.config import MODELS_DIR
from flightpredict.evaluation import run_stream
from flightpredict.logger import RunLogger
from flightpredict.memory import LongTermMemory
from flightpredict.simulator import Profile, generate_flights


class PrintLogger(RunLogger):
    def log(self, ts_sim, flight_id, phase, **d):
        super().log(ts_sim, flight_id, phase, **d)
        if phase == "percepcion":
            print(f"\n[{ts_sim}] PERCEPCION  vuelo={flight_id} {d.get('origin')}->{d.get('dest')} salida={d.get('sched_dep')} pronostico={'SIN DATO' if not d.get('forecast') else 'ok'}")
        elif phase == "decision":
            if d.get("action") == "REVISION_MANUAL":
                print(f"   DECISION    REVISION_MANUAL  motivo={d.get('estado')} {d.get('problemas')}")
            else:
                print(f"   DECISION    {d['action']:<11} P(retraso)={d['p_delay']:.2f} duracion_esp={d['d_hat']:.0f} min U(alertar)={d['u_alert']:+.2f} antelacion={d['lead_min']:.0f} min imputado={d['wx_imputed']}")
        elif phase == "accion":
            print(f"   ACCION      {d['tipo']} {d.get('sugerencia') or ''}")
        elif phase == "retroalimentacion":
            print(f"   [resultado real] retraso={d['retraso_real_min']:.0f} min, acierto={d['acierto']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenario", choices=["tipico", "falla"], default="tipico")
    ap.add_argument("--dias", type=int, default=3, help="aeronaves-dia a simular")
    a = ap.parse_args()
    try:
        model = joblib.load(MODELS_DIR / "delay_model.joblib")
    except Exception as e:      # el .joblib solo se puede leer con la misma version de scikit-learn con que se guardo
        sys.exit(f"No se pudo cargar models/delay_model.joblib ({type(e).__name__}). Ejecute primero: python scripts/train.py")
    lm = LongTermMemory.load(MODELS_DIR / "long_term_memory.json")
    prof = Profile(n_aircraft_days=a.dias) if a.escenario == "tipico" else Profile(
        n_aircraft_days=a.dias, corrupt_p=0.3, late_p=0.3, sensor_dropout_p=0.3)
    flights = generate_flights(prof, seed=2026)
    out = Path(__file__).resolve().parents[1] / "results" / "logs" / f"demo_{a.escenario}.jsonl.gz"
    logger = PrintLogger(out, "demo", a.escenario, 0)
    agent = FlightPredictAgent(model, lm, None, logger)
    df = run_stream(flights, agent, prof, np.random.default_rng(1))
    logger.close()
    print("\n--- resumen ---")
    print(df.action.value_counts().to_string())
    print(f"Mensajes enviados al sistema operativo (simulado): {len(agent.ops.outbox)}  | log: {out}")
