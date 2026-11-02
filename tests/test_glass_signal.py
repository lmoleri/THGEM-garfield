"""Fast physics/accounting/paired-analysis checks; integration runs use the CLI."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

import numpy as np

spec = importlib.util.spec_from_file_location("glass", Path(__file__).parents[1]/"scripts/glass_signal_study.py")
glass = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glass)


class GlassSignalTests(unittest.TestCase):
    def test_snapshot_conservation(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"snapshots.csv"
            header = "seed,path,attachment,time_ns,species,charge_e,x_cm,y_cm,z_cm,status\n"
            pair = "501,0,fixed,10000,electron,-1,0,0,0,moving\n501,0,fixed,10000,primary_ion,1,0,0,0,moving\n"
            p.write_text(header+pair)
            self.assertEqual(glass.validate_snapshots(p), 0.)
            p.write_text(header+pair.replace("electron,-1", "electron,-2"))
            with self.assertRaises(ValueError):
                glass.validate_snapshots(p)

    def test_full_contact_rc_numerical_relaxation(self):
        # Integrate the surface-node RC equation independently in units of tau.
        for gap in [.1, .2, .5, 1, 2]:
            p = glass.planar(gap, .8, 8, 1e10, 0)
            node_voltage = 1.
            dt = .001
            for _ in range(20000):
                node_voltage -= dt*node_voltage
            transferred = 1-(1-p["prompt"])*node_voltage
            self.assertAlmostEqual(transferred, 1., places=8)
            p2 = glass.planar(gap, .8, 8, 1e10, p["tau_s"]*20e9)
            self.assertAlmostEqual(transferred, p2["recovered"], places=8)

    def test_material_limits(self):
        self.assertEqual(glass.planar(.1, 0, 8, 1e10, 10000)["recovered"], 1.)
        self.assertGreater(glass.planar(.1, .8, 1e8, 1e10, 0)["prompt"], .999999)
        for gap in glass.GAPS:
            for eps in glass.EPSILONS:
                self.assertLess(glass.planar(gap,.8,eps,1e10,10000)["conservative_relative_bound"], .01)

    def test_signed_charge_and_pairing(self):
        metal = {(501, i): np.array([-10., 8., 1., 1.])*(i+1) for i in range(20)}
        readout = {(501, i): np.array([-5., 8., -4., 1.])*(i+1) for i in range(20)}
        r = glass.paired(metal, readout)
        self.assertTrue(r["valid"])
        self.assertAlmostEqual(r["F"], .5)
        self.assertAlmostEqual(r["top_factor"], 1.)
        self.assertAlmostEqual(r["F_hi"]-r["F_lo"], 0.)

    def test_bad_pairs_and_denominators(self):
        with self.assertRaises(ValueError):
            glass.paired({(1,0): np.ones(4)}, {(2,0): np.ones(4)})
        zero = {(1,0): np.array([-1.,0.,1.,0.])}
        self.assertFalse(glass.paired(zero, zero)["valid"])
        a = {(1,0): np.array([-1.,1.,0.,0.])}
        b = {(1,0): np.array([1.,-1.,0.,0.])}
        self.assertTrue(glass.paired(a,b)["polarity_change"])


if __name__ == "__main__":
    unittest.main()
