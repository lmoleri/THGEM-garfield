#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md — the decisive wall-release test.

Electrons released directly on the hole wall (source.release_z_cm) and transported to their
endpoint: on the uniform grid they essentially never reach the bottom copper, while on the
exact neBEM field (fields.use_raw_nebem) tens of percent collect there. Same geometry and
fields; only the transport-field representation differs. This isolates the grid artifact of
plot_rawgrid_edge_field.py as the cause of the over-extraction.

Data are the fate fractions printed by thgem_sim for the two representative diagnostic runs
(ΔV=1.9 kV, drift=1 kV/cm, E_ind=2.0, ig=0.1 mm, wall-release at several release x). The grid
gives ~0 % bottom copper independently of grid refinement, conductor in-painting and a small
copper-edge chamfer (each checked separately); the exact field collects the wall electrons."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "docs/figures/wall_release_grid_vs_exact.png"

# release x-position on the hole wall [mm] and bottom-copper collection fraction [%].
XPOS = [0.16, 0.20, 0.23]
GRID = [0.0, 0.0, 0.0]          # uniform grid 31x131 (anode ~93-97 %, bottom-Cu 0)
EXACT = [26.7, 80.0, 6.7]       # exact neBEM field (remainder: anode near, dielectric wall far)

x = np.arange(len(XPOS)); w = 0.38
fig, ax = plt.subplots(figsize=(7.2, 5.0))
ax.bar(x - w / 2, GRID, w, color="tab:gray", label="uniform grid (31×131)")
ax.bar(x + w / 2, EXACT, w, color="tab:green", label="exact neBEM field")
for xi, v in zip(x - w / 2, GRID):
    ax.text(xi, v + 1.5, "0", ha="center", fontsize=10, color="tab:gray")
for xi, v in zip(x + w / 2, EXACT):
    ax.text(xi, v + 1.5, f"{v:.0f}", ha="center", fontsize=10, color="tab:green")
ax.set_xticks(x); ax.set_xticklabels([f"{p:.2f}" for p in XPOS])
ax.set_xlabel("Electron release position on the hole wall,  x [mm]")
ax.set_ylabel("Collected on bottom copper  [%]")
ax.set_title("Wall-released electrons: bottom-copper collection\n"
             "grid vs exact field — ΔV=1.9 kV, E_ind=2.0, induction gap 0.1 mm")
ax.set_ylim(0, 100); ax.grid(True, axis="y", alpha=0.3)
ax.legend(loc="upper right", framealpha=0.95)
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130)
print("wrote", DEST)
