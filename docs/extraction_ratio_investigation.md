# Investigation: Anode/THGEM-top charge ratio vs induction gap

**Status:** root cause of the simulated over-extraction **identified and fixed** — it was a
*field-sampling artifact* of the uniform transport grid at the thin copper edge, not physics.
On the exact (neBEM) transport field the simulation finally collects charge on the bottom
copper and the extraction magnitude drops into the measured band. One feature of the
measurement — the **rise of the ratio at small induction gaps** — still has no counterpart in
the idealized electrostatic + microscopic model and remains open.

This note records the full investigation into reproducing, in the Garfield++ THGEM simulation,
a lab measurement of the **Anode/THGEM-top charge ratio as a function of the induction gap**.
It documents every hypothesis tested, why each was rejected, the tooling added along the way,
the grid artifact that turned out to be the real cause of the sim's over-extraction (a reusable
finding for any thin-electrode THGEM simulation), and the one measured feature that is still
unexplained.

---

## 1. The measurement and the target

The reference data (`charge_ratio.pdf`) were taken at **ΔV_THGEM = 1.9 kV, drift field = 1 kV/cm,
Ar:CO₂ 93:7**, for three induction fields E_ind ∈ {1.5, 2.0, 2.5} kV/cm, sweeping the induction gap
from 0.1 to 2.0 mm. The observable is the **Anode / THGEM-top charge ratio**.

Characteristic shape (E_ind = 2.0 kV/cm):

| induction gap [mm] | 0.1 | 0.2 | 0.5 | 1.0 | 2.0 |
|---|---|---|---|---|---|
| Anode/THGEM-top | 0.51 | 0.64 | **0.855** (peak) | 0.80 | 0.755 |

Two features drive the whole investigation:

1. A **rise to a peak at ~0.5 mm, then a gentle fall** — i.e. the ratio is *lowest at the smallest
   induction gap*.
2. The three E_ind curves **coincide at 0.1 and 0.2 mm** and separate only for gaps ≥ 0.5 mm. So the
   small-gap suppression is **independent of the induction field**.

## 2. The observable in the simulation

Following the interpretation used here, the measurement's denominator ("THGEM-top charge") is taken
to represent the **total avalanche charge**, so the ratio is compared to the simulated
**electron-collection fraction**

```
frac_anode = (electrons collected on the anode) / (total electrons produced in the avalanche)
```

classified from the avalanche electron endpoints (anode / THGEM bottom copper / top copper /
dielectric / attached), with no induced-signal weighting. At ΔV = 1.9 kV the ions are not drifted
(electrons only), consistent with a collection-fraction observable.

## 3. Study 1 — static extraction geometry (hole rim + transport grid)

**Hypothesis.** The default geometry has no rim (copper flush with the dielectric hole) and a
coarse transport grid, so the simulation *over-extracts*: nearly every avalanche electron reaches
the anode and almost none land on the bottom copper. A real THGEM has the copper etched back from
the hole edge (a ~0.1 mm rim), which should reduce extraction and add bottom-copper collection.

**Tool added — `collect_only` mode** (commit `44cecd1`). The collection fraction classifies
electron *endpoints* and never uses the Shockley–Ramo weighting fields, so a new
`simulation.collect_only` flag (implied by `drift_only`) skips weighting-field sampling, the
read-out electrodes, the induced-signal/charge/amplifier block and the weighting-map dump, keeping
only the transport field, drift area and the collection tally. Field sampling then needs one field
instead of four (**~4× faster**), which makes a finer hole-vicinity transport grid tractable. The
default avalanche path (induced charge) is unchanged.

**Method.** Avalanche collection sweep at ΔV = 1.9 kV, drift = 1 kV/cm, E_ind = 2.0 kV/cm,
Ar:CO₂ 93:7, induction gaps {0.1, 0.2, 0.5, 1.0, 2.0} mm, with **rim = 0.1 mm** and a refined
transport grid (**51 × 161**, ~20 µm lateral — ~5 points across the 100 µm rim). The collection
fraction is cap-independent without space charge, so a modest avalanche cap (500 e⁻) was used.

**Result.**

| induction gap [mm] | 0.1 | 0.2 | 0.5 | 1.0 | 2.0 |
|---|---|---|---|---|---|
| measurement | 0.51 | 0.64 | 0.855 | 0.80 | 0.755 |
| sim, rim = 0 | 0.95 | 0.92 | 0.91 | 0.90 | 0.89 |
| sim, rim = 0.1 mm | 0.95 | 0.89 | 0.71 | 0.50 | 0.48 |
| sim bottom-Cu, rim = 0.1 mm | 0.00 | 0.00 | 0.01 | 0.02 | 0.02 |

![Measurement vs simulation](figures/extraction_meas_vs_sim.png)

**Conclusion.** The rim changes the magnitude and adds a slope, but the slope is a **monotonic fall**
(0.95 → 0.48), the *opposite* of the measured rise at small gaps. Two things stood out and only
later made sense: the simulation is most anode-efficient (0.95) exactly where the measurement is
least (0.51), and the **bottom-copper collection stays ~0–2 % at every gap** even with a 0.1 mm rim.
That second fact — essentially *no* electron ever lands on the bottom copper — is physically wrong
for a biased THGEM (the user measures real charge there with a charge amplifier), and it turned out
to be the signature of the grid artifact of §7, not a property of the geometry.

## 4. Study 2 — single-avalanche space charge

**Motivation.** The measured rise-to-peak requires a mechanism whose strength *changes with the
induction gap*. Space charge at the real gain is the natural candidate: a dense avalanche confined
near the hole exit could suppress extraction most at small gaps (small volume → high density) and
relax as the gap opens. `AvalancheMicroscopic` has no space charge, so it is absent from the
simulation.

**Key constraint (from the measurement conditions).** The data were taken at a **very low rate,
~10 Hz**. Ion transit is µs–ms, so no ion cloud accumulates between events — any space-charge
effect must be the **self-field of a single avalanche** acting on its own electrons, not a
steady/accumulated cloud.

**Method (Stage 1 estimate).** Rather than a hand-drawn charge blob, the estimate uses the
**simulated avalanche's actual charge geometry** (ionization sites = ion birth positions, and
electron drift-line points, from the rim = 0 sweep), scales the total charge to a real
single-avalanche gain G, and Coulomb-sums the retarding axial field E_sc,z that an electron feels
at the hole exit. It is compared to E_ind = 2 kV/cm. (The avalanche's lateral RMS radius is
~120–130 µm at both 0.1 and 1.0 mm gaps.)

**Result — E_sc / E_ind at the hole exit (ion + electron contributions):**

| gain G | 10³ | 10⁴ | 10⁵ | 10⁶ | 10⁷ |
|---|---|---|---|---|---|
| ig = 0.1 mm | 0.0002 | 0.003 | 0.03 | 0.31 | ~3 |
| ig = 1.0 mm | 0.0002 | 0.002 | 0.02 | 0.23 | ~2 |
| upper bound* | 0.001 | 0.005 | 0.05 | 0.50 | ~5 |

\*all G·e compressed into a sphere of the observed 120 µm column radius — a hard ceiling.

![Single-avalanche self-field](figures/spacecharge_selffield.png)

**Verdict — ruled out**, for three independent reasons:

1. **Magnitude.** At this THGEM's realistic single-avalanche gain (10³–10⁴ at ΔV = 1.9 kV, kept
   modest by discharge-safe, low-rate operation), the self-field is **0.02–0.3 % of E_ind** — three
   orders of magnitude too small. Even at an optimistic 10⁵ it is ~2 %, and the hard upper bound
   stays below E_ind until G ≳ 10⁶ (streamer regime).
2. **No gap dependence.** The ions sit in the hole, so the field is essentially identical at 0.1 and
   1.0 mm. The measurement's whole signature is a strong gap dependence.
3. **The real bar is higher.** The hole-exit field also includes the THGEM dipole leakage (≫ E_ind),
   so the field the self-charge must compete with is larger still.

The planned Stage 2 (injecting the self-field into the solver) was skipped: adding a ~1 % field
changes nothing.

## 5. The denominator (ion collection) — ruled out

Both static studies addressed the **numerator** (anode extraction), while the measurement's own
structure — the three E_ind curves coinciding at small gaps — points at the **denominator**. The
"THGEM-top charge" was therefore examined as a possible driver, including an ion contribution to the
top electrode (ion drift off, 300 ns window → ions missing from the induced charge).

This is excluded by a simple bound. With the denominator read as the **total collected charge** (the
user integrates the THGEM-top charge over a few µs with a charge amplifier and is confident it is the
total), the ratio is

```
Anode/THGEM-top = ε / f_top    with ε = extraction efficiency, f_top = fraction landing on THGEM-top ≤ 1,
```

so **Anode/THGEM-top ≥ ε**. No distribution of charge over the top electrode can push the ratio
*below* the extraction efficiency, yet the measurement sits at 0.51 at the smallest gap — a small
number that must come from a genuinely low *numerator*, not a large denominator. Separately, the user
confirmed the bottom electrode collects **electrons** (it shows signal on a charge-sensitive
amplifier), not a drifting ion cloud, so simulating ion collection on the bottom does not address the
discrepancy. The denominator is not the cause.

## 6. Electron attachment — ruled out

Attachment is the only non-anode fate the simulation produced for a long time (see §7 for why), so it
was checked directly. Microscopic attachment comes from the Magboltz cross-sections, not the
macroscopic η table, so `ResetElectronAttachment` does not switch it off; the effective attachment
was varied through the CO₂ fraction instead. Lowering CO₂ (less attachment) simply moved the attached
electrons **to the anode** — `frac_anode` rose 0.86 → 0.92 as attachment fell 0.14 → 0.08 — and left
the bottom-copper fraction at zero. Attachment is a minor, roughly gap-flat loss; it cannot create a
measured ratio below the extraction efficiency, and it does not route electrons to the bottom copper.
Not the cause.

## 7. Root cause — the grid field-sampling artifact at the copper edge

Every study above shared one impossible symptom: **~0 % of avalanche electrons ever land on the
bottom copper**, at any rim size, grid resolution or CO₂ fraction. "Thinking from scratch about what
could stop an electron from ever reaching the bottom electrode" led to the transport field itself.

The simulation transports electrons on a **`ComponentGrid`**: the neBEM field is sampled onto a
**uniform** mesh once (fast per-step trilinear interpolation), instead of querying the exact but slow
`ComponentNeBem3d` at every step. The bottom copper is only **35 µm** thick, and its sharp inner
corner is a **field near-singularity** — the magnitude spikes and the direction rotates by ~90° over
a few µm. A uniform grid (and `SetMesh` is uniform-only) cannot resolve that:

- **Magnitude is smeared.** On a 5 µm dump slice the exact field peaks at **~110 kV/cm**; the sampled
  grid field never exceeds **~51 kV/cm**.
- **Direction reverses in a one-cell skin.** Trilinear interpolation across the metal boundary blends
  in-metal nodes with gas nodes, producing a thin layer — one grid cell wide — hugging the copper
  surface in which the sampled field points **up to ~160° away from the true field**, i.e. back
  toward the hole and the anode. An electron drifting down the copper surface in that skin is pushed
  **off the copper and up to the anode** instead of being collected.

![Grid field-sampling artifact at the copper edge](figures/rawgrid_edge_field.png)

The decisive test releases electrons **directly on the hole wall** (`source.release_z_cm`) and
transports them on the grid vs on the exact neBEM field (`fields.use_raw_nebem`), everything else
identical. On the grid they essentially never reach the bottom copper; on the exact field tens of
percent do.

![Wall-release: grid vs exact field](figures/wall_release_grid_vs_exact.png)

The artifact is a **resolution/interpolation** failure, not a bug in the geometry or potentials, so
the grid-side fixes do **not** remove it (all tried, all still ~0 % bottom copper):

- **Finer uniform grid** (31 × 131 → 61 × 201): the skin shrinks but never vanishes — the field
  rotates sub-cell at any feasible spacing.
- **Copper-edge chamfer** (`geometry.edge_round_um`): turns the 90° corner into an obtuse,
  grid-resolvable edge, but the thin skin along the remaining copper face persists.
- **Conductor in-painting** (`fields.inpaint_conductors`): fill the in-metal nodes with the
  neighbouring gas field before interpolating — removes the in-metal blend but not the sub-cell
  rotation; the reversed skin remains.

Both options are committed but **opt-in and off by default** (the default keeps the historical `_v2`
transport cache). The correct transport at the edge is **`use_raw_nebem`** — transport directly on
`ComponentNeBem3d`, no interpolation. It is slow (exact field query per step), but with a small
avalanche cap the *collection fraction* is cap-independent, so a handful of events suffices.

## 8. The corrected result and the remaining puzzle

Re-running the induction-gap sweep on the **exact neBEM field** (rim = 0, small cap, few events):

![Corrected extraction vs measurement](figures/rawfield_sweep_vs_meas.png)

| induction gap [mm] | 0.1 | 0.2 | 0.5 | 1.0 |
|---|---|---|---|---|
| measurement | 0.51 | 0.64 | 0.855 | 0.80 |
| sim anode/total (exact field) | 0.79 | 0.71 | 0.46\* | 0.73 |
| sim bottom-copper fraction | 0.15 | 0.03 | 0.15 | 0.15 |

\*wide statistical error (~6 events; per-point SEM 0.07–0.15).

Two things are fixed. The bottom copper now collects a real fraction (**~15 %**, zero on the grid),
and the extraction magnitude falls from the grid's ~0.9 to **~0.75**, inside the measured band. But
within the statistics the corrected extraction is **flat in the induction gap**, while the
measurement **rises** from 0.51 to 0.855. The idealized model does not contain the small-gap
suppression.

This is not a voltage-convention effect. The simulation holds the fields fixed and lets the electrode
potentials scale with the gap (confirmed to match the measurement's setup):

| induction gap [mm] | 0.1 | 0.2 | 0.5 | 1.0 |
|---|---|---|---|---|
| V_anode [V] | 0 | 0 | 0 | 0 |
| V_bottom-Cu [V] | −20 | −40 | −100 | −200 |
| V_top-Cu [V] | −1920 | −1940 | −2000 | −2100 |
| V_drift [V] | −2020 | −2040 | −2100 | −2200 |

(V_bottom-Cu = −E_ind·d_ind, V_top-Cu = V_bottom-Cu − ΔV_THGEM, V_drift = V_top-Cu − E_drift·d_drift.)
At fixed E_ind the hole-exit extraction field is gap-independent, which is exactly why the static
model gives a flat ratio. The measured rise-then-fall — strongest at small gaps and independent of
E_ind there — must come from something outside a single-avalanche electrostatic + microscopic
transport model (candidates not yet tested: dielectric charging-up at the hole wall, or a readout/
charge-definition effect in the denominator at small gaps). That is the open question.

## 9. Mechanisms tested and excluded

| # | Mechanism | How tested | Verdict |
|---|---|---|---|
| 1 | Hole rim + grid resolution (§3) | rim 0.1 mm, grid 51 × 161 | Sets magnitude but gives a monotonic **fall**, not the rise; its ~0 % bottom-Cu was the §7 artifact |
| 2 | Single-avalanche space charge (§4) | Coulomb self-field from the real avalanche geometry | Ruled out: ~10³× too weak at realistic gain, and gap-independent |
| 3 | Denominator / ion collection (§5) | ratio ≥ extraction-efficiency bound | Ruled out: cannot push the ratio below ε; bottom reads electrons |
| 4 | Electron attachment (§6) | vary CO₂ (microscopic Magboltz) | Ruled out: minor, gap-flat; routes to anode, not bottom copper |
| 5 | **Grid field-sampling artifact at the copper edge (§7)** | raw-neBEM vs grid, field dump, wall-release | **Root cause** of the over-extraction — fixed by `use_raw_nebem` |
| 6 | Copper-edge rounding / conductor in-painting (§7) | `edge_round_um`, `inpaint_conductors` | Do not fix the grid (sub-cell field rotation); kept opt-in, off by default |
| — | Measured rise at small induction gaps (§8) | exact-field sweep + voltage convention | **Open** — absent from the idealized electrostatic + microscopic model |

## 10. Reproducing

Simulation outputs live under `results/` (gitignored):

- `results/transparency_induction_avalanche/` — rim = 0 avalanche induction sweep (also carries the
  avalanche charge geometry used by the space-charge estimate).
- `results/transparency_induction_avalanche_rim100/` — rim = 0.1 mm, grid 51 × 161 sweep.
- `results/extraction_edge_field/` — the exact-field (`use_raw_nebem`) gap sweep
  (`raw_nebem_sweep.csv`) and a `dump_raw_field` slice through the copper edge
  (`raw_vs_grid_field_ig0p5.csv`).

Figures in this note regenerate from those outputs via:

```bash
python3 scripts/plot_extraction_comparison.py   # -> docs/figures/extraction_meas_vs_sim.png
python3 scripts/plot_spacecharge_estimate.py    # -> docs/figures/spacecharge_selffield.png (+ table)
python3 scripts/plot_rawgrid_edge_field.py      # -> docs/figures/rawgrid_edge_field.png
python3 scripts/plot_wall_release.py            # -> docs/figures/wall_release_grid_vs_exact.png
python3 scripts/plot_rawfield_sweep.py          # -> docs/figures/rawfield_sweep_vs_meas.png
```

Diagnostics used by this investigation (in `src/thgem_sim.cc`):

- `simulation.collect_only` — endpoint collection without induced-signal weighting (commit `44cecd1`).
- `fields.use_raw_nebem` — transport on the exact `ComponentNeBem3d`, bypassing the uniform grid; the
  correct field at the thin copper edge. **Slow** — use a small `simulation.max_avalanche_size` (the
  collection fraction is cap-independent) and a few events (commit `81f773c`).
- `fields.dump_raw_field` — dump the exact vs grid field on a fine x-z slice through the copper edge
  to `raw_vs_grid_field.csv` (commit `81f773c`).
- `source.release_z_cm` — release a drift-only electron at an absolute z (e.g. on the hole wall) for
  the wall-release test (commit `81f773c`).
- `geometry.edge_round_um`, `fields.inpaint_conductors` — opt-in copper-edge chamfer and conductor
  in-painting; off by default (neither fixes the grid artifact).
