# THGEM study status

Living document. The **Current state** section is rewritten whenever it changes; the **Log** below only grows (newest first). Each log entry records what binary produced it, so a result can be traced to code.

Conventions: *measured* = a number from a simulation output; *inferred* = a reading of those numbers; *assumed* = an input not yet confirmed. Uncertainties are 68 % bootstrap unless stated; weighted-path results are heavy-tailed, so quote the ESS.

---

## Current state (updated 2026-11-08)

**Question.** The measured anode/THGEM-top charge ratio drops at small induction gaps: 0.51 / 0.64 / 0.855 / 0.80 at d = 0.1 / 0.2 / 0.5 / 1.0 mm.

**Detector as measured** (confirmed by Luca): 0.8 mm FR4 THGEM, Cu 50 µm per side, hole 0.5 mm, pitch 1.0 mm, rim 100 µm; drift gap 5 mm, Ed 1 kV/cm, ΔV 1.9 kV; Ar/CO₂ 93:7; **0.8 mm resistive-glass anode** on the readout pad; DCB209A CSPs (~1.9 nF), charge read from the preamp plateau; 2×2 cm area. Measured charge ≤ 100 fC/event (effective gain ≲ 2.8e3).

**Best explanation (inferred).** The glass weighting effect. F = R_glass/R_copper = 0.52 / 0.64 / 0.80 / 0.89 at ε_r ≈ 6 (0.59 / 0.70 / 0.84 / 0.91 at ε_r 8) for d = 0.1 / 0.2 / 0.5 / 1.0 mm (quick test, 2026-11-05 and 2026-11-08), against 0.51 / 0.64 / 0.855 / 0.80. It matches the size and the gap shape of the small-gap suppression, and it becomes small at 1 mm as the data requires; F cannot produce the slight 0.5 → 1 mm dip. The missing anode charge reappears on the THGEM bottom electrode (bottom/anode ≈ 0.7–0.9 at 0.1 mm with glass, ≈ 0 with copper): a direct test if the bottom can be read out. *Assumed:* glass ε_r and ρ.

**What does not fit yet.**
- The simulated copper baseline falls with gap: anode fraction 0.90 / 0.76 / 0.64 at 0.1 / 0.2 / 0.5 mm (ΔV 1.9 kV), and still 0.882 / 0.799 / 0.686 at the measured gain (ΔV 1.77 kV, gain ≈ 3e3), so the fall is geometric, not a gain artefact. R_copper = 1.03 / 0.82 / 0.78 / 0.68, so the full R_glass is ≈ 0.6 at every gap (data 0.51 → 0.855 → 0.80). The data divided by F implies a flat or rising baseline.
- The simulated gain (median ~1.25e4, mean ~2.7e4 at 0.2 mm) is 2–10× above the measured gain.

**Running.** Nothing.

**Follow-up (parked by Luca, 2026-11-08).** The real hole pattern is **hexagonal**; every simulation uses a square lattice. A square-pitch-0.93 mm proxy (same hole density) is prepared but not launched in `results/hex_proxy_p093/`; true hex needs a mirror-symmetric p/2 × (√3/2)p cell.

**Not running.** A full glass production does not exist: `results/glass_signal/production_v3` was interrupted (SIGTERM) 102 s after its launch on 2026-11-05.

**Open inputs from Luca.**
1. ~~Hole lattice~~: hexagonal (2026-11-08); the gas is Ar/CO₂ 93:7 only.
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
See `docs/extraction_ratio_investigation.md` §1–16: grid edge artifact, rim charging, mean-avalanche mode, ion collection, collected-charge ratio. Last commit on `main`: `cbd1178`.
