#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md — corrected sweep vs measurement.

Anode/THGEM-top vs induction gap, computed on the exact neBEM transport field
(fields.use_raw_nebem — free of the copper-edge grid artifact), against the lab measurement.
Also shows the bottom-copper collection fraction that now appears (~15 %), absent on the grid.
The corrected extraction is flat (~0.75) in the gap: it fixes the magnitude and the missing
bottom-copper channel, but the measurement's rise at small gaps still has no counterpart.

Reads results/extraction_edge_field/raw_nebem_sweep.csv (written by a use_raw_nebem gap sweep;
columns gap_mm,frac_anode,sem_frac_anode,frac_bottom_cu,...,measurement). Small avalanche cap:
the collection fraction is cap-independent, but per-gap error bars are wide (~6 events)."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "results/extraction_edge_field/raw_nebem_sweep.csv"
DEST = REPO / "docs/figures/rawfield_sweep_vs_meas.png"

g, anode, sem, botcu, meas = [], [], [], [], []
for r in csv.DictReader(SRC.open()):
    g.append(float(r["gap_mm"])); anode.append(float(r["frac_anode"]))
    sem.append(float(r["sem_frac_anode"])); botcu.append(float(r["frac_bottom_cu"]))
    meas.append(float(r["measurement"]))

fig, ax = plt.subplots(figsize=(7.6, 5.4))
ax.plot(g, meas, marker="o", ms=7, lw=2.2, color="black", label="lab measurement (E_ind=2.0)")
ax.errorbar(g, anode, yerr=sem, marker="^", ms=7, capsize=3, lw=2.0, color="tab:red",
            label="sim, exact neBEM field — anode/total")
ax.plot(g, botcu, marker="s", ms=6, lw=1.6, ls="--", color="tab:green",
        label="sim — bottom-copper fraction")
ax.set_xlabel("Induction gap [mm]")
ax.set_ylabel("Fraction of total avalanche electrons")
ax.set_title("Corrected extraction (exact field) vs measurement\n"
             "ΔV=1.9 kV, drift=1 kV/cm, E_ind=2.0 kV/cm, Ar:CO₂ 93:7")
ax.set_ylim(0, 1.0); ax.set_xlim(0, 1.1); ax.grid(True, alpha=0.3)
ax.legend(loc="center right", framealpha=0.95)
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130)
print("wrote", DEST)
