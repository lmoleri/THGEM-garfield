#!/usr/bin/env python3
"""Field-line extraction screen via SUPERPOSITION (E_tot = E_uncharged + E_charge).

neBEM solves the uncharged field cleanly; the trapped bottom-rim charge is added analytically
(Coulomb field of the charged exposed-rim dielectric surface — lower hole wall + bottom rim
face), the exact decomposition used by Correia & Azevedo.  Electron drift lines (steps along
-E) are traced from seeds across the lower hole to termination (anode vs bottom copper), vs the
surface charge density sigma [C/cm^2].  A geometric/topological screen — fast, ranks sigma;
promising values are confirmed with full avalanche runs.

Reads the sigma=0 dump (raw_vs_grid_field.csv + run_config.json).
Usage: trace_superpos.py <sigma0_run_dir> <sigma1> [sigma2 ...]   (sigma in C/cm^2, e.g. -1.6e-9)
"""
import csv, json, sys
from pathlib import Path
import numpy as np

EPS0 = 8.8541878e-14          # F/cm
K = 1.0 / (4 * np.pi * EPS0)  # V*cm/C
RUN = Path(sys.argv[1])
SIGMAS = [float(s) for s in sys.argv[2:]]

cfg = json.loads((RUN / "run_config.json").read_text())
g = cfg["geometry"]
rHole = g["hole_diameter_um"] * 0.5e-4
rCu = rHole + g.get("rim_um", 0.) * 1e-4
zDielHalf = g["plate_thickness_um"] * 0.5e-4
tCu = g["copper_thickness_um"] * 1e-4
zBotCuBot = -(zDielHalf + tCu)
zAnode = zBotCuBot - g["induction_gap_mm"] * 0.1
RIMH = g.get("rim_charge_height_um", 100.) * 1e-4 or 100e-4   # charged height on the wall

rows = list(csv.DictReader((RUN / "raw_vs_grid_field.csv").open()))
X = np.array([float(r["x_cm"]) for r in rows]); Z = np.array([float(r["z_cm"]) for r in rows])
EXr = np.array([float(r["ex_raw"]) for r in rows]); EZr = np.array([float(r["ez_raw"]) for r in rows])
GASv = np.array([float(r["in_gas"]) for r in rows])
xs, zs = np.unique(X), np.unique(Z)
nx, nz = xs.size, zs.size
idx = {(round(x, 7), round(z, 7)): k for k, (x, z) in enumerate(zip(X, Z))}
def togrid(v):
    G = np.full((nz, nx), np.nan)
    for k, (x, z) in enumerate(zip(X, Z)):
        G[np.searchsorted(zs, z), np.searchsorted(xs, x)] = v[k]
    return G
EX0, EZ0, GAS = togrid(EXr), togrid(EZr), togrid(GASv)

# --- charged surface: lower hole wall (r=rHole, z in [zBot, zBot+RIMH]) + bottom rim face
# (z=zBot=-zDielHalf, r in [rHole, rCu]); modelled as rings of point charges (per unit sigma).
NPHI = 48
phis = np.linspace(0, 2 * np.pi, NPHI, endpoint=False)
elems = []   # (x', y', z', dA)  for sigma = 1 C/cm^2
nwall = max(2, int(round(RIMH / 5e-4)))
for zc in np.linspace(-zDielHalf + 2.5e-4, -zDielHalf + RIMH, nwall):
    dl = RIMH / nwall; dA = 2 * np.pi * rHole * dl / NPHI
    for p in phis:
        elems.append((rHole * np.cos(p), rHole * np.sin(p), zc, dA))
nface = max(2, int(round((rCu - rHole) / 5e-4)))
for rc in np.linspace(rHole + 2.5e-4, rCu - 2.5e-4, nface):
    dr = (rCu - rHole) / nface; dA = 2 * np.pi * rc * dr / NPHI
    for p in phis:
        elems.append((rc * np.cos(p), rc * np.sin(p), -zDielHalf, dA))
EL = np.array(elems)   # (M,4)

# field per unit sigma on the grid (field points at y=0, x=grid x which stands for r)
gx, gz = np.meshgrid(xs, zs)       # (nz,nx)
ECX = np.zeros_like(gx); ECZ = np.zeros_like(gx)
soft = (2.5e-4) ** 2
for (xp, yp, zp, dA) in EL:
    dx = gx - xp; dy = 0.0 - yp; dz = gz - zp
    d2 = dx * dx + dy * dy + dz * dz + soft
    inv = dA / d2 ** 1.5
    ECX += dx * inv; ECZ += dz * inv
ECX *= K; ECZ *= K                 # V/cm per (C/cm^2)


def bilin(M, x, z):
    x = abs(x)
    if x < xs[0] or x > xs[-1] or z < zs[0] or z > zs[-1]:
        return np.nan
    i = min(max(np.searchsorted(xs, x) - 1, 0), nx - 2)
    j = min(max(np.searchsorted(zs, z) - 1, 0), nz - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i]); tz = (z - zs[j]) / (zs[j + 1] - zs[j])
    return ((1 - tx) * (1 - tz) * M[j, i] + tx * (1 - tz) * M[j, i + 1] +
            (1 - tx) * tz * M[j + 1, i] + tx * tz * M[j + 1, i + 1])


def trace(EX, EZ, seed_z=-0.016, n_seed=50, step=2e-4, max_steps=8000):
    fates = {"anode": 0, "bottom_cu": 0, "dielectric": 0, "top_cu": 0, "unresolved": 0}
    for rs in np.linspace(0.02 * rHole, 0.97 * rHole, n_seed):
        x, z = rs, seed_z; fate = "unresolved"
        for _ in range(max_steps):
            ex = bilin(EX, x, z); ez = bilin(EZ, x, z)
            if np.isnan(ex) or np.hypot(ex, ez) < 1e-9:
                break
            n = np.hypot(ex, ez); x += -ex / n * step; z += -ez / n * step
            if z <= zs[0] + 2 * step:   # reached the dump bottom (≈ anode) → extracted
                fate = "anode"; break
            gg = bilin(GAS, x, z)
            if not np.isnan(gg) and gg < 0.5:
                fate = "bottom_cu" if z < -zDielHalf else ("top_cu" if z > zDielHalf else "dielectric")
                break
        fates[fate] += 1
    tot = sum(fates.values())
    return {k: v / tot for k, v in fates.items()}

print(f"geom: rHole={rHole*1e4:.0f} rCu={rCu*1e4:.0f} zBotCu={zBotCuBot*1e4:.0f} zAnode={zAnode*1e4:.0f} um")
print(f"charge surface: {len(EL)} elements (wall {nwall} rings + face {nface} rings), E_charge/sigma "
      f"max={np.nanmax(np.hypot(ECX,ECZ)):.2e} (V/cm)/(C/cm^2)")
print(f"\n sigma[C/cm^2]  ~1e10e/cm^2    anode   bottom_cu  diel  unres")
for s in SIGMAS:
    f = trace(EX0 + s * ECX, EZ0 + s * ECZ)
    print(f"  {s:+.2e}   ({s/1.6e-9:+.1f}x)   {f['anode']:.2f}    {f['bottom_cu']:.2f}    "
          f"{f['dielectric']:.2f}  {f['unresolved']:.2f}")
