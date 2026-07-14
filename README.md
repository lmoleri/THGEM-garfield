# THGEM Detector Simulation

A [Garfield++](https://garfieldpp.web.cern.ch/) simulation of a **THGEM** (Thick Gas Electron
Multiplier) — a dielectric foil, copper-clad on both faces, pierced by a periodic array of drilled
holes. Primary electrons released in the drift gap are funnelled into a hole, multiplied in its
high field, and collected on an anode pad across the induction gap.

The project ships a C++ simulation binary and a PyQt5 desktop GUI that share one JSON configuration
schema. It is a port of the sibling [tgc-garfield](https://github.com/lmoleri/tgc-garfield) (Thin
Gap Chamber) project: the gas, avalanche, signal, track and I/O machinery is shared, while the
field engine was rebuilt — a wire chamber has an analytic field, a hole multiplier does not.

> **Status:** working and verified end-to-end — field solve, multiplying avalanche (realistic
> gain), bounded ion drift, and the GUI. A ΔV≈1400 V run on the hole axis multiplies to ⟨~10³⟩
> electrons and induces a non-zero anode charge in a few seconds. The GUI's **3D Tracks** view
> renders the detector geometry and the full avalanche — the primary plus the secondary electrons'
> transport through the hole.

---

## Detector model

```
   z              ┌──────────────────────────────────┐  drift cathode   (V_drift)
   ↑                          drift gap (3 mm)
   │              ▓▓▓▓▓▓▓▓▓▓▓▓▓        ▓▓▓▓▓▓▓▓▓▓▓▓▓   top copper      (V_topCu)
   │  z=0 ──────  ███████████████  ⌀   ███████████████  dielectric foil (FR4, 400 µm)
   │              ▓▓▓▓▓▓▓▓▓▓▓▓▓        ▓▓▓▓▓▓▓▓▓▓▓▓▓   bottom copper   (V_botCu)
   │                        induction gap (2 mm)
   │              └──────────────────────────────────┘  anode pad       (0 V, readout)
                   |←────────── pitch 800 µm ────────→|
```

*(Dimensions above are the `standard` config; the shipped `default_thgem.json` uses a 5 mm drift gap
and 1000 µm pitch.)*

Electrons drift along **−z** toward the most-positive anode. The configuration is given in physics
terms (`e_drift_kvcm`, `delta_v_thgem_V`, `e_induction_kvcm`) and the four electrode potentials are
derived with the anode as the 0 V reference:

```
V_anode = 0
V_botCu = −E_ind   · d_ind
V_topCu = V_botCu  − ΔV_THGEM
V_drift = V_topCu  − E_drift · d_drift
```

## How the field is computed

A THGEM hole has no closed-form field, and no external FEM tool (gmsh/Elmer/ANSYS) is required
here. Instead:

1. **`ComponentNeBem3d`** — Garfield's native boundary-element solver — solves a *single unit cell*
   (`SolidBox` drift cathode + anode, `SolidHole` top-Cu / dielectric / bottom-Cu inside a
   `GeometrySimple`), tiled with mirror periodicity in x and y. The drift cathode and anode are
   one-cell patches that only *approximate* an infinite plane once tiled, so **`periodic_copies`
   must be large enough** (≥7 for the standard geometry, ≥9 for the larger default) — with too few
   copies the truncated periodic sum leaves the on-axis drift field *reversed* mid-gap, which traps
   drifting charges. `neBEM`'s `AddPlaneZ` is **not** a substitute: it does not enforce a plane
   boundary condition under a periodic solve.
2. Direct neBEM lookups are far too slow to drive an avalanche, so the solved field is **sampled
   once onto a `ComponentGrid`** (fast trilinear interpolation) and **cached to disk, keyed by the
   geometry and field settings** (`thgem_field_*.txt`). Re-running an unchanged geometry reloads the
   field in ~0.1 s instead of re-solving.
3. The sampler writes an **in-solid flag** per node, so `ComponentGrid::GetMedium` returns `null`
   inside the copper and dielectric and electrons are absorbed on contact. Without this a
   `ComponentGrid` has no material information and charges would drift straight through metal.
4. The anode's Shockley–Ramo weighting field used for the **signal** is supplied analytically by a
   `ComponentUser` (parallel-plate model over the induction gap, screened above the bottom copper)
   rather than a second neBEM solve. neBEM *also* solves the electrode's **true** weighting field
   (the anode solid is labelled, so 1 V is placed on it and 0 V on all others); that map is dumped
   for the Weighting Field tab and is what validates the analytic stand-in — see below.

The solved field is also dumped to the run's ROOT file (`field/`) as an x–z slice through the hole
centre plus an on-axis profile, which is what the GUI's **E-Field** tab renders.

## E-Field and Weighting Field views

Both tabs draw into an **interactive ROOT canvas** — right-click inside it to zoom, rescale the axes,
or save — showing an x–z colour map through the hole centre (with the copper/hole overlay) next to
the on-hole-axis profile. Each has a Quantity and a Palette selector.

- **E-Field** — `|E|` or the potential, from the neBEM solve.
- **Weighting Field** — the anode's **true** Shockley–Ramo weighting potential `W` (or `|E_w|`),
  solved by neBEM. It is cached separately from the transport field and keyed on the **geometry
  only** — a weighting field does not depend on the applied voltages, so a whole ΔV scan reuses a
  single solve. (Because a cached transport field means neBEM is never initialised, the weighting map
  needs its own cache; the first run on a given geometry solves once to build it.)

The weighting map is the honest check on the analytic stand-in used for the signal. The stand-in
assumes the bottom copper screens perfectly (`W = 0` above it), whereas the hole is an open window:
neBEM gives `W ≲ 3 %` just above the bottom copper and ~1 % inside the hole. An avalanche electron
born in the hole and collected at the anode therefore induces `ΔW ≈ 0.99` instead of `1.00` — a **~1 %
error on `Q_anode`**, so the parallel-plate stand-in is a good approximation and the signal stands.

## 3D Tracks view

The GUI's **3D Tracks** tab renders one event in a ROOT 3D canvas, in true z-scale:

- **Geometry** — an N×N block of hole cylinders (orange), the copper/dielectric plate faces (grey),
  and the drift (cyan) and anode (red) equipotential planes.
- **Charges** — the primary electron's drift line (blue); the avalanche both as orange birth-point
  markers *and* as semi-transparent orange **transport trajectories** of the secondary electrons;
  and, when ion drift is enabled, the ion paths colour-coded by destination — green (→ drift
  cathode), magenta (→ anode), grey (absorbed).
- **Controls** — Distance / X-pos / Event selectors; orientation presets (`Gap XY`, `Top XZ`,
  `Side YZ`, `3D`) with zoom and pan; a **Holes** spinbox (1–15, default 4 → a 4×4 block); and an
  **Aval paths** spinbox (0–200, default 50) capping how many avalanche trajectories are drawn
  (0 hides them).

The curved primary line and the avalanche trajectories require **`store_drift_lines`** (on in the
default config); with it off, the primary is a straight start→end segment and only the birth-point
cloud is shown. The avalanche trajectories are stored subsampled and capped (≤200 per event), so the
ROOT file stays small.

## Layout

```
├── src/thgem_sim.cc        simulation binary (C++20)
├── gui/app.py              PyQt5 desktop GUI
├── config/
│   ├── default_thgem.json  baseline configuration
│   └── smoke_thgem.json    fast, coarse-mesh smoke test (used by CTest)
├── gas/                    Magboltz gas tables (*.gas) + *_props.csv sidecars
├── field_cache/            sampled neBEM field caches (generated, gitignored)
├── third_party/nlohmann/   vendored single-header JSON library
└── CMakeLists.txt
```

`gas/*.gas` is a cached Magboltz transport table (a function of the gas + field grid only, not the
detector geometry); one is committed so a fresh clone can run the default configuration without an
hours-long regeneration. The `_props.csv` sidecar, `field_cache/`, build output, `results/` and
`neBEMOut/` are generated and gitignored. These data folders live next to wherever the binary is
run from — the GUI runs it from the project root, so they appear here.

## Build

ROOT's `FindVdt.cmake` does not locate Vdt automatically here, and sourcing `setupGarfield.sh` does
not propagate into CMake, so both paths are passed explicitly:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DVDT_INCLUDE_DIR=/path/to/miniforge3/include \
  -DVDT_LIBRARY=/path/to/miniforge3/lib/libvdt.dylib \
  -DCMAKE_PREFIX_PATH="/path/to/Garfield++/local/garfield;/path/to/miniforge3"
cmake --build build -j4
```

## Run

Ion mobility tables and the Heed database are found through the environment:

```bash
export GARFIELD_INSTALL=/path/to/Garfield++/local/garfield
export HEED_DATABASE=$GARFIELD_INSTALL/share/Heed/database

./build/thgem_sim --config config/default_thgem.json --out results
python3 gui/app.py
```

`thgem_sim` writes `thgem_sim.root`, `summary.csv` and a resolved `run_config.json` into a
timestamped subdirectory of `--out`. The GUI runs the same binary and loads those outputs into its
Summary / Plots / Waveforms / Integrals / [3D Tracks](#3d-tracks-view) / E-Field / Magboltz tabs.

Each run also prints a **primary-electron fate** line per source height, e.g.

```
  [fate] multiplied 25/30 events; primary endpoint: {attached @ in-hole: 6} {outside time window @ below-plate: 24}
```

`multiplied N/M` is how many events produced an avalanche; the `{status @ zone}` tally shows where
and why each primary ended (`zone` ∈ `in-hole` / `on-plate` / `in-gap` / `below-plate`). It is a
collection-efficiency and attachment readout: at the default ΔV≈1400 V about **85 %** of electrons
multiply, and the rest either **attach** in the hole (CO₂) or are collected on the copper — so a
single-event run is statistical and may show no avalanche. That is expected physics, not a bug.

## Configuration

| Section | Keys |
|---|---|
| `geometry` | `hole_diameter_um`, `hole_pitch_um`, `plate_thickness_um`, `copper_thickness_um`, `rim_um` (0 only), `drift_gap_mm`, `induction_gap_mm`, `dielectric_material` (`fr4`/`kapton`), plus neBEM mesh + transport-grid controls (`target_element_size_um`, `grid_nx`, `grid_nz`, `periodic_copies`, `hole_sectors`, `min_elements`, `max_elements`) |
| `fields` | `e_drift_kvcm`, `delta_v_thgem_V`, `e_induction_kvcm` |
| `source` | `energy_keV`, `source_distances_mm` (height above the top copper; `null` = random over the drift gap), `x_positions_cm` (`null` = random over the cell; a fixed `x` pins `y = 0`, so `x = 0` is the hole axis) |
| `gas` | Magboltz mixture, temperature, pressure, Penning, field grid |
| `simulation` | `n_events`, `max_avalanche_size`, `time_window_ns`, `time_step_ns`, `enable_ion_drift` (default off), `store_drift_lines`, `ion_max_step_um`, `ion_time_window_ns`, `max_ions_drifted`, `random_seed` |

Only the anode is read out. For compatibility with the shared TGC ROOT schema the `cathode`,
`cathode_top` and amplifier branches still exist but are written as zeros.

## Transport bounds (why runs terminate)

Two independent safeguards keep a run from hanging or exhausting memory, because a charge can stall
at a field feature and neither drifter is otherwise bounded from outside:

- **Electron avalanche** — `AvalancheMicroscopic::SetTimeWindow(0, time_window_ns)` bounds transport
  in time. (`Sensor::SetTimeWindow` only bins the induced signal; it does not stop transport.) A
  charge still in flight at the window's end terminates as `StatusOutsideTimeWindow`.
- **Ion drift** — uses **`AvalancheMC`** (Monte-Carlo, distance-stepped), *not* `DriftLineRKF`. The
  RKF integrator has no step-count or time bound, so a single ion looping near a field stagnation
  point runs forever with unbounded path storage (the earlier hang/OOM). `AvalancheMC` steps by a
  fixed distance (bounding a normal ion by geometry) and honours `ion_time_window_ns` (default 1 ms)
  as the backstop for a trapped ion. Ion drift is **off by default**: ions induce ~nothing on the
  anode, so the signal is unchanged, and they are ~1000× slower than electrons — enable it for the
  3D ion-path view or ion-backflow studies.

Verified end-to-end: the neBEM solve (0 V at the anode → negative at the drift cathode, field
funnelling into the hole) with no reversed drift-gap pocket at the shipped `periodic_copies`; the
geometry-keyed field cache; a realistic multiplying avalanche (⟨gain⟩ ~10³ at ΔV≈1400 V) that
completes in seconds with bounded memory; the CTest smoke run; and the GUI (construction, config
round-trip, derived-voltage readout, and every result-tab loader against real output).
