#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md.

Anode/THGEM-top vs induction gap at E_ind=2.0 kV/cm: the lab measurement (digitized from
charge_ratio.pdf) against the simulated electron-collection fraction (anode / total
produced) at rim=0 and rim=0.1 mm. Writes docs/figures/extraction_meas_vs_sim.png.

Reads the collection-sweep CSVs under results/ (gitignored sim output); run the avalanche
induction sweeps first if they are absent."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "docs" / "figures" / "extraction_meas_vs_sim.png"

# Lab measurement, E_ind=2.0 kV/cm (digitized from charge_ratio.pdf).
MEAS_G = [0.1, 0.2, 0.5, 1.0, 2.0]
MEAS_R = [0.51, 0.64, 0.855, 0.80, 0.755]


def load(csvpath, eind=None):
    g, f, s = [], [], []
    for row in csv.DictReader(open(csvpath)):
        if eind is not None and abs(float(row["e_ind"]) - eind) > 1e-6:
            continue
        g.append(float(row["gap_mm"]))
        f.append(float(row["frac_anode"]))
        s.append(float(row.get("sem_frac_anode", 0) or 0))
    order = sorted(range(len(g)), key=lambda i: g[i])
    return [g[i] for i in order], [f[i] for i in order], [s[i] for i in order]


rim0 = load(REPO / "results/transparency_induction_avalanche/collection_vs_induction_avalanche.csv",
            eind=2.0)
rim1 = load(REPO / "results/transparency_induction_avalanche_rim100/collection_vs_induction_rim100.csv")

fig, ax = plt.subplots(figsize=(7.6, 5.4))
ax.plot(MEAS_G, MEAS_R, marker="o", ms=7, lw=2.2, color="black",
        label="lab measurement (E_ind=2.0)")
ax.errorbar(rim0[0], rim0[1], yerr=rim0[2], marker="s", ms=6, capsize=3, lw=1.8,
            color="tab:gray", ls="--", label="sim, rim = 0")
ax.errorbar(rim1[0], rim1[1], yerr=rim1[2], marker="^", ms=7, capsize=3, lw=2.0,
            color="tab:red", label="sim, rim = 0.1 mm")
ax.set_xlabel("Induction gap [mm]")
ax.set_ylabel("Anode / THGEM-top  (= anode-collected / total produced)")
ax.set_title("Anode extraction vs induction gap — measurement vs simulation\n"
             "ΔV=1.9 kV, drift=1 kV/cm, E_ind=2.0 kV/cm, Ar:CO₂ 93:7")
ax.set_ylim(0.4, 1.0)
ax.set_xlim(0, 2.1)
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", framealpha=0.95)
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130)
print("wrote", DEST)
