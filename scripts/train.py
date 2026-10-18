"""Entrena el modelo con el historial simulado (sustituto del historial BTS) y valida con datos independientes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import joblib
import numpy as np

from flightpredict.config import MODELS_DIR, SEED_TRAIN
from flightpredict.decision import ALERTAR, utility_of_alert
from flightpredict.memory import LongTermMemory
from flightpredict.model import DelayModel
from flightpredict.simulator import Profile, generate_flights
from flightpredict.training import replay_features

if __name__ == "__main__":
    MODELS_DIR.mkdir(exist_ok=True)
    prof = Profile(name="historial", n_aircraft_days=8000, start_hour=(0.0, 16.0))
    hist = generate_flights(prof, SEED_TRAIN)
    lm = LongTermMemory.from_history(hist)
    feats, delayed, dd = replay_features(hist, lm)
    model = DelayModel().fit(feats, delayed, dd)
    joblib.dump(model, MODELS_DIR / "delay_model.joblib")
    lm.save(MODELS_DIR / "long_term_memory.json")
    feats.assign(delayed=delayed, dep_delay=dd).to_csv(MODELS_DIR / "history_features.csv.gz", index=False)
    val = generate_flights(Profile(name="val", n_aircraft_days=2000, start_hour=(0.0, 16.0)), 999)
    vf, vy, _ = replay_features(val, lm)
    p, d = model.predict(vf)
    alert = np.array([utility_of_alert(pi, di) > 0 for pi, di in zip(p, d)])
    rep = {"n_historial": len(hist), "tasa_retraso_historial": float(hist.delayed.mean()),
           "n_validacion": len(val), "tasa_retraso_validacion": float(vy.mean()),
           "accuracy_validacion": float((alert == vy).mean()),
           "recall_validacion": float((alert & vy).sum() / vy.sum()),
           "precision_validacion": float((alert & vy).sum() / max(1, alert.sum()))}
    (MODELS_DIR / "train_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))
