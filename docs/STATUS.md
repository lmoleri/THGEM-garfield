# THGEM study status

Two parts: a short **current state** (what is running, what is waiting, provenance problems), rewritten whenever it changes, and the **log** (newest first), which only grows. Each log entry records the binary, seeds and data paths of a run, so a result can be traced to code.

The study itself (question, model, results against the lab data, what is ruled out, open questions) is written up once in [`anode_charge_fraction.md`](anode_charge_fraction.md). Read that first; this file does not repeat it.

Labels: *lab* = measured on the detector; *sim* = from a simulation output; *inferred* = a reading of those numbers; *assumed* = an input not yet confirmed. Simulation intervals are 68 % bootstrap; weighted-path results are heavy-tailed, so quote the ESS. **Log entries before 2026-11-10 use Cu 50 µm and take the nominal gap as the gas gap from the copper;** their numbers are superseded by the 2026-11-10..11 entry and are kept as a record only.

---

## Current state (updated 2026-11-11)

**Headline (inferred).** The glass weighting factor gives a suppression of the right kind, but the full model does not reproduce R: the simulated copper baseline falls with gap, so R_glass is 0.1–0.25 below the data at 0.2–1.0 mm, and the 0.1 mm point is a clear miss. Details: [`anode_charge_fraction.md`](anode_charge_fraction.md) §4.

**Running.** Nothing.

**Parked by Luca.** Hexagonal lattice (2026-11-08): proxy prepared, not launched, in `results/hex_proxy_p093/`; true hex needs a mirror-symmetric p/2 × (√3/2)p cell. Gain-consistent charged-FR4 avalanche (2026-11-10). Further work on glass surface charging (2026-11-11).

**Not available.** A full glass production does not exist: `results/glass_signal/production_v3` was stopped 102 s after its launch on 2026-11-05.

**Open inputs from Luca.**
1. R at E_ind 1.5 kV/cm for 0.5 and 1.0 mm (the quoted 0.855 / 0.80 may be the E_ind 2.0 series), and absolute anode charges.
2. Glass ε_r and rear-contact type (ρ = 1e10 Ω·cm given 2026-11-11). Is there any bare-copper-anode measurement?
3. Real copper corner radius (Cu etched from 150 µm).
4. Size of the irradiated spot (collimation), and whether the preamp calibration was done with the detector connected at each gap.

**Provenance problems to fix.**
- `results/copper_baseline*` and `results/charged_equilibrium` use `../THGEM_corner/build/thgem_sim` (built 2026-10-29). That source tree is not under git, and its `botCornerRoundUm` option is in no commit.
- Branch `codex/glass-signal-10us` is not pushed (its commits are on `main`).
- Drivers live only under the gitignored `results/`: `charging_08/analysis/charging_driver_v2.py`, `thick_plate/gastools/merge_text.py`, `copper_baseline/{job.sh,analyse.py}`, `copper_baseline_gasgap/pool_cu90.py`, `glass_signal/quicktest_eind1.5/chunk_job.sh`, `glass_signal/quicktest_gasgap/summary_cu90.py`, `charged_equilibrium/{equilibrium_driver.py,solve_v2.py}`.
- The dense n110 Ar/CO₂ 93:7 gas table used since 2026-11-01 is not in `gas/`.

---

## Log

Template:

```
### YYYY-MM-DD — short title
Question:
Setup: config …, binary <commit or path, dirty?>, paths/seeds
Result (measured):
Reading (inferred):
Caveats:
Data: results/…
```

### 2026-11-11 — Glass resistivity and glass surface charging at 0.1 mm
Fact (Luca): glass volume resistivity ρ = 1e10 Ω·cm.
Estimate (no simulation): the mean potential of the glass surface is J·ρ·b (b = 0.8 mm). With Q_anode ≈ 0.41 pC/event (lab R × Q_top at 0.1 mm) at 10 Hz, it is ≈ 0.3 V for a 1 mm² irradiated spot and < 1 mV over 4 cm², against 15 V across the 10 µm gap. The relaxation time of a charge facing the 10 µm gap is ρ ε0 (ε_r + b/d) ≈ 80 ms at ε_r 7 (the 6 ms first quoted, ε0 ε_r ρ, ignores the gap); the mean potential does not depend on it.
Reading (inferred): glass surface charging cannot explain the 0.1 mm miss unless the irradiated spot is ≪ 1 mm². Luca asked to stop work on this hypothesis.

### 2026-11-10 — Readout impedance (anode charge diverted to the grounded bottom through C_AB)
Question (Luca): is part of the anode signal lost because the anode preamp's input impedance is high compared with that of the anode–bottom capacitance C_AB?
Method (estimate, no simulation): capacitive divider at the anode node, Q_CSA / Q = C_in,eff / (C_in,eff + C_AB). C_in,eff ≈ 1.84 nF (DCB209A: 2 nF HV coupling in series with 100 nF and A0·Cf ≈ 30 nF); the 40 MΩ bias path does not compete. C_AB = ε0 A (open fraction 0.77) / (d_gas + b/ε_r), A = 4 cm², fringing ignored (±30 % at ≥ 0.5 mm). Both impedances are capacitive, so the ratio is frequency-independent.
Result: first done with metal gap d − 50 µm (Cu 50 µm), then redone here for the real gas gap d − 90 µm. For glass ε_r 6–8, C_AB = 19–25 / 11–13 / 5.0–5.3 / 2.6–2.7 pF at d = 0.1 / 0.2 / 0.5 / 1.0 mm, a loss of 1.0–1.3 / 0.6–0.7 / 0.3 / 0.15 %. A copper anode would see 273 pF and 13 % at 0.1 mm (1.3 % at 0.2 mm), but the measurements used glass. The data need ~40 % at 0.1 mm, i.e. C_in,eff ≈ 30–40 pF, ~50× below the manual.
Reading (inferred): ruled out within the manual values. The loss has the same functional form as the glass factor, so the gap shape cannot separate them, and a bottom readout cannot either. Decisive test: preamp test pulse into the anode channel with the detector connected, at 0.1 mm vs ≥ 1 mm.
Caveats: preamp values from the manual, not measured; cable capacitance and any input protection unknown; if the calibration was done in situ at each gap, an impedance effect would already be calibrated out.
Data: project files `readout_impedance/` (estimate scripts).

### 2026-11-10..11 — Real geometry: Cu 90 µm, gas gap = nominal − 90 µm, E_ind × nominal/real, ΔV 1.9 kV
Facts (Luca, 2026-11-10): the spacers reference the FR4 (THGEM FR4 to the glass), not the copper; the copper is 90 µm on both faces; the induction voltage is set as E_ind × d_nominal. So the gas gap is d − 90 µm and the gas field is E_ind × d / (d − 0.09 mm). **All earlier log entries used Cu 50 µm and took d as the gas gap from the Cu surface at E_ind as set.** Luca's top_charge.pdf gives the measured top charge (0.80 / 0.83 / 0.30 / 0.24 pC at 0.1 / 0.2 / 0.5 / 1.0 mm, E_ind 1.5), so the simulated gain at 1.9 kV is ~2× high, not 10–30×.
Setup: ΔV 1.9 kV, Ed 1 kV/cm, Ar/CO₂ 93:7 (n110 table), FR4 0.8 mm, Cu 90 µm, hole 0.5 mm, rim 100 µm, square pitch 1 mm, production mesh (100 µm, 3–5 per primitive), raw-neBEM weighted mean avalanches. Gas gaps 0.010 / 0.110 / 0.410 / 0.910 mm at 15 / 2.727 / 1.829 / 1.648 kV/cm. Copper baseline: `THGEM_corner` binary (unversioned), recipe of `copper_baseline_gainmatched`, 3 × 600 paths per gap, seeds 979–981 / 970–972 / 973–975 / 976–978. Glass quick test: binary `fb42296` (`quicktest_gasgap/bin`, provenance copied), recipe of `quicktest_eind1.5` (5 × 100-path exports, paired copper + glass ε_r 4–12 replays, read at 10 µs, mobile attachment), seeds 661–665 / 671–675 / 681–685 / 691–695; snapshot residuals ≤ 5e-15. 10 µm mesh check (`results/gap10um_meshcheck/`): production mesh (2021 elements) vs 20 µm / 3–40 (13 938 elements, 4.3 h, swapped the Mac) differ ≤ 3.3 % in the gap field; under the copper both give 15 kV/cm within 1–3 %.
Result (measured), copper baseline (anode fraction excl. attachment, 68 % bootstrap):

| Nominal d (gas gap, field) | Anode fraction | ESS | Mean / median gain | Lowest 100 µm FR4 wall | Wall above | Bottom Cu |
|---|---|---|---|---|---|---|
| 0.1 mm (10 µm, 15 kV/cm) | 0.984 [0.981, 0.986] | 556 | 1.34e5 / 7.8e4 | 0.012 | 0.004 | 0.001 |
| 0.2 mm (110 µm, 2.73 kV/cm) | 0.838 [0.820, 0.857] | 455 | 3.6e4 / 1.8e4 | 0.080 | 0.030 | 0.048 |
| 0.5 mm (410 µm, 1.83 kV/cm) | 0.656 [0.632, 0.681] | 478 | 2.4e4 / 1.3e4 | 0.130 | 0.042 | 0.172 |
| 1.0 mm (910 µm, 1.65 kV/cm) | 0.568 [0.546, 0.592] | 488 | 2.2e4 / 1.2e4 | 0.135 | 0.043 | 0.254 |

Result (measured), glass quick test against data (per-event charge × 227 primaries, 10 µs; glass ε_r 6–8; measured in brackets; R_Cu = copper-anode replay):

| Nominal d | Top charge [pC] | R_glass | R_Cu | F |
|---|---|---|---|---|
| 0.1 mm | 4.44–4.47 (0.80) | 0.29–0.32 (0.51) | 1.05 | 0.27–0.31 |
| 0.2 mm | 1.42 (0.83) | 0.49–0.55 (0.64) | 0.92 | 0.53–0.60 |
| 0.5 mm | 0.77 (0.30) | 0.61–0.65 (0.855) | 0.80 | 0.77–0.81 |
| 1.0 mm | 0.68 (0.24) | 0.59–0.60 (0.80) | 0.67 | 0.88–0.90 |

Bootstrap 68 %: charges ±6–10 %, R ±5 % (±1 % at 0.1 mm), F ±0.002 (paired). Glass bottom charge (ε_r 6–8): 3.2–3.3 / 0.68–0.77 / 0.29–0.32 / 0.29–0.30 pC.
Reading (inferred):
- (a) The copper baseline still falls with gap, 0.98 → 0.84 → 0.66 → 0.57, and the loss moves increasingly onto the bottom-Cu underside (0.001 → 0.25); the real geometry does not remove it.
- (b) At 0.2–1.0 mm the top-charge shape is now data-like (steep rise below 0.5 mm, flat above; 0.2/0.5 ratio 1.86 against 2.8 measured, 1.25 with the old geometry) but 1.7–2.8× high; R_glass is ~0.15–0.2 low throughout, from the falling copper baseline.
- (c) 0.1 mm is a clear miss: gain 1.3e5 (the field stays ~16 kV/cm from the hole into the 10 µm gap), top 4.5 against 0.8 pC, R 0.29–0.32 against 0.51. The real 0.1 mm gap is not a clean, uncharged 10 µm gap. Candidates: flatness / partial contact of copper and glass; glass surface charging (only 15 V across the gap; ~1 pC per event on ~1 mm² of glass over a ~0.9 pF gap is ≈ 1 V per event, which accumulates if τ = ε0 ε_r ρ is long against the local event spacing, e.g. τ ≳ 0.1 s, ρ ≳ 1e11 Ω·cm); discharges or other gain limits.
Caveats: square lattice (real is hex); uncharged FR4 and glass; nominal glass ε_r / ρ; weighted paths heavy-tailed (ESS 74–189 for the glass top charge); 0.1 mm assumes a uniform 10 µm gap.
Data: `results/copper_baseline_gasgap/` (`runs/dV1900_cu90_*`, `pool_cu90.py`, `summary_cu90.csv`; Cu 50 µm starts in `stopped_cu50/`), `results/glass_signal/quicktest_gasgap/` (`chunks/`, `summary_cu90.py`, `summary_cu90.csv`; Cu 50 µm starts in `stopped_cu50/`), `results/gap10um_meshcheck/`.

### 2026-11-09 — Fully charged FR4 limit (zero normal field on the insulator), 0.5 mm, copper anode
Question (Luca): does the falling copper baseline come from electrons ending on uncharged FR4, which charging-up equilibrium would prevent?
Check of existing data (measured): in the gain-matched baseline only about half the extra loss from 0.1 to 0.5 mm lands on FR4 (FR4 wall 0.116 → 0.210, bottom-Cu underside 0.001 → 0.104). Even a perfect FR4 shield bounds the anode fraction at 1 − Cu loss = 0.999 / 0.966 / 0.896, so it would still fall.
Old charging run (`results/charging_08`, reread): the lowest wall zone kept collecting 0.10–0.20 net e⁻ per avalanche e⁻ even at σ = −4.4 nC/cm²; the wall field only scaled down with the hole field. Inferred cause: a uniformly charged band on a cylinder makes almost no radial field inside (Gauss), so only dσ/dz bends drift lines off the wall. The 6-zone run could not test the hypothesis.
Method: finer mesh (50 µm wall elements, 3207 elements), 12 wall bands + 2 rim faces, one neBEM charged solve per zone (σ = 1 nC/cm²) → linear response of E·n at probes 10 µm off the FR4 (y = 0 raw-field slice) → least squares for E·n = 0. Binary: `THGEM_corner` (unversioned). Driver: `results/charged_equilibrium/equilibrium_driver.py`, re-fit `solve_v2.py`.
Result (measured):
- The unbounded fit needs ±1–2 µC/cm² with alternating signs (condition number 5e4). Its verification run failed (hole field 18 → 0.7 kV/cm; wall E·n 0.3–3 kV/cm against ~15 V/cm predicted). Cause, checked: neBEM maps the charges correctly (ReTriM.c InitChargingUp; zone totals 0.977× requested), but random deposit points leave 10–20 % per-element scatter, and the ill-conditioned fit amplifies it.
- A bounded re-fit from the same responses (ridge fallback; scipy is missing on the Mac) at max |σ| = 2 / 5 / 10 / 20 nC/cm²: lower-wall E·n 3.5–3.8 / 3.1–3.5 / 1.5–2.1 / 0.5–1.8 kV/cm (uncharged 4.0–4.2), on-axis hole field 0.86 / 0.74 / 0.33 / 0.39× uncharged. With the hole field held fixed, the fit cannot reduce E·n at all.
Reading (inferred): clearing the wall needs 10–20 nC/cm² and removes the gain. The measured gain at 1.9 kV is only ~10× below the uncharged simulation (hole field ~7 % lower), which allows at most the ~1–2 nC/cm² state, where wall E·n drops only 10–15 %. Within this model the real detector cannot be in the fully charged state, and charging cannot explain the falling copper baseline. Luca chose to stop here (2026-11-10); the gain-consistent charged avalanche test (ΔV 1.9 kV, scaled σ, gain ≈ 3e3) was not run.
Caveats: azimuthally uniform zones; square lattice (real is hex); "no field lines on FR4" is a proxy for dynamic equilibrium; no avalanche run in a charged field; ridge fits rather than true bounded fits; rim-face responses took 3.6 h each (cause not found). If part of the 10× gain gap comes from gas or Penning settings, the real charging is smaller still.
Data: `results/charged_equilibrium/` (0.5 mm responses, solution.json, solve_v2_scan.json; 0.1 / 0.2 mm uncharged bases with caches at 1770 V, no responses).

### 2026-11-08 — Glass-anode quick test: 1.0 mm point
Setup: as the 2026-11-05 quick test (E_ind 1.5 kV/cm, ΔV 1.9 kV, 5 mm drift, K = 32, paired copper / glass replay, ε_r 4–12), d = 1.0 mm, 5 × 100 paths, seeds 631–635. Binary: `fb42296`. Gates: conservation ≤ 2.8e-15, partition residual ≤ 6.5e-13.
Result (measured): R_copper = 0.681 [0.640, 0.727]; F = 0.837 / 0.885 / 0.911 / 0.927 / 0.938 at ε_r 4 / 6 / 8 / 10 / 12 (planar 0.833 / 0.882 / 0.909 / 0.926 / 0.938); R_glass = 0.570 / 0.602 / 0.620 / 0.631 / 0.639. Bottom/top: copper −0.355, glass ε_r 8 −0.414. ESS 163/500. F is the same at 5 / 10 / 20 µs and for fixed / mobile attachment.
Reading (inferred): at 1 mm the glass matters little (F ≈ 0.9) and the copper baseline dominates; R_glass ≈ 0.62 is well below the measured 0.80.
Data: `results/glass_signal/quicktest_eind1.5/` (chunks `E1.5_ig1.00_s63x`), `summary_E1.5_t10us.csv`, `bottom_channel_E1.5.csv`.

### 2026-11-06 — Gain-matched copper baseline
Question: is the copper-baseline fall an artefact of the simulated gain being ~10× above the measured one?
Setup: as the copper-baseline scan, ΔV 1.77 kV (probes at 1.60–1.80 kV: gain halves per 50 V), E_ind 1.5 kV/cm, d = 0.1 / 0.2 / 0.5 mm, 1800 paths per gap (1000-path job + 2 × 400). Binary: `THGEM_corner` (unversioned).
Result (measured): mean gain 4.5e3 / 3.1e3 / 2.6e3; anode fraction (excluding attachment) 0.882 [0.870, 0.894] / 0.799 [0.782, 0.816] / 0.686 [0.666, 0.706], against 0.899 / 0.758 / 0.644 at 1.9 kV. Bottom-Cu-underside loss halves (0.114 → 0.034 at 0.2 mm, 0.208 → 0.104 at 0.5 mm) while the lowest-100 µm-wall loss grows (0.107 → 0.129, 0.114 → 0.153). ESS ~600 per gap.
Reading (inferred): the fall persists at the measured gain; it is geometric.
Data: `results/copper_baseline_gainmatched/` (`pooled_summary.csv`)

### 2026-11-05 — Glass quick test: THGEM bottom signal
From the same replays: with glass the anode charge the glass removes reappears on the THGEM bottom electrode, bottom/top ≈ −0.43 to −0.50 at 0.1–0.2 mm (ε_r 6–8), against ≈ 0 (0.1 mm) and −0.21 / −0.26 (0.2 / 0.5 mm) for copper. The four channels sum to zero within 3e-14.
Data: `results/glass_signal/quicktest_eind1.5/bottom_channel_E1.5.csv`

### 2026-11-06 — Copper-anode baseline scan
Question: is the fall of the copper baseline with gap real, or small-sample noise?
Setup: fast weighted mode, 5 mm drift, E_ind 1.5 kV/cm (plus a field scan at 0.1 / 0.2 mm), 13 points × 1000 paths. Binary: `THGEM_corner` (unversioned).
Result (measured): anode fraction (excluding attachment) 0.90 / 0.87 / 0.85 / 0.83 / 0.76 / 0.76 / 0.64 at d = 0.1 / 0.125 / 0.15 / 0.175 / 0.2 / 0.3 / 0.5 mm. Losses: a constant 7–10 % on the lowest 100 µm of the hole wall, plus a bottom-Cu underside loss growing from 0.6 % to 19 %. At 0.2 mm the fraction rises from 0.78 to 0.88 for E_ind 1 → 3 kV/cm. Unweighted, it is flat at ~0.79 up to 0.3 mm.
Reading (inferred): the fall is real, and it is carried by the highest-gain avalanches. The earlier 0.95 → 0.69 jump was noise. The E_ind dependence conflicts with the field-independent data unless the glass dominates.
Data: `results/copper_baseline/`

### 2026-11-05 — Glass-anode quick test
Setup: E_ind 1.5 kV/cm, 500 paths per gap, charge inventory at 10 µs, paired copper and glass replay (ε_r 4–12). Binary: `fb42296`.
Result (measured): F at ε_r 8 = 0.59 / 0.70 / 0.84; at ε_r 6 = 0.52 / 0.64 / 0.80 (0.1 / 0.2 / 0.5 mm). R_copper = 1.03 / 0.82 / 0.78.
Caveats: ESS ~31/500 at 0.1 mm; ε_r assumed; one field; no mesh checks.
Data: `results/glass_signal/quicktest_eind1.5/`. Write-up: project library `thgem-review/glass_quicktest_2026-11-05.md`.

### 2026-11-05 — Glass-study duplicate-terminal fix
`fb42296`: TrackNormalizer removes only verified exact duplicate terminal points; CTest `glass_trajectory_regression`.

### 2026-11-04 — Glass anode confirmed
Luca confirmed the measurements used the resistive-glass anode, so all copper-anode comparisons (charging, corner, R) are the wrong reference for the data. The real drift gap is 5 mm with Ed 1 kV/cm.

### 2026-11-02..04 — Self-consistent wall charging (0.8 mm, copper anode)
Result: the hole wall charges as a dipole (upper wall +, lower wall −) with no equilibrium after 12 iterations; gain falls 250–900×. Extraction at the gain-matched state is ~0.71–0.85 (0.1 mm) and ~0.61–0.72 (0.5 mm). Reading: wall charging does not explain the small-gap suppression. Note: 1 mm drift gap.
Data: `results/charging_08/`

### 2026-11-01 — Real plate is 0.8 mm; production at 0.8 mm
Before this, every study used a 0.4 mm plate. At 0.8 mm the axial gain is ~4e3, which resolves the 80–300× gain mismatch. Production (n110 gas table, seed 501, 500 paths): extraction 0.79 / 0.80 / 0.62 / 0.63, a trend still opposite to the data. Note: 1 mm drift gap.
Data: `results/thick_plate/`, `results/gain_mismatch/`

### 2026-10-30 — Corner-rounding sweep (0.4 mm plate)
R = 0 / 10 / 25 / 45 µm. Only R45 gives flat extraction, and every R stays ~0.25–0.3 below the data. Code: unversioned `THGEM_corner`.
Data: `results/corner_rounding/`

### ≤ 2026-10-29 — 0.4 mm-plate investigation
See `extraction_ratio_investigation.md` §1–16 (historical): grid edge artifact, rim charging, mean-avalanche mode, ion collection, collected-charge ratio. Last commit on `main`: `cbd1178`.
