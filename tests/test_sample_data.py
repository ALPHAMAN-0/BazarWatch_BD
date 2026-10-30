"""Tests for generate_sample_data.py — the seeded illustrative data."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from analytics import alert_level
from generate_sample_data import DEMO_USERS, generate
from manager import BazarManager
from storage import Storage


class SampleDataTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.end_date = date.today()
        generate(self.data_dir, self.end_date, quiet=True)

    def tearDown(self):
        self._tmp.cleanup()


class TestGeneratedFiles(SampleDataTestCase):
    def test_all_five_files_are_written(self):
        for name in (
            "products.json", "price_records.csv", "users.json",
            "baskets.json", "settings.json",
        ):
            self.assertTrue((self.data_dir / name).exists(), name)

    def test_twelve_products(self):
        storage = Storage(self.data_dir)
        self.assertEqual(len(storage.load_products()), 12)

    def test_three_markets(self):
        storage = Storage(self.data_dir)
        self.assertEqual(len(storage.load_settings()["markets"]), 3)

    def test_record_count_is_in_the_expected_range(self):
        storage = Storage(self.data_dir)
        records = storage.load_records()
        self.assertGreaterEqual(len(records), 250)
        self.assertLessEqual(len(records), 300)

    def test_four_demo_users(self):
        storage = Storage(self.data_dir)
        users = storage.load_users()
        self.assertEqual(len(users), 4)

    def test_one_admin_and_three_members(self):
        storage = Storage(self.data_dir)
        users = storage.load_users()
        admins = [u for u in users if u.role == "admin"]
        members = [u for u in users if u.role == "member"]
        self.assertEqual(len(admins), 1)
        self.assertEqual(len(members), 3)

    def test_one_basket_per_member(self):
        storage = Storage(self.data_dir)
        baskets = storage.load_baskets()
        self.assertEqual(len(baskets), 3)

    def test_reference_prices_are_empty(self):
        storage = Storage(self.data_dir)
        for product in storage.load_products():
            self.assertIsNone(product.reference_price)

    def test_all_records_load_without_warnings(self):
        storage = Storage(self.data_dir)
        products = storage.load_products()
        storage.load_records({p.product_id for p in products})
        self.assertEqual(storage.warnings, [])


class TestSeededReproducibility(unittest.TestCase):
    def test_two_runs_produce_identical_records(self):
        results = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                generate(Path(tmp), date(2026, 10, 30), quiet=True)
                storage = Storage(Path(tmp))
                records = storage.load_records()
                results.append([(r.record_id, r.product_id, r.market, r.date,
                                 r.price, r.added_by) for r in records])
        self.assertEqual(results[0], results[1])

    def test_the_planted_spike_is_reproducible(self):
        prices = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                generate(Path(tmp), date(2026, 10, 30), quiet=True)
                storage = Storage(Path(tmp))
                records = storage.load_records()
                spike = [
                    r for r in records
                    if r.product_id == "ONION"
                    and r.market == "Karwan Bazar"
                    and r.date == "2026-10-30"
                ]
                self.assertEqual(len(spike), 1)
                prices.append(spike[0].price)
        self.assertEqual(prices[0], prices[1])


class TestPlantedSpike(SampleDataTestCase):
    def test_a_spike_record_exists_on_the_last_day(self):
        storage = Storage(self.data_dir)
        records = storage.load_records()
        spikes = [
            r for r in records
            if r.product_id == "ONION"
            and r.market == "Karwan Bazar"
            and r.date == self.end_date.isoformat()
        ]
        self.assertEqual(len(spikes), 1)

    def test_the_spike_is_about_45_percent_above_normal(self):
        storage = Storage(self.data_dir)
        records = storage.load_records()
        spike = next(
            r for r in records
            if r.product_id == "ONION"
            and r.market == "Karwan Bazar"
            and r.date == self.end_date.isoformat()
        )
        onion_prices = [
            r.price for r in records
            if r.product_id == "ONION"
            and r.market == "Karwan Bazar"
            and r.date != self.end_date.isoformat()
        ]
        normal = sum(onion_prices) / len(onion_prices)
        self.assertGreater(spike.price / normal, 1.35)
        self.assertLess(spike.price / normal, 1.55)

    def test_the_spike_is_a_watch_with_no_reference_price(self):
        manager = BazarManager(self.data_dir)
        manager.login("admin", "admin123")
        spike = next(
            r for r in manager.records
            if r.product_id == "ONION"
            and r.market == "Karwan Bazar"
            and r.date == self.end_date.isoformat()
        )
        level, _z_value, pct_value = alert_level(
            spike, manager.records, manager.products, manager.settings
        )
        self.assertEqual(level, "Watch")
        self.assertIsNone(pct_value)

    def test_the_spike_becomes_a_spike_with_a_reference_price(self):
        manager = BazarManager(self.data_dir)
        manager.login("admin", "admin123")
        manager.set_reference_price("ONION", 40.0)
        spike = next(
            r for r in manager.records
            if r.product_id == "ONION"
            and r.market == "Karwan Bazar"
            and r.date == self.end_date.isoformat()
        )
        level, _z_value, pct_value = alert_level(
            spike, manager.records, manager.products, manager.settings
        )
        self.assertEqual(level, "Spike")
        self.assertIsNotNone(pct_value)


class TestDemoLogins(SampleDataTestCase):
    def test_every_demo_user_can_log_in(self):
        manager = BazarManager(self.data_dir)
        for username, password, role in DEMO_USERS:
            user = manager.login(username, password)
            self.assertEqual(user.role, role)
            manager.logout()

    def test_demo_passwords_are_hashed_in_the_file(self):
        storage = Storage(self.data_dir)
        for user in storage.load_users():
            self.assertNotEqual(user.password_hash, "admin123")
            self.assertNotEqual(user.password_hash, "rafi123")
            self.assertNotEqual(user.password_hash, "sadia123")
            self.assertNotEqual(user.password_hash, "tanvir123")


class TestRefusesToOverwrite(unittest.TestCase):
    def test_refuses_when_data_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            generate(data_dir, date.today(), quiet=True)
            with self.assertRaises(SystemExit):
                generate(data_dir, date.today(), quiet=True)

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            generate(data_dir, date.today(), quiet=True)
            generate(data_dir, date.today(), force=True, quiet=True)

    def test_end_date_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            generate(data_dir, date(2026, 10, 30), quiet=True)
            storage = Storage(data_dir)
            records = storage.load_records()
            self.assertTrue(all(r.date <= "2026-10-30" for r in records))


if __name__ == "__main__":
    unittest.main()
