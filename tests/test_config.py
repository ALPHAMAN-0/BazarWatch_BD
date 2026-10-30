"""Tests for config.py — paths, tuples and default settings."""

import unittest

import config


class TestConfigTuples(unittest.TestCase):
    def test_units_is_non_empty_tuple(self):
        self.assertIsInstance(config.UNITS, tuple)
        self.assertGreater(len(config.UNITS), 0)

    def test_categories_contains_planned_categories(self):
        for name in ("Grains", "Pulses", "Oil", "Grocery", "Vegetables", "Spices", "Protein"):
            self.assertIn(name, config.CATEGORIES)

    def test_alert_levels(self):
        self.assertEqual(config.ALERT_LEVELS, ("Normal", "Watch", "Spike"))

    def test_roles(self):
        self.assertEqual(config.ROLES, ("admin", "member"))

    def test_default_markets(self):
        self.assertIn("Karwan Bazar", config.DEFAULT_MARKETS)
        self.assertIn("Mohammadpur Krishi Market", config.DEFAULT_MARKETS)
        self.assertIn("Shwapno", config.DEFAULT_MARKETS)


class TestDefaultSettings(unittest.TestCase):
    def test_alert_thresholds(self):
        self.assertEqual(config.DEFAULT_SETTINGS["z_threshold"], 2.0)
        self.assertEqual(config.DEFAULT_SETTINGS["pct_threshold"], 15.0)
        self.assertEqual(config.DEFAULT_SETTINGS["perishable_z_threshold"], 2.5)
        self.assertEqual(config.DEFAULT_SETTINGS["perishable_pct_threshold"], 25.0)

    def test_min_history_and_recent_days(self):
        self.assertEqual(config.DEFAULT_SETTINGS["min_history"], 5)
        self.assertEqual(config.DEFAULT_SETTINGS["recent_days"], 14)

    def test_show_bangla_names_defaults_true(self):
        self.assertTrue(config.DEFAULT_SETTINGS["show_bangla_names"])

    def test_markets_default(self):
        self.assertEqual(list(config.DEFAULT_SETTINGS["markets"]), list(config.DEFAULT_MARKETS))

    def test_default_settings_has_every_expected_key(self):
        expected = {
            "markets",
            "z_threshold",
            "pct_threshold",
            "perishable_z_threshold",
            "perishable_pct_threshold",
            "min_history",
            "recent_days",
            "show_bangla_names",
        }
        self.assertEqual(expected, set(config.DEFAULT_SETTINGS))


class TestProductCatalogue(unittest.TestCase):
    def test_twelve_products_are_seeded(self):
        self.assertEqual(len(config.DEFAULT_PRODUCTS), 12)

    def test_known_product_ids_present(self):
        ids = {p["product_id"] for p in config.DEFAULT_PRODUCTS}
        for product_id in (
            "RICE", "ATTA", "DAL", "OIL", "SUGAR", "ONION",
            "POTATO", "GARLIC", "CHILLI", "EGG", "CHICKEN", "PANGAS",
        ):
            self.assertIn(product_id, ids)

    def test_reference_prices_start_empty(self):
        for product in config.DEFAULT_PRODUCTS:
            self.assertIsNone(product["reference_price"])

    def test_perishables_are_flagged(self):
        perishables = {p["product_id"] for p in config.DEFAULT_PRODUCTS if p["perishable"]}
        self.assertEqual(perishables, {"ONION", "POTATO", "CHILLI", "CHICKEN", "PANGAS"})

    def test_bangla_names_present(self):
        for product in config.DEFAULT_PRODUCTS:
            self.assertTrue(product["name_bn"].strip())


class TestPaths(unittest.TestCase):
    def test_data_dir_is_relative_to_code(self):
        self.assertTrue(config.DATA_DIR.is_absolute())
        self.assertEqual(config.DATA_DIR.name, "data")

    def test_reports_dir_exists_relative_to_code(self):
        self.assertEqual(config.REPORTS_DIR.name, "reports")

    def test_data_file_names(self):
        self.assertEqual(config.PRODUCTS_FILE.name, "products.json")
        self.assertEqual(config.RECORDS_FILE.name, "price_records.csv")
        self.assertEqual(config.USERS_FILE.name, "users.json")
        self.assertEqual(config.BASKETS_FILE.name, "baskets.json")
        self.assertEqual(config.SETTINGS_FILE.name, "settings.json")


if __name__ == "__main__":
    unittest.main()
