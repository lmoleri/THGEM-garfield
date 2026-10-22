#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md — the grid field-sampling artifact.

Compares the exact neBEM transport field to the uniform-grid (ComponentGrid) field on a fine
x-z slice through the bottom-copper inner edge, where the field is near-singular. Four panels:
exact |E|, grid |E|, grid/exact |E| ratio, and the angle between the two field vectors. The
grid smears the sharp edge field and reverses its direction in a one-cell skin at the copper
surface — the mechanism behind the simulated over-extraction.

Reads results/extraction_edge_field/raw_vs_grid_field_ig0p5.csv — a `fields.dump_raw_field`
dump (columns x_cm,z_cm,in_gas,ex_raw,ez_raw,emag_raw,ex_grid,ez_grid,emag_grid). Produce it
by running thgem_sim with fields.dump_raw_field=true; see the doc's "Reproducing" section."""
import csv
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    REPO / "results/extraction_edge_field/raw_vs_grid_field_ig0p5.csv")
DEST = REPO / "docs/figures/rawgrid_edge_field.png"

# Bottom-copper band (rim=0, cm): z in [-0.0235,-0.020], radius > 0.025. Singular corner at
# (x=250 um, z=-200 um).
Z_BOT, Z_TOP, RCU = -235., -200., 250.  # um

rows = list(csv.DictReader(CSV.open()))
X = np.array([float(r["x_cm"]) for r in rows]) * 1e4   # um
Z = np.array([float(r["z_cm"]) for r in rows]) * 1e4
gas = np.array([int(r["in_gas"]) for r in rows])
exR = np.array([float(r["ex_raw"]) for r in rows]); ezR = np.array([float(r["ez_raw"]) for r in rows])
exG = np.array([float(r["ex_grid"]) for r in rows]); ezG = np.array([float(r["ez_grid"]) for r in rows])
magR = np.hypot(exR, ezR) * 1e-3; magG = np.hypot(exG, ezG) * 1e-3   # kV/cm

xs, zs = np.unique(X), np.unique(Z)
xi = {x: i for i, x in enumerate(xs)}; zi = {z: i for i, z in enumerate(zs)}


def grid2d(v):
    g = np.full((zs.size, xs.size), np.nan)
    for k in range(len(X)):
        g[zi[Z[k]], xi[X[k]]] = v[k]
    return g


MR, MG = grid2d(magR), grid2d(magG)
ratio = np.where(MR > 1e-3, MG / MR, np.nan)
dot = exR * exG + ezR * ezG
ang = np.degrees(np.arccos(np.clip(dot / (np.hypot(exR, ezR) * np.hypot(exG, ezG) + 1e-30), -1, 1)))
ANG = np.where(grid2d(gas) == 1, grid2d(ang), np.nan)   # angle only meaningful in the gas

# Headline stats near the singular corner (gas side).
d = np.hypot(X - RCU, Z - Z_TOP)
near = (gas == 1) & (d < 35)
print(f"exact peak |E| = {magR.max():.0f} kV/cm; grid caps at {magG.max():.0f} kV/cm")
print(f"within 35 um of the corner (gas): grid/exact |E| mean = "
      f"{np.mean(magG[near] / np.maximum(magR[near], 1e-3)):.2f}, "
      f"max field-direction angle = {ang[near].max():.0f} deg, "
      f"reversed (>90 deg) nodes = {(near & (ang > 90)).sum()}")

ext = [xs.min(), xs.max(), zs.min(), zs.max()]


def copper(ax):
    ax.add_patch(plt.Rectangle((RCU, Z_BOT), xs.max() - RCU, Z_TOP - Z_BOT,
                               fill=False, edgecolor="red", lw=1.5))
    ax.set_xlabel("x [µm]"); ax.set_ylabel("z [µm]")


vmax = np.nanpercentile(MR, 99)
fig, axs = plt.subplots(1, 4, figsize=(19, 4.8))
for ax, M, t in ((axs[0], MR, "exact neBEM  |E| [kV/cm]"),
                 (axs[1], MG, "uniform grid  |E| [kV/cm]")):
    im = ax.imshow(M, origin="lower", extent=ext, aspect="auto", cmap="viridis", vmin=0, vmax=vmax)
    fig.colorbar(im, ax=ax); ax.set_title(t); copper(ax)
im = axs[2].imshow(ratio, origin="lower", extent=ext, aspect="auto", cmap="RdBu", vmin=0, vmax=2)
fig.colorbar(im, ax=axs[2]); axs[2].set_title("grid / exact  |E|\n(1 = agree, <1 = grid weaker)"); copper(axs[2])
im = axs[3].imshow(ANG, origin="lower", extent=ext, aspect="auto", cmap="inferno", vmin=0, vmax=180)
fig.colorbar(im, ax=axs[3], label="deg"); axs[3].set_title("angle(grid, exact)\n(>90° = reversed field)"); copper(axs[3])
fig.suptitle("Grid field-sampling artifact at the bottom-copper inner edge (induction gap 0.5 mm)", y=1.02)
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130, bbox_inches="tight")
print("wrote", DEST)
