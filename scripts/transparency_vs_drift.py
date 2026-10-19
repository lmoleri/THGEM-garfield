#!/usr/bin/env python3
"""Electron-transparency sweep: run the THGEM sim in drift-only (no-multiplication)
mode across a list of drift-gap sizes and plot the collection fractions vs drift gap.

For each gap it writes a one-off config (drift_only = true), runs `thgem_sim` once
(each gap is its own, cached, neBEM solve), reads the transparency fractions from that
run's summary.csv, and finally writes a CSV + PNG of:

  * frac_anode              - fraction of drifted electrons collected at the anode
  * anode/(anode+bottom)    - of the electrons that reached an electrode, the fraction
                              reaching the anode rather than the THGEM bottom copper

The binary needs GARFIELD_INSTALL and HEED_DATABASE in the environment (as for any run),
and is launched from the project root so gas/ and field_cache/ are found.

Example:
    export GARFIELD_INSTALL=/path/to/local/garfield
    export HEED_DATABASE=$GARFIELD_INSTALL/share/Heed/database
    python3 scripts/transparency_vs_drift.py \
        --config config/THGEM_0-4mm_drift.json \
        --gap-range 0.1 4.0 0.2 --events 2000 --out results/transparency
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config/THGEM_0-4mm_drift.json",
                   help="Base config (geometry/fields/gas); drift gap is overridden per point.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--gaps", help="Explicit comma-separated drift gaps in mm, e.g. 0.1,0.5,1,2,4")
    g.add_argument("--gap-range", nargs=3, type=float, metavar=("LO", "HI", "STEP"),
                   help="Drift-gap range in mm (inclusive of LO; stops at/below HI).")
    p.add_argument("--events", type=int, default=2000, help="Electrons drifted per gap.")
    p.add_argument("--out", default="results/transparency", help="Output directory.")
    p.add_argument("--binary", default="build/thgem_sim", help="Path to the thgem_sim binary.")
    p.add_argument("--release", default="random",
                   help="'random' = uniform over the drift gap (source_distances_mm=null), "
                        "or a number = fixed release height in mm above the top copper.")
    p.add_argument("--force", action="store_true",
                   help="Re-run gaps even if a previous summary.csv exists.")
    return p.parse_args()


def gap_list(args: argparse.Namespace) -> list[float]:
    if args.gaps:
        return [float(x) for x in args.gaps.split(",") if x.strip()]
    if args.gap_range:
        lo, hi, step = args.gap_range
        vals, v = [], lo
        while v <= hi + 1e-9:
            vals.append(round(v, 4))
            v += step
        return vals
    # sensible default sweep
    return [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0]


def run_one_gap(args, base_cfg: dict, gap: float, out_dir: Path) -> dict | None:
    run_name = f"gap_{gap:.3f}mm"
    run_dir = out_dir / run_name
    summary = run_dir / "summary.csv"
    if summary.exists() and not args.force:
        print(f"  gap {gap:.3f} mm: reusing {summary}")
    else:
        cfg = json.loads(json.dumps(base_cfg))  # deep copy
        cfg["geometry"]["drift_gap_mm"] = gap
        cfg["simulation"]["drift_only"] = True
        cfg["simulation"]["n_events"] = args.events
        if args.release == "random":
            cfg["source"]["source_distances_mm"] = None
        else:
            cfg["source"]["source_distances_mm"] = [float(args.release)]
        cfg_path = out_dir / f"{run_name}.json"
        cfg_path.write_text(json.dumps(cfg, indent=2))
        print(f"  gap {gap:.3f} mm: running (one-time neBEM solve if not cached)...", flush=True)
        r = subprocess.run([str(Path(args.binary)), "--config", str(cfg_path),
                            "--out", str(out_dir), "--run-name", run_name],
                           cwd=REPO_ROOT)
        if r.returncode != 0 or not summary.exists():
            print(f"  gap {gap:.3f} mm: FAILED (exit {r.returncode})", file=sys.stderr)
            return None
    row = list(csv.DictReader(summary.open()))[-1]
    return {
        "gap_mm": gap,
        "frac_anode": float(row["frac_anode"]),
        "sem_frac_anode": float(row["sem_frac_anode"]),
        "frac_bottom_cu": float(row["frac_bottom_cu"]),
        "sem_frac_bottom_cu": float(row["sem_frac_bottom_cu"]),
        "frac_top_cu": float(row["frac_top_cu"]),
        "frac_attached": float(row["frac_attached"]),
        "anode_over_anode_plus_bottom": float(row["anode_over_anode_plus_bottom"]),
    }


def main() -> int:
    args = parse_args()
    base_cfg = json.loads((REPO_ROOT / args.config).read_text())
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    gaps = gap_list(args)
    print(f"Transparency sweep over {len(gaps)} drift gaps: {gaps} mm "
          f"({args.events} electrons each)")

    rows = []
    for gap in gaps:
        res = run_one_gap(args, base_cfg, gap, out_dir)
        if res:
            rows.append(res)
            print(f"    -> anode {100*res['frac_anode']:.1f}%, "
                  f"bottom-Cu {100*res['frac_bottom_cu']:.1f}%, "
                  f"anode/(anode+bottom) {res['anode_over_anode_plus_bottom']:.3f}")
    if not rows:
        print("No successful runs.", file=sys.stderr)
        return 1

    csv_path = out_dir / "transparency_vs_drift.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {csv_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — CSV written, skipping plot.", file=sys.stderr)
        return 0

    x = [r["gap_mm"] for r in rows]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.errorbar(x, [r["frac_anode"] for r in rows],
                yerr=[r["sem_frac_anode"] for r in rows],
                marker="o", capsize=3, label="anode fraction (of all released)")
    ax.plot(x, [r["anode_over_anode_plus_bottom"] for r in rows],
            marker="s", ls="--", label="anode / (anode + bottom Cu)")
    ax.plot(x, [r["frac_bottom_cu"] for r in rows], marker="^", ls=":",
            label="bottom-Cu fraction")
    ax.set_xlabel("Drift gap [mm]")
    ax.set_ylabel("Fraction of electrons")
    ax.set_title("THGEM electron transparency vs drift gap (no multiplication)")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    png_path = out_dir / "transparency_vs_drift.png"
    fig.savefig(png_path, dpi=120)
    print(f"Wrote {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
