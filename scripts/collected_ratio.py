#!/usr/bin/env python3
"""The measured observable in collected charges:  R = N_e(anode) / N_ion(THGEM-top copper).

The extraction fraction of §12 (anode electrons / all electrons) equals R only if the THGEM-top
collects every avalanche ion.  Here every ion is followed to the electrode or surface that collects
it: the THGEM-top copper, the drift cathode (backflow), the top rim / hole wall / bottom rim
(dielectric), the bottom copper.

Input: weighted mean-avalanche runs (mc_weighted_paths) made with enable_ion_drift, so each sampled
ion birth (species 'b') was drifted in 3D on the exact field by AvalancheMC and its landing surface
written as species 'i' with the same weight.  Electrons are the path ends (species 'e').

Usage: collected_ratio.py <prod_dir>
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meanaval_rim import MEAS   # noqa: E402

ION_DEST = ["top_cu", "drift", "top_rim", "hole_wall", "bottom_rim", "bottom_cu", "anode", "other"]
E_DEST = ["anode", "bottom_cu", "bottom_rim", "hole_wall", "attached"]


def paths(prod, gap):
    P = defaultdict(lambda: {"e": defaultdict(float), "i": defaultdict(float)})
    for d in sorted(prod.glob(f"ig{gap:.2f}_s*")):
        f = d / "collection_endpoints.csv"
        if not f.exists(): continue
        for r in csv.DictReader(f.open()):
            if None in r.values() or r["species"] not in ("e", "i"): continue
            P[(d.name, r["event"])][r["species"]][r["surface"]] += float(r["weight"])
    return [p for p in P.values() if p["e"]]


def main(prod):
    rng = np.random.default_rng(13)
    rows = []
    for gap in (0.1, 0.2, 0.5, 1.0):
        P = paths(prod, gap)
        if not P: continue
        ne = {d: np.array([p["e"].get(d, 0.) for p in P]) for d in E_DEST}
        ne_tot = np.array([sum(p["e"].values()) for p in P])
        ni = {d: np.array([p["i"].get(d, 0.) for p in P]) for d in ION_DEST[:-1]}
        ni["other"] = np.array([sum(v for s, v in p["i"].items() if s not in ION_DEST[:-1]) for p in P])
        ni_tot = sum(ni.values())
        if ni_tot.sum() == 0:
            print(f"ig = {gap} mm: no drifted ions (run without enable_ion_drift?)"); continue
        idx = rng.integers(0, len(P), (2000, len(P)))
        R = ne["anode"].sum() / ni["top_cu"].sum()
        lo, hi = np.percentile(ne["anode"][idx].sum(1) / ni["top_cu"][idx].sum(1), [16, 84])
        ext = ne["anode"].sum() / ne_tot.sum()
        frac_i = {d: ni[d].sum() / ni_tot.sum() for d in ION_DEST}
        net_bottom = (ne["bottom_cu"].sum() - ni["bottom_cu"].sum()) / ne_tot.sum()
        print(f"\nig = {gap} mm ({len(P)} paths)")
        print(f"   electrons: anode {ext:.3f}, bottom Cu {ne['bottom_cu'].sum()/ne_tot.sum():.3f}, "
              f"bottom rim {ne['bottom_rim'].sum()/ne_tot.sum():.3f}, attached {ne['attached'].sum()/ne_tot.sum():.3f}")
        print("   ions:      " + ", ".join(f"{d} {frac_i[d]:.3f}" for d in ION_DEST))
        print(f"   R_sim = N_e(anode)/N_ion(top Cu) = {R:.3f} [{lo:.3f}, {hi:.3f}]   (measured {MEAS[gap]:.3f};"
              f" extraction {ext:.3f}); ions/electron {ni_tot.sum()/ne_tot.sum():.3f}")
        rows.append(dict(gap_mm=gap, paths=len(P), R_sim=R, R_lo=lo, R_hi=hi, extraction=ext,
                         ions_per_electron=ni_tot.sum() / ne_tot.sum(), measured=MEAS[gap],
                         net_bottom=net_bottom, **{f"ion_{d}": frac_i[d] for d in ION_DEST}))
    if rows:
        out = prod / "collected_ratio.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
