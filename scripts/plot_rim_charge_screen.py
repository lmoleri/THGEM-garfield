#!/usr/bin/env python3
"""Figure for docs/extraction_ratio_investigation.md §11 — the rim-charge extraction screen.

Left: screened extraction (anode/total) vs bottom-rim surface charge σ, on the superposed field
E_uncharged(neBEM) + σ·E_annulus(Coulomb).  Right: sample electron drift lines for σ = 0, one
negative and one positive — negative focuses electrons through to the anode, positive pulls them
out onto the bottom copper.  Uses the screen machinery in screen_rim_charge.py.

Usage: plot_rim_charge_screen.py <sigma0_dump_dir>   (default: results/extraction_charging/dump_ig0p5)
Writes docs/figures/rim_charge_screen.png."""
import sys, importlib.util
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "results/extraction_charging/dump_ig0p5"
DEST = REPO / "docs/figures/rim_charge_screen.png"

# load screen_rim_charge with argv pointing at the dump dir (its module body builds the fields)
spec = importlib.util.spec_from_file_location("screen", REPO / "scripts/screen_rim_charge.py")
sys.argv = ["screen", str(RUN)]
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
EX0, EZ0, GAS, ECX, ECZ, xs, zs = sc.EX0, sc.EZ0, sc.GAS, sc.ECX, sc.ECZ, sc.xs, sc.zs
rHole, rCu, zDielHalf, zBotCuBot, zAnode = sc.rHole, sc.rCu, sc.zDielHalf, sc.zBotCuBot, sc.zAnode

sig = np.sort(np.array([0, -1.6e-10, -4e-10, -8e-10, -1.6e-9, -4e-9, -8e-9, 8e-10, 1.6e-9, 4e-9]))
anode = [sc.trace(EX0 + s * ECX, EZ0 + s * ECZ)["anode"] for s in sig]

fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))
axL.axhline(0.855, color="k", ls=":", lw=1, label="measured peak (0.855)")
axL.axhline(0.51, color="gray", ls=":", lw=1, label="measured @0.1 mm (0.51)")
axL.plot(sig * 1e9, anode, "o-", color="tab:purple", lw=2); axL.axvline(0, color="k", lw=.5)
axL.set_xlabel("bottom-rim surface charge σ  [nC/cm²]   (1.6 ≈ 10¹⁰ e/cm²)")
axL.set_ylabel("extraction  (anode / total)")
axL.set_title("Field-line extraction screen vs rim charge  (ig = 0.5 mm)\n"
              "negative (electrons) → MORE extraction;  positive (ions) → less")
axL.set_ylim(0.1, 1.02); axL.grid(alpha=.3); axL.legend(fontsize=8, loc="lower left")


def lines(ax, s, col, lab):
    EX, EZ = EX0 + s * ECX, EZ0 + s * ECZ
    for rs in np.linspace(0.05 * rHole, 0.95 * rHole, 12):
        x, z = rs, -0.016; px, pz = [x], [z]
        for _ in range(8000):
            ex = sc.bilin(EX, x, z); ez = sc.bilin(EZ, x, z)
            if np.isnan(ex) or np.hypot(ex, ez) < 1e-9:
                break
            n = np.hypot(ex, ez); x += -ex / n * 2e-4; z += -ez / n * 2e-4
            px.append(x); pz.append(z)
            if z <= zs[0] + 4e-4:
                break
            gg = sc.bilin(GAS, x, z)
            if not np.isnan(gg) and gg < .5:
                break
        ax.plot(np.array(px) * 1e4, np.array(pz) * 1e4, col, lw=.8, alpha=.8)
    ax.plot([], [], col, label=lab)


axR.add_patch(plt.Rectangle((rCu * 1e4, zBotCuBot * 1e4), 450 - rCu * 1e4, 35, color="orange", alpha=.4))
axR.add_patch(plt.Rectangle((rHole * 1e4, -zDielHalf * 1e4), (rCu - rHole) * 1e4, 2 * zDielHalf * 1e4,
                            color="red", alpha=.3))
axR.axhline(zAnode * 1e4, color="green"); axR.axvline(rHole * 1e4, color="k", ls=":", lw=.6)
lines(axR, 0.0, "C0", "σ = 0")
lines(axR, -1.6e-9, "C2", "σ = −1.6 nC/cm²")
lines(axR, +1.6e-9, "C3", "σ = +1.6 nC/cm²")
axR.set_xlim(0, 450); axR.set_ylim(zAnode * 1e4 - 15, -90)
axR.set_xlabel("r [µm]"); axR.set_ylabel("z [µm]")
axR.set_title("electron drift lines from the hole exit\n(red = charged rim annulus, orange = bottom Cu)")
axR.legend(fontsize=8, loc="lower right")
fig.tight_layout()
DEST.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(DEST, dpi=130)
print("wrote", DEST, "| σ[nC/cm²]:anode", [f"{s*1e9:+.1f}:{a:.2f}" for s, a in zip(sig, anode)])
