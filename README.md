# THGEM Detector Simulation

A [Garfield++](https://garfieldpp.web.cern.ch/) simulation of a **THGEM** (Thick Gas Electron
Multiplier) — a dielectric foil, copper-clad on both faces, pierced by a periodic array of drilled
holes. Primary electrons released in the drift gap are funnelled into a hole, multiplied in its
high field, and collected on an anode pad across the induction gap.

The project ships a C++ simulation binary and a PyQt5 desktop GUI that share one JSON configuration
schema. It is a port of the sibling [tgc-garfield](https://github.com/lmoleri/tgc-garfield) (Thin
Gap Chamber) project: the gas, avalanche, signal, track and I/O machinery is shared, while the
field engine was rebuilt — a wire chamber has an analytic field, a hole multiplier does not.

> **Status:** the field solver and the GUI work and are verified. A **multiplying avalanche run
> currently hangs** — see [Known issues](#known-issues) before using this for physics.

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
   `GeometrySimple`), tiled with mirror periodicity in x and y.
2. Direct neBEM lookups are far too slow to drive an avalanche, so the solved field is **sampled
   once onto a `ComponentGrid`** (fast trilinear interpolation) and **cached to disk, keyed by the
   geometry and field settings** (`thgem_field_*.txt`). Re-running an unchanged geometry reloads the
   field in ~0.1 s instead of re-solving.
3. The sampler writes an **in-solid flag** per node, so `ComponentGrid::GetMedium` returns `null`
   inside the copper and dielectric and electrons are absorbed on contact. Without this a
   `ComponentGrid` has no material information and charges would drift straight through metal.
4. The anode's Shockley–Ramo weighting field is supplied analytically by a `ComponentUser`
   (parallel-plate model over the induction gap, screened above the bottom copper) rather than a
   second neBEM solve.

The solved field is also dumped to the run's ROOT file (`field/`) as an x–z slice through the hole
centre plus an on-axis profile, which is what the GUI's **E-Field** tab renders.

## Layout

```
├── src/thgem_sim.cc        simulation binary (C++20)
├── gui/app.py              PyQt5 desktop GUI
├── config/
│   ├── default_thgem.json  baseline configuration
│   └── smoke_thgem.json    fast, coarse-mesh smoke test (used by CTest)
├── third_party/nlohmann/   vendored single-header JSON library
└── CMakeLists.txt
```

`*.gas` is a cached Magboltz transport table; one is committed so a fresh clone can run the default
configuration without an hours-long regeneration. Build output, `results/`, `neBEMOut/` and the
sampled-field cache are generated and gitignored.

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
Summary / Plots / Waveforms / Integrals / 3D-Tracks / E-Field / Magboltz tabs.

## Configuration

| Section | Keys |
|---|---|
| `geometry` | `hole_diameter_um`, `hole_pitch_um`, `plate_thickness_um`, `copper_thickness_um`, `rim_um` (0 only), `drift_gap_mm`, `induction_gap_mm`, `dielectric_material` (`fr4`/`kapton`), plus neBEM mesh + transport-grid controls (`target_element_size_um`, `grid_nx`, `grid_nz`, `periodic_copies`, `hole_sectors`, `min_elements`, `max_elements`) |
| `fields` | `e_drift_kvcm`, `delta_v_thgem_V`, `e_induction_kvcm` |
| `source` | `energy_keV`, `source_distances_mm` (height above the top copper; `null` = random over the drift gap), `x_positions_cm` (`null` = random over the cell; a fixed `x` pins `y = 0`, so `x = 0` is the hole axis) |
| `gas` | Magboltz mixture, temperature, pressure, Penning, field grid |
| `simulation` | `n_events`, `max_avalanche_size`, `time_window_ns`, `time_step_ns`, `enable_ion_drift`, `store_drift_lines`, `ion_max_step_um`, `random_seed` |

Only the anode is read out. For compatibility with the shared TGC ROOT schema the `cathode`,
`cathode_top` and amplifier branches still exist but are written as zeros.

## Known issues

**Single-electron transport through the hole hangs.** A run that actually sends an electron into
the hole does not terminate in reasonable time.

- Reproducible with `max_avalanche_size: 1` (multiplication fully disabled), `x_positions_cm: [0.0]`
  (hole axis), `delta_v_thgem_V: 700`, and even a 30 ns `time_window_ns`: a single electron runs for
  minutes.
- It is therefore **not** the avalanche multiplication, and **not** the avalanche size limit.
- It is **not** a numerical field spike: the sampled grid's maximum is 22.7 kV/cm (physical, at the
  hole rim), with no outliers.
- Runs where the electron misses the hole and is absorbed on the top copper complete normally, which
  is why low/no-gain configurations finish.

Everything else is verified working: the neBEM solve (potential 0 V at the anode → −1745 V at the
drift cathode, field funnelling into the hole), the geometry-keyed field cache, and the GUI
(construction, config round-trip, derived-voltage readout, and every result-tab loader against real
output).

Suggested next debugging step: instrument the transport to dump one electron's energy, position and
status per step, then A/B the *same* electron on the neBEM-direct field versus the `ComponentGrid`,
and with mirror periodicity enabled and disabled, to isolate whether the interpolated periodic field
is the cause.
