"""REGISTRO (log) de ejecucion: percepciones, decisiones y acciones con marca de tiempo (JSONL comprimido)."""
from __future__ import annotations

import gzip
import json
import math
from datetime import datetime, timezone


def _clean(x):
    """Convierte NaN/Infinity en None para que cada linea sea JSON estricto (valido para jq, pandas, etc.)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


class RunLogger:
    def __init__(self, path=None, run_id="", scenario="", rep=0):
        self.f = gzip.open(path, "wt", encoding="utf-8") if path else None
        self.meta = {"run_id": run_id, "scenario": scenario, "rep": rep}
        self.n = 0

    def log(self, ts_sim, flight_id, phase, **data):
        self.n += 1
        if self.f:
            rec = {"ts_wall": datetime.now(timezone.utc).isoformat(), "ts_sim": str(ts_sim), **self.meta,
                   "flight_id": flight_id, "phase": phase, "data": _clean(data)}
            self.f.write(json.dumps(rec, default=str, allow_nan=False) + "\n")

    def close(self):
        if self.f:
            self.f.close()
