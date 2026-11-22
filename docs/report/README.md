# Anode signal study: pedagogical report

`THGEM_anode_signal_report.pdf` is a self-contained introduction to the study and a complete account of it (THGEM and signal-induction basics, detector, data, Garfield++ model, real-geometry results, ruled-out mechanisms, open questions, uncertainties). It was written on 2026-11-11 (revised 2026-11-22 with the exact lab values) from `docs/anode_charge_fraction.md` and `docs/STATUS.md` at commit `d431c49`. No new simulations were run for it. If those documents change, this report does not update itself.

## Files

- `report.html`: the source text (HTML, math in KaTeX).
- `figs.py`: redraws `fig/fig_*.png` from `results/copper_baseline_gasgap/summary_cu90.csv` and `results/glass_signal/quicktest_gasgap/summary_cu90.csv`. `results/` is gitignored, so this only works on the analysis machine. Figure 5 is `docs/figures/rawgrid_edge_field.png`.
- `build.js`: renders `report.html` to the PDF with Playwright (Chromium).
- `lab_data/`: lab values (R, top and anode charge for E_ind 1.5/2.0/2.5 kV/cm) extracted exactly from Luca's vector plots, with fit errors (error bars) and distribution widths (boxes); see `lab_data/README.md`. The simulations are compared with the E_ind 1.5 series.

## Rebuild

```sh
python3 docs/report/figs.py            # needs numpy, matplotlib and results/
cd docs/report && npm install          # KaTeX
npm install playwright                 # if Playwright is not installed globally
node build.js                          # writes THGEM_anode_signal_report.pdf
```
