"""Tests for manager.py — BazarManager: CRUD, login, permissions.

Each test uses a temp data folder so the real data/ directory is never touched.
"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from manager import BazarManager
from validators import (
    AuthError,
    DuplicateIDError,
    PermissionDeniedError,
    RecordNotFoundError,
    ValidationError,
)


class ManagerTestCase(unittest.TestCase):
    """Creates a manager with a temp folder and an Admin + Member logged in."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.manager = BazarManager(self.data_dir)
        self.manager.create_admin("admin", "admin123")
        # Adding members is an Admin action, so log in as the Admin first.
        self.manager.login("admin", "admin123")
        self.manager.add_member("rafi", "rafi123")
        self.manager.add_member("sadia", "sadia123")
        self.manager.logout()

    def tearDown(self):
        self._tmp.cleanup()

    def login_admin(self):
        self.manager.logout()
        return self.manager.login("admin", "admin123")

    def login_member(self, username="rafi", password="rafi123"):
        self.manager.logout()
        return self.manager.login(username, password)

    def yesterday(self):
        return (date.today() - timedelta(days=1)).isoformat()


class TestFirstRun(ManagerTestCase):
    """These tests need a genuinely fresh install, so they use their own folder."""

    def setUp(self):
        super().setUp()
        self._fresh = tempfile.TemporaryDirectory()
        self.fresh_dir = Path(self._fresh.name)

    def tearDown(self):
        self._fresh.cleanup()
        super().tearDown()

    def test_new_manager_has_no_users(self):
        manager = BazarManager(self.fresh_dir)
        self.assertEqual(manager.user_count, 0)

    def test_needs_admin_setup_before_login(self):
        manager = BazarManager(self.fresh_dir)
        self.assertTrue(manager.needs_admin_setup())

    def test_admin_creation_makes_setup_unnecessary(self):
        manager = BazarManager(self.fresh_dir)
        manager.create_admin("admin", "admin123")
        self.assertFalse(manager.needs_admin_setup())

    def test_admin_password_is_hashed_never_stored_plain(self):
        manager = BazarManager(self.fresh_dir)
        manager.create_admin("admin", "admin123")
        admin = manager.users["admin"]
        self.assertNotEqual(admin.password_hash, "admin123")
        self.assertNotEqual(admin.salt, "admin123")

    def test_cannot_create_a_second_admin(self):
        with self.assertRaises(ValidationError):
            self.manager.create_admin("another", "admin123")

    def test_cannot_create_admin_after_members_exist(self):
        manager = BazarManager(self.fresh_dir)
        manager.create_admin("admin", "admin123")
        manager.login("admin", "admin123")
        manager.add_member("rafi", "rafi123")
        with self.assertRaises(ValidationError):
            manager.create_admin("admin", "admin123")


class TestLogin(ManagerTestCase):
    def test_login_succeeds_with_correct_password(self):
        user = self.login_member()
        self.assertEqual(user.username, "rafi")
        self.assertEqual(user.role, "member")

    def test_wrong_password_raises_auth_error(self):
        self.manager.logout()
        with self.assertRaises(AuthError):
            self.manager.login("rafi", "wrongpass")

    def test_unknown_user_raises_auth_error(self):
        self.manager.logout()
        with self.assertRaises(AuthError):
            self.manager.login("nobody", "rafi123")

    def test_last_login_is_recorded(self):
        self.login_member()
        self.assertIsNotNone(self.manager.users["rafi"].last_login)

    def test_logout_clears_current_user(self):
        self.login_member()
        self.manager.logout()
        self.assertIsNone(self.manager.current_user)

    def test_action_without_login_raises_permission_denied(self):
        self.manager.logout()
        with self.assertRaises(PermissionDeniedError):
            self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)

    def test_admin_login_returns_admin_role(self):
        user = self.login_admin()
        self.assertEqual(user.role, "admin")

    def test_password_is_not_stored_as_plain_text(self):
        self.login_member()
        self.assertNotEqual(self.manager.users["rafi"].password_hash, "rafi123")


class TestMemberManagement(ManagerTestCase):
    def test_member_can_be_added(self):
        self.login_admin()
        self.manager.add_member("newbie", "newbie123")
        self.assertIn("newbie", self.manager.users)

    def test_duplicate_username_is_rejected(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_member("rafi", "rafi123")

    def test_duplicate_username_is_case_insensitive(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_member("RAFI", "rafi123")

    def test_short_password_is_rejected(self):
        self.login_admin()
        with self.assertRaises(ValidationError):
            self.manager.add_member("newbie", "123")

    def test_member_cannot_add_another_member(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.add_member("newbie", "newbie123")

    def test_member_can_be_removed(self):
        self.login_admin()
        self.manager.remove_member("rafi")
        self.assertNotIn("rafi", self.manager.users)

    def test_removing_member_keeps_their_records(self):
        self.login_member()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.login_admin()
        self.manager.remove_member("rafi")
        self.assertEqual(len(self.manager.records), 1)

    def test_removing_member_deletes_their_basket(self):
        self.login_member()
        self.manager.set_basket_item("rafi", "ONION", 2.0)
        self.login_admin()
        self.manager.remove_member("rafi")
        self.assertNotIn("rafi", self.manager.baskets)

    def test_admin_cannot_remove_their_own_account(self):
        self.login_admin()
        with self.assertRaises(ValidationError):
            self.manager.remove_member("admin")

    def test_admin_can_reset_a_member_password(self):
        self.login_admin()
        self.manager.reset_password("rafi", "newpass1")
        self.manager.logout()
        user = self.manager.login("rafi", "newpass1")
        self.assertEqual(user.username, "rafi")

    def test_member_can_change_their_own_password(self):
        self.login_member()
        self.manager.change_password("rafi", "rafi123", "brandnew1")
        self.manager.logout()
        self.assertEqual(self.manager.login("rafi", "brandnew1").username, "rafi")

    def test_change_password_requires_the_old_password(self):
        self.login_member()
        with self.assertRaises(AuthError):
            self.manager.change_password("rafi", "wrongold", "brandnew1")

    def test_member_cannot_change_another_password(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.change_password("sadia", "sadia123", "brandnew1")

    def test_admin_can_change_any_password(self):
        self.login_admin()
        self.manager.change_password("rafi", "rafi123", "brandnew1")
        self.manager.logout()
        self.assertEqual(self.manager.login("rafi", "brandnew1").username, "rafi")


class TestProductManagement(ManagerTestCase):
    def test_default_catalogue_is_loaded(self):
        self.assertEqual(len(self.manager.products), 12)

    def test_product_can_be_added_by_admin(self):
        self.login_admin()
        self.manager.add_product("MILK", "Milk powder", "দুধের গুঁড়া", "kg", "Grocery")
        self.assertIn("MILK", self.manager.products)

    def test_duplicate_product_id_is_rejected(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_product("RICE", "Another rice", "", "kg", "Grains")

    def test_duplicate_product_id_is_case_insensitive(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_product("rice", "Another rice", "", "kg", "Grains")

    def test_member_cannot_add_product(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.add_product("MILK", "Milk", "", "kg", "Grocery")

    def test_reference_price_can_be_set(self):
        self.login_admin()
        self.manager.set_reference_price("ONION", 35.0)
        self.assertEqual(self.manager.products["ONION"].reference_price, 35.0)

    def test_reference_price_can_be_cleared(self):
        self.login_admin()
        self.manager.set_reference_price("ONION", 35.0)
        self.manager.set_reference_price("ONION", None)
        self.assertIsNone(self.manager.products["ONION"].reference_price)

    def test_member_cannot_set_reference_price(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.set_reference_price("ONION", 35.0)

    def test_product_with_records_cannot_be_deleted(self):
        self.login_admin()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        with self.assertRaises(ValidationError):
            self.manager.remove_product("ONION")

    def test_product_without_records_can_be_deleted(self):
        self.login_admin()
        self.manager.add_product("MILK", "Milk powder", "", "kg", "Grocery")
        self.manager.remove_product("MILK")
        self.assertNotIn("MILK", self.manager.products)

    def test_unknown_product_cannot_be_deleted(self):
        self.login_admin()
        with self.assertRaises(RecordNotFoundError):
            self.manager.remove_product("GHOST")

    def test_member_cannot_remove_product(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.remove_product("ONION")


class TestMarketManagement(ManagerTestCase):
    def test_default_markets_are_loaded(self):
        self.assertEqual(len(self.manager.settings["markets"]), 3)

    def test_market_can_be_added_by_admin(self):
        self.login_admin()
        self.manager.add_market("Bashundhara")
        self.assertIn("Bashundhara", self.manager.settings["markets"])

    def test_duplicate_market_is_rejected(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_market("Karwan Bazar")

    def test_duplicate_market_is_case_insensitive(self):
        self.login_admin()
        with self.assertRaises(DuplicateIDError):
            self.manager.add_market("karwan bazar")

    def test_member_cannot_add_market(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.add_market("Bashundhara")

    def test_market_with_records_cannot_be_removed(self):
        self.login_admin()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        with self.assertRaises(ValidationError):
            self.manager.remove_market("Karwan Bazar")

    def test_market_without_records_can_be_removed(self):
        self.login_admin()
        self.manager.remove_market("Shwapno")
        self.assertNotIn("Shwapno", self.manager.settings["markets"])


class TestRecords(ManagerTestCase):
    def test_member_can_add_record(self):
        self.login_member()
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.assertEqual(record.product_id, "ONION")
        self.assertEqual(record.added_by, "rafi")

    def test_record_ids_are_sequential(self):
        self.login_member()
        first = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        second = self.manager.add_record("RICE", "Karwan Bazar", self.yesterday(), 50)
        self.assertEqual(first.record_id, "R00001")
        self.assertEqual(second.record_id, "R00002")

    def test_same_day_duplicate_is_rejected(self):
        self.login_member()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        with self.assertRaises(DuplicateIDError):
            self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 45)

    def test_another_user_may_log_the_same_product_market_date(self):
        self.login_member("rafi")
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.logout()
        self.manager.login("sadia", "sadia123")
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 42)
        self.assertEqual(record.added_by, "sadia")

    def test_invalid_price_is_rejected(self):
        self.login_member()
        with self.assertRaises(ValidationError):
            self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), "abc")

    def test_negative_price_is_rejected(self):
        self.login_member()
        with self.assertRaises(ValidationError):
            self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), -5)

    def test_unknown_product_is_rejected(self):
        self.login_member()
        with self.assertRaises(RecordNotFoundError):
            self.manager.add_record("GHOST", "Karwan Bazar", self.yesterday(), 40)

    def test_unknown_market_is_rejected(self):
        self.login_member()
        with self.assertRaises(ValidationError):
            self.manager.add_record("ONION", "Nowhere Market", self.yesterday(), 40)

    def test_future_date_is_rejected(self):
        self.login_member()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValidationError):
            self.manager.add_record("ONION", "Karwan Bazar", tomorrow, 40)

    def test_member_can_edit_own_record(self):
        self.login_member()
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.update_record(record.record_id, price=45.0)
        self.assertEqual(self.manager.get_record(record.record_id).price, 45.0)

    def test_member_cannot_edit_another_record(self):
        self.login_member("rafi")
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.logout()
        self.manager.login("sadia", "sadia123")
        with self.assertRaises(PermissionDeniedError):
            self.manager.update_record(record.record_id, price=45.0)

    def test_admin_can_edit_any_record(self):
        self.login_member("rafi")
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.login_admin()
        self.manager.update_record(record.record_id, price=45.0)
        self.assertEqual(self.manager.get_record(record.record_id).price, 45.0)

    def test_a_rejected_edit_leaves_the_record_untouched(self):
        """A refused change must not change anything.

        If the record were changed first and checked afterwards, the
        record would keep the new values even though the edit was
        refused, and the next save would write them to the file.
        """
        self.login_admin()
        first = self.manager.add_record("ONION", "Karwan Bazar", "2026-10-05", 40)
        second = self.manager.add_record("ONION", "Karwan Bazar", "2026-10-06", 45)

        with self.assertRaises(DuplicateIDError):
            self.manager.update_record(
                second.record_id, date="2026-10-05", price=999.0
            )

        # The record is exactly as it was.
        stored = self.manager.get_record(second.record_id)
        self.assertEqual(stored.date, "2026-10-06")
        self.assertEqual(stored.price, 45.0)
        # And the other record is still there.
        self.assertEqual(self.manager.get_record(first.record_id).price, 40.0)

    def test_a_rejected_edit_is_not_written_to_the_file(self):
        self.login_admin()
        self.manager.add_record("ONION", "Karwan Bazar", "2026-10-05", 40)
        second = self.manager.add_record("ONION", "Karwan Bazar", "2026-10-06", 45)
        with self.assertRaises(DuplicateIDError):
            self.manager.update_record(
                second.record_id, date="2026-10-05", price=999.0
            )
        # Saving must not write the refused values out.
        self.manager.save_all()
        rows = (self.data_dir / "price_records.csv").read_text(encoding="utf-8")
        self.assertNotIn("999", rows)
        self.assertEqual(
            self.manager.get_record(second.record_id).price, 45.0
        )

    def test_member_cannot_delete(self):
        self.login_member()
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        with self.assertRaises(PermissionDeniedError):
            self.manager.delete_record(record.record_id)

    def test_admin_can_delete(self):
        self.login_member()
        record = self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.login_admin()
        self.manager.delete_record(record.record_id)
        self.assertEqual(len(self.manager.records), 0)

    def test_missing_record_raises_not_found(self):
        self.login_admin()
        with self.assertRaises(RecordNotFoundError):
            self.manager.delete_record("R99999")
        with self.assertRaises(RecordNotFoundError):
            self.manager.update_record("R99999", price=10)
        with self.assertRaises(RecordNotFoundError):
            self.manager.get_record("R99999")

    def test_records_survive_a_reload(self):
        self.login_member()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.reload()
        self.assertEqual(len(self.manager.records), 1)
        self.assertEqual(self.manager.records[0].price, 40.0)


class TestFiltering(ManagerTestCase):
    def setUp(self):
        super().setUp()
        self.login_member("rafi")
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.add_record("RICE", "Shwapno", self.yesterday(), 50)
        self.manager.logout()
        self.manager.login("sadia", "sadia123")
        self.manager.add_record("ONION", "Shwapno", self.yesterday(), 45)
        self.manager.logout()

    def test_filter_by_product(self):
        results = self.manager.filter_records(product_id="ONION")
        self.assertEqual(len(results), 2)

    def test_filter_by_market(self):
        results = self.manager.filter_records(market="Shwapno")
        self.assertEqual(len(results), 2)

    def test_filter_by_user(self):
        results = self.manager.filter_records(added_by="rafi")
        self.assertEqual(len(results), 2)

    def test_filter_by_text_search(self):
        results = self.manager.filter_records(search="onion")
        self.assertEqual(len(results), 2)

    def test_filter_by_date_range(self):
        results = self.manager.filter_records(
            date_from=self.yesterday(), date_to=self.yesterday()
        )
        self.assertEqual(len(results), 3)

    def test_filter_by_date_range_excludes_older(self):
        # date_from is an inclusive lower bound, so records from 30 days ago
        # are included and the recent ones are not.
        old = (date.today() - timedelta(days=30)).isoformat()
        self.assertEqual(len(self.manager.filter_records(date_from=old)), 3)

    def test_filter_by_date_to_excludes_newer(self):
        # date_to is an inclusive upper bound.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(len(self.manager.filter_records(date_to=tomorrow)), 3)
        old = (date.today() - timedelta(days=30)).isoformat()
        self.assertEqual(len(self.manager.filter_records(date_to=old)), 0)

    def test_combined_filters(self):
        results = self.manager.filter_records(product_id="ONION", market="Shwapno")
        self.assertEqual(len(results), 1)

    def test_no_match_returns_empty_list(self):
        self.assertEqual(self.manager.filter_records(product_id="GHOST"), [])

    def test_empty_filter_returns_everything(self):
        self.assertEqual(len(self.manager.filter_records()), 3)


class TestBasket(ManagerTestCase):
    def test_item_can_be_added_to_own_basket(self):
        self.login_member()
        self.manager.set_basket_item("rafi", "ONION", 2.0)
        self.assertEqual(self.manager.get_basket("rafi")["items"], {"ONION": 2.0})

    def test_item_can_be_removed(self):
        self.login_member()
        self.manager.set_basket_item("rafi", "ONION", 2.0)
        self.manager.remove_basket_item("rafi", "ONION")
        self.assertEqual(self.manager.get_basket("rafi")["items"], {})

    def test_budget_can_be_set(self):
        self.login_member()
        self.manager.set_budget("rafi", 1000.0)
        self.assertEqual(self.manager.get_basket("rafi")["budget"], 1000.0)

    def test_member_cannot_touch_another_basket(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.set_basket_item("sadia", "ONION", 2.0)
        with self.assertRaises(PermissionDeniedError):
            self.manager.set_budget("sadia", 500.0)

    def test_invalid_quantity_is_rejected(self):
        self.login_member()
        with self.assertRaises(ValidationError):
            self.manager.set_basket_item("rafi", "ONION", -1)

    def test_basket_survives_a_reload(self):
        self.login_member()
        self.manager.set_basket_item("rafi", "ONION", 2.0)
        self.manager.set_budget("rafi", 500.0)
        self.manager.reload()
        self.assertEqual(self.manager.get_basket("rafi")["items"], {"ONION": 2.0})
        self.assertEqual(self.manager.get_basket("rafi")["budget"], 500.0)


class TestSettings(ManagerTestCase):
    def test_threshold_can_be_changed_by_admin(self):
        self.login_admin()
        self.manager.update_settings({"z_threshold": 3.0})
        self.assertEqual(self.manager.settings["z_threshold"], 3.0)

    def test_out_of_range_threshold_is_rejected(self):
        self.login_admin()
        with self.assertRaises(ValidationError):
            self.manager.update_settings({"z_threshold": 99})

    def test_member_cannot_change_settings(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.update_settings({"z_threshold": 3.0})

    def test_show_bangla_names_can_be_toggled(self):
        self.login_admin()
        self.manager.update_settings({"show_bangla_names": False})
        self.assertFalse(self.manager.settings["show_bangla_names"])

    def test_settings_survive_a_reload(self):
        self.login_admin()
        self.manager.update_settings({"z_threshold": 3.0})
        self.manager.reload()
        self.assertEqual(self.manager.settings["z_threshold"], 3.0)


class TestSummaries(ManagerTestCase):
    def test_dashboard_counts(self):
        self.login_member()
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        summary = self.manager.dashboard_summary()
        self.assertEqual(summary["products"], 12)
        self.assertEqual(summary["markets"], 3)
        self.assertEqual(summary["records"], 1)
        self.assertEqual(summary["my_records"], 1)

    def test_records_per_user(self):
        self.login_member("rafi")
        self.manager.add_record("ONION", "Karwan Bazar", self.yesterday(), 40)
        self.manager.logout()
        self.manager.login("sadia", "sadia123")
        self.manager.add_record("RICE", "Shwapno", self.yesterday(), 50)
        counts = self.manager.records_per_user()
        self.assertEqual(counts["rafi"], 1)
        self.assertEqual(counts["sadia"], 1)

    def test_user_list_for_admin(self):
        self.login_admin()
        users = self.manager.list_users()
        self.assertEqual(len(users), 3)

    def test_member_cannot_list_users(self):
        self.login_member()
        with self.assertRaises(PermissionDeniedError):
            self.manager.list_users()

    def test_products_missing_a_reference_price(self):
        self.login_admin()
        self.manager.set_reference_price("ONION", 35.0)
        missing = self.manager.products_missing_reference_price()
        self.assertEqual(len(missing), 11)
        self.assertNotIn("ONION", missing)


if __name__ == "__main__":
    unittest.main()
