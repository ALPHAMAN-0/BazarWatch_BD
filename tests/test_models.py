"""Tests for models.py — Product, PerishableProduct, PriceRecord, User, Admin."""

import unittest

from models import Admin, PerishableProduct, PriceRecord, Product, User


def make_settings(**overrides):
    """Settings dict shaped like config.DEFAULT_SETTINGS."""
    settings = {
        "z_threshold": 2.0,
        "pct_threshold": 15.0,
        "perishable_z_threshold": 2.5,
        "perishable_pct_threshold": 25.0,
    }
    settings.update(overrides)
    return settings


class TestProduct(unittest.TestCase):
    def test_display_name_without_bangla(self):
        product = Product("ONION", "Onion (local)", "দেশি পেঁয়াজ", "kg", "Vegetables")
        self.assertEqual(product.display_name(show_bn=False), "Onion (local)")

    def test_display_name_with_bangla(self):
        product = Product("ONION", "Onion (local)", "দেশি পেঁয়াজ", "kg", "Vegetables")
        self.assertEqual(
            product.display_name(show_bn=True), "Onion (local) (দেশি পেঁয়াজ)"
        )

    def test_display_name_without_bangla_name(self):
        product = Product("RICE", "Coarse rice", "", "kg", "Grains")
        self.assertEqual(product.display_name(show_bn=True), "Coarse rice")

    def test_percent_over_reference(self):
        product = Product("RICE", "Coarse rice", "", "kg", "Grains", reference_price=40.0)
        self.assertAlmostEqual(product.percent_over_reference(50.0), 25.0)

    def test_percent_over_reference_without_reference(self):
        product = Product("RICE", "Coarse rice", "", "kg", "Grains")
        self.assertIsNone(product.percent_over_reference(50.0))

    def test_percent_over_reference_with_zero_reference(self):
        product = Product("RICE", "Coarse rice", "", "kg", "Grains", reference_price=0.0)
        self.assertIsNone(product.percent_over_reference(50.0))

    def test_spike_thresholds_normal_product(self):
        product = Product("RICE", "Coarse rice", "", "kg", "Grains")
        self.assertEqual(product.spike_thresholds(make_settings()), (2.0, 15.0))

    def test_to_dict_round_trip(self):
        product = Product("RICE", "Coarse rice", "মোটা চাল", "kg", "Grains", 40.0)
        data = product.to_dict()
        restored = Product.from_dict(data)
        self.assertEqual(restored.product_id, "RICE")
        self.assertEqual(restored.name, "Coarse rice")
        self.assertEqual(restored.name_bn, "মোটা চাল")
        self.assertEqual(restored.reference_price, 40.0)
        self.assertFalse(restored.perishable)

    def test_from_dict_returns_perishable_product(self):
        product = Product.from_dict(
            {
                "product_id": "ONION",
                "name": "Onion (local)",
                "name_bn": "দেশি পেঁয়াজ",
                "unit": "kg",
                "category": "Vegetables",
                "reference_price": None,
                "perishable": True,
            }
        )
        self.assertIsInstance(product, PerishableProduct)

    def test_from_dict_returns_plain_product_when_not_perishable(self):
        product = Product.from_dict(
            {
                "product_id": "RICE",
                "name": "Coarse rice",
                "name_bn": "",
                "unit": "kg",
                "category": "Grains",
                "reference_price": None,
                "perishable": False,
            }
        )
        self.assertNotIsInstance(product, PerishableProduct)
        self.assertIsInstance(product, Product)


class TestPerishableProduct(unittest.TestCase):
    def test_overrides_thresholds(self):
        product = PerishableProduct("ONION", "Onion (local)", "", "kg", "Vegetables")
        self.assertEqual(product.spike_thresholds(make_settings()), (2.5, 25.0))

    def test_is_a_product(self):
        product = PerishableProduct("ONION", "Onion (local)", "", "kg", "Vegetables")
        self.assertIsInstance(product, Product)

    def test_to_dict_marks_perishable(self):
        product = PerishableProduct("ONION", "Onion (local)", "", "kg", "Vegetables")
        self.assertTrue(product.to_dict()["perishable"])


class TestPriceRecord(unittest.TestCase):
    def make_record(self):
        return PriceRecord("R00001", "ONION", "Karwan Bazar", "2026-10-30", 45.0, "rafi")

    def test_key_tuple(self):
        record = self.make_record()
        self.assertEqual(
            record.key(), ("ONION", "Karwan Bazar", "2026-10-30", "rafi")
        )

    def test_to_row(self):
        record = self.make_record()
        self.assertEqual(
            record.to_row(),
            ["R00001", "ONION", "Karwan Bazar", "2026-10-30", 45.0, "rafi"],
        )

    def test_from_row(self):
        record = PriceRecord.from_row(
            ["R00001", "ONION", "Karwan Bazar", "2026-10-30", "45.0", "rafi"]
        )
        self.assertEqual(record.record_id, "R00001")
        self.assertEqual(record.price, 45.0)
        self.assertEqual(record.added_by, "rafi")

    def test_round_trip(self):
        record = self.make_record()
        restored = PriceRecord.from_row(record.to_row())
        self.assertEqual(restored.key(), record.key())


class TestUser(unittest.TestCase):
    def make_user(self):
        return User("rafi", "member", "salt123", "hash123", "2026-10-01", None)

    def test_defaults_to_member_role(self):
        user = User("rafi", "member", "salt", "hash", "2026-10-01", None)
        self.assertEqual(user.role, "member")

    def test_member_cannot_delete(self):
        self.assertFalse(self.make_user().can_delete(None))

    def test_member_cannot_manage(self):
        self.assertFalse(self.make_user().can_manage())

    def test_member_can_edit_own_record(self):
        user = self.make_user()
        record = PriceRecord("R00001", "ONION", "Karwan Bazar", "2026-10-30", 45.0, "rafi")
        self.assertTrue(user.can_edit(record))

    def test_member_cannot_edit_other_record(self):
        user = self.make_user()
        record = PriceRecord("R00002", "ONION", "Karwan Bazar", "2026-10-30", 45.0, "sadia")
        self.assertFalse(user.can_edit(record))

    def test_to_dict_round_trip(self):
        user = self.make_user()
        restored = User.from_dict(user.to_dict())
        self.assertEqual(restored.username, "rafi")
        self.assertEqual(restored.role, "member")
        self.assertNotIsInstance(restored, Admin)

    def test_from_dict_returns_admin(self):
        user = User.from_dict(
            {
                "username": "admin",
                "role": "admin",
                "salt": "s",
                "password_hash": "h",
                "created_at": "2026-10-01",
                "last_login": None,
            }
        )
        self.assertIsInstance(user, Admin)

    def test_hashed_password_is_never_plain_text(self):
        user = self.make_user()
        self.assertNotEqual(user.password_hash, "rafi")


class TestAdmin(unittest.TestCase):
    def make_admin(self):
        return Admin("admin", "admin", "salt", "hash", "2026-10-01", None)

    def test_is_a_user(self):
        self.assertIsInstance(self.make_admin(), User)

    def test_admin_can_delete(self):
        self.assertTrue(self.make_admin().can_delete(None))

    def test_admin_can_manage(self):
        self.assertTrue(self.make_admin().can_manage())

    def test_admin_can_edit_any_record(self):
        admin = self.make_admin()
        record = PriceRecord("R00002", "ONION", "Karwan Bazar", "2026-10-30", 45.0, "sadia")
        self.assertTrue(admin.can_edit(record))


if __name__ == "__main__":
    unittest.main()
