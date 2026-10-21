#!/usr/bin/env python3
"""Figure + table for docs/extraction_ratio_investigation.md: Stage-1 single-avalanche
self-field estimate.

Uses the simulated avalanche charge geometry (ionization sites = ion birth positions,
electron drift-line points) from the existing avalanche runs, scaled to a real
single-avalanche gain G, and Coulomb-sums the retarding axial field E_sc,z an electron
feels at the hole exit. Compares to E_ind = 2 kV/cm. Writes
docs/figures/spacecharge_selffield.png and prints the E_sc/E_ind table.

Sign: anode at the bottom (z most negative, 0 V), bottom copper above; E_ind points +z,
electrons drift -z to the anode. The positive ion column above the exit (and the trailing
electron cloud) push an exiting electron back up -> retard extraction. Needs the ROOT
output of the rim=0 avalanche sweep (ion drift off), which stores the avalanche cloud."""
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "docs" / "figures" / "spacecharge_selffield.png"

EPS0 = 8.8541878128e-12
QE = 1.602176634e-19
K = 1.0 / (4 * np.pi * EPS0)
E_IND_VCM = 2000.0
Z_BOTCU_BOT = -0.0235                       # cm, hole exit (bottom copper bottom)
GAINS = np.array([1e3, 1e4, 1e5, 1e6, 1e7])
RUNS = {"0.1": REPO / "results/transparency_induction_avalanche/Eind2.0_ig0.10/thgem_sim.root",
        "1.0": REPO / "results/transparency_induction_avalanche/Eind2.0_ig1.00/thgem_sim.root"}


def pool(path, brs):
    t = uproot.open(path)["dist_rnd/t_signals"]
    a = t.arrays(brs, library="np")
    return [np.concatenate([np.asarray(e, float) for e in a[b]]) for b in brs]


def esc_z(pts, q_per, test):
    dx = (test[0] - pts[0]) * 1e-2
    dy = (test[1] - pts[1]) * 1e-2
    dz = (test[2] - pts[2]) * 1e-2
    r2 = dx * dx + dy * dy + dz * dz
    r2 = np.where(r2 < (5e-6) ** 2, (5e-6) ** 2, r2)         # soften within 5 um
    return K * q_per * np.sum(dz * r2 ** -1.5)               # V/m


test_zs = [Z_BOTCU_BOT - d for d in (0.001, 0.002, 0.005)]  # 10/20/50 um below exit
results = {}
print(f"{'gap':>5} {'src':>9} {'r_rms[um]':>9} " + " ".join(f"G={g:.0e}".rjust(9) for g in GAINS))
for lab, path in RUNS.items():
    cx, cy, cz = pool(path, ["cloud_x", "cloud_y", "cloud_z"])      # ions
    ax_, ay_, az_ = pool(path, ["aval_x", "aval_y", "aval_z"])      # electrons in transit
    r_rms = 1e4 * np.sqrt(np.mean(cx ** 2 + cy ** 2))
    ion, ele, ub = [], [], []
    for G in GAINS:
        qi = G * QE / cx.size
        qe = G * QE / ax_.size
        ion.append(max(abs(esc_z((cx, cy, cz), qi, (0, 0, z))) for z in test_zs) / 100.0)
        ele.append(max(abs(esc_z((ax_, ay_, az_), qe, (0, 0, z))) for z in test_zs) / 100.0)
        R = r_rms * 1e-6
        ub.append(K * G * QE / R ** 2 / 100.0)
    results[lab] = dict(r_rms=r_rms, ion=np.array(ion), ele=np.array(ele), ub=np.array(ub))
    print(f"{lab:>5} {'ion/Eind':>9} {r_rms:>9.1f} " + " ".join(f"{v/E_IND_VCM:>9.3f}" for v in ion))
    print(f"{lab:>5} {'e-/Eind':>9} {'':>9} " + " ".join(f"{v/E_IND_VCM:>9.3f}" for v in ele))
    print(f"{lab:>5} {'UB/Eind':>9} {'':>9} " + " ".join(f"{v/E_IND_VCM:>9.3f}" for v in ub))

fig, ax = plt.subplots(figsize=(7.6, 5.2))
for lab, c in (("0.1", "tab:red"), ("1.0", "tab:blue")):
    r = results[lab]
    ax.loglog(GAINS, (r["ion"] + r["ele"]) / E_IND_VCM, "o-", color=c,
              label=f"ig={lab} mm: ion+e⁻ at exit")
ax.loglog(GAINS, results["0.1"]["ub"] / E_IND_VCM, "k--", label="upper bound (all charge in r_rms)")
ax.axhline(1.0, color="gray", lw=1)
ax.text(1.1e3, 1.15, "E_sc = E_ind", color="gray")
ax.axvspan(1e3, 1e4, color="green", alpha=0.12)
ax.text(2.2e3, 2e-4, "realistic\ngain", color="green", ha="center", fontsize=9)
ax.set_xlabel("single-avalanche gain G")
ax.set_ylabel("E_sc / E_ind  at hole exit")
ax.set_title("Single-avalanche self-field vs extraction field\n"
             "(ΔV=1.9 kV, E_ind=2 kV/cm; charge geometry from the simulated avalanche)")
ax.grid(True, which="both", alpha=0.3)
ax.legend(loc="upper left")
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130)
print("\nwrote", DEST)
