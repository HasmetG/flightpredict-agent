"""FlightPredict-Agent - plataforma desplegada (Streamlit Community Cloud).

Ejecutar localmente:  streamlit run streamlit_app.py
"""
import streamlit as st

import core
from core import AIRLINES, AIRPORTS

st.set_page_config(page_title="FlightPredict-Agent", page_icon="✈️", layout="wide")

st.title("✈️ FlightPredict-Agent")
st.markdown(
    "**Agente basado en utilidad (con modelo interno y aprendizaje)** que, ≥ 3 h antes de la salida programada de un vuelo, estima la "
    "probabilidad y la duración esperada de un retraso y decide si alerta al equipo de operaciones de la aerolínea. "
    "Proyecto de *Inteligencia Artificial* (UTB) — Hasmet Gonzalez Perez y Dylan Andrés Ecker López.")
st.info("El entorno (clima, rotaciones de aeronaves, historial, sistema operativo de la aerolínea) es **simulado**. Los resultados describen el "
        "comportamiento del agente frente a ese simulador, no frente a datos reales.")
st.markdown("**Ciclo del agente:** `1 · percepción` (valida entradas, imputa clima) → `2 · decisión` (modelo ML + utilidad "
            "`U(alertar) = P·β·d − (1−P)·C_FA`) → `3 · acción` (alerta + sugerencia, o revisión manual) → `4 · resultado real` (retroalimentación).")

with st.expander("📋 Instrucciones de uso y casos de prueba sugeridos", expanded=True):
    st.markdown("""
| # | Pestaña | Qué hacer | Qué debe ocurrir |
|---|---|---|---|
| 1 | **Demo** | Escenario *Típico*, 2 días, **Ejecutar** | Tabla percepción → decisión → acción de cada vuelo, y el resultado real |
| 2 | **Demo** | Escenario *Falla esperada*, 2 días | Entradas inválidas / ventana < 3 h → `REVISION_MANUAL`; sensor sin dato → predice con clima imputado; **0 excepciones** |
| 3 | **Vuelo manual** | Valores por defecto (JFK→ORD, clima malo) | `ALERTAR` con P alta |
| 4 | **Vuelo manual** | Origen `ZZZ`, o antelación 1 h, o fecha `no-es-una-fecha` | `REVISION_MANUAL` (entrada inválida / ventana insuficiente) |
| 5 | **Vuelo manual** | Desmarcar «Pronóstico disponible» | El agente imputa el clima con la climatología (`clima imputado = True`) |
| 6 | **Vuelo manual** | Marcar «tramo anterior retrasado» con 60 min | Sube P(retraso): efecto del retraso en cadena (memoria de corto plazo) |
| 7 | **Pruebas M1–M4** | **Ejecutar las 65 corridas** (varios minutos) | Tabla vs. umbrales; M3 **no cumple** (análisis en el documento) |
""")

tab1, tab2, tab3, tab4 = st.tabs(["1 · Demo del agente", "2 · Vuelo manual", "3 · Pruebas M1–M4", "4 · Arquitectura y UML"])

# ------------------------------------------------------------------------------------------------ 1. demo
with tab1:
    c1, c2, c3 = st.columns([2, 2, 1])
    esc = c1.radio("Escenario", ["Típico (vuelos normales)", "Falla esperada (entradas inválidas, ventana < 3 h, sensor sin dato)"])
    dias = c2.slider("Aeronaves-día a simular (cada una hace 3–5 vuelos)", 1, 5, 2)
    filas = c3.number_input("Filas a mostrar", 20, 400, 120, step=20)
    if st.button("▶ Ejecutar el agente desde cero", type="primary", key="demo"):
        with st.spinner("Cargando modelo y ejecutando el agente…"):
            st.session_state["res_demo"] = core.run_demo(esc.startswith("Típico"), dias)
    if "res_demo" in st.session_state:
        df, resumen, logbytes = st.session_state["res_demo"]
        cols = st.columns(len(resumen))
        for c, (k, v) in zip(cols, resumen.items()):
            c.metric(k, v)
        st.dataframe(df.head(int(filas)), width="stretch", hide_index=True)
        st.download_button("⬇ Descargar el log completo (JSONL comprimido, con marca de tiempo)", logbytes, "log_demo.jsonl.gz")

# ------------------------------------------------------------------------------------------------ 2. manual
with tab2:
    st.caption("Controle usted las entradas de **un** vuelo. El agente se activa a la antelación indicada.")
    a, b, c = st.columns(3)
    o = a.selectbox("Origen (ZZZ = aeropuerto desconocido)", AIRPORTS + ["ZZZ"], index=AIRPORTS.index("JFK"))
    d = b.selectbox("Destino", AIRPORTS, index=AIRPORTS.index("ORD"))
    al = c.selectbox("Aerolínea", AIRLINES, index=AIRLINES.index("NK"))
    a, b = st.columns(2)
    sd = a.text_input("Salida programada (AAAA-MM-DD HH:MM)", "2026-07-15 17:30")
    lead = b.slider("Antelación con que se activa el agente (horas; el diseño exige ≥ 3)", 0.5, 6.0, 3.5, 0.25)
    hf = st.checkbox("Pronóstico disponible (desmarcar = sensor sin dato)", True)
    a, b, c, e = st.columns(4)
    vis, wind = a.number_input("Visibilidad", value=2.0), b.number_input("Viento", value=28.0)
    prc, tmp = c.number_input("Precipitación", value=6.0), e.number_input("Temperatura (°C)", value=12.0)
    a, b = st.columns(2)
    hp = a.checkbox("El tramo anterior de la misma aeronave salió retrasado", False)
    pdl = b.number_input("Retraso del tramo anterior (min)", value=60.0)
    if st.button("▶ Ejecutar el agente", type="primary", key="manual"):
        dec, percept, logdf, outbox = core.run_manual(o, d, al, sd, lead, hf, vis, wind, prc, tmp, hp, pdl)
        st.markdown(core.manual_markdown(dec, percept))
        st.dataframe(logdf, width="stretch", hide_index=True)
        st.caption("Mensajes enviados al sistema operativo de la aerolínea (simulado)")
        st.code(outbox, language="json")

# ------------------------------------------------------------------------------------------------ 3. pruebas
with tab3:
    st.markdown(
        "Ejecuta **`scripts/run_tests.py`** (13 escenarios × 5 repeticiones = 65 corridas, ≈ 19 600 vuelos) con los umbrales de "
        "`config/thresholds.json`, fijados **antes** de ejecutar. Tarda varios minutos; **no cierre la pestaña**. "
        "Genera los logs y las tablas desde cero y los ofrece como `.zip`.")
    if st.button("▶ Ejecutar las 65 corridas y calcular M1–M4", type="primary", key="suite"):
        if not core.SUITE_LOCK.acquire(blocking=False):
            st.warning("Ya hay una ejecución de pruebas en curso. Espere a que termine y vuelva a intentar.")
        else:
            try:
                bar = st.progress(0.0, text="Preparando…")
                st.session_state["res_suite"] = core.run_suite(lambda f, t: bar.progress(min(f, 1.0), text=t))
                bar.empty()
            finally:
                core.SUITE_LOCK.release()
    if "res_suite" in st.session_state:
        tabla, por_esc, zbytes = st.session_state["res_suite"]
        st.subheader("Resultado de esta ejecución")
        st.dataframe(tabla, width="stretch", hide_index=True)
        st.dataframe(por_esc, width="stretch", hide_index=True)
        st.download_button("⬇ Descargar evidencia (logs de las 65 corridas + CSV)", zbytes, "evidencia_pruebas.zip")
    st.divider()
    st.subheader("Resultados guardados del documento (ejecución original, para comparar)")
    t0, p0 = core.saved_results()
    st.dataframe(t0, width="stretch", hide_index=True)
    st.dataframe(p0, width="stretch", hide_index=True)

# ------------------------------------------------------------------------------------------------ 4. UML
with tab4:
    st.caption("Diagramas del documento (sección 9). El código de cada módulo está en `src/flightpredict/`.")
    base = core.ROOT / "docs" / "diagramas"
    st.image(str(base / "arquitectura.png"), caption="Arquitectura")
    st.image(str(base / "secuencia_tipico.png"), caption="Secuencia — escenario típico")
    st.image(str(base / "secuencia_excepcion.png"), caption="Secuencia — escenario de excepción")
