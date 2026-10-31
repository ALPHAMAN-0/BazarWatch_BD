"""A data file the app cannot read must never close the app (PDF section 9).

The file is moved aside and kept, so the next save cannot overwrite it.

Every test uses a temp folder, so the real data/ directory is never touched.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from manager import BazarManager
from storage import Storage

GARBAGE = b"\xff\xfe\x00\x80garbage\x81"
DATA_FILES = (
    "products.json",
    "price_records.csv",
    "users.json",
    "baskets.json",
    "settings.json",
)


class DataFolderTestCase(unittest.TestCase):
    """Gives each test a temp folder with a working set of data files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        manager = BazarManager(self.data_dir)
        manager.create_admin("admin", "secret1")

    def tearDown(self):
        self._tmp.cleanup()

    def backups(self, name: str) -> list[Path]:
        return list(self.data_dir.glob(f"{name}.corrupt-*"))


class TestABinaryRecordsFile(DataFolderTestCase):
    def setUp(self):
        super().setUp()
        (self.data_dir / "price_records.csv").write_bytes(GARBAGE)

    def test_the_app_still_starts_and_says_why(self):
        manager = BazarManager(self.data_dir)
        self.assertEqual(manager.records, [])
        self.assertTrue(
            any("price_records.csv" in w for w in manager.startup_warnings)
        )

    def test_the_file_is_kept(self):
        BazarManager(self.data_dir)
        backups = self.backups("price_records.csv")
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), GARBAGE)

    def test_the_app_keeps_working_afterwards(self):
        manager = BazarManager(self.data_dir)
        manager.login("admin", "secret1")
        record = manager.add_record("ONION", manager.markets()[0], "2026-01-05", "40")
        self.assertEqual(
            BazarManager(self.data_dir).get_record(record.record_id).price, 40.0
        )


class TestAFileThatCannotBeOpened(DataFolderTestCase):
    """A folder in the file's place fails to open on every operating system."""

    def test_no_data_file_stops_the_app(self):
        for name in DATA_FILES:
            with self.subTest(name=name):
                path = self.data_dir / name
                saved = path.read_bytes()
                path.unlink()
                path.mkdir()

                manager = BazarManager(self.data_dir)

                self.assertTrue(any(name in w for w in manager.startup_warnings))
                path.unlink(missing_ok=True)
                path.write_bytes(saved)


class TestAFileWithoutReadPermission(DataFolderTestCase):
    def test_the_file_survives_the_next_save(self):
        for name in DATA_FILES:
            with self.subTest(name=name):
                path = self.data_dir / name
                saved = path.read_bytes()
                path.chmod(0)
                if os.access(path, os.R_OK):
                    path.chmod(0o644)
                    self.skipTest("this user can read every file")

                manager = BazarManager(self.data_dir)
                manager.save_all()

                backups = self.backups(name)
                self.assertEqual(len(backups), 1)
                backups[0].chmod(0o644)
                self.assertEqual(backups[0].read_bytes(), saved)
                backups[0].unlink()
                path.write_bytes(saved)


class TestAFolderThatCannotBeWritten(unittest.TestCase):
    """The data folder's path is taken by a file, so nothing can be created."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.blocked = Path(self._tmp.name) / "data"
        self.blocked.write_text("in the way", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_app_still_starts_and_says_why(self):
        manager = BazarManager(self.blocked)
        self.assertEqual(len(manager.products), 12)
        self.assertTrue(manager.startup_warnings)

    def test_a_save_reports_the_failure_to_the_caller(self):
        manager = BazarManager(self.blocked)
        with self.assertRaises(OSError):
            manager.save_all()


class TestAFileThatCannotBeMovedAside(DataFolderTestCase):
    def test_the_file_is_not_overwritten_and_the_warning_is_true(self):
        path = self.data_dir / "settings.json"
        path.write_bytes(GARBAGE)
        storage = Storage(self.data_dir)

        with mock.patch("storage.shutil.move", side_effect=OSError("locked")):
            settings = storage.load_settings()

        self.assertEqual(settings["recent_days"], 14)
        self.assertEqual(path.read_bytes(), GARBAGE)
        self.assertIn("settings.json", storage.warning_summary())
        self.assertIn("could not be renamed", storage.warning_summary())


class TestBadValuesInTheBasketsFile(DataFolderTestCase):
    def write_baskets(self, baskets: dict) -> None:
        (self.data_dir / "baskets.json").write_text(
            json.dumps(baskets), encoding="utf-8"
        )

    def test_a_budget_that_is_not_a_number_skips_that_basket_only(self):
        self.write_baskets(
            {"rafi": {"budget": "abc", "items": {}}, "sadia": {"budget": 500, "items": {}}}
        )
        manager = BazarManager(self.data_dir)
        self.assertEqual(set(manager.baskets), {"sadia"})
        self.assertTrue(any("rafi" in w for w in manager.startup_warnings))

    def test_a_quantity_that_is_not_a_number_skips_that_basket_only(self):
        self.write_baskets(
            {
                "rafi": {"budget": 100, "items": {"EGG": "two"}},
                "sadia": {"budget": 500, "items": {"EGG": 2}},
            }
        )
        manager = BazarManager(self.data_dir)
        self.assertEqual(set(manager.baskets), {"sadia"})
        self.assertTrue(any("rafi" in w for w in manager.startup_warnings))


if __name__ == "__main__":
    unittest.main()
