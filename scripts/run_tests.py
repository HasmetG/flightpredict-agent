"""Fase 3: ejecuta los 13 escenarios x 5 repeticiones, guarda logs y calcula la tabla de resultados contra las medidas M1-M4.
Los umbrales se leen de config/thresholds.json (fijados antes de ejecutar)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import joblib
import numpy as np
import pandas as pd

from flightpredict.agent import FlightPredictAgent
from flightpredict.config import MODELS_DIR, RESULTS_DIR, load_thresholds
from flightpredict.evaluation import classification_metrics, run_stream
from flightpredict.logger import RunLogger
from flightpredict.memory import LongTermMemory
from flightpredict.simulator import HUBS, Profile, generate_flights

H = ["ORD", "JFK", "ATL", "SFO", "DFW", "BOS"]
SCENARIOS = [  # (id, nombre, tipo, perfil, retrain_every)
    ("S01", "Operación normal diurna", "normal", Profile(), None),
    ("S02", "Hub congestionado en hora pico", "normal", Profile(start_hour=(12.0, 16.0), airport_weights={a: 1 for a in H}), None),
    ("S03", "Tormenta severa", "limite", Profile(p_storm=0.6), None),
    ("S04", "Madrugada de bajo tráfico", "limite",
     Profile(start_hour=(0.0, 3.0), airport_weights={a: 1 for a in ["PHX", "LAS", "MSP", "MCO", "SEA", "CLT"]}), None),
    ("S05", "Retrasos en cadena por incidentes", "limite", Profile(incident_p=0.15, incident_mean=80.0), None),
    ("S06", "Aeropuertos poco frecuentes", "limite",
     Profile(airport_weights={"ANC": 3, "BZN": 3, "MSO": 3, "PHX": 1, "DEN": 1, "SEA": 1}), None),
    ("S07", "Temporada alta de verano", "normal", Profile(month=7, p_storm=0.08), None),
    ("S08", "Aerolínea poco vista", "limite", Profile(airline_weights={"XP": 1.0}), None),
    ("S09", "Invierno con clima adverso", "normal", Profile(month=1, p_storm=0.15), None),
    ("S10", "Deriva operativa con retroalimentación", "limite",
     Profile(n_aircraft_days=150, cong_scale=1.3, base_shift=0.5, airport_extra={"ORD": 1.0, "JFK": 1.0, "ATL": 0.8}), 150),
    ("S11", "FALLA: entradas inválidas", "falla", Profile(corrupt_p=0.5), None),
    ("S12", "FALLA: ventana menor a 3 h", "falla", Profile(late_p=0.4), None),
    ("S13", "FALLA: sensor meteorológico sin dato", "falla", Profile(sensor_dropout_p=0.6), None),
]


def main():
    th = load_thresholds()
    reps = th["repeticiones"]
    (RESULTS_DIR / "logs").mkdir(parents=True, exist_ok=True)
    try:
        model = joblib.load(MODELS_DIR / "delay_model.joblib")
    except Exception as e:      # el .joblib solo se puede leer con la misma version de scikit-learn con que se guardo
        sys.exit(f"No se pudo cargar models/delay_model.joblib ({type(e).__name__}). Ejecute primero: python scripts/train.py")
    lm = LongTermMemory.load(MODELS_DIR / "long_term_memory.json")
    hf = pd.read_csv(MODELS_DIR / "history_features.csv.gz")
    base = (hf.drop(columns=["delayed", "dep_delay"]), hf.delayed.to_numpy(), hf.dep_delay.to_numpy())
    proto = FlightPredictAgent(model, lm, base)
    runs, all_flights = [], []
    for si, (sid, name, kind, prof, retrain_every) in enumerate(SCENARIOS, start=1):
        for rep in range(1, reps + 1):
            seed = 1000 * si + rep
            flights = generate_flights(prof, seed)
            logger = RunLogger(RESULTS_DIR / "logs" / f"{sid}_rep{rep}.jsonl.gz", f"{sid}-{rep}", sid, rep)
            agent = proto.fresh(logger)
            rng = np.random.default_rng(seed + 777)
            df = run_stream(flights, agent, prof, rng, retrain_every)
            logger.close()
            df.insert(0, "escenario", sid)
            df.insert(1, "rep", rep)
            all_flights.append(df)
            m = classification_metrics(df)
            has_p = df.lead_min.notna()
            row = {"escenario": sid, "nombre": name, "tipo": kind, "rep": rep, "seed": seed, "vuelos": len(df),
                   "retrains": agent.n_retrains, "crashes": int(df.crash.sum()), **m,
                   "pred_emitidas": int(has_p.sum()), "pred_lead_ok": int((df.lead_min[has_p] >= th["M2_antelacion_min_minutos"]).sum())}
            c = df[df.corruption.notna()]
            row["M4_S11"] = float((c.action == "REVISION_MANUAL").mean()) if len(c) else np.nan
            row["falsas_marcas_S11"] = int(((df.corruption.isna()) & (df.action == "REVISION_MANUAL")).sum()) if sid == "S11" else 0
            l = df[df.late_record]
            row["M4_S12"] = float((l.action == "REVISION_MANUAL").mean()) if len(l) else np.nan
            s = df[df.sensor_dropped]
            row["M4_S13"] = float(((s.action.isin(["ALERTAR", "NO_ALERTAR"])) & (s.wx_imputed == True)).mean()) if len(s) else np.nan
            runs.append(row)
            print(f"{sid} rep{rep}: n={len(df)} acc={m['accuracy']:.3f} rec={m['recall']:.3f} crashes={row['crashes']}", flush=True)
    R = pd.DataFrame(runs)
    pd.concat(all_flights).to_csv(RESULTS_DIR / "vuelos_detalle.csv.gz", index=False)
    R.to_csv(RESULTS_DIR / "detalle_por_corrida.csv", index=False)

    # ---- resumen por escenario (media y desviacion estandar sobre repeticiones) ----
    agg = R.groupby(["escenario", "nombre", "tipo"]).agg(
        vuelos=("vuelos", "sum"), exactitud_media=("accuracy", "mean"), exactitud_std=("accuracy", lambda x: x.std(ddof=1)),
        recall_media=("recall", "mean"), recall_std=("recall", lambda x: x.std(ddof=1)),
        precision_media=("precision", "mean"), base_media=("base_rate", "mean"), baseline_acc=("baseline_acc", "mean"),
        crashes=("crashes", "sum")).reset_index()
    agg.to_csv(RESULTS_DIR / "resumen_por_escenario.csv", index=False)

    ok = R[R.tipo != "falla"]
    m1_mean, m1_std = ok.accuracy.mean(), ok.accuracy.std(ddof=1)
    m3_mean, m3_std = ok.recall.mean(), ok.recall.std(ddof=1)
    m2 = R.pred_lead_ok.sum() / R.pred_emitidas.sum()
    m4 = {k: R[k].mean() for k in ["M4_S11", "M4_S12", "M4_S13"]}
    m4_min = min(m4.values()); crashes = int(R.crashes.sum())
    flights_ok = int(ok.vuelos.sum())
    table = [
        {"medida": "M1 Exactitud de clasificación (retrasado / no retrasado)", "formula": "(VP + VN) / total; media de 50 corridas (S01–S10 × 5 rep.)",
         "umbral": f"≥ {th['M1_exactitud_media_min']:.0%}", "casos": f"10 escenarios × 5 rep. = 50 corridas, {flights_ok} vuelos",
         "resultado": f"{m1_mean:.1%} (DE {m1_std*100:.1f} pts)", "cumple": bool(m1_mean >= th["M1_exactitud_media_min"]),
         "evidencia": "results/detalle_por_corrida.csv, results/vuelos_detalle.csv.gz, results/logs/S01-S10"},
        {"medida": "M2 Antelación de la predicción", "formula": "predicciones con antelación ≥ 180 min / predicciones emitidas",
         "umbral": f"≥ {th['M2_proporcion_min']:.0%}", "casos": f"13 escenarios × 5 rep. = 65 corridas, {int(R.pred_emitidas.sum())} predicciones",
         "resultado": f"{m2:.1%}", "cumple": bool(m2 >= th["M2_proporcion_min"]),
         "evidencia": "columna lead_min de results/vuelos_detalle.csv.gz; fase «decision» de los logs"},
        {"medida": "M3 Sensibilidad (recall) de vuelos retrasados", "formula": "VP / (VP + FN); media de 50 corridas (S01–S10 × 5 rep.)",
         "umbral": f"≥ {th['M3_recall_media_min']:.0%}", "casos": f"10 escenarios × 5 rep. = 50 corridas, {flights_ok} vuelos",
         "resultado": f"{m3_mean:.1%} (DE {m3_std*100:.1f} pts)", "cumple": bool(m3_mean >= th["M3_recall_media_min"]),
         "evidencia": "results/detalle_por_corrida.csv (columna recall)"},
        {"medida": "M4 Manejo de fallas (entrada inválida, ventana < 3 h, sensor sin dato)",
         "formula": "casos de falla manejados correctamente / casos de falla inyectados (sin excepciones)",
         "umbral": f"≥ {th['M4_manejo_fallas_min']:.0%} en cada escenario de falla",
         "casos": "3 escenarios de falla × 5 rep. = 15 corridas",
         "resultado": f"S11 {m4['M4_S11']:.1%}; S12 {m4['M4_S12']:.1%}; S13 {m4['M4_S13']:.1%}; excepciones: {crashes}",
         "cumple": bool(m4_min >= th["M4_manejo_fallas_min"] and crashes == 0),
         "evidencia": "logs S11, S12 y S13 (fase «accion» = MARCAR_REVISION_MANUAL) y columnas M4_* del detalle"},
    ]
    T = pd.DataFrame(table)
    T.to_csv(RESULTS_DIR / "tabla_resultados.csv", index=False)
    summary = {"umbrales": th, "M1_media": m1_mean, "M1_std": m1_std, "M2": m2, "M3_media": m3_mean, "M3_std": m3_std,
               "M4": m4, "excepciones": crashes, "falsas_marcas_S11": int(R.falsas_marcas_S11.sum()),
               "total_vuelos": int(R.vuelos.sum()), "total_corridas": len(R)}
    (RESULTS_DIR / "resumen.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    import gzip, shutil
    muestra = RESULTS_DIR / "logs_muestra"; muestra.mkdir(exist_ok=True)
    for nm in ("S01_rep1", "S11_rep1", "S13_rep1"):      # copias sin comprimir (JSONL de texto) para abrir con cualquier editor
        with gzip.open(RESULTS_DIR / "logs" / f"{nm}.jsonl.gz", "rb") as fi, open(muestra / f"{nm}.jsonl", "wb") as fo:
            shutil.copyfileobj(fi, fo)
    print("\n", T[["medida", "umbral", "resultado", "cumple"]].to_string(index=False))
    print(agg[["escenario", "exactitud_media", "exactitud_std", "recall_media", "precision_media", "baseline_acc"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
