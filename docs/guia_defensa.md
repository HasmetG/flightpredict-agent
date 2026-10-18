# Guía de defensa (para el video y para preguntas del docente)

Cada respuesta está respaldada por el código del repositorio. Léanla **después** de haber leído `agent.py`, `decision.py`, `perception.py` y `evaluation.py` (≈ 350 líneas en total). Reparto sugerido: cada integrante explica al menos la mitad de las preguntas.

## Diseño y elección
1. **¿Por qué eligieron FlightPredict y no ClauseCheck?** Matriz ponderada: 4,25 vs 3,35. Pesó el costo (CPU, sin API de pago), la viabilidad con Python/scikit-learn y que la verdad terreno es objetiva. La decisión no cambia al mover ±10 puntos Costo o Viabilidad. Se pierde NLP jurídico con CUAD.
2. **¿Por qué es un agente basado en utilidad y no solo un clasificador?** `decision.py`: compara U(alertar) = P·β·d − (1−P)·C_FA contra U(no alertar) = 0. El umbral de probabilidad P* = C_FA/(C_FA+β·d) cambia con la duración esperada d. Un clasificador con umbral fijo no hace eso.
3. **¿De dónde salen β = 0,05 y C_FA = 1?** Son supuestos del diseño (`config.py`), no se ajustaron viendo los resultados de prueba. Con costos reales de la aerolínea se calibrarían; ese es trabajo futuro.
4. **¿Dónde está el ciclo percepción → decisión → acción?** `agent.py`: `perceive()` (valida y registra), `decide()` (modelo + utilidad), `act()` (actuadores) y `step()` que los encadena. Cada fase escribe una línea con marca de tiempo en el log.
5. **¿Qué parte razona el código y qué parte la librería?** El código: validación, memoria, función de utilidad, ciclo y aprendizaje por lotes. scikit-learn (HistGradientBoosting) solo estima P(retraso) y la duración. No hay LLM.

## Simulador y datos
6. **¿Por qué un simulador y no datos reales del BTS?** No hay sistema de aerolínea ni API meteorológica real, y el simulador permite repeticiones y verdad terreno conocida. Limitación: los resultados valen contra el simulador, no contra el tráfico real (sección 9.8). El README explica cómo cambiar la fuente por el BTS.
7. **¿El simulador es estocástico?** Sí: clima, congestión, incidentes ocultos y error de pronóstico usan aleatoriedad con semilla. Por eso hay 5 repeticiones por escenario con media y desviación estándar.

## Pruebas
8. **¿Qué se cumplió y qué no?** M1 exactitud 74,0 % (≥ 70 %) sí; M2 antelación 100 % sí; M4 fallas 100 % sí; M3 recall 46,0 % (≥ 60 %) **no**.
9. **¿Por qué falla M3 y qué harían?** Con β = 0,05 el agente alerta solo si P supera ≈ 0,25–0,40 y el modelo rara vez llega ahí en retrasos ordinarios; además la observabilidad es parcial. Subir β a 0,10 da recall 67,0 % pero exactitud 64,7 %: M1 y M3 no se cumplen a la vez con este modelo. Cambiarían: recalcular a T−90/T−60, acordar costos con operaciones y fusionar M1 y M3 en una métrica (F1 o costo esperado) con umbral nuevo fijado antes.
10. **Pregunta probable: ¿M1 ≥ 70 % no es trivial?** Sí, con ≈ 20 % de retrasos «nunca alertar» ya da ≈ 80 %, y en 6 de 10 escenarios la línea base supera al agente. Por eso se agregó M3 y el documento lo reconoce.
11. **Pregunta probable: ¿M2 = 100 % no es circular?** En buena parte sí: el disparador se activa a T−180 y la validación manda a revisión manual lo que llega con menos ventana. Prueba que el agente respeta la regla, no que la regla sea alcanzable con datos reales (donde depende de cuándo llegue el registro).
12. **¿Cómo prueban las fallas?** S11 (50 % de registros corruptos), S12 (40 % con menos de 3 h) y S13 (60 % de pronósticos ausentes o imposibles). Se mide que no haya excepciones y que cada falla termine en revisión manual (S11, S12) o en imputación con bandera (S13).
13. **¿Funciona el aprendizaje?** El ciclo funciona de extremo a extremo (S10 reentrena cada 150 resultados), pero la mejora medida es del orden de la desviación entre repeticiones: no se afirma que mejore.
14. **¿Los umbrales se fijaron antes?** Sí: `config/thresholds.json` lleva la fecha de fijación (2026-10-16 14:40:04 UTC), anterior a los logs de las corridas.

## Reproducibilidad
15. **¿Se puede ejecutar en otro computador?** `pip install -r requirements.txt`, `python scripts/train.py` (≈ 10 s), `python scripts/demo.py`, `python scripts/run_tests.py` (≈ 4 min). Con versiones más nuevas M3 pasó de 46,0 % a 46,2 %; las conclusiones no cambian.
