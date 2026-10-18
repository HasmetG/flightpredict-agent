"""FlightPredict-Agent: ciclo PERCEPCION -> DECISION -> ACCION (agente basado en utilidad, con modelo y aprendizaje)."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .actuators import Actuators, OperationsSystemStub
from .config import LEAD_MIN
from .decision import ALERTAR, REVISION, Decision, decide
from .logger import RunLogger
from .memory import AircraftMemory, LongTermMemory
from .model import DelayModel
from .perception import FEATURES, OK, extract_features, perceive

PLAN = ["recopilar_y_validar_entradas", "consultar_historial_similares", "estimar_probabilidad_y_duracion",
        "comparar_utilidad", "emitir_alerta_y_sugerencia"]       # componente IBM 2: planificacion


class FlightPredictAgent:
    def __init__(self, model: DelayModel, long_memory: LongTermMemory, base=None, logger: RunLogger | None = None):
        self.model, self.long, self.base = model, long_memory, base   # base = (feats_df, delayed, dep_delay)
        self.mem = AircraftMemory()
        self.ops = OperationsSystemStub()
        self.actuators = Actuators(self.ops)
        self.log = logger or RunLogger()
        self.pending = {}
        self.feedback = []
        self.n_retrains = 0

    def fresh(self, logger=None):
        """Nueva instancia con memoria de corto plazo vacia; el modelo base no se muta (retrain crea otro)."""
        return FlightPredictAgent(self.model, self.long.clone(), self.base, logger)

    # ---- planificacion -------------------------------------------------------------------------------
    @staticmethod
    def trigger_time(sched_dep):
        """El agente se activa a LEAD_MIN minutos de la salida programada."""
        return sched_dep - timedelta(minutes=LEAD_MIN)

    # ---- ciclo percepcion -> decision -> accion ------------------------------------------------------------------
    def perceive(self, raw):
        fid = raw.get("flight_id") if isinstance(raw, dict) else None
        now = raw.get("now") if isinstance(raw, dict) else None
        self.log.log(now, fid, "percepcion", sched_dep=raw.get("sched_dep") if isinstance(raw, dict) else None,
                     origin=raw.get("origin") if isinstance(raw, dict) else None,
                     dest=raw.get("dest") if isinstance(raw, dict) else None,
                     forecast=raw.get("forecast") if isinstance(raw, dict) else None)
        return perceive(raw, self.long)

    def decide(self, percept):
        feats = extract_features(percept, self.mem)
        p, d = self.model.predict(pd.DataFrame([feats]))
        dec = decide(percept.flight_id, float(p[0]), float(d[0]), feats["est_carry"])
        self.pending[percept.flight_id] = (feats, dec)
        self.log.log(percept.now, percept.flight_id, "decision", plan=PLAN, action=dec.action, p_delay=dec.p_delay,
                     d_hat=dec.d_hat, u_alert=dec.u_alert, lead_min=percept.lead_min,
                     wx_imputed=percept.wx_imputed, issues=percept.issues,
                     last_delay=feats["last_delay"], est_carry=feats["est_carry"])
        return dec

    def act(self, dec: Decision, percept):
        if dec.action == ALERTAR:
            self.actuators.send_alert(dec, percept, self.long.similar_flights_rate(percept.origin, percept.sched_dep.hour))
            self.actuators.suggest_reassignment(dec)
            self.log.log(percept.now, dec.flight_id, "accion", tipo="ALERTA+SUGERENCIA", sugerencia=dec.suggestion)
        else:
            self.log.log(percept.now, dec.flight_id, "accion", tipo="SIN_ALERTA")

    def step(self, raw):
        """Un ciclo completo para un vuelo. Devuelve (decision, percepto)."""
        percept, status, issues = self.perceive(raw)
        if status != OK:
            fid = raw.get("flight_id") if isinstance(raw, dict) else None
            dec = Decision(str(fid), REVISION, reason=status)
            self.actuators.flag_manual_review(fid, status, issues)
            self.log.log(raw.get("now") if isinstance(raw, dict) else None, fid, "decision", action=REVISION,
                         estado=status, problemas=issues)
            self.log.log(raw.get("now") if isinstance(raw, dict) else None, fid, "accion", tipo="MARCAR_REVISION_MANUAL")
            return dec, None
        dec = self.decide(percept)
        self.act(dec, percept)
        return dec, percept

    # ---- aprendizaje y adaptacion -------------------------------------------------------------------
    def receive_outcome(self, flight_id, tail, leg, dep_delay, actual_dep, delay_threshold=15):
        """Resultado real del vuelo: actualiza la memoria de la aeronave y acumula retroalimentacion."""
        self.mem.update_from_outcome(tail, leg, dep_delay, actual_dep)
        item = self.pending.pop(flight_id, None)
        if item is not None:
            feats, dec = item
            self.feedback.append((feats, bool(dep_delay >= delay_threshold), float(dep_delay)))
            self.actuators.record_outcome(flight_id, dec.p_delay, dec.action == ALERTAR, dep_delay)
            self.log.log(actual_dep, flight_id, "retroalimentacion", retraso_real_min=dep_delay,
                         acierto=bool((dec.action == ALERTAR) == (dep_delay >= delay_threshold)))

    def retrain(self, feedback_weight=5.0):
        """Reentrena con historial base + retroalimentacion acumulada (las muestras nuevas pesan mas)."""
        bf, bd, bl = self.base
        nf = pd.DataFrame([f for f, _, _ in self.feedback])[FEATURES]
        feats = pd.concat([bf, nf], ignore_index=True)
        delayed = np.concatenate([bd, [y for _, y, _ in self.feedback]])
        dd = np.concatenate([bl, [d for _, _, d in self.feedback]])
        w = np.concatenate([np.ones(len(bf)), np.full(len(nf), feedback_weight)])
        self.model = DelayModel(seed=self.n_retrains + 1).fit(feats, delayed, dd, w)
        self.n_retrains += 1
        self.log.log(None, None, "aprendizaje", muestras_nuevas=len(nf), reentrenamiento=self.n_retrains)
