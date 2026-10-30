"""Tests for analytics.py — the NumPy statistics, alert rule, cheapest market
and basket maths.

These tests follow plan section 5 exactly:

* history = prices of the same product dated on or before the record
* z = (price - mean) / std, sample std (ddof=1), only when len(history) >=
  min_history and std > 0
* pct = (price - reference) / reference * 100, only when a reference is set
* Spike if both rules fire, Watch if exactly one, Normal otherwise
* cheapest market = lowest average over the last recent_days
* basket total = numpy dot(quantities, 14-day averages) over the set
  intersection of markets that price every item
"""

import unittest
from datetime import date, timedelta

from analytics import (
    alert_level,
    basket_plan,
    budget_status,
    cheapest_market,
    history_for,
    product_statistics,
)
from models import PerishableProduct, PriceRecord, Product


def days_ago(count: int) -> str:
    return (date.today() - timedelta(days=count)).isoformat()


def make_settings(**overrides):
    settings = {
        "z_threshold": 2.0,
        "pct_threshold": 15.0,
        "perishable_z_threshold": 2.5,
        "perishable_pct_threshold": 25.0,
        "min_history": 5,
        "recent_days": 14,
        "show_bangla_names": True,
    }
    settings.update(overrides)
    return settings


def make_product(perishable=False, reference_price=None):
    product_cls = PerishableProduct if perishable else Product
    return product_cls(
        "ONION", "Onion (local)", "দেশি পেঁয়াজ", "kg", "Vegetables",
        reference_price=reference_price,
    )


def make_record(product_id, price, day_offset, market="Karwan Bazar", user="rafi",
                record_id="R00001"):
    return PriceRecord(
        record_id, product_id, market, days_ago(day_offset), price, user
    )


class TestHistory(unittest.TestCase):
    def test_history_excludes_the_record_itself(self):
        records = [
            make_record("ONION", 40, 5),
            make_record("ONION", 100, 1, record_id="R00002"),
        ]
        history = history_for(records[1], records)
        self.assertEqual([r.price for r in history], [40])

    def test_history_only_includes_earlier_dates(self):
        records = [
            make_record("ONION", 40, 5),
            make_record("ONION", 100, 1, record_id="R00002"),
        ]
        history = history_for(records[0], records)
        # The record dated later (offset 1) is in the future of offset 5.
        self.assertEqual(history, [])

    def test_history_only_includes_the_same_product(self):
        records = [
            make_record("ONION", 40, 5),
            make_record("RICE", 60, 6, record_id="R00002"),
            make_record("ONION", 100, 1, record_id="R00003"),
        ]
        history = history_for(records[2], records)
        self.assertEqual([r.price for r in history], [40])

    def test_same_day_different_user_is_included(self):
        records = [
            make_record("ONION", 40, 3, user="sadia"),
            make_record("ONION", 100, 3, user="rafi", record_id="R00002"),
        ]
        history = history_for(records[1], records)
        self.assertEqual(len(history), 1)

    def test_history_is_ordered_by_date(self):
        records = [
            make_record("ONION", 30, 9),
            make_record("ONION", 40, 5),
            make_record("ONION", 100, 1, record_id="R00003"),
        ]
        history = history_for(records[2], records)
        self.assertEqual([r.price for r in history], [30, 40])


class TestProductStatistics(unittest.TestCase):
    def test_basic_statistics(self):
        records = [
            make_record("ONION", 30, 5),
            make_record("ONION", 40, 4, record_id="R00002"),
            make_record("ONION", 50, 3, record_id="R00003"),
        ]
        stats = product_statistics("ONION", records)
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["mean"], 40.0)
        self.assertAlmostEqual(stats["median"], 40.0)
        self.assertAlmostEqual(stats["min"], 30.0)
        self.assertAlmostEqual(stats["max"], 50.0)
        self.assertAlmostEqual(stats["std"], 10.0)
        self.assertEqual(stats["latest"], 50.0)

    def test_no_records_gives_zero_count(self):
        stats = product_statistics("ONION", [])
        self.assertEqual(stats["count"], 0)
        self.assertIsNone(stats["mean"])

    def test_reference_is_included(self):
        product = make_product(reference_price=40.0)
        records = [make_record("ONION", 40, 5)]
        stats = product_statistics("ONION", records, products={"ONION": product})
        self.assertEqual(stats["reference"], 40.0)

    def test_std_of_one_record_is_zero(self):
        records = [make_record("ONION", 40, 5)]
        stats = product_statistics("ONION", records)
        self.assertEqual(stats["std"], 0.0)


class TestAlertLevel(unittest.TestCase):
    """The alert rule from plan section 5.

    The history below has mean 39.17 and sample std 7.36, so a price of 55
    gives z = 2.15: above the normal limit of 2.0 but below the perishable
    limit of 2.5.  That is what makes the perishable override testable.
    """

    HISTORY = (30, 35, 40, 45, 50, 35)

    def make_history(self, prices=None):
        """A history of prices, then a record that jumps."""
        records = []
        for index, price in enumerate(prices or self.HISTORY):
            records.append(
                make_record("ONION", price, 10 - index, record_id=f"R{index:05d}")
            )
        return records

    def test_normal_when_neither_rule_fires(self):
        records = self.make_history()
        record = make_record("ONION", 40, 0, record_id="R99999")
        level, z, pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertEqual(level, "Normal")
        self.assertIsNotNone(z)
        self.assertIsNone(pct)

    def test_spike_when_both_rules_fire(self):
        records = self.make_history()
        record = make_record("ONION", 100, 0, record_id="R99999")
        product = make_product(reference_price=40.0)
        level, z, pct = alert_level(
            record, records, {"ONION": product}, make_settings()
        )
        self.assertEqual(level, "Spike")
        self.assertGreaterEqual(z, 2.0)
        self.assertGreaterEqual(pct, 15.0)

    def test_watch_when_only_the_z_rule_fires(self):
        records = self.make_history()
        record = make_record("ONION", 100, 0, record_id="R99999")
        level, _z, pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertEqual(level, "Watch")
        self.assertIsNone(pct)

    def test_watch_when_only_the_percentage_rule_fires(self):
        # A long flat history means a huge price gives a small z, so only the
        # reference rule can fire.
        records = self.make_history([40] * 30)
        record = make_record("ONION", 50, 0, record_id="R99999")
        product = make_product(reference_price=40.0)
        level, z, pct = alert_level(
            record, records, {"ONION": product}, make_settings()
        )
        self.assertEqual(level, "Watch")
        self.assertIsNone(z)
        self.assertGreaterEqual(pct, 15.0)

    def test_no_reference_means_at_most_watch(self):
        records = self.make_history()
        record = make_record("ONION", 100, 0, record_id="R99999")
        level, _z, pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertEqual(level, "Watch")
        self.assertIsNone(pct)

    def test_too_little_history_means_no_z_score(self):
        records = self.make_history([40, 41])
        record = make_record("ONION", 100, 0, record_id="R99999")
        level, z, _pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertIsNone(z)
        self.assertEqual(level, "Normal")

    def test_min_history_boundary_is_inclusive(self):
        # Exactly min_history (5) earlier records gives a z-score.
        records = self.make_history([40, 41, 39, 40, 42])
        record = make_record("ONION", 100, 0, record_id="R99999")
        _level, z, _pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertIsNotNone(z)

    def test_zero_standard_deviation_means_no_z_score(self):
        records = self.make_history([40, 40, 40, 40, 40])
        record = make_record("ONION", 100, 0, record_id="R99999")
        level, z, _pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertIsNone(z)
        self.assertEqual(level, "Normal")

    def test_normal_product_flags_a_moderate_jump(self):
        # z = 2.15 is above the normal limit of 2.0.
        records = self.make_history()
        record = make_record("ONION", 55, 0, record_id="R99999")
        level, z, _pct = alert_level(
            record, records, {"ONION": make_product()}, make_settings()
        )
        self.assertEqual(level, "Watch")
        self.assertAlmostEqual(z, 2.15, places=1)

    def test_perishable_tolerates_the_same_jump(self):
        # The same price and history: z = 2.15 is below the perishable limit
        # of 2.5, so the perishable product stays Normal.
        records = self.make_history()
        record = make_record("ONION", 55, 0, record_id="R99999")
        product = make_product(perishable=True)
        level, _z, _pct = alert_level(
            record, records, {"ONION": product}, make_settings()
        )
        self.assertEqual(level, "Normal")

    def test_perishable_flags_a_bigger_jump(self):
        # z = 2.56 is above the perishable limit of 2.5.
        records = self.make_history()
        record = make_record("ONION", 58, 0, record_id="R99999")
        product = make_product(perishable=True)
        level, _z, _pct = alert_level(
            record, records, {"ONION": product}, make_settings()
        )
        self.assertEqual(level, "Watch")

    def test_perishable_uses_the_looser_percentage_limit(self):
        records = self.make_history()
        # 16% over the reference: above the 15% normal limit, below the 25%
        # perishable limit.
        record = make_record("ONION", 46.4, 0, record_id="R99999")
        normal_level, _, _ = alert_level(
            record, records, {"ONION": make_product(reference_price=40.0)},
            make_settings(),
        )
        perishable_level, _, _ = alert_level(
            record, records,
            {"ONION": make_product(perishable=True, reference_price=40.0)},
            make_settings(),
        )
        self.assertEqual(normal_level, "Watch")
        self.assertEqual(perishable_level, "Normal")

    def test_missing_product_gives_normal(self):
        records = self.make_history()
        record = make_record("ONION", 100, 0, record_id="R99999")
        level, _z, _pct = alert_level(record, records, {}, make_settings())
        self.assertEqual(level, "Normal")


class TestCheapestMarket(unittest.TestCase):
    def test_lowest_average_wins(self):
        records = [
            make_record("ONION", 40, 2, market="Karwan Bazar"),
            make_record("ONION", 45, 1, market="Shwapno", record_id="R00002"),
        ]
        market, average = cheapest_market(
            "ONION", records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(market, "Karwan Bazar")
        self.assertAlmostEqual(average, 40.0)

    def test_old_records_are_ignored(self):
        records = [
            make_record("ONION", 10, 30, market="Karwan Bazar"),
            make_record("ONION", 45, 1, market="Shwapno", record_id="R00002"),
        ]
        market, average = cheapest_market(
            "ONION", records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(market, "Shwapno")
        self.assertAlmostEqual(average, 45.0)

    def test_future_records_are_ignored(self):
        records = [
            make_record("ONION", 10, -5, market="Karwan Bazar"),
            make_record("ONION", 45, 1, market="Shwapno", record_id="R00002"),
        ]
        market, _average = cheapest_market(
            "ONION", records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(market, "Shwapno")

    def test_average_over_several_records(self):
        records = [
            make_record("ONION", 40, 3, market="Karwan Bazar"),
            make_record("ONION", 50, 2, market="Karwan Bazar", record_id="R00002"),
            make_record("ONION", 60, 1, market="Shwapno", record_id="R00003"),
        ]
        market, average = cheapest_market(
            "ONION", records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(market, "Karwan Bazar")
        self.assertAlmostEqual(average, 45.0)

    def test_no_recent_data_returns_none(self):
        records = [make_record("ONION", 40, 30, market="Karwan Bazar")]
        market, average = cheapest_market(
            "ONION", records, ["Karwan Bazar"], 14
        )
        self.assertIsNone(market)
        self.assertIsNone(average)

    def test_no_records_at_all_returns_none(self):
        market, _average = cheapest_market("ONION", [], ["Karwan Bazar"], 14)
        self.assertIsNone(market)

    def test_market_without_data_is_skipped(self):
        records = [make_record("ONION", 45, 1, market="Shwapno")]
        market, _average = cheapest_market(
            "ONION", records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(market, "Shwapno")


class TestBasketPlan(unittest.TestCase):
    def make_records(self):
        return [
            make_record("ONION", 40, 2, market="Karwan Bazar"),
            make_record("RICE", 50, 2, market="Karwan Bazar", record_id="R00002"),
            make_record("ONION", 60, 1, market="Shwapno", record_id="R00003"),
            make_record("RICE", 55, 1, market="Shwapno", record_id="R00004"),
        ]

    def test_totals_per_market(self):
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            self.make_records(),
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        # Karwan: 2*40 + 3*50 = 230.  Shwapno: 2*60 + 3*55 = 285.
        self.assertAlmostEqual(plan["totals"]["Karwan Bazar"], 230.0)
        self.assertAlmostEqual(plan["totals"]["Shwapno"], 285.0)

    def test_best_single_market_is_the_lowest_total(self):
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            self.make_records(),
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        self.assertEqual(plan["best_market"], "Karwan Bazar")
        self.assertAlmostEqual(plan["best_total"], 230.0)

    def test_split_plan_uses_each_items_cheapest_market(self):
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            self.make_records(),
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        self.assertEqual(plan["split_plan"]["ONION"]["market"], "Karwan Bazar")
        self.assertEqual(plan["split_plan"]["RICE"]["market"], "Karwan Bazar")
        self.assertAlmostEqual(plan["split_total"], 230.0)

    def test_saving_is_the_difference(self):
        records = self.make_records()
        # Make ONION much cheaper at Shwapno so splitting genuinely saves.
        records[2] = make_record("ONION", 20, 1, market="Shwapno", record_id="R00003")
        plan = basket_plan(
            {"ONION": 5.0, "RICE": 1.0},
            records,
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        # Karwan total: 5*40 + 1*50 = 250.  Shwapno total: 5*20 + 1*55 = 155.
        # Shwapno is the better single market at 155.
        self.assertEqual(plan["best_market"], "Shwapno")
        self.assertAlmostEqual(plan["best_total"], 155.0)
        # The split plan buys ONION at Shwapno (20) and RICE at Karwan (50):
        # 5*20 + 1*50 = 150, so splitting saves 155 - 150 = 5.
        self.assertEqual(plan["split_plan"]["ONION"]["market"], "Shwapno")
        self.assertEqual(plan["split_plan"]["RICE"]["market"], "Karwan Bazar")
        self.assertAlmostEqual(plan["split_total"], 150.0)
        self.assertAlmostEqual(plan["saving"], 5.0)

    def test_saving_is_zero_when_one_market_is_cheapest_for_everything(self):
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            self.make_records(),
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        self.assertAlmostEqual(plan["saving"], 0.0)

    def test_market_missing_an_item_is_excluded(self):
        # Shwapno has no RICE price, so it is not in the intersection.
        records = [
            make_record("ONION", 40, 2, market="Karwan Bazar"),
            make_record("RICE", 50, 2, market="Karwan Bazar", record_id="R00002"),
            make_record("ONION", 60, 1, market="Shwapno", record_id="R00003"),
        ]
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            records,
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        self.assertNotIn("Shwapno", plan["totals"])
        self.assertEqual(plan["best_market"], "Karwan Bazar")

    def test_item_with_no_recent_price_is_listed_and_left_out(self):
        records = [
            make_record("ONION", 40, 2, market="Karwan Bazar"),
        ]
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            records,
            ["Karwan Bazar"],
            14,
        )
        self.assertIn("RICE", plan["unpriced_items"])
        self.assertNotIn("RICE", plan["split_plan"])

    def test_no_market_prices_everything(self):
        records = [make_record("ONION", 40, 2, market="Karwan Bazar")]
        plan = basket_plan(
            {"ONION": 2.0, "RICE": 3.0},
            records,
            ["Karwan Bazar", "Shwapno"],
            14,
        )
        self.assertIsNone(plan["best_market"])
        self.assertIsNone(plan["best_total"])
        self.assertEqual(plan["totals"], {})

    def test_empty_basket(self):
        plan = basket_plan({}, self.make_records(), ["Karwan Bazar"], 14)
        self.assertIsNone(plan["best_market"])
        self.assertEqual(plan["totals"], {})

    def test_single_item_basket(self):
        records = [
            make_record("ONION", 40, 2, market="Karwan Bazar"),
            make_record("ONION", 60, 1, market="Shwapno", record_id="R00002"),
        ]
        plan = basket_plan(
            {"ONION": 2.0}, records, ["Karwan Bazar", "Shwapno"], 14
        )
        self.assertEqual(plan["best_market"], "Karwan Bazar")
        self.assertAlmostEqual(plan["best_total"], 80.0)
        self.assertAlmostEqual(plan["saving"], 0.0)


class TestBudgetStatus(unittest.TestCase):
    def test_within_budget(self):
        status, message = budget_status(100.0, 1000.0)
        self.assertEqual(status, "Within budget")
        self.assertIn("100", message)

    def test_close_to_budget(self):
        status, _message = budget_status(950.0, 1000.0)
        self.assertEqual(status, "Close to budget")

    def test_over_budget(self):
        status, message = budget_status(1200.0, 1000.0)
        self.assertEqual(status, "Over budget")
        self.assertIn("200", message)

    def test_exactly_at_budget_is_close(self):
        # The plan puts 90-100% in the "Close to budget" band, so spending
        # exactly the whole budget lands there, not in "Within budget".
        status, _message = budget_status(1000.0, 1000.0)
        self.assertEqual(status, "Close to budget")

    def test_exactly_ninety_percent_is_within(self):
        status, _message = budget_status(900.0, 1000.0)
        self.assertEqual(status, "Within budget")

    def test_just_over_ninety_percent_is_close(self):
        status, _message = budget_status(901.0, 1000.0)
        self.assertEqual(status, "Close to budget")

    def test_zero_budget_with_zero_total(self):
        status, _message = budget_status(0.0, 0.0)
        self.assertEqual(status, "Within budget")

    def test_zero_budget_with_spend(self):
        status, _message = budget_status(50.0, 0.0)
        self.assertEqual(status, "Over budget")


if __name__ == "__main__":
    unittest.main()
