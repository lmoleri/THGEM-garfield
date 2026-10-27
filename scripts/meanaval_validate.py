#!/usr/bin/env python3
"""Check the weighted mean-avalanche (AvalancheMC, local field) against microscopic avalanches.

Both runs must release primaries at the same place (source.release_z_cm + release_r_max_cm,
same field).  Per primary, binned by release radius, compares the mean number of avalanche
electrons, where they end (anode / bottom copper / rim / wall / attached) and the fraction of
ions that field-line onto the bottom rim — the quantities the rim-charging study rests on.  The
near-wall bins test the corner gain that the local-field approximation may overstate.

Usage: meanaval_validate.py <ig_mm> <weighted_run_dir> <microscopic_run_dir> [more micro dirs...]
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meanaval_rim import FIELD, load_field, ion_dest, cell_r   # noqa: E402

GAP = float(sys.argv[1])
WDIR, MDIRS = Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]]
F = load_field(FIELD[GAP])
FATES = ["anode", "bottom_cu", "bottom_rim", "hole_wall", "attached"]
RBINS = [(0, 120), (120, 200), (200, 245)]          # release radius [um]


def rows(d):
    f = d / "collection_endpoints.csv"
    if not f.exists(): return []
    return [r for r in csv.DictReader(f.open()) if None not in r.values() and r.get("surface")]


def primaries_weighted(d):
    """one record per path: release r, electrons by fate (weights), ion births (r, z, w)."""
    P = defaultdict(lambda: {"e": defaultdict(float), "b": [], "r0": None})
    for r in rows(d):
        p = P[r["event"]]
        if r["species"] == "b":
            p["b"].append((cell_r(float(r["birth_x_cm"]), float(r["birth_y_cm"])), float(r["birth_z_cm"]),
                           float(r["weight"])))
        else:
            p["e"][r["surface"]] += float(r["weight"])
            p["r0"] = cell_r(float(r["birth_x_cm"]), float(r["birth_y_cm"])) * 1e4
    return [p for p in P.values() if p["e"]]


def primaries_micro(dirs):
    """one record per event: the primary is the first electron row; every later one is a birth."""
    out = []
    for d in dirs:
        ev = defaultdict(list)
        for r in rows(d):
            if r["species"] == "e": ev[r["event"]].append(r)
        for rs in ev.values():
            p = {"e": defaultdict(float), "b": [],
                 "r0": cell_r(float(rs[0]["birth_x_cm"]), float(rs[0]["birth_y_cm"])) * 1e4}
            for x in rs: p["e"][x["surface"]] += 1.
            p["b"] = [(cell_r(float(x["birth_x_cm"]), float(x["birth_y_cm"])), float(x["birth_z_cm"]), 1.)
                      for x in rs[1:]]
            out.append(p)
    return out


def summary(P):
    if not P: return None
    tot = np.array([sum(p["e"].values()) for p in P])
    fate = {f: np.array([p["e"].get(f, 0.) for p in P]) for f in FATES}
    irim = np.array([sum(w for r0, z0, w in p["b"] if ion_dest(F, r0, z0) == "bottom_rim") for p in P])
    sem = lambda a: a.std(ddof=1) / np.sqrt(len(a)) if len(a) > 1 else 0.
    s = {"n": len(P), "electrons": (tot.mean(), sem(tot))}
    for f in FATES: s[f] = (fate[f].sum() / tot.sum(), sem(fate[f]) / tot.mean())
    s["ion_rim"] = (irim.sum() / tot.sum(), sem(irim) / tot.mean())
    return s


W, M = primaries_weighted(WDIR), primaries_micro(MDIRS)
print(f"ig = {GAP} mm; weighted paths {len(W)}, microscopic primaries {len(M)}")
for lo, hi in [(0, 245)] + RBINS:
    sw = summary([p for p in W if lo <= p["r0"] < hi]); sm = summary([p for p in M if lo <= p["r0"] < hi])
    print(f"\nrelease r in [{lo}, {hi}) um       weighted (n={sw['n'] if sw else 0:4d})    microscopic (n={sm['n'] if sm else 0:3d})")
    for q in ["electrons"] + FATES + ["ion_rim"]:
        cell = lambda s: (f"{s[q][0]:8.3f} ± {s[q][1]:6.3f}" if s else " " * 17)
        print(f"   {q:>22}   {cell(sw):>20}   {cell(sm):>20}")
print("\n(electrons = mean per primary; fates and ion_rim = fraction of all avalanche electrons)")
