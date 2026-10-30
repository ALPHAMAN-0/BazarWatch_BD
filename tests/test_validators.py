"""Tests for validators.py — input checks and the custom exception hierarchy."""

import unittest
from datetime import date, timedelta

from validators import (
    AuthError,
    BazarError,
    DuplicateIDError,
    PermissionDeniedError,
    RecordNotFoundError,
    ValidationError,
    validate_budget,
    validate_date,
    validate_password,
    validate_price,
    validate_product_id,
    validate_quantity,
    validate_threshold,
    validate_username,
)


class TestExceptionHierarchy(unittest.TestCase):
    """Every custom exception derives from BazarError so the GUI can catch one thing."""

    def test_all_exceptions_derive_from_bazar_error(self):
        for exc in (
            ValidationError,
            DuplicateIDError,
            RecordNotFoundError,
            AuthError,
            PermissionDeniedError,
        ):
            self.assertTrue(issubclass(exc, BazarError))

    def test_validation_error_carries_message(self):
        err = ValidationError("Price must be a number")
        self.assertEqual(str(err), "Price must be a number")


class TestValidatePrice(unittest.TestCase):
    def test_accepts_valid_number(self):
        self.assertEqual(validate_price("45.50"), 45.50)
        self.assertEqual(validate_price(12), 12.0)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationError):
            validate_price("")

    def test_rejects_none(self):
        with self.assertRaises(ValidationError):
            validate_price(None)

    def test_rejects_non_numeric_text(self):
        with self.assertRaises(ValidationError):
            validate_price("abc")

    def test_rejects_zero(self):
        with self.assertRaises(ValidationError):
            validate_price(0)

    def test_rejects_negative(self):
        with self.assertRaises(ValidationError):
            validate_price(-5)

    def test_rejects_value_above_maximum(self):
        with self.assertRaises(ValidationError):
            validate_price(100001)

    def test_accepts_boundary_values(self):
        self.assertEqual(validate_price(0.01), 0.01)
        self.assertEqual(validate_price(100000), 100000.0)


class TestValidateDate(unittest.TestCase):
    def test_accepts_iso_string(self):
        self.assertEqual(validate_date("2026-10-30"), date(2026, 10, 30))

    def test_accepts_date_object(self):
        self.assertEqual(validate_date(date(2026, 1, 2)), date(2026, 1, 2))

    def test_rejects_bad_format(self):
        with self.assertRaises(ValidationError):
            validate_date("30/10/2026")

    def test_rejects_impossible_date(self):
        with self.assertRaises(ValidationError):
            validate_date("2026-13-01")

    def test_rejects_future_date(self):
        tomorrow = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            validate_date(tomorrow.isoformat())

    def test_accepts_today(self):
        self.assertEqual(validate_date(date.today()), date.today())


class TestValidateQuantity(unittest.TestCase):
    def test_accepts_positive_number(self):
        self.assertEqual(validate_quantity("2.5"), 2.5)

    def test_rejects_zero(self):
        with self.assertRaises(ValidationError):
            validate_quantity(0)

    def test_rejects_negative(self):
        with self.assertRaises(ValidationError):
            validate_quantity(-1)

    def test_rejects_text(self):
        with self.assertRaises(ValidationError):
            validate_quantity("two")

    def test_rejects_empty(self):
        with self.assertRaises(ValidationError):
            validate_quantity("")


class TestValidateBudget(unittest.TestCase):
    def test_accepts_positive_number(self):
        self.assertEqual(validate_budget("500"), 500.0)

    def test_rejects_negative(self):
        with self.assertRaises(ValidationError):
            validate_budget(-100)

    def test_rejects_text(self):
        with self.assertRaises(ValidationError):
            validate_budget("abc")

    def test_allows_zero_budget(self):
        # A budget of zero is meaningful: it means "no money planned".
        self.assertEqual(validate_budget(0), 0.0)


class TestValidateThreshold(unittest.TestCase):
    def test_rejects_z_below_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("z_threshold", 0.4)

    def test_rejects_z_above_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("z_threshold", 5.1)

    def test_accepts_z_in_range(self):
        self.assertEqual(validate_threshold("z_threshold", 2.0), 2.0)

    def test_rejects_percent_below_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("pct_threshold", 0.5)

    def test_rejects_percent_above_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("pct_threshold", 201)

    def test_rejects_min_history_below_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("min_history", 1)

    def test_rejects_min_history_above_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("min_history", 51)

    def test_rejects_recent_days_below_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("recent_days", 0)

    def test_rejects_recent_days_above_range(self):
        with self.assertRaises(ValidationError):
            validate_threshold("recent_days", 91)

    def test_accepts_recent_days_in_range(self):
        self.assertEqual(validate_threshold("recent_days", 14), 14)

    def test_rejects_unknown_threshold_name(self):
        with self.assertRaises(ValidationError):
            validate_threshold("nonsense", 1)

    def test_rejects_non_numeric(self):
        with self.assertRaises(ValidationError):
            validate_threshold("z_threshold", "high")


class TestValidatePassword(unittest.TestCase):
    def test_rejects_short_password(self):
        with self.assertRaises(ValidationError):
            validate_password("12345")

    def test_accepts_six_characters(self):
        self.assertEqual(validate_password("123456"), "123456")

    def test_rejects_empty(self):
        with self.assertRaises(ValidationError):
            validate_password("")

    def test_rejects_whitespace_only(self):
        with self.assertRaises(ValidationError):
            validate_password("      ")


class TestValidateUsername(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(ValidationError):
            validate_username("")

    def test_rejects_spaces_only(self):
        with self.assertRaises(ValidationError):
            validate_username("   ")

    def test_accepts_normal_username(self):
        self.assertEqual(validate_username("rafi"), "rafi")

    def test_rejects_invalid_characters(self):
        with self.assertRaises(ValidationError):
            validate_username("raf i!")

    def test_rejects_too_long(self):
        with self.assertRaises(ValidationError):
            validate_username("a" * 33)


class TestValidateProductId(unittest.TestCase):
    def test_accepts_uppercase_id(self):
        self.assertEqual(validate_product_id("RICE"), "RICE")

    def test_rejects_empty(self):
        with self.assertRaises(ValidationError):
            validate_product_id("")

    def test_rejects_lowercase(self):
        with self.assertRaises(ValidationError):
            validate_product_id("rice")

    def test_rejects_invalid_characters(self):
        with self.assertRaises(ValidationError):
            validate_product_id("RIC-E")

    def test_rejects_too_long(self):
        with self.assertRaises(ValidationError):
            validate_product_id("A" * 17)


if __name__ == "__main__":
    unittest.main()
