#!/usr/bin/env python3
"""Paired metal/contacted-glass diagnostics. No modification of existing results.

Commands: benchmark, pilot, sweep, analyse. Runs are sequential and resumable;
the cache identity includes the executable and full resolved configuration.
"""
import argparse
import copy
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np

REPO = Path(__file__).resolve().parents[1]
EPS0 = 8.8541878128e-12
GAPS = [.1, .2, .5, 1., 2.]
FIELDS = [1.5, 2., 2.5]
EPSILONS = [4., 6., 8., 10., 12.]
CHANNELS = ["anode_e", "top_e", "bottom_e", "drift_e"]
RUN_BINARY_SHA = None


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gas_filename(g):
    def integer(x):
        return str(math.floor(x+.5))
    return (f"{g['gas1']}{integer(g['gas1_fraction_pct'])}_{g['gas2']}_{integer(100-g['gas1_fraction_pct'])}"
            f"_T{integer(g['temperature_K'])}_P{integer(g['pressure_Torr'])}"
            f"_Ee{integer(g['max_electron_energy_eV'])}_Ef{integer(g['e_field_min_vcm'])}v-"
            f"{integer(g['e_field_max_vcm']/1000)}k_n{g['n_field_points']}_c{g['n_magboltz_collisions']}"
            f"_{'pen' if g['enable_penning'] else 'nopen'}.gas")


def planar(gap_mm, thickness_mm, epsilon, rho_ohm_cm, time_ns):
    """Full rear-face ohmic contact; glass conductance is parallel to C_glass.

    Charge transfer after an instantaneous gas traversal, normalized to Q.
    tau = R_bulk*(C_glass+C_gap), not simply rho*epsilon.
    """
    if gap_mm <= 0 or thickness_mm < 0 or epsilon < 1 or rho_ohm_cm <= 0 or time_ns < 0:
        raise ValueError("Invalid planar parameters")
    f = gap_mm / (gap_mm + thickness_mm / epsilon)
    tau = rho_ohm_cm * .01 * EPS0 * (epsilon + thickness_mm / gap_mm)
    recovered = f + (1-f) * -math.expm1(-time_ns * 1e-9 / tau)
    # Conservative bound on any lateral mode's local relaxation time.
    tau_min = rho_ohm_cm * .01 * EPS0 * min(epsilon+1, epsilon+thickness_mm/gap_mm)
    return dict(prompt=f, tau_s=tau, recovered=recovered,
                relative_conduction=(recovered-f)/f,
                conservative_relative_bound=(1-f)/f * -math.expm1(-time_ns*1e-9/tau_min))


def run(binary, root, config, mode, snapshots=None, gas_source=None):
    executable_hash = sha(binary)
    if RUN_BINARY_SHA is not None and executable_hash != RUN_BINARY_SHA:
        raise RuntimeError("Executable changed during study; restart to preserve reproducibility")
    table = None
    if mode == "export":
        candidates = [REPO / "gas", REPO / "results/thick_plate/prod/work/gas"]
        if gas_source:
            candidates.insert(0, gas_source)
        table = next((d / gas_filename(config["gas"]) for d in candidates if (d / gas_filename(config["gas"])).exists()), None)
        if table is None:
            raise RuntimeError("Required gas table unavailable; supply --gas-source containing " + gas_filename(config["gas"]))
    identity = dict(config=config, mode=mode, binary_sha256=executable_hash,
                    gas_sha256=sha(table) if table else None,
                    snapshot_sha256=sha(snapshots) if snapshots else None)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    folder = root / "jobs" / key
    folder.mkdir(parents=True, exist_ok=True)
    done = folder / "complete.json"
    expected = {"export": "charge_snapshots.csv", "replay": "signal_charges.csv", "planar": "planar.json"}[mode]
    if done.exists() and (folder / expected).exists():
        if json.loads(done.read_text())["output_sha256"] != sha(folder / expected):
            raise RuntimeError(f"Changed cached output: {folder}")
        return folder
    cf = folder / "config.json"
    cf.write_text(json.dumps(config, indent=2) + "\n")
    if mode == "export":
        gas_dir = folder / "gas"
        gas_dir.mkdir(exist_ok=True)
        shutil.copy2(table, gas_dir / table.name)
    cmd = [str(binary), "--config", str(cf), "--out", str(folder.parent), "--run-name", folder.name,
           f"--glass-{mode}"]
    if snapshots:
        cmd.append(str(snapshots))
    env = dict(os.environ)
    env["GARFIELD_INSTALL"] = str(REPO.parents[1] / "local/garfield")
    env["HEED_DATABASE"] = env["GARFIELD_INSTALL"] + "/share/Heed/database"
    begin = time.monotonic()
    (root / "status.json").write_text(json.dumps(dict(pid=os.getpid(), state="running", stage=mode,
                                                       job=str(folder), log=str(folder/"run.log")), indent=2)+"\n")
    print(f"{mode}: {folder.name} gap={config['geometry']['induction_gap_mm']} "
          f"field={config['fields']['e_induction_kvcm']} model={config['glass_signal']['model']}", flush=True)
    with (folder / "run.log").open("w") as log:
        result = subprocess.run(cmd, cwd=folder, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{mode} failed ({result.returncode}); see {folder / 'run.log'}")
    identity.update(elapsed_s=time.monotonic()-begin, output_sha256=sha(folder / expected))
    done.write_text(json.dumps(identity, indent=2) + "\n")
    return folder


def read_charges(path, attachment, t):
    values = {}
    with Path(path).open() as f:
        for row in csv.DictReader(f):
            if row["attachment"] != attachment or float(row["time_ns"]) != t:
                continue
            key = (int(row["seed"]), int(row["path"]))
            if key in values:
                raise ValueError("Duplicate path/time in charge output")
            values[key] = np.array([float(row[c]) for c in CHANNELS])
    return values


def validate_snapshots(path):
    """Check signed accounting independently of the exporter's internal ledger."""
    totals, scales, primary = {}, {}, {}
    with Path(path).open() as f:
        for row in csv.DictReader(f):
            key = (int(row["seed"]), int(row["path"]), row["attachment"], float(row["time_ns"]))
            q = float(row["charge_e"])
            if not all(math.isfinite(float(row[c])) for c in ["charge_e", "x_cm", "y_cm", "z_cm", "time_ns"]):
                raise ValueError("Non-finite snapshot")
            if row["status"].startswith("failed"):
                raise ValueError("Failed transport in snapshot")
            totals[key] = totals.get(key, 0.)+q
            scales[key] = scales.get(key, 0.)+abs(q)
            if row["species"] == "primary_ion":
                primary[key] = primary.get(key, 0.)+q
    if not totals or any(abs(v) > 1e-9*max(scales[k], 1.) or primary.get(k) != 1. for k, v in totals.items()):
        raise ValueError("Snapshot charge conservation or primary-pair check failed")
    return max(abs(v)/max(scales[k], 1.) for k, v in totals.items())


def paired(metal, glass, replicates=2000):
    if metal.keys() != glass.keys() or not metal:
        raise ValueError("Metal and glass path identities differ or are empty")
    keys = sorted(metal)
    m = np.array([metal[k] for k in keys]); g = np.array([glass[k] for k in keys])
    def metrics(a, b):
        scale = np.maximum(np.abs(a).max(axis=-1), 1.)
        valid = (np.abs(a[..., 1]) > 1e-10*scale) & (np.abs(b[..., 1]) > 1e-10*scale) & (np.abs(a[..., 0]) > 1e-10*scale)
        with np.errstate(divide="ignore", invalid="ignore"):
            rm = np.abs(a[..., 0]/a[..., 1]); rg = np.abs(b[..., 0]/b[..., 1])
            out = np.stack((rm, rg, rg/rm, b[..., 0]/a[..., 0], b[..., 1]/a[..., 1]), axis=-1)
        return np.where(np.expand_dims(valid, -1), out, np.nan)
    a, b = m.sum(0), g.sum(0)
    central = metrics(a, b)
    rng = np.random.default_rng(812)
    # Batch to bound memory during 4,000-path convergence runs.
    boot = []
    for start in range(0, replicates, 100):
        ix = rng.integers(0, len(keys), (min(100, replicates-start), len(keys)))
        boot.append(metrics(m[ix].sum(1), g[ix].sum(1)))
    boot = np.concatenate(boot)
    good = np.all(np.isfinite(boot), axis=1)
    polarity = bool(np.any(a[:2]*b[:2] < 0))
    result = dict(paths=len(keys), invalid_bootstrap_fraction=float(1-good.mean()), polarity_change=polarity)
    for j, name in enumerate(["R_metal", "R_glass", "F", "anode_factor", "top_factor"]):
        lo, hi = np.percentile(boot[good, j], [2.5, 97.5]) if good.any() else (np.nan, np.nan)
        result.update({name: float(central[j]), name+"_lo": float(lo), name+"_hi": float(hi)})
    result.update({"metal_"+c: float(v) for c, v in zip(CHANNELS, a)})
    result.update({"glass_"+c: float(v) for c, v in zip(CHANNELS, b)})
    result["valid"] = bool(np.all(np.isfinite(central)) and good.mean() >= .99 and not polarity)
    return result


def analyse(root):
    index = json.loads((root / "index.json").read_text())
    rows = []
    groups = {}
    for record in index:
        groups.setdefault((record["gap"], record["field"], record["epsilon"], record.get("variant", "baseline")), []).append(record)
    for (gap, field, eps, variant), records in sorted(groups.items()):
        for attachment in ["fixed", "mobile"]:
            for t in [1000, 2000, 5000, 10000, 20000]:
                m, g = {}, {}
                max_partition = 0.
                for record in records:
                    # Verify transport hasn't changed since either replay.
                    digest = sha(record["snapshots"])
                    replay_hashes = set()
                    for arm in ["metal", "glass"]:
                        job = Path(record[arm])
                        meta = json.loads((job / "complete.json").read_text())
                        replay_hashes.add(meta["binary_sha256"])
                        if meta["snapshot_sha256"] != digest:
                            raise RuntimeError("Transport hash mismatch")
                        checks = json.loads((job / "weighting_checks.json").read_text())
                        max_partition = max(max_partition, checks["max_partition_residual"])
                        if abs(checks.get("rear_weighting_potential", 1.)-1.) > .01:
                            max_partition = max(max_partition, 1.)
                    if len(replay_hashes) != 1:
                        raise RuntimeError("Replay executable differs between arms")
                    m.update(read_charges(Path(record["metal"])/"signal_charges.csv", attachment, t))
                    g.update(read_charges(Path(record["glass"])/"signal_charges.csv", attachment, t))
                row = dict(gap_mm=gap, field_kvcm=field, epsilon_r=eps, variant=variant,
                           attachment=attachment, time_ns=t, max_partition_residual=max_partition,
                           **paired(m, g))
                p = planar(gap, records[0].get("thickness_mm", .8), eps, records[0].get("rho_ohm_cm", 1e10), t)
                row["conduction_bound"] = p["conservative_relative_bound"]
                row["valid"] &= max_partition < .01 and row["conduction_bound"] < .01
                for arm in ["metal", "glass"]:
                    for channel in ["anode", "top"]:
                        row[f"{arm}_{channel}_fC"] = row[f"{arm}_{channel}_e"] / row["paths"] * 227 * 1.602176634e-4
                rows.append(row)
    if not rows:
        raise RuntimeError("No complete pairs")
    with (root / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    os.environ.setdefault("MPLCONFIGDIR", str(root / "mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    pilot_label = "Validation pilot — insufficient statistics" if any(r["paths"] < 1000 for r in rows) else "Paired readout comparison"
    fig.suptitle(pilot_label + " | 10 µs, 2 kV/cm")
    for eps in sorted({r["epsilon_r"] for r in rows}):
        a = [r for r in rows if r["time_ns"] == 10000 and r["attachment"] == "mobile" and r["epsilon_r"] == eps and r["field_kvcm"] == 2 and r["variant"] == "baseline"]
        if not a: continue
        for ax, key in zip(axes.flat, ["R_glass", "F", "anode_factor", "top_factor"]):
            ax.errorbar([r["gap_mm"] for r in a], [r[key] for r in a],
                        yerr=np.array([[max(0, r[key]-r[key+"_lo"]) for r in a], [max(0, r[key+"_hi"]-r[key]) for r in a]]),
                        marker="o", label=f"εr={eps:g}")
            ax.set(xlabel="Induction gap [mm]", ylabel=key); ax.grid(alpha=.3)
    axes[0, 0].legend(); fig.savefig(root / "glass_comparison.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    fig.suptitle(pilot_label)
    central = [r for r in rows if r["epsilon_r"] == 8 and r["field_kvcm"] == 2 and r["variant"] == "baseline"]
    for gap in sorted({r["gap_mm"] for r in central}):
        for mode in ["fixed", "mobile"]:
            a = [r for r in central if r["gap_mm"] == gap and r["attachment"] == mode]
            axes[0].plot([r["time_ns"]/1000 for r in a], [r["F"] for r in a], marker="o", label=f"{gap:g} mm {mode}")
        a = [r for r in central if r["gap_mm"] == gap and r["attachment"] == "mobile" and r["time_ns"] == 10000]
        for r in a:
            for arm, marker in [("metal", "o"), ("glass", "x")]:
                axes[1].scatter(gap, abs(r[f"{arm}_anode_fC"]), marker=marker, color="C0")
                axes[1].scatter(gap, abs(r[f"{arm}_top_fC"]), marker=marker, color="C1")
    axes[0].set(xlabel="Observation time [µs]", ylabel="Glass / metal ratio factor F")
    axes[0].legend(fontsize=7); axes[0].grid(alpha=.3)
    axes[1].set(xlabel="Gap [mm]", ylabel="Input-equivalent charge [fC / 5.9 keV]", title="Anode blue; top orange; metal o; glass x")
    axes[1].grid(alpha=.3)
    fig.savefig(root / "time_and_charges.png", dpi=160); plt.close(fig)
    valid = all(r["valid"] for r in rows)
    numerical = []
    for r in rows:
        if r["variant"] != "refined" or r["time_ns"] != 10000:
            continue
        reference = next((v for v in rows if all(v[k] == r[k] for k in ["gap_mm", "field_kvcm", "epsilon_r", "attachment", "time_ns"]) and v["variant"] == "baseline"), None)
        if reference:
            numerical.append(dict(gap_mm=r["gap_mm"], epsilon_r=r["epsilon_r"], attachment=r["attachment"],
                                  relative_change=abs(r["F"]/reference["F"]-1)))
    (root / "convergence.json").write_text(json.dumps(numerical, indent=2)+"\n")
    by_gap = {r["gap_mm"]: r for r in central if r["attachment"] == "mobile" and r["time_ns"] == 10000}
    converged = len(numerical) >= 20 and all(v["relative_change"] < .02 for v in numerical)
    attachment_ok = all(abs(r["F"]/next(v["F"] for v in rows if all(v[k] == r[k] for k in ["gap_mm", "field_kvcm", "epsilon_r", "variant", "time_ns"]) and v["attachment"] == "fixed")-1) < .02 for r in rows if r["attachment"] == "mobile" and r["time_ns"] == 10000)
    precise = all(r["paths"] >= 1000 and r["F_hi"]-r["F_lo"] <= .05 for r in rows if r["time_ns"] == 10000)
    status = "inconclusive"
    details = "Numerical convergence, attachment sensitivity, statistical precision, and complete gap coverage are required."
    complete_grid = {(r["gap_mm"], r["field_kvcm"], r["epsilon_r"]) for r in rows if r["variant"] == "baseline"} == {(g,f,e) for g in GAPS for f in FIELDS for e in EPSILONS}
    if valid and converged and attachment_ok and precise and complete_grid and set(by_gap) == set(GAPS):
        small, peak = by_gap[.1], by_gap[.5]
        suppression = small["F"]/peak["F"]
        required = (.51/.855)/(small["R_metal"]/peak["R_metal"])
        if suppression >= .98:
            status = "unsupported within this model"
        elif suppression <= required:
            status = "sufficient in scale within this model"
        else:
            status = "partial"
        details = f"F(0.1 mm)/F(0.5 mm)={suppression:.4g}; required relative suppression for the reference measured shape={required:.4g}. This is a scale test, not an experimental fit."
    text = ["# Glass signal study", "", f"Status: **{status}**.", "", details,
            "", f"Complete paired summary rows: {len(rows)}. Internal validity gates passed: {valid}.",
            f"Convergence passed: {converged}; attachment sensitivity below 2%: {attachment_ok}; statistical precision passed: {precise}.",
            "", "These are signed, input-equivalent charges; no DCB209 voltage response is assumed.",
            "The readout is in ideal ohmic contact with the entire glass rear face.",
            "", "The square lattice, 50 µm copper, and copper-to-collection-surface gap convention are controlled model assumptions.",
            "", "No permittivity or per-gap normalization has been fitted. Attachment and numerical sensitivities must be examined before interpreting agreement with measurement."]
    (root / "study.md").write_text("\n".join(text)+"\n")
    return rows


def benchmark(args, base):
    rows = []
    for gap in [.1, 1., 2.]:
        for thickness, eps in [(0., 8.), (.8, 4.), (.8, 8.), (.8, 12.), (.8, 1000.)]:
            c = copy.deepcopy(base); c["geometry"]["induction_gap_mm"] = gap
            c["glass_signal"].update(glass_thickness_mm=thickness, glass_epsilon_r=eps)
            job = run(args.binary, args.out, c, "planar")
            r = json.loads((job/"planar.json").read_text())
            r.update(gap_mm=gap, thickness_mm=thickness, epsilon=eps, **planar(gap, thickness, eps, base["glass_signal"].get("glass_resistivity_ohm_cm", 1e10), 10000))
            rows.append(r)
    (args.out / "benchmark.json").write_text(json.dumps(rows, indent=2)+"\n")
    if any(r["relative_error"] > .01 or abs(r["rear_value"]-1) > .01 or
           r.get("trajectory_relative_error", math.inf) > .01 or
           r.get("growth_balance_residual", math.inf) > 1e-10 or
           r["conservative_relative_bound"] > .01 for r in rows):
        raise RuntimeError("Planar/contact/relaxation benchmark failed")


def contact(args, base):
    """Actual perforated geometry: reject far-copy weighting approximations."""
    probe = args.out / "contact_probe"
    probe.mkdir(exist_ok=True)
    (probe/"input_config.json").write_text(json.dumps(base))
    g = base["geometry"]
    z_front = -(g["plate_thickness_um"]/2+g["copper_thickness_um"])*1e-4-g["induction_gap_mm"]*.1
    z_drift = (g["plate_thickness_um"]/2+g["copper_thickness_um"])*1e-4+g["drift_gap_mm"]*.1
    snapshots = probe/"charge_snapshots.csv"
    snapshots.write_text("seed,path,attachment,time_ns,species,charge_e,x_cm,y_cm,z_cm,status\n"
                         f"501,0,fixed,10000,electron,-1,0,0,{z_front},anode\n"
                         f"501,0,fixed,10000,primary_ion,1,0,0,{z_drift},drift\n")
    validate_snapshots(snapshots)
    for model in ["metal", "glass"]:
        c = copy.deepcopy(base); c["glass_signal"]["model"] = model
        folder = run(args.binary, args.out, c, "replay", snapshots)
        checks = json.loads((folder/"weighting_checks.json").read_text())
        if abs(checks["rear_weighting_potential"]-1) > .01 or checks["max_partition_residual"] > .01:
            raise RuntimeError("THGEM full-face contact integration check failed")


def study(args, base):
    index_file = args.out / "index.json"
    index = json.loads(index_file.read_text()) if index_file.exists() else []
    pilot = args.command == "pilot"
    for gap in ([.1, 2.] if pilot else GAPS):
        for field in ([2.] if pilot else FIELDS):
            variants = ["baseline"] + (["refined"] if args.convergence and gap in [.1, 2.] and field == 2 else [])
            for variant in variants:
                counts = [args.paths] if pilot else [500, 1000, 2000]
                for count in counts:
                    for seed in ([501] if pilot else [501, 502]):
                        c = copy.deepcopy(base)
                        c["geometry"]["induction_gap_mm"] = gap
                        c["fields"]["e_induction_kvcm"] = field
                        c["simulation"].update(n_events=count, random_seed=seed)
                        if variant == "refined":
                            c["geometry"].update(target_element_size_um=25, min_elements=5, max_elements=20)
                            c["simulation"].update(mc_step_um=2, ion_max_step_um=2.5, mc_ion_samples=64)
                        transport = run(args.binary, args.out, c, "export", gas_source=args.gas_source)
                        snapshot = transport / "charge_snapshots.csv"
                        validate_snapshots(snapshot)
                        c["glass_signal"]["model"] = "metal"
                        metal = run(args.binary, args.out, c, "replay", snapshot)
                        for eps in ([8.] if pilot else EPSILONS):
                            c["glass_signal"].update(model="glass", glass_epsilon_r=eps)
                            glass = run(args.binary, args.out, c, "replay", snapshot)
                            index = [r for r in index if (r["gap"], r["field"], r["epsilon"], r["seed"], r.get("variant", "baseline")) != (gap, field, eps, seed, variant)]
                            index.append(dict(gap=gap, field=field, epsilon=eps, seed=seed, variant=variant,
                                              paths=count, snapshots=str(snapshot), metal=str(metal), glass=str(glass),
                                              thickness_mm=c["glass_signal"].get("glass_thickness_mm", .8),
                                              rho_ohm_cm=c["glass_signal"].get("glass_resistivity_ohm_cm", 1e10)))
                            index_file.write_text(json.dumps(index, indent=2)+"\n")
                    rows = analyse(args.out)
                    subset = [r for r in rows if r["gap_mm"] == gap and r["field_kvcm"] == field and r["time_ns"] == 10000 and r["variant"] == variant]
                    if all(r["valid"] and r["F_hi"]-r["F_lo"] <= .05 for r in subset):
                        break
                    if any(not r["valid"] for r in subset):
                        raise RuntimeError("Readout validity gate failed; inspect summary.csv before increasing statistics")


def main():
    global RUN_BINARY_SHA
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["benchmark", "contact", "pilot", "sweep", "analyse"])
    p.add_argument("--binary", type=Path, default=REPO/"build/thgem_sim")
    p.add_argument("--config", type=Path, default=REPO/"config/glass_signal.json")
    p.add_argument("--out", type=Path, default=REPO/"results/glass_signal/study")
    p.add_argument("--gas-source", type=Path)
    p.add_argument("--paths", type=int, default=4, help="pilot paths only; production uses 500/1000/2000")
    p.add_argument("--convergence", action="store_true", help="run the prescribed refined extreme-gap cases")
    args = p.parse_args()
    args.binary = args.binary.resolve(); args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=True)
    RUN_BINARY_SHA = sha(args.binary)
    (args.out / "status.json").write_text(json.dumps(dict(pid=os.getpid(), state="waiting_for_solver_lock",
                                                          command=args.command), indent=2)+"\n")
    with Path("/tmp/thgem-glass-nebem.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        base = json.loads(args.config.read_text())
        try:
            if args.command == "benchmark": benchmark(args, base)
            elif args.command == "contact": contact(args, base)
            elif args.command == "analyse": analyse(args.out)
            else: study(args, base)
        except BaseException as error:
            (args.out / "status.json").write_text(json.dumps(dict(pid=os.getpid(), state="failed_or_interrupted", message=str(error)), indent=2)+"\n")
            raise
        (args.out / "status.json").write_text(json.dumps(dict(pid=os.getpid(), state="complete", command=args.command), indent=2)+"\n")


if __name__ == "__main__":
    main()
