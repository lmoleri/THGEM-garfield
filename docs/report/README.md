# Anode signal study: pedagogical report

`THGEM_anode_signal_report.pdf` is a self-contained introduction to the study and a complete account of it (THGEM and signal-induction basics, detector, data, Garfield++ model, real-geometry results, ruled-out mechanisms, open questions, uncertainties). It was written on 2026-11-11 from `docs/anode_charge_fraction.md` and `docs/STATUS.md` at commit `d431c49`. No new simulations were run for it. If those documents change, this report does not update itself.

## Files

- `report.html`: the source text (HTML, math in KaTeX).
- `figs.py`: redraws `fig/fig_*.png` from `results/copper_baseline_gasgap/summary_cu90.csv` and `results/glass_signal/quicktest_gasgap/summary_cu90.csv`. `results/` is gitignored, so this only works on the analysis machine. Figure 5 is `docs/figures/rawgrid_edge_field.png`.
- `build.js`: renders `report.html` to the PDF with Playwright (Chromium).

## Rebuild

```sh
python3 docs/report/figs.py            # needs numpy, matplotlib and results/
cd docs/report && npm install          # KaTeX
npm install playwright                 # if Playwright is not installed globally
node build.js                          # writes THGEM_anode_signal_report.pdf
```

Caveats: the E_ind 2.0 and 2.5 kV/cm top-charge values in Fig. 4 are approximate (read from the lab plot); no lab error bars were available.
