"""Tests for the defects the review pass found after the main build.

Each test here names the behaviour that was wrong.  They were written first
(RED), then the code was changed to make them pass (GREEN).
"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from manager import BazarManager
from models import PriceRecord, Product
from reports import build_weekly_report
from validators import ValidationError


def days_before(end: date, count: int) -> str:
    return (end - timedelta(days=count)).isoformat()


class TestReportUsesItsOwnEndDate(unittest.TestCase):
    """The cheapest-market section must match the week the report covers."""

    def setUp(self):
        self.end = date(2026, 3, 15)
        self.products = {"ONION": Product("ONION", "Onion", "পেঁয়াজ", "kg", "Vegetables")}
        self.settings = {
            "z_threshold": 2.0,
            "pct_threshold": 15.0,
            "perishable_z_threshold": 2.5,
            "perishable_pct_threshold": 25.0,
            "min_history": 5,
            "recent_days": 14,
            "show_bangla_names": True,
            "markets": ["Karwan Bazar", "Shwapno"],
        }

    def test_the_cheapest_market_is_looked_up_as_of_the_report_date(self):
        # Around the report date, Karwan Bazar is the cheap market.
        # Much later, Shwapno is the cheap market.
        records = [
            PriceRecord("R1", "ONION", "Karwan Bazar", days_before(self.end, 2), 40.0, "rafi"),
            PriceRecord("R2", "ONION", "Shwapno", days_before(self.end, 3), 60.0, "rafi"),
        ]
        text = build_weekly_report(
            records, self.products, self.settings,
            markets=["Karwan Bazar", "Shwapno"], end_date=self.end,
        )
        cheapest = _cheapest_line(text)
        self.assertIn("Karwan Bazar", cheapest)

    def test_a_report_for_an_older_week_ignores_later_prices(self):
        # Shwapno only became the cheap market after the report week.
        records = [
            PriceRecord("R1", "ONION", "Karwan Bazar", days_before(self.end, 2), 40.0, "rafi"),
            PriceRecord("R2", "ONION", "Shwapno", days_before(self.end, 3), 60.0, "rafi"),
            PriceRecord("R3", "ONION", "Shwapno", "2026-09-01", 10.0, "rafi"),
            PriceRecord("R4", "ONION", "Karwan Bazar", "2026-09-01", 90.0, "rafi"),
        ]
        text = build_weekly_report(
            records, self.products, self.settings,
            markets=["Karwan Bazar", "Shwapno"], end_date=self.end,
        )
        cheapest = _cheapest_line(text)
        self.assertIn("Karwan Bazar", cheapest)
        self.assertNotIn("Shwapno", cheapest)


def _cheapest_line(text: str) -> str:
    """The line of the report that names the cheapest market."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "CHEAPEST MARKET" in line:
            return "\n".join(lines[index : index + 6])
    raise AssertionError("The report has no cheapest-market section.")


class TestDateFiltersAreValidated(unittest.TestCase):
    """A malformed date filter must be refused, not silently mis-compared."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.manager = BazarManager(self.data_dir)
        self.manager.create_admin("admin", "admin123")
        self.manager.login("admin", "admin123")
        self.manager.add_record("ONION", "Karwan Bazar", "2026-10-05", 40)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_malformed_from_date_is_refused(self):
        with self.assertRaises(ValidationError):
            self.manager.filter_records(date_from="not-a-date")

    def test_a_malformed_to_date_is_refused(self):
        with self.assertRaises(ValidationError):
            self.manager.filter_records(date_to="2026-13-45")

    def test_a_valid_range_still_filters(self):
        results = self.manager.filter_records(
            date_from="2026-10-01", date_to="2026-10-31"
        )
        self.assertEqual(len(results), 1)

    def test_an_empty_filter_is_ignored(self):
        results = self.manager.filter_records(date_from="", date_to="")
        self.assertEqual(len(results), 1)


class TestSettingsKeepTheirType(unittest.TestCase):
    """The settings that count something are stored as whole numbers."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.manager = BazarManager(self.data_dir)
        self.manager.create_admin("admin", "admin123")
        self.manager.login("admin", "admin123")

    def tearDown(self):
        self._tmp.cleanup()

    def test_min_history_is_a_whole_number(self):
        self.manager.update_settings({"min_history": 6})
        self.assertIsInstance(self.manager.settings["min_history"], int)
        self.assertEqual(self.manager.settings["min_history"], 6)

    def test_recent_days_is_a_whole_number(self):
        self.manager.update_settings({"recent_days": 20})
        self.assertIsInstance(self.manager.settings["recent_days"], int)
        self.assertEqual(self.manager.settings["recent_days"], 20)

    def test_the_file_holds_whole_numbers(self):
        self.manager.update_settings({"min_history": 7, "recent_days": 21})
        stored = (self.data_dir / "settings.json").read_text(encoding="utf-8")
        self.assertIn('"min_history": 7', stored)
        self.assertIn('"recent_days": 21', stored)
        self.assertNotIn("7.0", stored)
        self.assertNotIn("21.0", stored)

    def test_the_thresholds_stay_floats(self):
        self.manager.update_settings({"z_threshold": 3})
        self.assertIsInstance(self.manager.settings["z_threshold"], float)


class TestMissingSettingsDoNotCrashTheAlerts(unittest.TestCase):
    """A hand-edited settings file must not break the alert code."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.manager = BazarManager(self.data_dir)
        self.manager.create_admin("admin", "admin123")
        self.manager.login("admin", "admin123")

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_missing_threshold_falls_back_to_the_default(self):
        del self.manager.settings["z_threshold"]
        record = self.manager.add_record(
            "ONION", "Karwan Bazar", "2026-10-05", 40
        )
        level, z_value, _ = self.manager.alert_level_for(record)
        self.assertIn(level, {"Normal", "Watch", "Spike"})

    def test_a_null_threshold_falls_back_to_the_default(self):
        self.manager.settings["z_threshold"] = None
        record = self.manager.add_record(
            "ONION", "Karwan Bazar", "2026-10-05", 40
        )
        level, z_value, _ = self.manager.alert_level_for(record)
        self.assertIn(level, {"Normal", "Watch", "Spike"})

    def test_a_missing_perishable_threshold_falls_back_to_the_default(self):
        del self.manager.settings["perishable_pct_threshold"]
        record = self.manager.add_record(
            "ONION", "Karwan Bazar", "2026-10-05", 40
        )
        level, z_value, _ = self.manager.alert_level_for(record)
        self.assertIn(level, {"Normal", "Watch", "Spike"})


if __name__ == "__main__":
    unittest.main()
