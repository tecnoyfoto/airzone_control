from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "airzone_control"
    / "energy.py"
)
SPEC = importlib.util.spec_from_file_location("airzone_energy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ENERGY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENERGY)


class UpdateIntervalTotalsTests(unittest.TestCase):
    def test_seeds_and_adds_each_period_once(self) -> None:
        stored: dict = {}
        first = {
            "energy_acc": 0.309,
            "energy_period_end_dt": "2026-09-15T01:59:40.000Z",
        }
        self.assertTrue(ENERGY.update_interval_totals(stored, "meter", first))
        self.assertEqual(first["energy_acc_total"], 0.309)

        same_period = {
            "energy_acc": 0.999,
            "energy_period_end_dt": "2026-09-15T01:59:40.000Z",
        }
        self.assertFalse(
            ENERGY.update_interval_totals(stored, "meter", same_period)
        )
        self.assertEqual(same_period["energy_acc_total"], 0.309)

        next_period = {
            "energy_acc": 0.431,
            "energy_period_end_dt": "2026-09-15T02:59:40.000Z",
        }
        self.assertTrue(
            ENERGY.update_interval_totals(stored, "meter", next_period)
        )
        self.assertEqual(next_period["energy_acc_total"], 0.74)

    def test_ignores_older_invalid_and_negative_intervals(self) -> None:
        stored = {
            "meter": {
                "energy_acc": {
                    "period": "2026-09-15T02:59:40.000Z",
                    "total": 1.25,
                }
            }
        }
        older = {
            "energy_acc": 5,
            "energy_period_end_dt": "2026-09-15T01:59:40.000Z",
        }
        self.assertFalse(ENERGY.update_interval_totals(stored, "meter", older))
        self.assertEqual(older["energy_acc_total"], 1.25)

        invalid = {"energy_acc": -1, "energy_period_end_dt": "not-a-date"}
        self.assertFalse(
            ENERGY.update_interval_totals(stored, "meter", invalid)
        )
        self.assertNotIn("energy_acc_total", invalid)

    def test_tracks_import_return_and_phases_independently(self) -> None:
        stored: dict = {}
        meter = {
            "energy_acc": 1.2,
            "energy_ret": 0.2,
            "energy1_acc": 1.1,
            "energy2_acc": 0.1,
            "energy_period_end_dt": "2026-09-15T02:59:40Z",
            "energy1_period_end_dt": "2026-09-15T02:59:40Z",
            "energy2_period_end_dt": "2026-09-15T02:59:40Z",
        }
        self.assertTrue(ENERGY.update_interval_totals(stored, "meter", meter))
        self.assertEqual(meter["energy_acc_total"], 1.2)
        self.assertEqual(meter["energy_ret_total"], 0.2)
        self.assertEqual(meter["energy1_acc_total"], 1.1)
        self.assertEqual(meter["energy2_acc_total"], 0.1)

    def test_supports_documented_latest_hour_fields(self) -> None:
        stored: dict = {}
        meter = {
            "energy_hour_latest": 0.42,
            "energy_hour_latest_date": "2026-09-15T03:00:00Z",
        }
        self.assertTrue(ENERGY.update_interval_totals(stored, "meter", meter))
        self.assertEqual(meter["energy_hour_total"], 0.42)


if __name__ == "__main__":
    unittest.main()
