# Bitácora de uso de IA

**Herramienta:** Claude (Anthropic). **Fechas:** 16/10/2026 y 17/10/2026. **Curso:** Inteligencia Artificial (UTB).
**Integrantes:** Hasmet Gonzalez Perez, Dylan Andrés Ecker López.

| # | Qué se pidió | Qué produjo la IA | Qué verificó / modificó el equipo |
|---|---|---|---|
| 1 | Explicar la actividad y proponer un plan por fases | Plan de trabajo en cuatro etapas | [completar] |
| 2 | Comparar ClauseCheck-Agent y FlightPredict-Agent y recomendar uno | Matriz de decisión ponderada con evidencia por puntaje, sensibilidad y justificación (4,25 vs 3,35) | [completar: p. ej. revisamos que los puntajes de viabilidad reflejaran lo que sabemos hacer] |
| 3 | Implementar el agente, el simulador, el log y las pruebas | Código del repositorio (Python/scikit-learn), scripts de entrenamiento, demo y pruebas; 65 corridas | [completar: reproducimos en nuestro equipo, versiones usadas, qué parte del código leímos y entendimos] |
| 4 | Diagramas de arquitectura y secuencia UML | Archivos `.dot`/`.mmd` y PNG (Graphviz, matplotlib) | [completar: contrastamos los diagramas con el código] |
| 5 | Redactar el documento de diseño ajustado | PDF con matriz, tabla de cambios, diseño corregido y sección 9 | [completar] |
| 6 | Revisar el entregable frente a la rúbrica (17/10) | Reejecución independiente del repositorio (M1 74,0 %, M2 100 %, M4 100 %, M3 46,2 % con scikit-learn 1.9.1 vs 46,0 % original); lista de brechas | [completar] |
| 7 | Corregir diagramas, documento y repositorio | Participante «Entorno» en los diagramas de secuencia, retrain() corregido, `requirements.txt` con versiones fijas, `scripts/construir_documento.py` (documento con cifras tomadas de los CSV), Anexo A con el log real, `docs/guia_defensa.md` | [completar: revisamos los cambios y regeneramos resultados en nuestro equipo] |
| 8 | Corregir defectos hallados en la revisión | Logger con JSON estricto (NaN a null) y logs regenerados con resultados idénticos; copias sin comprimir en `results/logs_muestra/`; textos con tildes en la tabla de resultados; diagramas de secuencia con letra más grande; documento y PDF regenerados | [completar: reejecutamos run_tests.py y verificamos que las cifras no cambiaron] |
| 9 | Desplegar el agente como plataforma pública (17/10): primero Hugging Face Spaces (app Gradio); al recibir el error 403 de cuota `cpu-basic` se cambió a Streamlit Community Cloud | `core.py` y `streamlit_app.py` (interfaz que reutiliza el agente sin reimplementarlo), pruebas automáticas de la interfaz y re-ejecución de las 65 corridas (mismos resultados: M1 74,0 %, M3 46,0 %) | [completar: desplegamos en Streamlit, probamos los casos de la pestaña inicial y verificamos que las cifras coinciden con el documento] |

**Declaración:** los resultados numéricos provienen de ejecutar el código incluido sobre un entorno simulado; no se inventaron cifras. La IA no ha grabado el video ni pegado los enlaces; la retroalimentación del docente y los enlaces los completa el equipo.
El equipo es responsable de comprender, reproducir y defender el trabajo. Editen las celdas resaltadas con su participación real antes de entregar.
