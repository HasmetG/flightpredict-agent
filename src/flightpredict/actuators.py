"""ACTUADORES / LLAMADA DE HERRAMIENTAS (componente IBM 5): escriben en el sistema operativo de la aerolinea (simulado)."""
from __future__ import annotations


class OperationsSystemStub:
    """Sustituto del sistema operativo de la aerolinea: recibe alertas, sugerencias, marcas de revision y registros."""

    def __init__(self):
        self.outbox = []

    def send(self, kind: str, payload: dict):
        self.outbox.append({"kind": kind, **payload})

    def count(self, kind):
        return sum(1 for m in self.outbox if m["kind"] == kind)


class Actuators:
    def __init__(self, ops: OperationsSystemStub):
        self.ops = ops

    def send_alert(self, d, p, context_rate):
        self.ops.send("ALERTA", {"flight_id": d.flight_id, "p_delay": round(d.p_delay, 4),
                                 "d_hat_min": round(d.d_hat, 1), "origin": p.origin,
                                 "tasa_historica_similares": round(context_rate, 3)})

    def suggest_reassignment(self, d):
        self.ops.send("SUGERENCIA_REASIGNACION", {"flight_id": d.flight_id, "accion": d.suggestion})

    def flag_manual_review(self, flight_id, status, issues):
        self.ops.send("REVISION_MANUAL", {"flight_id": flight_id, "estado": status, "problemas": issues})

    def record_outcome(self, flight_id, predicted_p, predicted_alert, actual_delay):
        self.ops.send("REGISTRO_RESULTADO", {"flight_id": flight_id, "p_delay": predicted_p,
                                             "alerta": predicted_alert, "retraso_real_min": round(actual_delay, 1)})
