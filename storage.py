"""File storage for BazarWatch BD.

:class:`Storage` is the only part of the app that reads and writes files.  It
takes a ``data_dir`` so tests can point it at a temp folder.

File rules (see plan section 8):

* A missing file is created with sensible defaults.
* A corrupt JSON file is renamed to ``<name>.corrupt-<timestamp>`` and the
  defaults are loaded instead, with a warning.
* A malformed CSV row is skipped and reported, with a warning per problem.
* Saves are safe: the data is written to ``<file>.tmp`` and then moved into
  place with ``os.replace``, so a crash mid-save never leaves a half-written
  file behind.
* Every read and write uses ``encoding="utf-8"`` so Bangla text survives on
  Windows.
"""

from __future__ import annotations

import contextlib
import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import config
from models import PriceRecord, Product, User


class Storage:
    """Loads and saves the five data files in one directory."""

    RECORD_HEADER = (
        "record_id",
        "product_id",
        "market",
        "date",
        "price",
        "added_by",
    )

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.products_file = self.data_dir / "products.json"
        self.records_file = self.data_dir / "price_records.csv"
        self.users_file = self.data_dir / "users.json"
        self.baskets_file = self.data_dir / "baskets.json"
        self.settings_file = self.data_dir / "settings.json"

        # Warnings collected while loading; the GUI shows them at startup.
        self.warnings: list[str] = []

        # Rows that were skipped on load because their product is not in
        # the catalogue.  They are written back out on the next save.
        self.skipped_rows: list[list[str]] = []

    # -- warnings -----------------------------------------------------------
    def clear_warnings(self) -> None:
        """Forget the warnings from the last load."""
        self.warnings = []

    def warning_summary(self) -> str:
        """One-line summary of the collected warnings, for a message box."""
        if not self.warnings:
            return ""
        return "\n".join(self.warnings)

    # -- low-level helpers --------------------------------------------------
    def _backup_name(self, path: Path) -> Path:
        """A free name for a corrupt file that is being renamed.

        The timestamp only has one-second resolution, so two corruptions
        of the same file in the same second would get the same name and
        the second would overwrite the first.  A counter is added when
        the name is already taken.
        """
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.corrupt-{stamp}")
        number = 2
        while backup.exists():
            backup = path.with_name(f"{path.name}.corrupt-{stamp}-{number}")
            number += 1
        return backup

    def _read_json(self, path: Path, default):
        """Read JSON, backing up a corrupt file and returning ``default``."""
        if not path.exists():
            self._write_json(path, default)
            return json.loads(json.dumps(default))
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            backup = self._backup_name(path)
            # If the file cannot be moved aside, carry on: the defaults
            # are still written below, and the warning tells the user
            # what happened.
            with contextlib.suppress(OSError):
                shutil.move(str(path), str(backup))
            self.warnings.append(
                f"{path.name} was corrupt ({exc}); it was renamed to "
                f"{backup.name} and defaults were loaded."
            )
            self._write_json(path, default)
            return json.loads(json.dumps(default))

    def _write_json(self, path: Path, data) -> None:
        """Write JSON safely: to a .tmp file first, then move it into place."""
        tmp_path = path.with_name(path.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(str(tmp_path), str(path))

    # -- products -----------------------------------------------------------
    def load_products(self) -> list[Product]:
        """Load the catalogue, creating it with the starter products if missing."""
        default = [dict(product) for product in config.DEFAULT_PRODUCTS]
        data = self._read_json(self.products_file, default)
        if not isinstance(data, list):
            self.warnings.append(
                f"{self.products_file.name} did not contain a list; defaults were loaded."
            )
            return [Product.from_dict(product) for product in default]
        products = []
        for entry in data:
            if not isinstance(entry, dict) or "product_id" not in entry:
                self.warnings.append(
                    f"{self.products_file.name}: skipped an entry with no product ID."
                )
                continue
            try:
                products.append(Product.from_dict(entry))
            except (KeyError, TypeError, ValueError) as exc:
                self.warnings.append(
                    f"{self.products_file.name}: skipped product "
                    f"{entry.get('product_id', '?')}: {exc}"
                )
        if not products:
            products = [Product.from_dict(product) for product in default]
        return products

    def save_products(self, products: list[Product]) -> None:
        """Save the catalogue."""
        self._write_json(self.products_file, [p.to_dict() for p in products])

    # -- users --------------------------------------------------------------
    def load_users(self) -> list[User]:
        """Load the accounts, creating an empty file if missing."""
        data = self._read_json(self.users_file, [])
        if not isinstance(data, list):
            self.warnings.append(
                f"{self.users_file.name} did not contain a list; defaults were loaded."
            )
            return []
        users = []
        for entry in data:
            if not isinstance(entry, dict) or "username" not in entry:
                self.warnings.append(
                    f"{self.users_file.name}: skipped an entry with no username."
                )
                continue
            try:
                users.append(User.from_dict(entry))
            except (KeyError, TypeError, ValueError) as exc:
                self.warnings.append(
                    f"{self.users_file.name}: skipped user "
                    f"{entry.get('username', '?')}: {exc}"
                )
        return users

    def save_users(self, users: list[User]) -> None:
        """Save the accounts."""
        self._write_json(self.users_file, [u.to_dict() for u in users])

    # -- baskets ------------------------------------------------------------
    def load_baskets(self) -> dict:
        """Load the baskets, creating an empty file if missing."""
        data = self._read_json(self.baskets_file, {})
        if not isinstance(data, dict):
            self.warnings.append(
                f"{self.baskets_file.name} did not contain an object; defaults were loaded."
            )
            return {}
        baskets = {}
        for username, basket in data.items():
            if not isinstance(basket, dict):
                self.warnings.append(
                    f"{self.baskets_file.name}: skipped basket for '{username}'."
                )
                continue
            items = basket.get("items", {})
            if not isinstance(items, dict):
                items = {}
            baskets[username] = {
                "budget": float(basket.get("budget", 0.0) or 0.0),
                "items": {str(k): float(v) for k, v in items.items()},
            }
        return baskets

    def save_baskets(self, baskets: dict) -> None:
        """Save the baskets."""
        self._write_json(self.baskets_file, baskets)

    # -- settings -----------------------------------------------------------
    def load_settings(self) -> dict:
        """Load the settings, filling in any missing key with its default.

        A value that is not the right shape is replaced by the default
        and reported, so a hand-edited settings file cannot break the
        alert code.
        """
        default = config.default_settings()
        data = self._read_json(self.settings_file, default)
        if not isinstance(data, dict):
            self.warnings.append(
                f"{self.settings_file.name} did not contain an object; defaults were loaded."
            )
            return default
        settings = dict(default)
        settings.update(data)
        if not isinstance(settings.get("markets"), list) or not settings["markets"]:
            settings["markets"] = list(config.DEFAULT_MARKETS)
        settings = self._fix_bad_numbers(settings)
        return settings

    def _fix_bad_numbers(self, settings: dict) -> dict:
        """Replace a setting that is not a number with its default.

        The alert code reads these settings, so a value like ``"abc"``
        would raise where a number is expected.  The bad value is
        replaced and reported, and the user is told which one it was.

        Only the numeric settings are checked.  The market list is not a
        number, and putting the default list itself in would share it
        with the defaults, so adding a market would then change the
        default for everyone.
        """
        defaults = config.default_settings()
        for key in config.NUMERIC_SETTINGS:
            value = settings.get(key)
            if value is None or isinstance(value, bool):
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                settings[key] = defaults[key]
                self.warnings.append(
                    f"{self.settings_file.name} had an unusable value for "
                    f"'{key}' ({value!r}); the default was used instead."
                )
        return settings

    def save_settings(self, settings: dict) -> None:
        """Save the settings."""
        self._write_json(self.settings_file, settings)

    # -- price records ------------------------------------------------------
    def load_records(self, known_product_ids=None) -> list[PriceRecord]:
        """Load the price records, skipping and reporting malformed rows.

        ``known_product_ids`` is a set of product IDs that exist in the
        catalogue.  When given, a row naming an unknown product is skipped.

        A skipped row is kept in :attr:`skipped_rows` and written back
        out with the next save.  It is not shown to the user and it does
        not take part in any calculation, but it is not thrown away
        either: the product may come back, and until then the history is
        not the app's to lose.
        """
        if not self.records_file.exists():
            self.skipped_rows = []
            self.save_records([])
            return []

        records: list[PriceRecord] = []
        seen_ids: set[str] = set()
        problems: list[str] = []
        skipped_rows: list[list[str]] = []

        with open(self.records_file, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))

        if not rows:
            return []

        start = 0
        header = [cell.strip() for cell in rows[0]]
        if header == list(self.RECORD_HEADER):
            start = 1

        for offset, row in enumerate(rows[start:], start=start + 1):
            reason = self._record_problem(row, seen_ids, known_product_ids)
            if reason is not None:
                problems.append(f"line {offset}: {reason}")
                if self._keep_skipped_row(row, reason):
                    skipped_rows.append([cell.strip() for cell in row])
                continue
            record = PriceRecord.from_row(row)
            seen_ids.add(record.record_id)
            records.append(record)

        self.skipped_rows = skipped_rows
        if problems:
            self.warnings.append(
                f"Skipped {len(problems)} row(s) in {self.records_file.name}: "
                + "; ".join(problems)
            )
        return records

    @staticmethod
    def _keep_skipped_row(row, reason: str) -> bool:
        """Whether a skipped row is worth keeping in the file.

        A row naming a product that is not in the catalogue is kept: the
        product may be added back, and the record is real history.  A
        row that is malformed — a price that is not a number, a date in
        the wrong format — is dropped, because there is nothing to keep
        and no way to read it back.
        """
        return reason.startswith("unknown product ")

    @staticmethod
    def _record_problem(row, seen_ids: set[str], known_product_ids) -> str | None:
        """Return why a CSV row is unusable, or None when the row is fine."""
        if len(row) != len(Storage.RECORD_HEADER):
            return f"expected {len(Storage.RECORD_HEADER)} fields, found {len(row)}"
        record_id, product_id, market, date_text, price_text, added_by = (
            cell.strip() for cell in row
        )
        if not record_id:
            return "missing record ID"
        if record_id in seen_ids:
            return f"duplicate record ID '{record_id}'"
        if not product_id:
            return "missing product ID"
        if known_product_ids is not None and product_id not in known_product_ids:
            return f"unknown product '{product_id}'"
        if not market:
            return "missing market"
        if not added_by:
            return "missing username"
        try:
            float(price_text)
        except ValueError:
            return f"price '{price_text}' is not a number"
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            return f"date '{date_text}' is not in YYYY-MM-DD format"
        return None

    def save_records(self, records: list[PriceRecord]) -> None:
        """Save the price records, safely.

        The rows that were skipped on load because their product is not
        in the catalogue are written back out, so saving does not throw
        away a record the app merely could not read.
        """
        tmp_path = self.records_file.with_name(self.records_file.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.RECORD_HEADER)
            for record in records:
                writer.writerow(record.to_row())
            for row in self.skipped_rows:
                writer.writerow(row)
        os.replace(str(tmp_path), str(self.records_file))
