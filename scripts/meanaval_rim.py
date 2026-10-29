#!/usr/bin/env python3
"""Bottom-rim charging vs induction gap from weighted mean-avalanche paths (exact field).

Reads runs made with simulation.mc_weighted_paths (+ dump_collection).  Each event is one
non-branching AvalancheMC path standing for its whole expected avalanche: 'e' rows carry the
expected electrons ending on each surface (and 'attached'), 'b' rows the expected ion births
along it (`weight` column).  The ions are traced along +E on that gap's exact-field slice
(results/extraction_charging/dump_ig*, from fields.dump_raw_field) — they diffuse ~100x less
than electrons.  Per gap, pooling every run dir ig<gap>_s<seed>:

  extraction = sum w_e(anode)      / sum w_e(all)
  e_rim      = sum w_e(bottom_rim) / sum w_e(all)     electrons landing on the rim
  i_rim      = sum w_i(bottom_rim) / sum w_e(all)     ions landing on the rim
  net        = i_rim - e_rim                          (+ = the rim charges positive)

all per avalanche electron, with 68% bootstrap intervals over paths (the weights are
heavy-tailed: a few corner-wrapping paths carry much of the total, so the intervals matter).

Usage: meanaval_rim.py <prod_dir> [out.csv]
Importable: load_field / trace_ion / ion_dest / cell_r / FIELD / MEAS.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DUMPS = REPO / "results" / "extraction_charging"
FIELD = {0.1: DUMPS / "dump_ig0p1", 0.2: DUMPS / "dump_ig0p2",
         0.5: DUMPS / "dump_ig0p5", 1.0: DUMPS / "dump_ig1p0"}
MEAS = {0.1: 0.51, 0.2: 0.64, 0.5: 0.855, 1.0: 0.80}
PITCH = 0.1   # cm, square hole lattice (hole_pitch_um = 1000)
SURF = ["anode", "bottom_rim", "hole_wall", "bottom_cu", "top_rim", "top_cu", "attached",
        "drift", "unresolved"]


def cell_r(x, y, pitch=PITCH):
    """Radius from the nearest hole axis: charges can cross into a neighbouring cell."""
    return np.hypot(x - pitch * np.round(x / pitch), y - pitch * np.round(y / pitch))


def load_field(d):
    g = json.loads((d / "run_config.json").read_text())["geometry"]
    rHole = g["hole_diameter_um"] * 0.5e-4
    rCu = rHole + g.get("rim_um", 0.) * 1e-4
    zDH = g["plate_thickness_um"] * 0.5e-4
    tCu = g["copper_thickness_um"] * 1e-4
    rimBand = g.get("rim_charge_height_um", 0.) * 1e-4 or tCu   # categorizeSurface default
    rows = list(csv.DictReader((d / "raw_vs_grid_field.csv").open()))
    X = np.array([float(r["x_cm"]) for r in rows]); Z = np.array([float(r["z_cm"]) for r in rows])
    ex = np.array([float(r["ex_raw"]) for r in rows]); ez = np.array([float(r["ez_raw"]) for r in rows])
    gas = np.array([float(r["in_gas"]) for r in rows])
    xs, zs = np.unique(X), np.unique(Z)

    def grid(v):
        G = np.full((zs.size, xs.size), np.nan)
        G[np.searchsorted(zs, Z), np.searchsorted(xs, X)] = v
        return G

    # holes are 4(n-1)-gons inscribed in the nominal circle: copper wall spans [rCu cos(pi/N), rCu]
    nCorner = 4 * (g.get("hole_sectors", 4) - 1)
    return dict(EX=grid(ex), EZ=grid(ez), GAS=grid(gas), xs=xs, zs=zs,
                rCuIn=rCu * np.cos(np.pi / nCorner), zDH=zDH, rimBand=rimBand,
                zBC=-(zDH + tCu), zTop=zDH + tCu, zA=-(zDH + tCu) - g["induction_gap_mm"] * 0.1)


def bil(F, M, x, z):
    xs, zs = F["xs"], F["zs"]; x = abs(x)
    if x < xs[0] or x > xs[-1] or z < zs[0] or z > zs[-1]: return np.nan
    i = min(max(np.searchsorted(xs, x) - 1, 0), xs.size - 2)
    j = min(max(np.searchsorted(zs, z) - 1, 0), zs.size - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i]); tz = (z - zs[j]) / (zs[j + 1] - zs[j])
    return ((1 - tx) * (1 - tz) * M[j, i] + tx * (1 - tz) * M[j, i + 1]
            + (1 - tx) * tz * M[j + 1, i] + tx * tz * M[j + 1, i + 1])


def classify(F, r, z):   # mirrors categorizeSurface in src/thgem_sim.cc
    if z < F["zBC"] - 1e-4: return "anode"
    if z > F["zTop"]: return "drift"
    if r >= F["rCuIn"] - 1e-5:
        if z < -F["zDH"]: return "bottom_cu"
        if z > F["zDH"]: return "top_cu"
    if z < -F["zDH"] + F["rimBand"]: return "bottom_rim"
    if z > F["zDH"] - F["rimBand"]: return "top_rim"
    return "hole_wall"


def trace_ion(F, r, z, step=2e-4):   # +E field line (ions follow +E), diffusion neglected
    """The slice starts one row (5 um) above the anode plane zA; below that first row the field is
    taken from it, and an ion counts as 'anode' only if it actually travels down to zA."""
    for _ in range(12000):
        zq = max(z, F["zs"][0])
        ex = bil(F, F["EX"], r, zq); ez = bil(F, F["EZ"], r, zq)
        if np.isnan(ex) and abs(r) > F["xs"][-1] and z > F["zTop"]:
            # left the slice sideways above the plate: over the top copper the drift field points
            # up (the cathode is the more negative electrode), so the ion drifts to the cathode
            return "drift"
        if np.isnan(ex) or np.hypot(ex, ez) < 1e-9: return "stuck"
        n = np.hypot(ex, ez); r += ex / n * step; z += ez / n * step
        if z <= F["zA"]: return "anode"
        if z >= F["zs"][-1] - step: return "drift"
        gg = bil(F, F["GAS"], r, max(z, F["zs"][0]))
        if not np.isnan(gg) and gg < 0.5: return classify(F, abs(r), z)
    return "stuck"


def ion_dest(F, r0, z0):
    """Where an ion born at (r0, z0) lands.  The slices cover only the lower hole and the gap
    (z <= -100 um): an ion born higher sits in the upward hole field and drifts out of the
    top, so it can never reach the bottom rim — it counts as 'drift', not as missing."""
    if z0 > F["zs"][-1]: return "drift"
    if r0 > F["xs"][-1]: return "outside"
    return trace_ion(F, r0, z0)


def paths_for(prod, gap):
    P = defaultdict(lambda: {"e": defaultdict(float), "b": []})
    for d in sorted(prod.glob(f"ig{gap:.2f}_s*")):
        f = d / "collection_endpoints.csv"
        if not f.exists(): continue
        for r in csv.DictReader(f.open()):
            if None in r.values(): continue            # partially flushed row of a live run
            p = P[(d.name, r["event"])]
            w = float(r["weight"])
            if r["species"] == "b":
                p["b"].append((cell_r(float(r["birth_x_cm"]), float(r["birth_y_cm"])),
                               float(r["birth_z_cm"]), w))
            elif r["species"] == "e":
                p["e"][r["surface"]] += w
    return [p for p in P.values() if p["e"]]


def boot(num, den, rng, B=2000):
    """Pooled ratio sum(num)/sum(den) and its 16/84% bootstrap interval over paths."""
    num, den = np.asarray(num), np.asarray(den)
    idx = rng.integers(0, len(den), size=(B, len(den)))
    lo, hi = np.percentile(num[idx].sum(1) / den[idx].sum(1), [16, 84])
    return num.sum() / den.sum(), lo, hi


def main(prod, out):
    rng = np.random.default_rng(7)
    rows_out = []
    print(f"{'gap':>4} {'paths':>6} {'extraction':>22} {'e_rim':>22} {'i_rim':>22} {'NET (i-e)':>22} | meas")
    for gap in [0.1, 0.2, 0.5, 1.0]:
        P = paths_for(prod, gap)
        if not P:
            print(f"{gap:4.1f}  (no data)"); continue
        F = load_field(FIELD[gap])
        tot = np.array([sum(p["e"].values()) for p in P])
        e_by = {s: np.array([p["e"].get(s, 0.) for p in P]) for s in SURF}
        i_rim = np.array([sum(w for r0, z0, w in p["b"] if ion_dest(F, r0, z0) == "bottom_rim") for p in P])
        i_tot = np.array([sum(w for *_, w in p["b"]) for p in P])
        ext, er = boot(e_by["anode"], tot, rng), boot(e_by["bottom_rim"], tot, rng)
        ir, nt = boot(i_rim, tot, rng), boot(i_rim - e_by["bottom_rim"], tot, rng)
        fmt = lambda t: f"{t[0]:8.4f} [{t[1]:.4f},{t[2]:.4f}]"
        print(f"{gap:4.1f} {len(P):6d} {fmt(ext):>22} {fmt(er):>22} {fmt(ir):>22} {fmt(nt):>22} | {MEAS[gap]:.3f}")
        rows_out.append(dict(
            gap_mm=gap, paths=len(P), ess=tot.sum() ** 2 / (tot ** 2).sum(),
            extraction=ext[0], extraction_lo=ext[1], extraction_hi=ext[2],
            e_rim=er[0], e_rim_lo=er[1], e_rim_hi=er[2], i_rim=ir[0], i_rim_lo=ir[1], i_rim_hi=ir[2],
            net=nt[0], net_lo=nt[1], net_hi=nt[2],
            e_bottom_cu=e_by["bottom_cu"].sum() / tot.sum(), e_hole_wall=e_by["hole_wall"].sum() / tot.sum(),
            e_attached=e_by["attached"].sum() / tot.sum(), ions_per_electron=i_tot.sum() / tot.sum(),
            measured=MEAS[gap]))
    if rows_out:
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0])); w.writeheader(); w.writerows(rows_out)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    prod = Path(sys.argv[1])
    main(prod, Path(sys.argv[2]) if len(sys.argv) > 2 else prod / "rim_charge_vs_gap.csv")
