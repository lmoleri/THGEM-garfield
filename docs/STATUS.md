# THGEM study status

Living document. The **Current state** section is rewritten whenever it changes; the **Log** below only grows (newest first). Each log entry records what binary produced it, so a result can be traced to code.

Conventions: *measured* = a number from a simulation output; *inferred* = a reading of those numbers; *assumed* = an input not yet confirmed. Uncertainties are 68 % bootstrap unless stated; weighted-path results are heavy-tailed, so quote the ESS.

---

## Current state (updated 2026-11-06)

**Question.** The measured anode/THGEM-top charge ratio drops at small induction gaps: 0.51 / 0.64 / 0.855 / 0.80 at d = 0.1 / 0.2 / 0.5 / 1.0 mm.

**Detector as measured** (confirmed by Luca): 0.8 mm FR4 THGEM, Cu 50 µm per side, hole 0.5 mm, pitch 1.0 mm, rim 100 µm; drift gap 5 mm, Ed 1 kV/cm, ΔV 1.9 kV; Ar/CO₂ 93:7; **0.8 mm resistive-glass anode** on the readout pad; DCB209A CSPs (~1.9 nF), charge read from the preamp plateau; 2×2 cm area. Measured charge ≤ 100 fC/event (effective gain ≲ 2.8e3).

**Best explanation (inferred).** The glass weighting effect. F = R_glass/R_copper = 0.52 / 0.64 / 0.80 at ε_r ≈ 6 (quick test, 2026-11-05), against 0.51 / 0.64 / 0.855. It matches both the size and the gap shape, and it is field-independent like the data. *Assumed:* glass ε_r and ρ.

**What does not fit yet.**
- The simulated copper baseline falls with gap: anode fraction 0.90 / 0.76 / 0.64 at 0.1 / 0.2 / 0.5 mm. The data divided by F implies a flat or rising baseline.
- The simulated gain (median ~1.25e4, mean ~2.7e4 at 0.2 mm) is 2–10× above the measured gain.

**Running.**
- `results/copper_baseline_gainmatched/`: copper anode at reduced ΔV (gain ≈ 3e3), d = 0.1 / 0.2 / 0.5 mm, 1000 paths each. Tests whether the copper loss is gain-driven. ETA 2026-11-06 ~16:00–16:30. Binary: `THGEM_corner` (see Provenance).

**Not running.** A full glass production does not exist: `results/glass_signal/production_v3` was interrupted (SIGTERM) 102 s after its launch on 2026-11-05.

**Open inputs from Luca.**
1. Hole lattice: hexagonal or square? (The simulation uses square.)
2. Measured absolute top/anode charges, and the E_ind of the 0.51 / 0.64 / 0.855 series.
3. Glass type, ε_r, resistivity, rear-contact type. Is there any bare-copper-anode measurement? It would measure F directly.
4. Real copper corner radius (Cu etched from 150 µm to 50 µm).

**Provenance problems to fix.**
- `results/copper_baseline*` uses `../THGEM_corner/build/thgem_sim` (built 2026-10-29). That source tree is not under git, and its `botCornerRoundUm` option is in no commit.
- Branch `codex/glass-signal-10us` is not pushed.
- Drivers live only under the gitignored `results/`: `charging_08/analysis/charging_driver_v2.py`, `thick_plate/gastools/merge_text.py`, `copper_baseline/{job.sh,analyse.py}`, `glass_signal/quicktest_eind1.5/chunk_job.sh`.
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
See `docs/extraction_ratio_investigation.md` §1–16: grid edge artifact, rim charging, mean-avalanche mode, ion collection, collected-charge ratio. Last commit on `main`: `cbd1178`.
