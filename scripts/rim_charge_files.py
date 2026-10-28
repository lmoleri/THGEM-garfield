#!/usr/bin/env python3
"""Write neBEM charging-up input that puts a uniform test charge on the bottom rim.

The bottom rim is the exposed dielectric the rim-charging study tallies as `bottom_rim`
(categorizeSurface in src/thgem_sim.cc): the dielectric's bottom face between the hole and the
etched-back copper, plus the lowest band of the hole wall.  Deposits are written as neBEM
charging-up "ion" lines — a short last segment from the gas side into the dielectric — so neBEM
maps each onto the dielectric element it pierces and solves the field with the full conductor /
dielectric response (fields.charging_up).  Holes are 12-gons inscribed in the nominal circle, so
deposits are kept where they hit a dielectric face for any polygon orientation: face points at
r in [rHole, rCu*cos(pi/N)], wall segments running radially across [rHole*cos(pi/N), rHole].

Writes <workdir>/neBEMInp/{neBEMChargingUp.inp, rim_e.txt, rim_i.txt}.
Usage: rim_charge_files.py <run_config.json> <workdir> <sigma_C_per_cm2> [n_deposits]
"""
import json
import sys
from pathlib import Path

import numpy as np

E_CHARGE = 1.60217646e-19   # C, as neBEM's Q_I


def rim_geometry(cfg):
    g = cfg["geometry"]
    rHole = g["hole_diameter_um"] * 0.5e-4
    rCu = rHole + g.get("rim_um", 0.) * 1e-4
    zDH = g["plate_thickness_um"] * 0.5e-4
    band = g.get("rim_charge_height_um", 0.) * 1e-4 or g["copper_thickness_um"] * 1e-4
    cosN = np.cos(np.pi / (4 * (g.get("hole_sectors", 4) - 1)))
    return rHole, rCu, zDH, band, cosN


def deposits(cfg, n, rng):
    """(last-but-end, end) point pairs, uniform over the bottom-rim area, and that area [cm^2]."""
    rHole, rCu, zDH, band, cosN = rim_geometry(cfg)
    r0, r1 = rHole + 3e-4, rCu * cosN - 3e-4                    # face, 3 um clear of both edges
    a_face = np.pi * (r1 ** 2 - r0 ** 2)
    a_wall = 2 * np.pi * rHole * cosN * band                     # mean 12-gon perimeter x band
    n_face = int(round(n * a_face / (a_face + a_wall))); n_wall = n - n_face
    seg = []
    r = np.sqrt(rng.uniform(r0 ** 2, r1 ** 2, n_face)); ph = rng.uniform(0, 2 * np.pi, n_face)
    for ri, p in zip(r, ph):                                     # face: gas below -> dielectric above
        x, y = ri * np.cos(p), ri * np.sin(p)
        seg.append(((x, y, -zDH - 2e-4), (x, y, -zDH + 2e-4)))
    z = rng.uniform(-zDH + 2e-4, -zDH + band - 2e-4, n_wall); ph = rng.uniform(0, 2 * np.pi, n_wall)
    for zi, p in zip(z, ph):                                     # wall: hole -> dielectric, radially
        c, s = np.cos(p), np.sin(p)
        seg.append(((rHole * cosN - 3e-4) * np.array([c, s, 0]) + [0, 0, zi],
                    (rHole + 3e-4) * np.array([c, s, 0]) + [0, 0, zi]))
    return seg, a_face + a_wall


def write_line(fh, label, k, lbe, end):
    fh.write(f"{label} 1 {k} {lbe[0]:.8g} {end[0]:.8g} {lbe[1]:.8g} {end[1]:.8g} "
             f"{lbe[2]:.8g} {end[2]:.8g}\n")


def main(cfg_path, workdir, sigma, n):
    cfg = json.loads(Path(cfg_path).read_text())
    seg, area = deposits(cfg, n, np.random.default_rng(1))
    d = Path(workdir) / "neBEMInp"; d.mkdir(parents=True, exist_ok=True)
    # neBEM needs a non-empty electron file: one electron on the first deposit, so the net is n-1.
    unit = sigma * area / ((len(seg) - 1) * E_CHARGE)            # elementary charges per line
    with (d / "rim_i.txt").open("w") as fh:
        fh.write("# label vol n xlbe xend ylbe yend zlbe zend [cm]\n")
        for k, (lbe, end) in enumerate(seg, 1): write_line(fh, "I", k, lbe, end)
    with (d / "rim_e.txt").open("w") as fh:
        fh.write("# label vol n xlbe xend ylbe yend zlbe zend [cm]\n")
        write_line(fh, "E", 1, *seg[0])
    (d / "neBEMChargingUp.inp").write_text(
        "OptChargingUp: 1\n"
        f"ChargingUpEFile: {(d / 'rim_e.txt').resolve()}\n"
        f"ChargingUpIFile: {(d / 'rim_i.txt').resolve()}\n"
        "LScaleFactor: 100\n"
        f"ChUpFactor: {unit:.10g}\n")
    print(f"{len(seg)} deposits over {area * 1e8:.0f} um^2 -> sigma {sigma:.3g} C/cm^2, "
          f"{unit:.4g} e per line, total {sigma * area:.4g} C")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 6000)
