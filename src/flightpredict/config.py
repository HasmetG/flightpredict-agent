"""Constantes del agente y carga de umbrales de aceptacion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAD_MIN = 180                 # antelacion minima de la prediccion (minutos) - Seccion 7 del diseno
DELAY_THRESHOLD_MIN = 15       # un vuelo se considera retrasado si sale >= 15 min tarde
BETA_PER_MIN = 0.05            # valor (unidades de utilidad) de anticipar cada minuto de retraso esperado
COST_FALSE_ALARM = 1.0         # costo (unidades de utilidad) de una alerta innecesaria
SEED_TRAIN = 12345
MIN_TURNAROUND = 30            # minutos minimos en tierra entre dos vuelos de la misma aeronave
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"


def load_thresholds() -> dict:
    return json.loads((ROOT / "config" / "thresholds.json").read_text(encoding="utf-8"))
