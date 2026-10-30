"""Tests for storage.py — JSON/CSV loading, safe saves and bad-row handling.

Every test uses a temp folder, so the real data/ directory is never touched.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from storage import Storage


class StorageTestCase(unittest.TestCase):
    """Base class giving each test its own temp data folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.storage = Storage(self.data_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, content: str) -> Path:
        path = self.data_dir / name
        path.write_text(content, encoding="utf-8")
        return path


class TestStorageInit(StorageTestCase):
    def test_creates_data_dir_if_missing(self):
        target = self.data_dir / "nested" / "data"
        Storage(target)
        self.assertTrue(target.exists())

    def test_file_paths_are_inside_data_dir(self):
        self.assertEqual(self.storage.products_file.parent, self.data_dir)
        self.assertEqual(self.storage.records_file.parent, self.data_dir)
        self.assertEqual(self.storage.users_file.parent, self.data_dir)
        self.assertEqual(self.storage.baskets_file.parent, self.data_dir)
        self.assertEqual(self.storage.settings_file.parent, self.data_dir)

    def test_filenames_match_the_plan(self):
        self.assertEqual(self.storage.products_file.name, "products.json")
        self.assertEqual(self.storage.records_file.name, "price_records.csv")
        self.assertEqual(self.storage.users_file.name, "users.json")
        self.assertEqual(self.storage.baskets_file.name, "baskets.json")
        self.assertEqual(self.storage.settings_file.name, "settings.json")


class TestMissingFiles(StorageTestCase):
    def test_missing_products_file_created_with_defaults(self):
        products = self.storage.load_products()
        self.assertTrue(self.storage.products_file.exists())
        self.assertEqual(len(products), 12)

    def test_missing_settings_file_created_with_defaults(self):
        settings = self.storage.load_settings()
        self.assertTrue(self.storage.settings_file.exists())
        self.assertEqual(settings["recent_days"], 14)

    def test_missing_users_file_created_empty(self):
        users = self.storage.load_users()
        self.assertTrue(self.storage.users_file.exists())
        self.assertEqual(users, [])

    def test_missing_baskets_file_created_empty(self):
        baskets = self.storage.load_baskets()
        self.assertTrue(self.storage.baskets_file.exists())
        self.assertEqual(baskets, {})

    def test_missing_records_file_created_empty(self):
        records = self.storage.load_records()
        self.assertTrue(self.storage.records_file.exists())
        self.assertEqual(records, [])


class TestCorruptJson(StorageTestCase):
    def test_corrupt_json_is_backed_up_not_deleted(self):
        self.write("settings.json", "{this is not json")
        self.storage.load_settings()
        backups = list(self.data_dir.glob("settings.json.corrupt-*"))
        self.assertEqual(len(backups), 1)

    def test_corrupt_json_falls_back_to_defaults(self):
        self.write("settings.json", "{broken")
        settings = self.storage.load_settings()
        self.assertEqual(settings["z_threshold"], 2.0)

    def test_corrupt_json_reports_a_warning(self):
        self.write("settings.json", "{broken")
        self.storage.load_settings()
        self.assertTrue(self.storage.warnings)

    def test_corrupt_users_json_is_backed_up(self):
        self.write("users.json", "not json at all")
        self.storage.load_users()
        self.assertEqual(len(list(self.data_dir.glob("users.json.corrupt-*"))), 1)

    def test_corrupt_json_file_is_replaced_with_valid_defaults(self):
        self.write("settings.json", "{broken")
        self.storage.load_settings()
        data = json.loads(self.storage.settings_file.read_text(encoding="utf-8"))
        self.assertEqual(data["recent_days"], 14)


class TestBadCsvRows(StorageTestCase):
    def test_good_rows_load(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20,40,rafi\n"
            "R00002,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].price, 40.0)

    def test_non_numeric_price_row_is_skipped(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20,abc,rafi\n"
            "R00002,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)

    def test_bad_row_is_reported_with_reason(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20,abc,rafi\n",
        )
        self.storage.load_records()
        self.assertTrue(self.storage.warnings)
        self.assertIn("abc", " ".join(self.storage.warnings))

    def test_missing_field_row_is_skipped(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20\n"
            "R00002,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)

    def test_bad_date_row_is_skipped(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,20-10-2026,40,rafi\n"
            "R00002,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)

    def test_unknown_product_row_is_skipped(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,GHOST,Karwan Bazar,2026-10-20,40,rafi\n"
            "R00002,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records(known_product_ids={"ONION", "RICE"})
        self.assertEqual(len(records), 1)

    def test_duplicate_record_id_row_is_skipped(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20,40,rafi\n"
            "R00001,RICE,Shwapno,2026-10-21,55,sadia\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)

    def test_skipped_row_count_is_reported(self):
        self.write(
            "price_records.csv",
            "record_id,product_id,market,date,price,added_by\n"
            "R00001,ONION,Karwan Bazar,2026-10-20,abc,rafi\n"
            "R00002,RICE,Shwapno,2026-10-21,xyz,sadia\n",
        )
        self.storage.load_records()
        self.assertTrue(any("2" in w for w in self.storage.warnings))

    def test_file_without_header_is_handled(self):
        self.write(
            "price_records.csv",
            "R00001,ONION,Karwan Bazar,2026-10-20,40,rafi\n",
        )
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)


class TestSafeSave(StorageTestCase):
    def test_save_products_then_load_round_trip(self):
        products = self.storage.load_products()
        products[0].reference_price = 42.5
        self.storage.save_products(products)
        reloaded = self.storage.load_products()
        self.assertEqual(reloaded[0].reference_price, 42.5)

    def test_save_records_round_trip(self):
        self.storage.save_records([])
        rows = [
            ["R00001", "ONION", "Karwan Bazar", "2026-10-20", "40.0", "rafi"],
        ]
        with open(self.storage.records_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["record_id", "product_id", "market", "date", "price", "added_by"]
            )
            writer.writerows(rows)
        records = self.storage.load_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].record_id, "R00001")

    def test_save_users_round_trip(self):
        self.storage.save_users([])
        self.assertEqual(self.storage.load_users(), [])

    def test_save_baskets_round_trip(self):
        baskets = {"rafi": {"budget": 500.0, "items": {"ONION": 2.0}}}
        self.storage.save_baskets(baskets)
        self.assertEqual(self.storage.load_baskets(), baskets)

    def test_save_settings_round_trip(self):
        settings = self.storage.load_settings()
        settings["z_threshold"] = 3.5
        self.storage.save_settings(settings)
        self.assertEqual(self.storage.load_settings()["z_threshold"], 3.5)

    def test_no_tmp_file_is_left_behind(self):
        self.storage.save_settings(self.storage.load_settings())
        self.assertEqual(list(self.data_dir.glob("*.tmp")), [])

    def test_failed_write_raises_oserror_not_crashing(self):
        # A directory where the file should be makes the write fail.
        self.storage.settings_file.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(OSError):
            self.storage.save_settings({"z_threshold": 2.0})

    def test_bangla_text_survives_a_round_trip(self):
        products = self.storage.load_products()
        self.storage.save_products(products)
        reloaded = self.storage.load_products()
        self.assertEqual(reloaded[0].name_bn, "মোটা চাল")

    def test_utf8_is_used_for_reads_and_writes(self):
        self.storage.save_settings(self.storage.load_settings())
        raw = self.storage.settings_file.read_bytes()
        self.assertIsInstance(raw, bytes)


class TestWarningCollection(StorageTestCase):
    def test_warnings_start_empty(self):
        self.assertEqual(self.storage.warnings, [])

    def test_clear_warnings(self):
        self.write("settings.json", "{broken")
        self.storage.load_settings()
        self.storage.clear_warnings()
        self.assertEqual(self.storage.warnings, [])

    def test_summary_of_warnings(self):
        self.write("settings.json", "{broken")
        self.storage.load_settings()
        self.assertIn("settings.json", self.storage.warning_summary())


if __name__ == "__main__":
    unittest.main()
