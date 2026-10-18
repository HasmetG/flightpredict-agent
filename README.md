# FlightPredict-Agent

Agente inteligente **basado en utilidad (con modelo interno y aprendizaje)** que, 3 horas antes de la salida programada de cada vuelo,
estima la probabilidad y la duración esperada de un retraso y decide si alerta al equipo de operaciones de una aerolínea.
Implementación de la Tarea 3 del curso *Inteligencia Artificial* (UTB). Diseño original: *FlightPredict-Agent* (Tarea 2).

> **Importante:** el entorno (clima, rotaciones de aeronaves, historial de vuelos, sistema operativo de la aerolínea) es **simulado**
> (`src/flightpredict/simulator.py`). Los resultados describen el comportamiento del agente frente a ese simulador, no frente a datos reales del BTS.

## Estructura

| Ruta | Contenido |
|---|---|
| `src/flightpredict/perception.py` | **Percepción**: validación, imputación de clima, extracción de características |
| `src/flightpredict/memory.py` | **Memoria**: estado por aeronave (corto plazo), climatología/tasas históricas (largo plazo) |
| `src/flightpredict/model.py` | Modelo ML (HistGradientBoosting): P(retraso ≥ 15 min) y duración esperada |
| `src/flightpredict/decision.py` | **Decisión**: función de utilidad `U(alertar) = P·β·d − (1−P)·C_FA` |
| `src/flightpredict/actuators.py` | **Acción**: alerta, sugerencia de reasignación, revisión manual, registro del resultado |
| `src/flightpredict/agent.py` | Ciclo `perceive → decide → act` + `receive_outcome` y `retrain` (aprendizaje) |
| `src/flightpredict/simulator.py` | Entorno simulado (verdad terreno oculta al agente) |
| `src/flightpredict/logger.py` | Log JSONL comprimido con marca de tiempo (percepción, decisión, acción, retroalimentación) |
| `config/thresholds.json` | Umbrales de aceptación **fijados antes** de ejecutar las pruebas |
| `scripts/` | `train.py`, `demo.py`, `run_tests.py`, `sensibilidad_utilidad.py`, `figuras.py`, `dibujar_secuencia.py` |
| `results/` | Logs, tablas CSV y figuras de la Fase 3 |
| `docs/diagramas/` | Arquitectura (`.dot`), secuencia UML (`.mmd` Mermaid + PNG) |

## Ejecución desde cero (Python ≥ 3.10; probado con 3.12.3)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/train.py            # genera historial simulado, entrena y valida el modelo (≈ 1 min)
python scripts/demo.py --escenario tipico --dias 1     # demo del ciclo percepción → decisión → acción
python scripts/demo.py --escenario falla  --dias 2     # demo de fallas esperadas
python scripts/run_tests.py        # 13 escenarios x 5 repeticiones (≈ 3-5 min) -> results/
python scripts/sensibilidad_utilidad.py && python scripts/figuras.py
```

Las semillas están fijas (`1000*escenario + repetición`), por lo que los resultados son repetibles **con las mismas versiones de `requirements.txt`**; con otras versiones de scikit-learn las cifras pueden variar en décimas (probado: M3 = 46,2 % con scikit-learn 1.9.1 frente a 46,0 %). Los logs son JSON estricto (una línea por evento; `NaN` se guarda como `null`); copias sin comprimir de tres corridas en `results/logs_muestra/`. Los logs de cada corrida quedan en
`results/logs/<escenario>_rep<n>.jsonl.gz` (`zcat archivo | head`).

## Plataforma desplegada (Streamlit Community Cloud)
La interfaz web (`streamlit_app.py` + `core.py`) ejecuta **el mismo código del agente** (`src/flightpredict/`), el mismo simulador y el mismo
`scripts/run_tests.py`; no reimplementa nada. Pestañas: demo típica y de falla, vuelo manual, pruebas M1–M4 (65 corridas) y diagramas.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py        # http://localhost:8501
```
Enlace público: **PEGAR_AQUI_EL_ENLACE_DE_STREAMLIT** (si la app está dormida, pulsar «Yes, get this app back up!»; tarda ~1 min).

## Documento de la entrega
```bash
pip install -r requirements-doc.txt
python scripts/construir_documento.py     # genera docs/FlightPredict_Agent_Entrega_Final.docx con las cifras de results/*.csv
```
Abrir el .docx, completar los campos resaltados en amarillo (retroalimentación del docente y enlaces) y exportar a PDF.

## Datos reales (opcional)
Para usar el historial real del BTS, reemplace `generate_flights` en `scripts/train.py` por un cargador que produzca las mismas columnas
(origen, destino, aerolínea, `sched_dep`, aeronave, retraso real, pronóstico) y vuelva a ejecutar `train.py` y `run_tests.py`.

## Resultado resumido (ver documento PDF, sección 9.7)
M1 exactitud 74,0 % (umbral ≥ 70 %) ✔ · M2 antelación 100 % ✔ · M3 recall 46,0 % (umbral ≥ 60 %) ✘ · M4 manejo de fallas 100 % ✔.
