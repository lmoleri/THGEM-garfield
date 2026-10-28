#!/usr/bin/env python3
"""Can the avalanche's own ion space charge push ions onto the anode?

At small induction gaps the avalanche head grows in the gap, so the ion cloud it leaves sits just
above the anode.  Below a positive cloud its own field points down, toward the anode, and the
anode's image doubles it; if that beats the applied field (which points up, away from the
anode), the lower ions are driven onto the anode.  This static (t = 0) check:

  cloud   : the weighted ion births of a mean-avalanche run (species 'b'), folded into the unit
            cell, weight-sampled into M equal macro-ions carrying the event charge Q.  All of
            an event's charge in one hole's cloud — the worst case.
  field   : the applied exact field (axisymmetric x–z slice, fields.dump_raw_field) plus the
            Coulomb field of the macro-ions (Plummer-softened) and their images in the grounded
            anode plane, evaluated on the same slice (the cloud is near-axisymmetric).
  output  : per gap and Q, the fraction of ions whose +E field line ends on the anode (same tracer
            as §13; a local "E_z points down" test is wrong — near the copper corner field lines
            dip before curving up into the hole), and the threshold Q* above 1 %.

The cloud is frozen at its birth positions (it expands as it drifts, which only weakens it), and
images in the copper and hole walls are neglected (the anode's dominates under the hole at small
gaps).  Usage: gap_ion_spacecharge.py <prod_dir> [Q_fC ...]   (--selftest checks the field)
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meanaval_rim import FIELD, load_field, ion_dest, PITCH   # noqa: E402

K = 8.9875517923e11      # 1/(4 pi eps0) [V cm / C]
SOFT = 5e-4              # Plummer softening [cm]
M = 3000                 # macro-ions


def coulomb(pts, src, q, soft=SOFT, chunk=400):
    """Field [V/cm] at pts from point charges q at src (softened)."""
    E = np.zeros_like(pts)
    for a in range(0, len(pts), chunk):
        d = pts[a:a + chunk, None, :] - src[None, :, :]
        r2 = (d ** 2).sum(-1) + soft ** 2
        E[a:a + chunk] = K * (d * (q / r2 ** 1.5)[..., None]).sum(1)
    return E


def cloud_field(probe, src, zA, q):
    """Field at probe points of the cloud src plus its image in the grounded plane z = zA."""
    img = src.copy(); img[:, 2] = 2 * zA - img[:, 2]
    return coulomb(probe, src, q) + coulomb(probe, img, -q)


def births(prod, gap, rng):
    pts, w = [], []
    for f in prod.glob(f"ig{gap:.2f}_s*/collection_endpoints.csv"):
        for r in csv.DictReader(f.open()):
            if r["species"] != "b" or None in r.values(): continue
            x, y = float(r["birth_x_cm"]), float(r["birth_y_cm"])
            pts.append((x - PITCH * np.round(x / PITCH), y - PITCH * np.round(y / PITCH), float(r["birth_z_cm"])))
            w.append(float(r["weight"]))
    w = np.array(w)
    return np.array(pts)[rng.choice(len(w), M, p=w / w.sum())]


def selftest():
    """A uniformly charged disk of radius R at height h << R above the grounded plane: the field
    between them is ~sigma/eps0, pointing down at the disk's centre."""
    rng = np.random.default_rng(0)
    R, h, Q, zA = 0.03, 0.002, 1e-12, 0.0
    r = R * np.sqrt(rng.uniform(0, 1, 4000)); ph = rng.uniform(0, 2 * np.pi, 4000)
    src = np.c_[r * np.cos(ph), r * np.sin(ph), np.full(4000, zA + h)]
    q = np.full(4000, Q / 4000)
    img = src.copy(); img[:, 2] = 2 * zA - img[:, 2]
    probe = np.array([[0., 0., zA + h / 2]])
    Ez = (coulomb(probe, src, q, soft=2e-4) + coulomb(probe, img, -q, soft=2e-4))[0, 2]
    sigma = Q / (np.pi * R ** 2)
    print(f"selftest: E_z midway = {Ez:.4g} V/cm, sigma/eps0 = {-sigma * 4 * np.pi * K:.4g} V/cm")


def main(prod, qs_fC, n_trace=1000):
    rng = np.random.default_rng(5)
    for gap in (0.1, 0.2, 0.5, 1.0):
        if not list(prod.glob(f"ig{gap:.2f}_s*")): continue
        F0 = load_field(FIELD[gap]); zA = F0["zBC"] - gap * 0.1
        P = births(prod, gap, rng)
        X, Z = np.meshgrid(F0["xs"], F0["zs"])                            # the slice, y = 0
        probe = np.c_[X.ravel(), np.zeros(X.size), Z.ravel()]
        E1 = cloud_field(probe, P, zA, np.full(M, 1e-15 / M))            # per fC of event charge
        E1x, E1z = E1[:, 0].reshape(X.shape), E1[:, 2].reshape(X.shape)
        gas = F0["GAS"] > 0.5
        under = gas & (X < F0["rCuIn"]) & (Z < F0["zBC"])                 # gap below the hole
        print(f"\nig = {gap} mm: {np.mean(P[:, 2] < F0['zBC']):.0%} of ions in the gap; under the hole: "
              f"applied E_z median {np.median(F0['EZ'][under]) / 1e3:.1f} kV/cm, space-charge E_z per fC "
              f"down to {E1z[under].min():.1f} V/cm")
        trace = P[rng.choice(M, n_trace, replace=False)]
        print(f"{'Q [fC]':>10} {'ions -> anode':>14} {'-> bottom rim':>14} {'-> up the hole':>15}")
        qstar = None
        for Q in qs_fC:
            F = dict(F0); F["EX"] = F0["EX"] + Q * E1x; F["EZ"] = F0["EZ"] + Q * E1z
            dest = [ion_dest(F, np.hypot(x, y), z) for x, y, z in trace]
            fa = np.mean([d == "anode" for d in dest])
            print(f"{Q:10.0f} {fa:14.4f} {np.mean([d == 'bottom_rim' for d in dest]):14.4f} "
                  f"{np.mean([d == 'drift' for d in dest]):15.4f}")
            if qstar is None and fa > 0.01: qstar = Q
        print(f"   Q* (> 1 % of ions onto the anode) = {qstar if qstar else '> ' + str(max(qs_fC))} fC")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main(Path(sys.argv[1]), [float(q) for q in sys.argv[2:]] or [10, 30, 100, 300, 1000, 3000, 10000, 30000])
