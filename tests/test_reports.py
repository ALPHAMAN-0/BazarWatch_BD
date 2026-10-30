"""Tests for reports.py — the weekly text report."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from models import PerishableProduct, PriceRecord, Product
from reports import build_weekly_report, save_weekly_report, weekly_report


def days_ago(count: int) -> str:
    return (date.today() - timedelta(days=count)).isoformat()


def make_product(perishable=False, reference_price=None):
    product_cls = PerishableProduct if perishable else Product
    return product_cls(
        "ONION", "Onion (local)", "দেশি পেঁয়াজ", "kg", "Vegetables",
        reference_price=reference_price,
    )


def make_products():
    return {
        "ONION": make_product(),
        "RICE": Product(
            "RICE", "Rice", "চাল", "kg", "Grains", reference_price=50.0
        ),
    }


def make_records():
    """A week of records: this week and the week before."""
    return [
        # This week
        PriceRecord("R00001", "ONION", "Karwan Bazar", days_ago(1), 45.0, "rafi"),
        PriceRecord("R00002", "ONION", "Shwapno", days_ago(2), 50.0, "sadia"),
        PriceRecord("R00003", "RICE", "Karwan Bazar", days_ago(1), 52.0, "rafi"),
        # Previous week
        PriceRecord("R00004", "ONION", "Karwan Bazar", days_ago(9), 40.0, "rafi"),
        PriceRecord("R00005", "RICE", "Karwan Bazar", days_ago(8), 50.0, "rafi"),
        # Too old to matter
        PriceRecord("R00006", "ONION", "Karwan Bazar", days_ago(30), 10.0, "rafi"),
    ]


def make_settings(**overrides):
    settings = {
        "z_threshold": 2.0,
        "pct_threshold": 15.0,
        "perishable_z_threshold": 2.5,
        "perishable_pct_threshold": 25.0,
        "min_history": 5,
        "recent_days": 14,
        "show_bangla_names": True,
        "markets": ["Karwan Bazar", "Shwapno"],
    }
    settings.update(overrides)
    return settings


class TestBuildWeeklyReport(unittest.TestCase):
    def test_report_is_a_string(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)

    def test_report_contains_a_header(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("BazarWatch", text)
        self.assertIn("Weekly Report", text)

    def test_report_contains_the_date_range(self):
        end = date.today()
        start = end - timedelta(days=6)
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn(start.isoformat(), text)
        self.assertIn(end.isoformat(), text)

    def test_report_lists_the_record_count(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("3", text)

    def test_report_lists_prices_per_product(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("Onion", text)
        self.assertIn("Rice", text)

    def test_report_shows_the_percentage_change(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        # ONION went from 40 to an average of 47.5, an increase.
        self.assertIn("%", text)

    def test_report_lists_the_cheapest_market(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("Karwan Bazar", text)

    def test_report_lists_products_not_priced_this_week(self):
        products = dict(make_products())
        products["EGG"] = make_product()
        text = build_weekly_report(
            make_records(), products, make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("not priced", text.lower())

    def test_report_mentions_the_sample_data_note(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("illustrative", text.lower())

    def test_report_with_no_records_still_builds(self):
        text = build_weekly_report(
            [], make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("Weekly Report", text)

    def test_report_includes_spike_and_watch_sections(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("Spike", text)
        self.assertIn("Watch", text)

    def test_report_lists_top_contributors(self):
        text = build_weekly_report(
            make_records(), make_products(), make_settings(), markets=["Karwan Bazar", "Shwapno"]
        )
        self.assertIn("rafi", text)


class TestSaveWeeklyReport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_report_is_saved_with_the_dated_filename(self):
        path = save_weekly_report(
            make_records(), make_products(), make_settings(),
            markets=["Karwan Bazar", "Shwapno"], reports_dir=self.reports_dir,
        )
        expected = f"weekly_report_{date.today().isoformat()}.txt"
        self.assertEqual(path.name, expected)
        self.assertTrue(path.exists())

    def test_saved_report_has_the_same_content(self):
        path = save_weekly_report(
            make_records(), make_products(), make_settings(),
            markets=["Karwan Bazar", "Shwapno"], reports_dir=self.reports_dir,
        )
        content = path.read_text(encoding="utf-8")
        self.assertIn("Weekly Report", content)

    def test_reports_dir_is_created_if_missing(self):
        target = self.reports_dir / "nested" / "reports"
        path = save_weekly_report(
            make_records(), make_products(), make_settings(),
            markets=["Karwan Bazar", "Shwapno"], reports_dir=target,
        )
        self.assertTrue(path.exists())


class TestWeeklyReportAlias(unittest.TestCase):
    def test_weekly_report_is_callable(self):
        text = weekly_report(
            make_records(), make_products(), make_settings(),
            markets=["Karwan Bazar", "Shwapno"],
        )
        self.assertIn("Weekly Report", text)


if __name__ == "__main__":
    unittest.main()
