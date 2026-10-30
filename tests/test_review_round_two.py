"""Tests for the defects the second review pass found.

Each test here failed before the fix that goes with it.  They are grouped
by the defect they cover, and each one names the behaviour that was
wrong, so a later reader can see what the fix was for.
"""

import json
import tempfile
import unittest
from pathlib import Path

import config
from auth import hash_password
from manager import BazarManager
from models import Product
from storage import Storage
from validators import ValidationError


class DataFolderTestCase(unittest.TestCase):
    """Base class giving each test its own temp data folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, content: str) -> Path:
        path = self.data_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_products(self, *product_ids: str) -> None:
        """A products file holding exactly these product IDs."""
        entries = [
            {
                "product_id": product_id,
                "name": product_id.title(),
                "name_bn": "",
                "unit": "kg",
                "category": "Grocery",
                "reference_price": 50.0,
                "perishable": False,
            }
            for product_id in product_ids
        ]
        self.write("products.json", json.dumps(entries))

    def write_users(self) -> None:
        """A users file with one Admin whose password is known."""
        salt, digest = hash_password("admin123")
        self.write(
            "users.json",
            json.dumps(
                [
                    {
                        "username": "admin",
                        "role": "admin",
                        "salt": salt,
                        "password_hash": digest,
                        "created_at": "2026-01-01",
                        "last_login": None,
                    }
                ]
            ),
        )

    def write_settings(self) -> None:
        self.write("settings.json", json.dumps(dict(config.DEFAULT_SETTINGS)))

    def write_baskets(self) -> None:
        self.write("baskets.json", "[]")

    def write_records(self, *rows: str) -> None:
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n" + "".join(rows),
        )


class TestAnOrphanedRecordIsNotDestroyed(DataFolderTestCase):
    """A row naming a product that is not in the catalogue.

    The row is skipped, so it never reaches the in-memory list.  When the
    file is written back out, the row must still be there: the user can
    restore the product later, and until then the history is not theirs
    to lose.
    """

    def make_manager(self) -> BazarManager:
        self.write_products("ONION", "DAL")
        self.write_users()
        self.write_settings()
        self.write_baskets()
        self.write_records(
            "R00001,RICE,Karwan Bazar,2026-10-05,40.0,rafi\n",
            "R00002,ONION,Karwan Bazar,2026-10-05,45.0,rafi\n",
        )
        manager = BazarManager(self.data_dir)
        manager.login("admin", "admin123")
        return manager

    def test_the_orphan_row_is_still_in_the_file_after_a_save(self):
        manager = self.make_manager()
        manager.add_record("ONION", "Karwan Bazar", "2026-10-06", 50.0)
        text = (self.data_dir / "price_records.csv").read_text(encoding="utf-8")
        self.assertIn("R00001,RICE", text)

    def test_the_orphan_row_is_still_in_the_file_after_a_reload(self):
        manager = self.make_manager()
        manager.reload()
        manager.add_record("ONION", "Karwan Bazar", "2026-10-06", 50.0)
        text = (self.data_dir / "price_records.csv").read_text(encoding="utf-8")
        self.assertIn("R00001,RICE", text)

    def test_the_orphan_row_is_still_there_after_many_saves(self):
        manager = self.make_manager()
        for day in range(6, 12):
            manager.add_record("ONION", "Karwan Bazar", f"2026-10-{day:02d}", 50.0)
        text = (self.data_dir / "price_records.csv").read_text(encoding="utf-8")
        self.assertIn("R00001,RICE", text)

    def test_the_orphan_row_is_still_reported(self):
        manager = self.make_manager()
        warnings = " ".join(manager.storage.warnings)
        self.assertIn("unknown product 'RICE'", warnings)

    def test_the_orphan_row_does_not_reach_the_records_list(self):
        manager = self.make_manager()
        self.assertNotIn("R00001", [r.record_id for r in manager.records])


class TestRemovingAMarketUsesTheSameComparisonAsTheCheck(DataFolderTestCase):
    """The market name is matched without regard to case.

    The check that finds the market and the filter that removes it have
    to agree, or removing a market silently does nothing.
    """

    def make_manager(self) -> BazarManager:
        self.write_products("ONION")
        self.write_users()
        self.write_settings()
        self.write_baskets()
        self.write_records()
        manager = BazarManager(self.data_dir)
        manager.login("admin", "admin123")
        return manager

    def test_a_market_can_be_removed_with_a_different_case(self):
        manager = self.make_manager()
        manager.add_market("Shwapno")
        manager.remove_market("shwapno")
        self.assertNotIn("Shwapno", manager.markets())

    def test_the_exact_name_still_works(self):
        manager = self.make_manager()
        manager.add_market("Shwapno")
        manager.remove_market("Shwapno")
        self.assertNotIn("Shwapno", manager.markets())

    def test_removing_a_market_that_is_not_there_is_refused(self):
        from validators import RecordNotFoundError

        manager = self.make_manager()
        with self.assertRaises(RecordNotFoundError):
            manager.remove_market("Nowhere Market")


class TestTwoCorruptBackupsDoNotCollide(DataFolderTestCase):
    """A corrupt file is renamed, not deleted.

    Two corruptions of the same file have to end up under two different
    names, or the second one overwrites the first backup.
    """

    def test_two_corrupt_files_get_two_different_names(self):
        storage = Storage(self.data_dir)
        storage.save_settings(dict(config.DEFAULT_SETTINGS))

        (self.data_dir / "settings.json").write_text("BAD1", encoding="utf-8")
        storage.load_settings()
        (self.data_dir / "settings.json").write_text(
            "BAD2-LONGER-CONTENT", encoding="utf-8"
        )
        storage.load_settings()

        backups = sorted(self.data_dir.glob("settings.json.corrupt-*"))
        self.assertEqual(len(backups), 2)

    def test_the_first_backup_keeps_its_own_content(self):
        storage = Storage(self.data_dir)
        storage.save_settings(dict(config.DEFAULT_SETTINGS))

        (self.data_dir / "settings.json").write_text("BAD1", encoding="utf-8")
        storage.load_settings()
        (self.data_dir / "settings.json").write_text(
            "BAD2-LONGER-CONTENT", encoding="utf-8"
        )
        storage.load_settings()

        backups = sorted(self.data_dir.glob("settings.json.corrupt-*"))
        contents = {p.read_text(encoding="utf-8") for p in backups}
        self.assertEqual(contents, {"BAD1", "BAD2-LONGER-CONTENT"})


class TestANonNumericThresholdDoesNotCrashTheAlerts(DataFolderTestCase):
    """A hand-edited settings file must not break the alert code.

    A threshold that is not a number falls back to the default, the same
    way a missing one does.
    """

    def test_a_text_threshold_falls_back_to_the_default(self):
        settings = {"z_threshold": "abc"}
        product = Product("ONION", "Onion", "", "kg", "V")
        z_limit, pct_limit = product.spike_thresholds(settings)
        self.assertEqual(z_limit, config.DEFAULT_Z_THRESHOLD)
        self.assertEqual(pct_limit, config.DEFAULT_PCT_THRESHOLD)

    def test_a_text_threshold_falls_back_for_a_perishable(self):
        settings = {"perishable_z_threshold": "abc"}
        product = Product("ONION", "Onion", "", "kg", "V", perishable=True)
        z_limit, pct_limit = product.spike_thresholds(settings)
        self.assertEqual(z_limit, config.DEFAULT_PERISHABLE_Z_THRESHOLD)
        self.assertEqual(pct_limit, config.DEFAULT_PERISHABLE_PCT_THRESHOLD)

    def test_a_numeric_string_threshold_still_works(self):
        settings = {"z_threshold": "3.5"}
        product = Product("ONION", "Onion", "", "kg", "V")
        z_limit, _ = product.spike_thresholds(settings)
        self.assertEqual(z_limit, 3.5)

    def test_a_text_threshold_in_the_file_is_reported(self):
        storage = Storage(self.data_dir)
        storage.save_settings(dict(config.DEFAULT_SETTINGS))
        settings = storage.load_settings()
        settings["z_threshold"] = "abc"
        storage.save_settings(settings)

        reloaded = storage.load_settings()
        self.assertEqual(reloaded["z_threshold"], config.DEFAULT_Z_THRESHOLD)

    def test_the_alert_code_still_runs_with_a_text_threshold(self):
        from analytics import alert_level
        from models import PriceRecord

        product = Product("ONION", "Onion", "", "kg", "V", reference_price=50.0)
        record = PriceRecord("R1", "ONION", "Karwan Bazar", "2026-10-01", 50.0, "rafi")
        level, z, pct = alert_level(
            record,
            [record],
            {"ONION": product},
            {"z_threshold": "abc", "pct_threshold": "def"},
        )
        self.assertIn(level, {"Normal", "Watch", "Spike"})


class TestACountSettingKeepsItsWholeNumber(DataFolderTestCase):
    """The settings that count something are stored as whole numbers.

    A count of 2.4 does not mean anything, so it is refused rather than
    quietly rounded down to 2.
    """

    def test_a_fractional_count_is_refused(self):
        from validators import validate_threshold

        with self.assertRaises(ValidationError):
            validate_threshold("min_history", 2.4)

    def test_a_fractional_recent_days_is_refused(self):
        from validators import validate_threshold

        with self.assertRaises(ValidationError):
            validate_threshold("recent_days", 5.9)

    def test_a_whole_count_is_kept(self):
        from validators import validate_threshold

        self.assertEqual(validate_threshold("min_history", 5), 5)

    def test_a_whole_number_that_is_written_as_a_float_is_kept(self):
        from validators import validate_threshold

        self.assertEqual(validate_threshold("min_history", 5.0), 5)


if __name__ == "__main__":
    unittest.main()
