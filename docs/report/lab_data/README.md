# Lab measurement points (extracted 2026-11-22)

Source: Luca's matplotlib PDFs `top_charge.pdf`, `anode_charge.pdf`, `charge_ratio.pdf`
(Ar:CO2 93:7, ΔV_THGEM 1.9 kV, E_drift 1 kV/cm, "approx." E_ind 1.5/2.0/2.5 kV/cm, nominal gaps 0.1/0.2/0.5/1/2 mm).

Method: the PDFs are vector. Values come straight from the drawing coordinates
(series polyline vertices = marker positions, error-bar segments, translucent boxes),
mapped to data units with a linear fit to the tick marks (fit residual < 1e-8).
Extraction error is therefore negligible (rounded to 4 decimals here). Script: `extract_vector_points.py`.

Series identity: legend colour + dash pattern. Blue dashed = 1.5, red dash-dot = 2.0, green = 2.5.

Columns:
- `value`: plotted point.
- `errbar_lo/hi`: the drawn vertical error bar (small, ~0.1–1 %).
- `box_lo/hi`: the translucent box drawn behind each point (symmetric; ~11–24 % on charges, ~1.5–6 % on R).
  Meaning (Luca, 2026-11-22): error bars = fit errors on the underlying distributions;
  boxes = width of the same distributions.

Check: R ≈ anode/top within ≤3.4 % (0.1 and 0.2 mm agree to <0.5 %), so R is probably the mean of per-event ratios.
