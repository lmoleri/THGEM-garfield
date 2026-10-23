#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md §9 — the recapture map.

From a collection dump (simulation.dump_collection → collection_endpoints.csv + run_config.json)
of an exact-field avalanche run, shows where every classified electron was BORN (r,z) coloured by
fate (left) and where the bottom-copper electrons are RECAPTURED (right).  The bottom-copper
electrons are born throughout the hole like the extracted ones but all end at the sharp inner
corner of the bottom copper — a near-exit, near-singular-edge effect.

Usage: plot_recapture_map.py <run_dir>   (default: results/extraction_charging/recapture_ig0p2)
Writes docs/figures/recapture_map.png."""
import csv, json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "results/extraction_charging/recapture_ig0p2"
DEST = REPO / "docs/figures/recapture_map.png"

g = json.loads((RUN / "run_config.json").read_text())["geometry"]
RH = g["hole_diameter_um"] * 0.5
ZDH = g["plate_thickness_um"] * 0.5
TCU = g["copper_thickness_um"]
IG = g["induction_gap_mm"]
ZANODE = -(ZDH + TCU) - IG * 1000.           # µm
Z_BOTCU = (-(ZDH + TCU), -ZDH)
Z_TOPCU = (ZDH, ZDH + TCU)

rows = list(csv.DictReader((RUN / "collection_endpoints.csv").open()))
br = np.array([np.hypot(float(r["birth_x_cm"]), float(r["birth_y_cm"])) for r in rows]) * 1e4
bz = np.array([float(r["birth_z_cm"]) for r in rows]) * 1e4
er = np.array([np.hypot(float(r["end_x_cm"]), float(r["end_y_cm"])) for r in rows]) * 1e4
ez = np.array([float(r["end_z_cm"]) for r in rows]) * 1e4
cat = np.array([r["category"] for r in rows])
frac = {c: (cat == c).mean() for c in ("anode", "bottom_cu", "attached", "dielectric", "top_cu")}
COL = {"anode": "tab:green", "bottom_cu": "tab:red", "attached": "tab:gray",
       "dielectric": "tab:orange", "top_cu": "tab:blue", "drift": "black"}
rmax = max(np.nanmax(br), np.nanmax(er), 420.)


def geom(ax):
    ax.add_patch(plt.Rectangle((RH, Z_BOTCU[0]), rmax - RH, TCU, color="orange", alpha=.35, lw=0))
    ax.add_patch(plt.Rectangle((RH, Z_TOPCU[0]), rmax - RH, TCU, color="orange", alpha=.35, lw=0))
    ax.add_patch(plt.Rectangle((RH, -ZDH), rmax - RH, 2 * ZDH, color="khaki", alpha=.25, lw=0))
    ax.axvline(RH, color="k", lw=.6, ls=":"); ax.axhline(ZANODE, color="green", lw=1.2)
    ax.text(rmax * .98, ZANODE + 6, "anode", color="green", ha="right", fontsize=8)
    ax.text(RH + 6, Z_BOTCU[0] + 10, "bottom Cu", fontsize=8)
    ax.set_xlabel("r = √(x²+y²)  [µm]"); ax.set_ylabel("z [µm]")
    ax.set_xlim(0, rmax); ax.set_ylim(ZANODE - 20, 260)


fig, axs = plt.subplots(1, 2, figsize=(13, 6))
for c in ("anode", "bottom_cu", "attached", "dielectric", "top_cu"):
    m = cat == c
    if m.any():
        axs[0].scatter(br[m], bz[m], s=10, alpha=.5, color=COL[c], label=f"{c} ({m.sum()})")
geom(axs[0]); axs[0].set_title("electron BIRTH position, coloured by fate")
axs[0].legend(loc="upper right", fontsize=8, framealpha=.9)
mb = cat == "bottom_cu"; ma = cat == "anode"
axs[1].scatter(er[mb], ez[mb], s=16, color="tab:red", alpha=.7, label=f"bottom_cu endpoints ({mb.sum()})")
axs[1].scatter(er[ma], ez[ma], s=6, color="tab:green", alpha=.25, label=f"anode ({ma.sum()})")
geom(axs[1]); axs[1].set_title("where bottom_cu electrons are RECAPTURED")
axs[1].legend(loc="upper right", fontsize=8, framealpha=.9)
fig.suptitle(f"Recapture map — induction gap {IG} mm   (bottom_cu {frac['bottom_cu']:.0%}, "
             f"attached {frac['attached']:.0%}, anode {frac['anode']:.0%})", y=1.0)
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130, bbox_inches="tight")
print("wrote", DEST)
