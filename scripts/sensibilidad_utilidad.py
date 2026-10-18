"""Compromiso exactitud/recall al variar el valor BETA de la funcion de utilidad (solo datos de VALIDACION, no de prueba)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from flightpredict.config import COST_FALSE_ALARM, MODELS_DIR, RESULTS_DIR
from flightpredict.memory import LongTermMemory
from flightpredict.simulator import Profile, generate_flights
from flightpredict.training import replay_features

model = joblib.load(MODELS_DIR / "delay_model.joblib")
lm = LongTermMemory.load(MODELS_DIR / "long_term_memory.json")
val = generate_flights(Profile(n_aircraft_days=2000, start_hour=(0.0, 16.0)), 999)
vf, vy, _ = replay_features(val, lm)
p, d = model.predict(vf)
rows = []
for beta in [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]:
    a = (p * beta * d - (1 - p) * COST_FALSE_ALARM) > 0
    rows.append({"BETA": beta, "exactitud": (a == vy).mean(), "recall": (a & vy).sum() / vy.sum(),
                 "precision": (a & vy).sum() / max(1, a.sum()), "tasa_alertas": a.mean()})
df = pd.DataFrame(rows)
df.to_csv(RESULTS_DIR / "sensibilidad_utilidad_validacion.csv", index=False)
print(df.round(3).to_string(index=False))
fig, ax = plt.subplots(figsize=(6.2, 3.6))
ax.plot(df.BETA, df.exactitud * 100, "o-", label="Exactitud")
ax.plot(df.BETA, df.recall * 100, "s-", label="Recall")
ax.axhline(70, color="C0", ls="--", lw=0.8); ax.axhline(60, color="C1", ls="--", lw=0.8)
ax.axvline(0.05, color="gray", ls=":", lw=1)
ax.set_xlabel("BETA (valor por minuto de retraso anticipado)"); ax.set_ylabel("%")
ax.set_title("Compromiso exactitud vs. recall (validacion)", fontsize=10); ax.legend(); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(RESULTS_DIR / "fig_compromiso_beta.png", dpi=170)
