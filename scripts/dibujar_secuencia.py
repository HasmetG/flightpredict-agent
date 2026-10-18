"""Dibuja los diagramas de secuencia UML (escenario tipico y de excepcion) con matplotlib.
La version fuente en Mermaid esta en docs/diagramas/secuencia.mmd (renderizable en mermaid.live)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parents[1] / "docs" / "diagramas"
P = {  # participante -> (x, etiqueta)
    "Ops": (0.0, "Equipo de\noperaciones\n(actor)"), "Env": (1.0, "Entorno\n(simulador:\nvuelos, clima,\nresultados)"),
    "SOA": (2.0, "Sistema\noperativo\naerolínea\n(interfaz)"),
    "Plan": (3.0, "Planifi-\ncador"), "Met": (4.0, "Servicio\nmeteoro-\nlógico"),
    "Per": (5.0, "Percepción"), "Mem": (6.0, "Memoria"), "Dec": (7.0, "Decisión\n(modelo +\nutilidad)"),
    "Act": (8.0, "Acción\n(actuado-\nres)")}
XR = max(x for x, _ in P.values()) + 1.7     # borde derecho de los fragmentos


def draw(items, fname, title):
    ROW = 0.5
    inc = {"msg": ROW, "self": ROW, "start": ROW * 1.15, "else": ROW * 1.0, "end": ROW * 0.15}
    total = 0.2 + sum(inc[it[0]] for it in items)
    fig, ax = plt.subplots(figsize=(9.0, (total + 2.3) * 0.62))
    ax.set_xlim(-0.8, XR + 0.1); ax.set_ylim(-(total + 0.1), 1.9); ax.axis("off")
    ax.set_title(title, fontsize=9, fontweight="bold")
    ybottom = -(total + 0.05)
    for k, (x, lab) in P.items():
        ax.add_patch(Rectangle((x - 0.42, 0.55), 0.84, 1.0, fc="#E8EEF7", ec="#34495E", lw=0.8))
        ax.text(x, 1.05, lab, ha="center", va="center", fontsize=6.9)
        ax.plot([x, x], [0.55, ybottom], ls=(0, (4, 3)), color="#7F8C8D", lw=0.6)
    y, stack, n, frames = 0.2, [], 0, []
    for it in items:
        t = it[0]
        if t == "start":
            stack.append((it[1], it[2], y)); y -= ROW * 1.15
            ax.text(-0.75, y + ROW * 0.55, "", fontsize=5)
        elif t == "else":
            kind, lab, y0 = stack[-1]
            d = len(stack)
            ax.plot([-0.65 + 0.07 * d, XR - 0.05 - 0.07 * d], [y + ROW * 0.35] * 2, ls="--", color="#555", lw=0.6)
            ax.text(-0.62 + 0.07 * d, y + ROW * 0.12, f"[{it[1]}]", fontsize=8.2, style="italic", va="center")
            y -= ROW * 1.0
        elif t == "end":
            kind, lab, y0 = stack.pop(); d = len(stack) + 1
            frames.append((kind, lab, y0, y + ROW * 0.55, d)); y -= ROW * 0.15
        elif t == "msg":
            _, a, b, text, dashed = it
            xa, xb = P[a][0], P[b][0]
            ax.annotate("", xy=(xb, y), xytext=(xa, y), arrowprops=dict(arrowstyle="->" if not dashed else "->",
                        ls="--" if dashed else "-", lw=0.7, color="#1B2631"))
            n += 1
            ax.text((xa + xb) / 2, y + 0.06, f"{n}. {text}", ha="center", va="bottom", fontsize=8.2)
            y -= ROW
        elif t == "self":
            _, a, text = it
            xa = P[a][0]
            ax.plot([xa, xa + 0.25, xa + 0.25, xa], [y, y, y - 0.17, y - 0.17], lw=0.7, color="#1B2631")
            ax.annotate("", xy=(xa, y - 0.17), xytext=(xa + 0.08, y - 0.17), arrowprops=dict(arrowstyle="->", lw=0.7))
            n += 1
            ax.text(xa + 0.3, y - 0.08, f"{n}. {text}", ha="left", va="center", fontsize=8.2)
            y -= ROW
    for kind, lab, y0, y1, d in frames:
        x0, x1 = -0.7 + 0.07 * (d - 1), XR - 0.1 - 0.07 * (d - 1)
        ax.add_patch(Rectangle((x0, y1), x1 - x0, y0 - y1, fill=False, ec="#2C3E50", lw=0.9))
        ax.add_patch(Rectangle((x0, y0 - 0.2), 0.45 + 0.05 * len(kind), 0.2, fc="#D5DBDB", ec="#2C3E50", lw=0.7))
        ax.text(x0 + 0.04, y0 - 0.1, kind, fontsize=8.2, fontweight="bold", va="center")
        ax.text(x0 + 0.55 + 0.05 * len(kind), y0 - 0.1, f"[{lab}]", fontsize=8.2, style="italic", va="center")
    fig.tight_layout(); fig.savefig(OUT / fname, dpi=220); plt.close(fig)


M = lambda a, b, t, d=False: ("msg", a, b, t, d)
typical = [
    ("start", "loop", "por cada vuelo programado"),
    M("Env", "SOA", "vuelo programado (id, aeronave, ruta, salida)"),
    M("SOA", "Plan", "registro del vuelo"),
    ("self", "Plan", "activar a salida − 180 min"),
    M("Plan", "Met", "solicitar pronóstico (origen, hora)"),
    M("Met", "Plan", "vis, viento, precip, temp", True),
    M("Plan", "Per", "registro crudo"),
    ("self", "Per", "validar campos, rangos, antelación"),
    ("start", "alt", "entrada válida y antelación ≥ 180 min"),
    M("Per", "Mem", "consultar estado de la aeronave"),
    M("Mem", "Per", "último retraso conocido", True),
    M("Per", "Dec", "percepto + características"),
    ("self", "Dec", "P(retraso) y duración esperada"),
    ("self", "Dec", "U(alertar) = P·β·d − (1−P)·C_FA"),
    ("start", "alt", "U(alertar) > 0"),
    M("Dec", "Act", "ALERTAR + sugerencia"),
    M("Act", "SOA", "alerta + sugerencia de reasignación"),
    M("SOA", "Ops", "notificación de riesgo de retraso"),
    ("else", "U(alertar) ≤ 0"),
    M("Dec", "Act", "NO_ALERTAR (solo queda en el log)"),
    ("end",),
    ("end",),
    ("end",),
    M("Env", "SOA", "resultado real del vuelo (min de retraso)"),
    M("SOA", "Act", "receive_outcome(resultado real)"),
    M("Act", "Mem", "actualizar estado + guardar retroalimentación"),
    ("start", "opt", "≥ 150 muestras nuevas acumuladas"),
    ("self", "Dec", "retrain() con muestras nuevas"),
    ("end",),
]
exc = [
    M("Env", "SOA", "vuelo programado (puede traer defectos)"),
    M("SOA", "Plan", "registro del vuelo"),
    M("Plan", "Per", "registro crudo"),
    ("self", "Per", "validar campos, rangos, antelación"),
    ("start", "alt", "pronóstico ausente o inválido"),
    M("Per", "Mem", "climatología (origen, mes)"),
    M("Mem", "Per", "valores imputados", True),
    M("Per", "Dec", "percepto con wx_imputed = verdadero"),
    M("Dec", "Act", "decisión (ALERTAR o NO_ALERTAR)"),
    M("Act", "SOA", "alerta si U(alertar) > 0"),
    ("else", "campo faltante, código desconocido o fecha inválida"),
    M("Per", "Act", "ENTRADA_INVALIDA + problemas"),
    M("Act", "SOA", "marcar para revisión manual (sin predicción)"),
    M("SOA", "Ops", "vuelo pendiente de revisión humana"),
    ("else", "antelación < 180 min"),
    M("Per", "Act", "VENTANA_INSUFICIENTE"),
    M("Act", "SOA", "marcar para revisión manual (sin predicción)"),
    M("SOA", "Ops", "vuelo pendiente de revisión humana"),
    ("end",),
]
draw(typical, "secuencia_tipico.png", "Diagrama de secuencia 1 — Escenario típico (ciclo percepción → decisión → acción → aprendizaje)")
draw(exc, "secuencia_excepcion.png", "Diagrama de secuencia 2 — Escenarios de excepción")
print("ok")
