"""Figuras de resultados a partir de results/resumen_por_escenario.csv."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from flightpredict.config import RESULTS_DIR

a = pd.read_csv(RESULTS_DIR / "resumen_por_escenario.csv")
a = a[a.tipo != "falla"]
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.8))
axs[0].bar(a.escenario, a.exactitud_media * 100, yerr=a.exactitud_std * 100, capsize=3, color="#4C78A8", label="Exactitud (media ± DE)")
axs[0].scatter(a.escenario, a.baseline_acc * 100, color="#E45756", marker="_", s=300, zorder=3, label="Linea base: nunca alertar")
axs[0].axhline(70, color="k", ls="--", lw=1, label="Umbral M1 (70 %)")
axs[0].set_ylim(40, 100); axs[0].set_title("M1 Exactitud por escenario", fontsize=10); axs[0].legend(fontsize=7, loc="lower left")
axs[1].bar(a.escenario, a.recall_media * 100, yerr=a.recall_std * 100, capsize=3, color="#54A24B", label="Recall (media ± DE)")
axs[1].axhline(60, color="k", ls="--", lw=1, label="Umbral M3 (60 %)")
axs[1].set_ylim(0, 100); axs[1].set_title("M3 Recall por escenario", fontsize=10); axs[1].legend(fontsize=7, loc="upper left")
for ax in axs: ax.grid(axis="y", alpha=.3)
fig.tight_layout(); fig.savefig(RESULTS_DIR / "fig_resultados_escenarios.png", dpi=170)
print("ok")
