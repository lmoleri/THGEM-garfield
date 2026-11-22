# THGEM anode signal talk (Beamer)

Short talk (13 main slides, ~13-15 min) + 23 backup slides (B1-B23), built from
the report in `../report/`. No new simulations.

Update 2026-11-22: lab data replaced by the exact values extracted from Luca's original
plots (copies in `data/`, same as `../report/lab_data/`). The report's old "lab R" was the E_ind 2.0 series;
the slides now compare the simulation (E_ind 1.5) with the 1.5 series only. Error bars on lab
points = fit errors on the underlying distributions; translucent boxes = distribution widths.

Build: `pdflatex thgem_anode_signal_talk.tex` (run twice so the backup links resolve).
Needs beamer, siunitx, booktabs, array, appendixnumberbeamer, lmodern.

Figures:
- `fig/*_v2*.png` (measured data, ratio/glass factor, charges): redrawn by
  `python3 figs_slides.py data fig` from `data/` (lab CSVs + glass quick-test sim summary,
  `results/glass_signal/quicktest_gasgap/summary_cu90.csv`). Needs matplotlib, numpy, Pillow.
- other figures copied from `../report/fig/` (and `../figures/`); `*_L/_R.png` are panel crops. Only the figures the .tex uses are committed.

Note: frame labels must not contain ':' (beamer then silently drops the frame).
