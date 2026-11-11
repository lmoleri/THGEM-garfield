# Anode charge fraction vs induction gap

The single write-up of the study. It states what is measured, how the simulation models it, the
current results, what has been ruled out and why, and what is still open. The dated record of every
run (setup, seeds, binaries, data paths) is the log in [`STATUS.md`](STATUS.md); this document
does not repeat it.

Labels used below: **lab** = measured on the detector; **sim** = a number from a simulation output;
**inferred** = our reading of those numbers; **assumed** = an input nobody has measured.
Simulation intervals are 68 % bootstrap over weighted paths, which are heavy-tailed (quote the ESS).

Last revised 2026-11-11.

---

## 1. Question and data

The anode / THGEM-top charge ratio R falls at small induction gaps (lab):

| Nominal gap d [mm] | 0.1 | 0.2 | 0.5 | 1.0 | 2.0 |
|---|---|---|---|---|---|
| R = Q_anode / Q_top | 0.51 | 0.64 | 0.855 | 0.80 | 0.755 |
| Q_top [pC/event], E_ind 1.5 kV/cm | 0.80 | 0.83 | 0.30 | 0.24 | ~0.25 |
| Q_anode = R × Q_top [pC], inferred | 0.41 | 0.53 | 0.26 | 0.19 | – |

ΔV 1.9 kV, E_d 1 kV/cm, Ar/CO₂ 93:7, 5.9 keV X-rays at ~10 Hz. Two features matter:

- The **R curves for E_ind 1.5 / 2.0 / 2.5 kV/cm coincide at 0.1 and 0.2 mm** and separate only at
  ≥ 0.5 mm, so the small-gap suppression does not depend on the induction field.
- **Q_top rises 3–4× below 0.5 mm** (and with E_ind there), so the drop in R is driven at least as
  much by a larger top charge as by a smaller anode charge.

*Uncertain:* the R row above is the series quoted from `charge_ratio.pdf`, which the old research log
attributes to E_ind 2.0 kV/cm; Q_top is the E_ind 1.5 series. All simulations below use E_ind 1.5.
Below 0.5 mm this does not matter (curves coincide); at 0.5 and 1.0 mm the R of the 1.5 series is
needed for a like-for-like comparison.

## 2. The detector as measured

Confirmed by Luca unless marked.

- THGEM: FR4 0.8 mm, **copper 90 µm on both faces** (plate ≈ 0.98 mm), hole 0.5 mm, rim 100 µm,
  pitch 1.0 mm, **hexagonal** lattice. Drift gap 5 mm. Active area ≈ 2 × 2 cm.
- Anode: readout pad behind **0.8 mm resistive glass**, volume resistivity **ρ = 1e10 Ω·cm**.
  *Assumed:* glass ε_r (6–8 used; scanned 4–12) and ideal ohmic rear contact.
- Gap convention: the spacers set d between the THGEM **FR4** and the glass surface, so the gas gap
  from the bottom copper is **d − 90 µm = 10 / 110 / 410 / 910 µm**. The induction voltage was set as
  E_ind × d, so the gas field is E_ind × d / (d − 0.09 mm) = **15 / 2.73 / 1.83 / 1.65 kV/cm** for the
  E_ind 1.5 series.
- Readout: NAICAM DCB209A charge preamplifiers on top and anode (C_in,eff ≈ 1.84 nF, decay 100 µs,
  no shaper); charge = plateau of the digitised pulse; bottom copper hard-grounded. HV reaches both
  electrodes through the preamp bias input (40 MΩ). Luca: the amplitude is read after all ions
  have arrived.

## 3. Simulation model

- **Field:** neBEM periodic unit cell (square lattice, ≥ 9 copies), transport on the exact
  (raw) neBEM field. The uniform transport grid is not used: at the thin copper edge it
  mis-samples the field and over-extracts electrons (the main finding of the 0.4 mm-plate phase,
  see [`extraction_ratio_investigation.md`](extraction_ratio_investigation.md) §7).
- **Avalanche:** weighted mean-avalanche paths (`AvalancheMC`, local Townsend/attachment), Ar/CO₂
  93:7 dense 110-point gas table, Penning r = 0.405.
- **Signal:** the charge inventory at 10 µs is scored with exact weighting potentials twice, once
  for a copper anode and once for the pad behind glass (Shockley–Ramo, paired on the same charges;
  method and checks in [`glass_signal_hypothesis.md`](glass_signal_hypothesis.md)). This gives

  - R_Cu, R_glass = anode / top induced charge for each anode type,
  - **F = R_glass / R_Cu**, the pure glass weighting factor (planar limit d / (d + b/ε_r)).

  F is unchanged between 5, 10 and 20 µs and between fixed and mobile attachment.
- **Copper baseline:** a separate endpoint run with a copper anode gives the anode electron
  fraction and where the lost electrons end.

## 4. Results (real geometry, 2026-11-11)

Cu 90 µm, gas gap d − 90 µm, field as in §2, ΔV 1.9 kV, 500 paths per gap (signal) and 1800 per gap
(copper baseline). Glass ε_r 6–8; lab values in brackets.

| Nominal d | 0.1 mm | 0.2 mm | 0.5 mm | 1.0 mm |
|---|---|---|---|---|
| Q_top [pC] | 4.44–4.47 (0.80) | 1.42 (0.83) | 0.77 (0.30) | 0.68 (0.24) |
| Q_top sim / lab | 5.6 | 1.7 | 2.6 | 2.8 |
| R_glass | 0.29–0.32 (0.51) | 0.49–0.55 (0.64) | 0.61–0.65 (0.855) | 0.59–0.60 (0.80) |
| R_Cu | 1.05 | 0.92 | 0.80 | 0.67 |
| F = R_glass / R_Cu | 0.27–0.31 | 0.53–0.60 | 0.77–0.81 | 0.88–0.90 |
| Lab R / R_Cu (F the data would need) | 0.49 | 0.70 | **1.07** | **1.19** |
| Copper anode e⁻ fraction | 0.984 | 0.838 | 0.656 | 0.568 |
| … lost on bottom-Cu underside | 0.001 | 0.048 | 0.172 | 0.254 |
| … lost on lowest 100 µm of FR4 wall | 0.012 | 0.080 | 0.130 | 0.135 |
| Mean gain | 1.3e5 | 3.6e4 | 2.4e4 | 2.2e4 |
| Q_bottom with glass [pC] | 3.2–3.3 | 0.68–0.77 | 0.29–0.32 | 0.29–0.30 |

Precision: Q ±6–10 %, R ±5 % (±1 % at 0.1 mm), F ±0.002 (paired), copper fraction ±0.02. ESS
74–189 of 500 for the glass top charge, 455–556 of 1800 for the copper baseline. No ε_r in 4–12
brings R_glass to the data at 0.5 or 1.0 mm (at most 0.69 / 0.62 at ε_r 12).

What these numbers say (inferred):

1. **The glass produces a suppression of the right kind.** F falls from ~0.9 at 1 mm to ~0.55 at
   0.2 mm, is geometric and field-independent, as the data are. Between 0.2 and 1.0 mm it is the
   only mechanism we have found that lowers R in the observed direction.
2. **But the full model does not reproduce R.** R_glass is 0.1–0.25 below the data at 0.2–1.0 mm
   and roughly flat (0.5–0.65) instead of rising to 0.855. The cause is the copper baseline: R_Cu
   falls from 1.05 to 0.67 because more and more avalanche electrons end on the bottom-copper
   underside and the lowest hole wall as the gap grows.
3. **At 0.5 and 1.0 mm the data need F > 1** with the simulated R_Cu. Glass can only lower R, so
   the main remaining error is on the copper/transport side (or in the comparison itself, §1), not in
   the glass.
4. **The top charge has the right shape at 0.2–1.0 mm but is 1.7–2.8× too high**, equivalent to
   roughly 25–30 V of ΔV. The real geometry fixed the shape (sim 0.2/0.5 ratio 1.86 vs lab 2.8; it was
   1.25 with the old geometry).
5. **0.1 mm is a clear miss.** With a uniform 10 µm gap the hole field (~16 kV/cm) continues into the
   gap, the gain reaches 1.3e5, Q_top is 5.6× the lab value and R_glass 0.29–0.32 is below the lab
   0.51. The real 0.1 mm gap is almost certainly not a clean, uniform 10 µm gap (§6).
6. The charge the glass removes from the anode appears on the THGEM bottom (last row). A bottom
   readout would show where the charge goes, but not which mechanism moved it there: glass,
   readout impedance and copper hole-exit loss all put it on the bottom with the same sign.

## 5. Ruled out, and why

Mechanisms tested against the gap dependence. "Strength" says how firm the exclusion is.

| Mechanism | Test | Why it is excluded | Strength |
|---|---|---|---|
| Transport-grid artefact at the copper edge | raw neBEM vs grid, wall-release test | Real bug; it caused the early over-extraction. Fixed: all runs since use raw neBEM | Firm (fixed) |
| Field mesh | element count ×4; 10 µm gap at 2021 vs 13 938 elements | Field changes 1–2 % (≤ 3.3 % in the 10 µm gap) | Firm |
| Drift gap 1 vs 5 mm | field comparison | < 1.4 % change in hole and gap field | Firm |
| Electron attachment | CO₂ variation, Magboltz | Small and gap-flat | Firm |
| Avalanche space charge, ions reaching the anode | self-field estimate; ion field lines incl. charged rim | ~10³× too weak; ions reach the anode only at 3–10 pC per event (lab 0.2–0.8 pC) | Firm for the lab charge (tested on the 0.4 mm plate) |
| Local-field (mean-avalanche) approximation | weighted vs microscopic at the hole exit | Same corner loss | Firm |
| Gain as the cause of the falling copper baseline | gain-matched run at ΔV 1.77 kV | Same fall at ~10× lower gain (0.88 / 0.80 / 0.69, Cu 50 µm) | Firm |
| Copper-corner rounding | R = 0–45 µm, 0.4 mm plate | Only R = 45 µm gives a flat trend; all stay far below the data | Moderate (real radius unknown; old geometry) |
| FR4 charging-up, iterative | 12 neBEM iterations, 0.1 and 0.5 mm | No equilibrium; gain collapses 250–900×; extraction does not move toward the data | Moderate |
| FR4 charging-up, fully charged limit | E·n = 0 fit, 12 wall bands + rims, 0.5 mm | Clearing the wall needs 10–20 nC/cm², which cuts the hole field to ~0.4× (no gain). The lab gain allows ≲ 1–2 nC/cm², which lowers wall E·n by only 10–15 %. Even a perfect FR4 shield leaves the bottom-Cu loss, so the baseline would still fall | Moderate (uniform zones, square lattice, no charged avalanche run) |
| Readout impedance / anode–bottom capacitance | capacitive divider, DCB209A values | C_AB 19–25 pF at 0.1 mm (glass) vs C_in,eff 1.84 nF → ≤ 1.3 % loss. The data would need C_in,eff ≈ 30–40 pF, ~50× below spec | Moderate (relies on the manual; not measured) |
| Glass surface charging at 0.1 mm | estimate with ρ = 1e10 Ω·cm | Mean surface potential = J·ρ·b. With Q_anode 0.41 pC × 10 Hz on ≥ 1 mm², it is ≈ 0.3 V against 15 V across the gap (≈ 2 %) | Moderate (holds unless the irradiated spot is ≪ 1 mm²) |
| Electron extraction fraction as the observable | ions followed in 3D | Wrong observable: the top collects only ~45 % of the ions. Replaced by induced charge on each electrode (§3) | Firm (corrected) |

Inputs corrected along the way (each changed the numbers, none explains the data on its own): plate
0.4 → 0.8 mm FR4; copper 35 → 50 → 90 µm; drift gap 1 → 5 mm; copper anode → glass anode; gap
measured from the copper → from the FR4 (gas gap d − 90 µm, field E_ind × d / (d − 0.09 mm)); lab
gain "≲ 2.8e3" → Q_top 0.24–0.83 pC.

Correction to an earlier argument: the glass-charging exclusion was first argued from
τ = ε0 ε_r ρ ≈ 6 ms ≪ 100 ms between events. For a charge on the glass facing a 10 µm gas gap the
relevant time is ρ ε0 (ε_r + b/d) ≈ 80 ms, not ≪ 100 ms. The exclusion holds anyway because the mean
potential above depends only on the current density, not on τ; the per-event step (~1 V) decays
between hits on the same spot only if the spot is not hit faster than every ~0.1 s.

## 6. Open questions

Ranked by how much of the discrepancy they could carry (inferred).

1. **Why the simulated copper baseline falls (0.98 → 0.57).** It is the largest error at 0.2–1.0 mm
   (§4, point 3). Untested candidates: the **hexagonal lattice** (farthest copper from a hole 0.58 mm
   instead of 0.71 mm; a square-pitch-0.93 mm proxy is prepared in `results/hex_proxy_p093/`, parked);
   the real hole-exit profile (copper etched from 150 µm; corner radius unknown); the E_ind mismatch at
   0.5–1.0 mm (§1; at 0.2 mm the copper fraction rises 0.78 → 0.88 for E_ind 1 → 3 kV/cm).
2. **What the real 0.1 mm gap looks like.** A 10 µm clearance held over 2 × 2 cm is unlikely; spacer
   tolerance, glass and THGEM flatness, or partial contact would raise the effective gap and lower
   the gain. Not modelled.
3. **Absolute gain ~2× high** at 0.2–1.0 mm. Candidates: Penning transfer (0.405 used, not measured
   for this mixture), gas table, lattice.
4. **Glass ε_r** is assumed. It sets F directly (F at 0.2 mm: 0.43 / 0.60 / 0.69 at ε_r 4 / 8 / 12).
5. **Time window.** The simulation scores at 10 µs; the preamp decays with 100 µs while backflow ions
   need ~370 µs to cross the drift gap. F is stable over 5–20 µs, but R_Cu and Q_top at the true
   readout time have not been checked.

Lab measurements that would settle most of this, cheapest first:

- **Test pulse into the anode channel** with the detector connected, at 0.1 mm and ≥ 1 mm: settles
  the readout-impedance question (≤ 1.3 % expected from the manual values vs ~40 % needed).
- **A bare-copper anode** at the same gaps: measures R_Cu directly, so it tests both the glass
  factor (F = R_glass / R_Cu) and the simulated copper baseline.
- **Gap and flatness at 0.1 mm** (feeler or capacitance across the gap).
- **Glass ε_r** (capacitance of a known area).
- **Bottom readout** at 0.1 mm: confirms the missing charge is on the bottom (~3 pC with glass),
  but cannot separate glass from impedance.

## 7. How we got here

- ≤ 2026-10-29, 0.4 mm plate, copper anode: found and fixed the transport-grid artefact; switched to
  weighted mean avalanches and to collected charges. The simulation still disagreed most at small gaps.
  Record: [`extraction_ratio_investigation.md`](extraction_ratio_investigation.md) (historical).
- 2026-11-01: the real plate is 0.8 mm. This removed the 80–300× gain mismatch; the trend stayed
  opposite to the data.
- 2026-11-02..04: iterative FR4 charging, no explanation.
- 2026-11-04: the measurements used the glass anode, so every copper-anode comparison was the wrong
  reference. Glass signal method built and validated (branch `codex/glass-signal-10us`, merged).
- 2026-11-05..08: glass quick test (Cu 50 µm, gap from the copper): F alone matched the data at
  0.1–0.5 mm. The copper baseline was found to fall with gap, and the gain-matched run showed this is
  geometric. Superseded numbers: F 0.52 / 0.64 / 0.80 / 0.89 at ε_r 6.
- 2026-11-09..10: fully charged FR4 limit and readout impedance, both excluded.
- 2026-11-10..11: real copper thickness and gap convention. The 0.2–1.0 mm shapes improved; 0.1 mm
  became a clear miss, and the "F alone matches" reading no longer holds. Glass ρ = 1e10 Ω·cm.

## 8. Data and provenance

- Copper baseline: `results/copper_baseline_gasgap/summary_cu90.csv` (binary `../THGEM_corner/build/thgem_sim`, unversioned).
- Glass signal: `results/glass_signal/quicktest_gasgap/summary_cu90.csv` (binary `fb42296`).
- Charged FR4 limit: `results/charged_equilibrium/`.
- Readout-impedance estimate: log entry 2026-11-10 in [`STATUS.md`](STATUS.md).
- Provenance gaps (unversioned binary, drivers under gitignored `results/`, unpushed branch, gas
  table not in `gas/`) are tracked in `STATUS.md`.
