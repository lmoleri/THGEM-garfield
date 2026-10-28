#!/usr/bin/env python3
"""Can a positive bottom-rim charge send avalanche ions onto the anode?

Per induction gap, neBEM gives the field with the rim uncharged (q0) and carrying a uniform
+1 nC/cm^2 test charge (q1; fields.charging_up + scripts/rim_charge_files.py), both on the
exact-field x–z slice of fields.dump_raw_field.  The problem is linear, so for any rim charge
sigma [nC/cm^2]:  E(sigma) = E0 + sigma (E1 - E0).  Ions are born where the sigma = 0 mean
avalanche ionises (weighted 'b' rows of results/extraction_charging/meanaval_sigma0) and follow
+E to the surface they land on.  Reports, per gap and sigma, the ion fractions reaching the
anode / bottom rim / bottom copper / up through the hole, and the rim-recess potential relative
to the anode (neBEM's potentials carry a uniform, field-free offset, so only differences count).

Usage: rim_ions_to_anode.py <dump_root> [sigma ...]   (dump_root holds ig<gap>_q0, ig<gap>_q1)
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meanaval_rim import REPO, load_field, ion_dest, cell_r   # noqa: E402

ROOT = Path(sys.argv[1])
SIGMAS = [float(s) for s in sys.argv[2:]] or [0., 1., 2., 5., 10., 20., 50.]
BIRTHS = REPO / "results" / "extraction_charging" / "meanaval_sigma0"
DEST = ["anode", "bottom_rim", "bottom_cu", "drift", "other"]


def potential_grid(d, F):
    rows = list(csv.DictReader((d / "raw_vs_grid_field.csv").open()))
    X = np.array([float(r["x_cm"]) for r in rows]); Z = np.array([float(r["z_cm"]) for r in rows])
    V = np.full((F["zs"].size, F["xs"].size), np.nan)
    V[np.searchsorted(F["zs"], Z), np.searchsorted(F["xs"], X)] = [float(r["v_raw"]) for r in rows]
    return V


def ion_births(gap, n, rng):
    pts, w = [], []
    for f in BIRTHS.glob(f"ig{gap:.2f}_s*/collection_endpoints.csv"):
        for r in csv.DictReader(f.open()):
            if r["species"] == "b":
                pts.append((cell_r(float(r["birth_x_cm"]), float(r["birth_y_cm"])), float(r["birth_z_cm"])))
                w.append(float(r["weight"]))
    w = np.array(w)
    k = rng.choice(len(w), n, p=w / w.sum())          # weight-proportional sample: equal weights after
    return [pts[i] for i in k]


def main():
    rng = np.random.default_rng(11)
    out = []
    for gap in (0.1, 0.2, 0.5, 1.0):
        d0, d1 = ROOT / f"ig{gap:.2f}_q0", ROOT / f"ig{gap:.2f}_q1"
        if not (d0.exists() and d1.exists()): continue
        F0, F1 = load_field(d0), load_field(d1)
        V0, V1 = potential_grid(d0, F0), potential_grid(d1, F1)
        xs, zs = F0["xs"] * 1e4, F0["zs"] * 1e4
        recess = (np.abs(zs + 205) < 6)[:, None] & ((xs > 255) & (xs < 335))[None, :]
        births = ion_births(gap, 1500, rng)
        print(f"\nig = {gap} mm  ({len(births)} ion births, weight-sampled)")
        print(f"{'sigma[nC/cm2]':>14} {'V_recess-V_anode[V]':>20} " + " ".join(f"{k:>11}" for k in DEST))
        for s in SIGMAS:
            F = dict(F0); F["EX"] = F0["EX"] + s * (F1["EX"] - F0["EX"]); F["EZ"] = F0["EZ"] + s * (F1["EZ"] - F0["EZ"])
            V = V0 + s * (V1 - V0)
            dv = np.nanmean(V[recess]) - np.nanmean(V[0])   # row 0 sits 5 um above the anode
            dest = [ion_dest(F, r0, z0) for r0, z0 in births]
            frac = {k: np.mean([x == k for x in dest]) for k in DEST[:-1]}
            frac["other"] = 1 - sum(frac.values())
            print(f"{s:14.1f} {dv:20.1f} " + " ".join(f"{frac[k]:11.4f}" for k in DEST))
            out.append(dict(gap_mm=gap, sigma_nC_cm2=s, v_recess_minus_anode=dv, **{f"ion_{k}": frac[k] for k in DEST}))
    with (ROOT / "ions_vs_rim_charge.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f"\nwrote {ROOT / 'ions_vs_rim_charge.csv'}")


if __name__ == "__main__":
    main()
