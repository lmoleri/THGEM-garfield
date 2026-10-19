#!/usr/bin/env python3
"""Dedicated GUI for the THGEM electron-transparency study.

Sweeps the drift gap in drift-only (no-multiplication) mode and plots, live as each
gap completes, the fraction of drift electrons collected at the anode versus the THGEM
bottom copper.  Each gap is one `thgem_sim` run (a one-time, cached neBEM solve); the
heavy work runs in a worker thread so the window stays responsive.

    python3 gui/transparency_app.py

Geometry and gas come from the chosen base config (default config/THGEM_0-4mm_drift.json);
the fields, drift-gap range, event count and release are set here.  The physics is the
same drift-only mode the CLI sweep (scripts/transparency_vs_drift.py) drives.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

# ── Paths + the shared sweep logic ───────────────────────────────────────────────
GUI_DIR          = Path(__file__).parent.resolve()
THGEM_DIR        = (GUI_DIR / "..").resolve()
BINARY           = THGEM_DIR / "build" / "thgem_sim"
GARFIELD_INSTALL = (THGEM_DIR / "../../local/garfield").resolve()
CONFIG_DIR       = THGEM_DIR / "config"
DEFAULT_CONFIG   = CONFIG_DIR / "THGEM_0-4mm_drift.json"

sys.path.insert(0, str(THGEM_DIR / "scripts"))
import transparency_vs_drift as tvd  # noqa: E402  (build_gap_config / parse_summary / gap_range)


def run_env() -> dict:
    """A process env with GARFIELD_INSTALL / HEED_DATABASE set (respects existing)."""
    env = os.environ.copy()
    env.setdefault("GARFIELD_INSTALL", str(GARFIELD_INSTALL))
    env.setdefault("HEED_DATABASE", str(GARFIELD_INSTALL / "share" / "Heed" / "database"))
    return env


# ── Worker: run the per-gap sweep without blocking the UI ────────────────────────
class SweepRunner(QThread):
    """Run `thgem_sim --drift-only` once per drift gap, streaming progress.

    Mirrors gui/app.py's SimRunner (env, cwd, stdout streaming) but loops over gaps and
    emits a parsed result per gap so the plot can grow live.
    """
    log_line  = pyqtSignal(str)
    gap_done  = pyqtSignal(dict)   # parsed transparency fractions for one gap
    sweep_done = pyqtSignal()
    failed    = pyqtSignal(str)
    stopped   = pyqtSignal()

    def __init__(self, base_cfg: dict, gaps: list[float], events: int, release: str,
                 out_dir: Path, force: bool = False, parent=None):
        super().__init__(parent)
        self._base_cfg = base_cfg
        self._gaps     = gaps
        self._events   = events
        self._release  = release
        self._out_dir  = Path(out_dir)
        self._force    = force
        self._proc: subprocess.Popen | None = None
        self._stopped  = False

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self):
        self._out_dir.mkdir(parents=True, exist_ok=True)
        env = run_env()
        for gap in self._gaps:
            if self._stopped:
                self.stopped.emit()
                return
            run_name = f"gap_{gap:.3f}mm"
            summary = self._out_dir / run_name / "summary.csv"
            if summary.exists() and not self._force:
                self.log_line.emit(f"gap {gap:.3f} mm: reusing cached result")
            else:
                cfg_path = self._out_dir / f"{run_name}.json"
                cfg_path.write_text(json.dumps(
                    tvd.build_gap_config(self._base_cfg, gap, self._events, self._release),
                    indent=2))
                self.log_line.emit(f"gap {gap:.3f} mm: running (one-time solve if not cached)…")
                try:
                    self._proc = subprocess.Popen(
                        [str(BINARY), "--config", str(cfg_path),
                         "--out", str(self._out_dir), "--run-name", run_name],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1, cwd=str(THGEM_DIR), env=env)
                    for line in self._proc.stdout:
                        self.log_line.emit(line.rstrip())
                    self._proc.wait()
                except Exception as exc:  # noqa: BLE001
                    self.failed.emit(f"gap {gap:.3f} mm: {exc}")
                    return
                if self._stopped:
                    self.stopped.emit()
                    return
                if self._proc.returncode != 0 or not summary.exists():
                    self.failed.emit(f"gap {gap:.3f} mm: binary exited "
                                     f"{self._proc.returncode}")
                    return
            try:
                self.gap_done.emit(tvd.parse_summary(summary, gap))
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(f"gap {gap:.3f} mm: could not read summary ({exc})")
                return
        self.sweep_done.emit()


# ── Matplotlib canvas ────────────────────────────────────────────────────────────
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(figsize=(6, 4.5))
        self.ax = self.figure.add_subplot(111)
        super().__init__(self.figure)


def _dspin(lo, hi, step, dec, val) -> QDoubleSpinBox:
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step)
    w.setDecimals(dec); w.setValue(val); return w


# ── Main window ──────────────────────────────────────────────────────────────────
class TransparencyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("THGEM electron transparency — drift-gap sweep")
        self.resize(1150, 680)
        self._base_cfg: dict = {}
        self._rows: list[dict] = []
        self._runner: SweepRunner | None = None

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.addWidget(self._build_config_panel(), 0)
        root.addWidget(self._build_results_panel(), 1)

        self._load_config(DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)

    # ── left: config ────────────────────────────────────────────────────────
    def _build_config_panel(self) -> QWidget:
        panel = QWidget(); panel.setFixedWidth(380)
        v = QVBoxLayout(panel)

        box = QGroupBox("Base config (geometry + gas)"); bv = QVBoxLayout(box)
        self.cfg_path = QLineEdit(str(DEFAULT_CONFIG))
        row = QHBoxLayout(); row.addWidget(self.cfg_path, 1)
        browse = QPushButton("Browse…"); browse.clicked.connect(self._on_browse)
        load = QPushButton("Load"); load.clicked.connect(
            lambda: self._load_config(Path(self.cfg_path.text())))
        row.addWidget(browse); row.addWidget(load)
        bv.addLayout(row)
        self.cfg_summary = QLabel("—"); self.cfg_summary.setWordWrap(True)
        self.cfg_summary.setStyleSheet("color:#555;")
        bv.addWidget(self.cfg_summary)
        v.addWidget(box)

        box = QGroupBox("Drift-gap sweep"); f = QFormLayout(box)
        self.gap_min  = _dspin(0.01, 20.0, 0.1, 2, 0.1)
        self.gap_max  = _dspin(0.01, 20.0, 0.1, 2, 4.0)
        self.gap_step = _dspin(0.01, 10.0, 0.05, 2, 0.4)
        self.events   = QSpinBox(); self.events.setRange(10, 1_000_000); self.events.setValue(2000)
        f.addRow("Gap min [mm]",  self.gap_min)
        f.addRow("Gap max [mm]",  self.gap_max)
        f.addRow("Gap step [mm]", self.gap_step)
        f.addRow("Electrons / gap", self.events)
        v.addWidget(box)

        box = QGroupBox("Fields (override base)"); f = QFormLayout(box)
        self.e_drift   = _dspin(0.0, 20.0, 0.05, 2, 0.0)
        self.delta_v   = _dspin(0.0, 5000.0, 10.0, 0, 1400.0)
        self.e_induct  = _dspin(0.0, 20.0, 0.1, 2, 1.0)
        f.addRow("E_drift [kV/cm]",   self.e_drift)
        f.addRow("ΔV_THGEM [V]",      self.delta_v)
        f.addRow("E_induction [kV/cm]", self.e_induct)
        v.addWidget(box)

        box = QGroupBox("Release + output"); f = QFormLayout(box)
        self.release_mode = QComboBox()
        self.release_mode.addItems(["random (uniform over gap)", "fixed height [mm]"])
        self.release_mode.currentIndexChanged.connect(
            lambda i: self.release_h.setEnabled(i == 1))
        self.release_h = _dspin(0.0, 20.0, 0.05, 2, 0.1); self.release_h.setEnabled(False)
        self.out_dir = QLineEdit(str(THGEM_DIR / "results" / "transparency"))
        self.force = QCheckBox("Re-run cached gaps")
        f.addRow("Release", self.release_mode)
        f.addRow("Fixed height [mm]", self.release_h)
        f.addRow("Output dir", self.out_dir)
        f.addRow("", self.force)
        v.addWidget(box)

        row = QHBoxLayout()
        self.run_btn = QPushButton("Run sweep"); self.run_btn.clicked.connect(self._on_run)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self.run_btn); row.addWidget(self.stop_btn)
        v.addLayout(row)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setStyleSheet("font-family: monospace; font-size: 11px;")
        v.addWidget(self.log, 1)
        return panel

    # ── right: results ──────────────────────────────────────────────────────
    def _build_results_panel(self) -> QWidget:
        panel = QWidget(); v = QVBoxLayout(panel)
        self.canvas = MplCanvas()
        self._reset_plot()
        v.addWidget(self.canvas, 1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["gap [mm]", "anode", "bottom-Cu", "anode/(a+b)", "attached"])
        self.table.setMaximumHeight(170)
        v.addWidget(self.table)

        row = QHBoxLayout()
        self.save_csv_btn = QPushButton("Save CSV"); self.save_csv_btn.setEnabled(False)
        self.save_csv_btn.clicked.connect(self._on_save_csv)
        self.save_png_btn = QPushButton("Save PNG"); self.save_png_btn.setEnabled(False)
        self.save_png_btn.clicked.connect(self._on_save_png)
        row.addStretch(1); row.addWidget(self.save_csv_btn); row.addWidget(self.save_png_btn)
        v.addLayout(row)
        return panel

    # ── config load ─────────────────────────────────────────────────────────
    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select base config", str(CONFIG_DIR), "JSON (*.json)")
        if path:
            self.cfg_path.setText(path); self._load_config(Path(path))

    def _load_config(self, path: Path | None):
        if not path or not path.exists():
            self.cfg_summary.setText("No base config loaded — pick one.")
            return
        try:
            self._base_cfg = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Config error", f"Could not read {path}:\n{exc}")
            return
        g, fl = self._base_cfg.get("geometry", {}), self._base_cfg.get("fields", {})
        gas = self._base_cfg.get("gas", {})
        self.e_drift.setValue(fl.get("e_drift_kvcm", 0.0))
        self.delta_v.setValue(fl.get("delta_v_thgem_V", 1400.0))
        self.e_induct.setValue(fl.get("e_induction_kvcm", 1.0))
        self.cfg_summary.setText(
            f"⌀{g.get('hole_diameter_um','?')} µm / pitch {g.get('hole_pitch_um','?')} µm, "
            f"plate {g.get('plate_thickness_um','?')} µm, induction "
            f"{g.get('induction_gap_mm','?')} mm · gas {gas.get('gas1','?')}"
            f"{int(gas.get('gas1_fraction_pct',0))}/{gas.get('gas2','?')}")

    # ── run / stop ──────────────────────────────────────────────────────────
    def _effective_base_cfg(self) -> dict:
        cfg = json.loads(json.dumps(self._base_cfg))
        cfg.setdefault("fields", {})
        cfg["fields"]["e_drift_kvcm"]     = self.e_drift.value()
        cfg["fields"]["delta_v_thgem_V"]  = self.delta_v.value()
        cfg["fields"]["e_induction_kvcm"] = self.e_induct.value()
        return cfg

    def _on_run(self):
        if not self._base_cfg:
            QMessageBox.warning(self, "No config", "Load a base config first."); return
        gaps = tvd.gap_range(self.gap_min.value(), self.gap_max.value(), self.gap_step.value())
        if not gaps:
            QMessageBox.warning(self, "No gaps", "The gap range is empty."); return
        release = "random" if self.release_mode.currentIndex() == 0 else str(self.release_h.value())
        self._rows.clear(); self.table.setRowCount(0); self._reset_plot(); self.log.clear()
        self.log.appendPlainText(f"Sweeping {len(gaps)} gaps: {gaps} mm "
                                 f"({self.events.value()} electrons each)")
        self._runner = SweepRunner(self._effective_base_cfg(), gaps, self.events.value(),
                                   release, Path(self.out_dir.text()), self.force.isChecked())
        self._runner.log_line.connect(lambda s: self.log.appendPlainText(s))
        self._runner.gap_done.connect(self._on_gap_done)
        self._runner.sweep_done.connect(lambda: self._finish("Sweep complete."))
        self._runner.failed.connect(lambda m: self._finish(f"FAILED: {m}", error=True))
        self._runner.stopped.connect(lambda: self._finish("Stopped."))
        self.run_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.save_csv_btn.setEnabled(False); self.save_png_btn.setEnabled(False)
        self._runner.start()

    def _on_stop(self):
        if self._runner:
            self.log.appendPlainText("Stopping after the current gap…")
            self._runner.stop()

    def _finish(self, msg: str, error: bool = False):
        self.log.appendPlainText(msg)
        self.run_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        have = bool(self._rows)
        self.save_csv_btn.setEnabled(have); self.save_png_btn.setEnabled(have)
        if error:
            QMessageBox.warning(self, "Sweep failed", msg)

    # ── results update ──────────────────────────────────────────────────────
    def _on_gap_done(self, res: dict):
        self._rows.append(res)
        self._rows.sort(key=lambda r: r["gap_mm"])
        self.log.appendPlainText(
            f"  → gap {res['gap_mm']:.3f} mm: anode {100*res['frac_anode']:.1f}%, "
            f"bottom-Cu {100*res['frac_bottom_cu']:.1f}%, "
            f"anode/(a+b) {res['anode_over_anode_plus_bottom']:.3f}")
        self._refresh_table(); self._refresh_plot()

    def _refresh_table(self):
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            vals = [f"{r['gap_mm']:.3f}", f"{r['frac_anode']:.3f}",
                    f"{r['frac_bottom_cu']:.3f}", f"{r['anode_over_anode_plus_bottom']:.3f}",
                    f"{r['frac_attached']:.3f}"]
            for j, s in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(s))

    def _reset_plot(self):
        ax = self.canvas.ax; ax.clear()
        ax.set_xlabel("Drift gap [mm]"); ax.set_ylabel("Fraction of electrons")
        ax.set_title("Electron transparency vs drift gap (no multiplication)")
        ax.set_ylim(0, 1.05); ax.grid(True, alpha=0.3)
        self.canvas.figure.tight_layout(); self.canvas.draw()

    def _refresh_plot(self):
        ax = self.canvas.ax; ax.clear()
        x = [r["gap_mm"] for r in self._rows]
        ax.errorbar(x, [r["frac_anode"] for r in self._rows],
                    yerr=[r["sem_frac_anode"] for r in self._rows],
                    marker="o", capsize=3, label="anode fraction (of all)")
        ax.plot(x, [r["anode_over_anode_plus_bottom"] for r in self._rows],
                marker="s", ls="--", label="anode / (anode + bottom Cu)")
        ax.plot(x, [r["frac_bottom_cu"] for r in self._rows],
                marker="^", ls=":", label="bottom-Cu fraction")
        ax.set_xlabel("Drift gap [mm]"); ax.set_ylabel("Fraction of electrons")
        ax.set_title("Electron transparency vs drift gap (no multiplication)")
        ax.set_ylim(0, 1.05); ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
        self.canvas.figure.tight_layout(); self.canvas.draw()

    # ── save ────────────────────────────────────────────────────────────────
    def _on_save_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", str(Path(self.out_dir.text()) / "transparency_vs_drift.csv"),
            "CSV (*.csv)")
        if not path:
            return
        import csv as _csv
        with open(path, "w", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=list(self._rows[0].keys()))
            w.writeheader(); w.writerows(self._rows)
        self.log.appendPlainText(f"Wrote {path}")

    def _on_save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", str(Path(self.out_dir.text()) / "transparency_vs_drift.png"),
            "PNG (*.png)")
        if path:
            self.canvas.figure.savefig(path, dpi=120)
            self.log.appendPlainText(f"Wrote {path}")


def main() -> int:
    app = QApplication(sys.argv)
    win = TransparencyWindow(); win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
