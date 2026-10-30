"""Smoke tests for the GUI.

These drive the real tkinter widgets against a temp data folder.  They are
skipped when there is no display available (a headless CI machine), so the
rest of the suite still runs there.

Run them with:

    python -m unittest tests.test_gui -v
"""

import contextlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import config as config_module

try:
    import tkinter as tk

    _probe = tk.Tk()
    _probe.withdraw()
    _probe.destroy()
    TK_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the machine
    TK_AVAILABLE = False

if TK_AVAILABLE:
    # The message boxes are modal, so they would block the test run.  They
    # are replaced with harmless stubs that record what was shown.
    from gui import widgets
    from gui.app import BazarApp
    from gui.records_tab import EditRecordDialog
    from manager import BazarManager

    _SHOWN = {"errors": [], "infos": [], "warnings": [], "confirm": True}

    def _fake_showerror(parent, message, title="Error"):
        _SHOWN["errors"].append(message)

    def _fake_showinfo(parent, message, title="BazarWatch BD"):
        _SHOWN["infos"].append(message)

    def _fake_showwarning(parent, message, title="Warning"):
        _SHOWN["warnings"].append(message)

    def _fake_confirm(parent, question, title="Please confirm"):
        _SHOWN["confirm"] = True
        return True

    widgets.show_error = _fake_showerror
    widgets.show_info = _fake_showinfo
    widgets.show_warning = _fake_showwarning
    widgets.confirm = _fake_confirm

    # The simple dialogs are modal too; they are stubbed so they cannot
    # block the test run.
    from tkinter import simpledialog

    def _fake_askstring(title, prompt, initialvalue="", parent=None, show=None,
                        **kwargs):
        return _SHOWN.get("askstring")

    simpledialog.askstring = _fake_askstring

    # The other modules import these names directly, so patch them there too.
    import gui.admin_tab
    import gui.app
    import gui.basket_tab
    import gui.log_price_tab
    import gui.login_view
    import gui.records_tab
    import gui.stats_tab

    for _module in (
        gui.admin_tab, gui.app, gui.basket_tab, gui.login_view,
        gui.log_price_tab, gui.records_tab, gui.stats_tab,
    ):
        if hasattr(_module, "show_error"):
            _module.show_error = _fake_showerror  # type: ignore[attr-defined]
        if hasattr(_module, "show_info"):
            _module.show_info = _fake_showinfo  # type: ignore[attr-defined]
        if hasattr(_module, "show_warning"):
            _module.show_warning = _fake_showwarning  # type: ignore[attr-defined]
        if hasattr(_module, "confirm"):
            _module.confirm = _fake_confirm  # type: ignore[attr-defined]


@unittest.skipUnless(TK_AVAILABLE, "no display available")
class GuiTestCase(unittest.TestCase):
    """A manager on a temp folder, plus an app window."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.manager = BazarManager(self.data_dir)
        self.manager.create_admin("admin", "admin123")
        # Adding a member is an Admin action, so log in as the Admin first.
        self.manager.login("admin", "admin123")
        self.manager.add_member("rafi", "rafi123")
        self.manager.logout()

        self.app = BazarApp(manager=self.manager)
        self.app.update_idletasks()

    def tearDown(self):
        # The window may already be gone, so a failure here is not
        # interesting.
        with contextlib.suppress(Exception):
            self.app.destroy()
        self._tmp.cleanup()

    def _login(self, username="admin", password="admin123"):
        """Log in through the real login screen."""
        view = self.app._body.winfo_children()[0]
        view.title_var.set(username)
        view.password_var.set(password)
        view._do_login()
        self.app.update_idletasks()

    def _settle(self):
        """Let the window finish laying out."""
        for _ in range(4):
            self.app.update_idletasks()
            self.app.update()

    def _select_tab(self, name):
        """Make a tab the visible page and let it lay out."""
        tab = self.app._tabs[name]
        self.app._notebook.select(tab)
        self._settle()
        return tab

    def _packed_frames(self):
        """The frames that are packed into the root window."""
        return [
            child
            for child in self.app.winfo_children()
            if child.winfo_manager() == "pack"
        ]


class TestLoginScreen(GuiTestCase):
    def test_login_screen_is_shown_first(self):
        self.assertTrue(self.app._body.winfo_children())

    def test_first_run_shows_create_admin(self):
        # A brand new manager with no users.
        with tempfile.TemporaryDirectory() as tmp:
            manager = BazarManager(Path(tmp))
            app = BazarApp(manager=manager)
            try:
                view = app._body.winfo_children()[0]
                self.assertTrue(view.is_first_run)
            finally:
                app.destroy()

    def test_wrong_password_shows_an_error_and_stays_on_login(self):
        self._login("admin", "wrongpass")
        view = self.app._body.winfo_children()[0]
        self.assertIn("Wrong username", view.error_var.get())

    def test_successful_login_builds_the_tabs(self):
        self._login()
        self.assertIn("Dashboard", self.app._tabs)
        self.assertIn("Log Price", self.app._tabs)
        self.assertIn("Records", self.app._tabs)
        self.assertIn("Statistics & Alerts", self.app._tabs)
        self.assertIn("My Basket", self.app._tabs)

    def test_admin_gets_the_admin_tab(self):
        self._login()
        self.assertIn("Admin", self.app._tabs)

    def test_member_does_not_get_the_admin_tab(self):
        self._login("rafi", "rafi123")
        self.assertNotIn("Admin", self.app._tabs)

    def test_logout_returns_to_the_login_screen(self):
        self._login()
        self.app._logout()
        self.app.update_idletasks()
        self.assertNotIn("Dashboard", self.app._tabs)


class TestLogPriceTab(GuiTestCase):
    def test_logging_a_price_shows_the_alert_level(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["Log Price"]

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tab.product_var.set(tab.product_box["values"][0])
        tab.market_var.set(tab.market_box["values"][0])
        tab.date_var.set(yesterday)
        tab.price_var.set("45")
        tab._save()
        self.app.update_idletasks()

        self.assertIn("Normal", tab.result_label.cget("text"))
        self.assertEqual(len(self.manager.records), 1)

    def test_an_invalid_price_shows_a_message_and_saves_nothing(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["Log Price"]
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tab.product_var.set(tab.product_box["values"][0])
        tab.market_var.set(tab.market_box["values"][0])
        tab.date_var.set(yesterday)
        tab.price_var.set("abc")
        tab._save()
        self.assertEqual(len(self.manager.records), 0)

    def test_a_future_date_is_refused(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["Log Price"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        tab.product_var.set(tab.product_box["values"][0])
        tab.market_var.set(tab.market_box["values"][0])
        tab.date_var.set(tomorrow)
        tab.price_var.set("45")
        tab._save()
        self.assertEqual(len(self.manager.records), 0)


class TestRecordsTab(GuiTestCase):
    def setUp(self):
        super().setUp()
        self._login("rafi", "rafi123")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.manager.add_record("ONION", "Karwan Bazar", yesterday, 45.0)

    def test_the_table_shows_the_records(self):
        tab = self.app._tabs["Records"]
        tab.refresh()
        rows = tab.table.tree.get_children()
        self.assertEqual(len(rows), 1)

    def test_the_delete_button_is_disabled_for_a_member(self):
        tab = self.app._tabs["Records"]
        tab.refresh()
        tab.table.tree.selection_set(tab.table.tree.get_children()[0])
        tab._update_buttons()
        self.assertEqual(str(tab.delete_button.cget("state")), "disabled")

    def test_the_edit_button_is_enabled_for_the_owner(self):
        tab = self.app._tabs["Records"]
        tab.refresh()
        tab.table.tree.selection_set(tab.table.tree.get_children()[0])
        tab._update_buttons()
        self.assertEqual(str(tab.edit_button.cget("state")), "normal")

    def test_clicking_a_row_enables_the_edit_button(self):
        """The buttons must follow the user's own selection.

        The user clicks a row, not a method call, so the tab has to
        listen for the selection event.
        """
        tab = self.app._tabs["Records"]
        tab.refresh()
        row = tab.table.tree.get_children()[0]
        tab.table.tree.selection_set(row)
        tab.table.tree.event_generate("<<TreeviewSelect>>")
        self.app.update_idletasks()
        self.assertEqual(str(tab.edit_button.cget("state")), "normal")

    def test_an_admin_can_delete_through_the_button(self):
        self.app._logout()
        self._login("admin", "admin123")
        tab = self.app._tabs["Records"]
        tab.refresh()
        row = tab.table.tree.get_children()[0]
        tab.table.tree.selection_set(row)
        tab.table.tree.event_generate("<<TreeviewSelect>>")
        self.app.update_idletasks()
        self.assertEqual(str(tab.delete_button.cget("state")), "normal")

    def test_the_selection_survives_a_refresh(self):
        tab = self.app._tabs["Records"]
        tab.refresh()
        row = tab.table.tree.get_children()[0]
        tab.table.tree.selection_set(row)
        tab.refresh()
        self.assertEqual(tab.table.selected_id(), row)

    def test_search_filters_the_table(self):
        tab = self.app._tabs["Records"]
        tab.search_var.set("onion")
        tab.refresh()
        self.assertEqual(len(tab.table.tree.get_children()), 1)
        tab.search_var.set("nothing matches this")
        tab.refresh()
        self.assertEqual(len(tab.table.tree.get_children()), 0)


class TestRecordsTabActions(GuiTestCase):
    """Editing, deleting and filtering the records."""

    def setUp(self):
        super().setUp()
        self._login("rafi", "rafi123")
        self.yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.record = self.manager.add_record(
            "ONION", "Karwan Bazar", self.yesterday, 45.0
        )
        self.tab = self.app._tabs["Records"]
        self.tab.refresh()

    def _select_the_record(self):
        """Select the only record in the table."""
        rows = self.tab.table.tree.get_children()
        self.tab.table.tree.selection_set(rows[0])
        return rows[0]

    def test_clearing_the_filters_shows_everything_again(self):
        self.tab.search_var.set("onion")
        self.tab.from_var.set(self.yesterday)
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab._clear_filters()
        self.assertEqual(self.tab.search_var.get(), "")
        self.assertEqual(self.tab.from_var.get(), "")
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)

    def test_the_product_filter_narrows_the_table(self):
        self.tab.product_var.set(self.manager.product_label("ONION"))
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab.product_var.set(self.manager.product_label("RICE"))
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 0)

    def test_the_market_filter_narrows_the_table(self):
        self.tab.market_var.set("Karwan Bazar")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab.market_var.set("Shwapno")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 0)

    def test_the_logged_by_filter_narrows_the_table(self):
        self.tab.user_var.set("rafi")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab.user_var.set("admin")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 0)

    def test_the_level_filter_narrows_the_table(self):
        self.tab.level_var.set("Normal")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab.level_var.set("Spike")
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 0)

    def test_the_date_range_filter_narrows_the_table(self):
        self.tab.from_var.set(self.yesterday)
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 1)
        self.tab.from_var.set((date.today() + timedelta(days=5)).isoformat())
        self.tab.refresh()
        self.assertEqual(len(self.tab.table.tree.get_children()), 0)

    def test_editing_without_a_selection_shows_a_message(self):
        self.tab.table.tree.selection_remove(*self.tab.table.tree.get_children())
        self.tab._edit_selected()
        self.assertTrue(_SHOWN["infos"])

    def test_the_edit_dialog_saves_the_new_price(self):
        record_id = self._select_the_record()
        self.tab._edit_selected(record_id)
        # The dialog is modal, so it is driven directly.
        dialog = EditRecordDialog(
            self.app, self.manager, self.manager.get_record(record_id),
            self.tab.refresh,
        )
        dialog.price_var.set("50")
        dialog._save()
        self.assertEqual(self.manager.get_record(record_id).price, 50.0)

    def test_the_edit_dialog_keeps_a_bad_price_on_screen(self):
        record_id = self._select_the_record()
        dialog = EditRecordDialog(
            self.app, self.manager, self.manager.get_record(record_id),
            self.tab.refresh,
        )
        dialog.price_var.set("not a price")
        dialog._save()
        self.assertIn("price", dialog.error_var.get().lower())
        # The record is unchanged.
        self.assertEqual(self.manager.get_record(record_id).price, 45.0)
        dialog.destroy()

    def test_deleting_without_a_selection_shows_a_message(self):
        self.tab.table.tree.selection_remove(*self.tab.table.tree.get_children())
        self.tab._delete_selected()
        self.assertTrue(_SHOWN["infos"])

    def test_a_member_cannot_delete_a_record(self):
        self._select_the_record()
        self.tab._delete_selected()
        self.assertTrue(_SHOWN["infos"])
        self.assertEqual(len(self.manager.records), 1)

    def test_an_admin_can_delete_a_record(self):
        self.app._logout()
        self._login("admin", "admin123")
        tab = self.app._tabs["Records"]
        tab.refresh()
        rows = tab.table.tree.get_children()
        tab.table.tree.selection_set(rows[0])
        tab._delete_selected()
        self.assertEqual(len(self.manager.records), 0)
        self.assertEqual(len(tab.table.tree.get_children()), 0)

    def test_an_admin_can_edit_any_record(self):
        self.app._logout()
        self._login("admin", "admin123")
        tab = self.app._tabs["Records"]
        tab.refresh()
        rows = tab.table.tree.get_children()
        tab.table.tree.selection_set(rows[0])
        tab._update_buttons()
        self.assertEqual(str(tab.edit_button.cget("state")), "normal")


class TestLogPriceTabDetails(GuiTestCase):
    """The details shown next to the Log Price form."""

    def setUp(self):
        super().setUp()
        self._login("rafi", "rafi123")
        self.tab = self.app._tabs["Log Price"]

    def test_logging_in_does_not_show_an_error(self):
        """Every tab must be able to reload itself without an exception."""
        _SHOWN["errors"].clear()
        self.app.refresh_all()
        self.assertEqual(_SHOWN["errors"], [])

    def test_the_log_price_tab_can_reload_itself(self):
        self.tab.refresh()
        self.assertTrue(self.tab.product_box["values"])

    def test_the_product_details_are_shown(self):
        self.tab.product_var.set(self.tab.product_box["values"][0])
        self.tab._on_product()
        self.assertTrue(self.tab.detail_var.get())

    def test_a_reference_price_is_shown_when_it_is_set(self):
        # Only an Admin may set a reference price, so log in as one.
        self.app._logout()
        self._login("admin", "admin123")
        self.manager.set_reference_price("ONION", 40.0)
        self.tab = self.app._tabs["Log Price"]
        self.tab.refresh_choices()
        for name in self.tab.product_box["values"]:
            if "Onion" in name:
                self.tab.product_var.set(name)
                break
        self.tab._on_product()
        self.assertIn("40", self.tab.detail_var.get())

    def test_the_form_can_be_cleared(self):
        self.tab.price_var.set("45")
        self.tab._clear()
        self.assertEqual(self.tab.price_var.get(), "")
        self.assertEqual(self.tab.result_label.cget("text"), "")

    def test_a_saved_record_shows_its_alert_level(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.tab.product_var.set(self.tab.product_box["values"][0])
        self.tab.market_var.set(self.tab.market_box["values"][0])
        self.tab.date_var.set(yesterday)
        self.tab.price_var.set("45")
        self.tab._save()
        self.assertIn("Normal", self.tab.result_label.cget("text"))


class TestStatsTabReport(GuiTestCase):
    """Previewing and saving the weekly report."""

    def setUp(self):
        super().setUp()
        self._login("admin", "admin123")
        self.tab = self.app._tabs["Statistics & Alerts"]

    def test_the_report_can_be_previewed(self):
        self.tab._preview_report()
        text = self.tab.preview.get("1.0", "end")
        self.assertIn("WEEKLY", text.upper())

    def test_a_bad_report_date_shows_a_message(self):
        self.tab.report_date_var.set("not a date")
        self.tab._preview_report()
        self.assertTrue(_SHOWN["infos"])

    def test_a_bad_report_date_is_refused_when_saving(self):
        self.tab.report_date_var.set("31-12-2026")
        self.tab._save_report()
        self.assertTrue(_SHOWN["infos"])

    def test_the_report_can_be_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = config_module.REPORTS_DIR
            config_module.REPORTS_DIR = Path(tmp)
            try:
                self.tab._save_report()
                files = list(Path(tmp).glob("weekly_report_*.txt"))
                self.assertEqual(len(files), 1)
            finally:
                config_module.REPORTS_DIR = original

    def test_the_statistics_table_has_a_row_per_product(self):
        rows = self.tab.stats_table.tree.get_children()
        self.assertEqual(len(rows), len(self.manager.products))

    def test_the_alerts_table_only_holds_alerts(self):
        for row in self.tab.alerts_table.tree.get_children():
            level = self.tab.alerts_table.tree.item(row, "values")[0]
            self.assertIn(level, ("Spike", "Watch"))


class TestBasketTabActions(GuiTestCase):
    """Adding, removing and budgeting."""

    def setUp(self):
        super().setUp()
        self._login("rafi", "rafi123")
        self.tab = self.app._tabs["My Basket"]

    def _choose(self, product_id):
        """Pick a product in the dropdown."""
        self.tab.product_var.set(self.manager.product_label(product_id))

    def test_adding_an_item_without_a_product_shows_a_message(self):
        self.tab.product_var.set("")
        self.tab._add_item()
        self.assertTrue(_SHOWN["infos"])

    def test_an_item_can_be_removed_by_the_dropdown(self):
        self._choose("ONION")
        self.tab.quantity_var.set("2")
        self.tab._add_item()
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 1)
        self.tab._remove_item()
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 0)

    def test_an_item_can_be_removed_by_double_clicking(self):
        self._choose("ONION")
        self.tab._add_item()
        self.tab._remove_by_id("ONION")
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 0)

    def test_removing_nothing_shows_a_message(self):
        self.tab.product_var.set("")
        self.tab._remove_item()
        self.assertTrue(_SHOWN["infos"])

    def test_the_budget_can_be_saved(self):
        self.tab.budget_var.set("500")
        self.tab._save_budget()
        self.assertEqual(self.manager.get_basket("rafi")["budget"], 500.0)

    def test_the_basket_can_be_cleared(self):
        self._choose("ONION")
        self.tab._add_item()
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 1)
        self.tab._clear_basket()
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 0)

    def test_the_basket_is_empty_before_anything_is_added(self):
        self.assertEqual(len(self.tab.items_table.tree.get_children()), 0)

    def test_the_totals_table_always_has_a_row(self):
        self._choose("ONION")
        self.tab._add_item()
        # With no prices recorded there is no market to total up, but
        # the table still explains that.
        self.assertTrue(self.tab.totals_table.tree.get_children())


class TestAdminTabActions(GuiTestCase):
    """The Admin sub-tabs."""

    def setUp(self):
        super().setUp()
        self._login("admin", "admin123")
        self.tab = self.app._tabs["Admin"]

    @staticmethod
    def _select(table, item_id):
        """Select the row with the given id."""
        table.tree.selection_set(item_id)

    def test_a_member_can_be_removed(self):
        users = self.tab.users_tab
        self._select(users.table, "rafi")
        users._remove_member()
        self.assertNotIn("rafi", self.manager.users)

    def test_removing_without_a_selection_shows_a_message(self):
        users = self.tab.users_tab
        users.table.tree.selection_remove(*users.table.tree.get_children())
        users._remove_member()
        self.assertTrue(_SHOWN["infos"])

    def test_a_product_can_be_removed(self):
        products = self.tab.products_tab
        products.product_id_var.set("MILK")
        products.name_var.set("Milk powder")
        products.unit_var.set("kg")
        products.category_var.set("Grocery")
        products._add_product()
        self.assertIn("MILK", self.manager.products)
        self._select(products.table, "MILK")
        products._remove_product()
        self.assertNotIn("MILK", self.manager.products)

    def test_a_market_can_be_removed(self):
        markets = self.tab.markets_tab
        markets.market_var.set("Bashundhara")
        markets._add_market()
        self.assertIn("Bashundhara", self.manager.markets())
        self._select(markets.table, "Bashundhara")
        markets._remove_market()
        self.assertNotIn("Bashundhara", self.manager.markets())

    def test_the_settings_can_be_reset(self):
        settings = self.tab.settings_tab
        settings.vars["z_threshold"].set("3.0")
        settings._save()
        self.assertEqual(self.manager.settings["z_threshold"], 3.0)
        settings._reset()
        self.assertEqual(self.manager.settings["z_threshold"], 2.0)


class TestWindowLayout(GuiTestCase):
    """The window must not steal vertical space from the tables.

    The login screen and the tabbed screen each live in their own frame
    packed into the root window.  If the login frame is left behind, it
    keeps its space and the tables are squeezed to nothing.
    """

    def test_the_login_frame_is_destroyed_when_the_user_logs_in(self):
        self._login()
        # Only the header and the tabbed body may remain packed.
        frames = self._packed_frames()
        self.assertLessEqual(
            len(frames),
            2,
            "the old login frame is still packed into the window",
        )

    def test_the_tab_area_gets_most_of_the_window_height(self):
        self._login()
        self._settle()
        notebook_height = self.app._notebook.winfo_height()
        window_height = self.app.winfo_height()
        self.assertGreater(
            notebook_height,
            window_height * 0.6,
            "the tabs do not have enough vertical space",
        )

    def test_the_records_table_is_visible_after_login(self):
        self._login()
        tab = self._select_tab("Records")
        self.assertGreater(tab.table.tree.winfo_height(), 100)
        self.assertGreater(tab.table.tree.winfo_width(), 100)

    def test_the_statistics_tables_are_visible_after_login(self):
        self._login()
        tab = self._select_tab("Statistics & Alerts")
        self.assertGreater(tab.stats_table.tree.winfo_height(), 50)
        self.assertGreater(tab.alerts_table.tree.winfo_height(), 50)

    def test_the_basket_tables_are_visible_after_login(self):
        self._login()
        tab = self._select_tab("My Basket")
        self.assertGreater(tab.items_table.tree.winfo_height(), 50)
        self.assertGreater(tab.totals_table.tree.winfo_height(), 20)

    def test_logging_out_returns_the_login_screen(self):
        self._login()
        self.app._logout()
        self._settle()
        self.assertTrue(self.app._body.winfo_children())
        frames = self._packed_frames()
        self.assertLessEqual(len(frames), 2)


class TestBasketTab(GuiTestCase):
    def test_adding_an_item_shows_it_in_the_table(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["My Basket"]
        tab.product_var.set(tab.product_box["values"][0])
        tab.quantity_var.set("2")
        tab._add_item()
        self.app.update_idletasks()
        self.assertEqual(len(tab.items_table.tree.get_children()), 1)

    def test_the_budget_status_is_shown(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["My Basket"]
        self.assertTrue(tab.budget_var_out.get())

    def test_an_invalid_quantity_is_refused(self):
        self._login("rafi", "rafi123")
        tab = self.app._tabs["My Basket"]
        tab.product_var.set(tab.product_box["values"][0])
        tab.quantity_var.set("-1")
        tab._add_item()
        self.assertEqual(len(tab.items_table.tree.get_children()), 0)


class TestAdminTab(GuiTestCase):
    def test_the_admin_tab_has_four_sub_tabs(self):
        self._login()
        tab = self.app._tabs["Admin"]
        names = [tab.notebook.tab(i, "text") for i in range(tab.notebook.index("end"))]
        self.assertEqual(names, ["Users", "Products", "Markets", "Settings"])

    def test_adding_a_member_through_the_tab(self):
        self._login()
        tab = self.app._tabs["Admin"]
        tab.users_tab.username_var.set("newbie")
        tab.users_tab.password_var.set("newbie123")
        tab.users_tab._add_member()
        self.assertIn("newbie", self.manager.users)

    def test_adding_a_product_through_the_tab(self):
        self._login()
        tab = self.app._tabs["Admin"]
        products_tab = tab.products_tab
        products_tab.product_id_var.set("MILK")
        products_tab.name_var.set("Milk powder")
        products_tab.unit_var.set("kg")
        products_tab.category_var.set("Grocery")
        products_tab._add_product()
        self.assertIn("MILK", self.manager.products)

    def test_adding_a_market_through_the_tab(self):
        self._login()
        tab = self.app._tabs["Admin"]
        tab.markets_tab.market_var.set("Bashundhara")
        tab.markets_tab._add_market()
        self.assertIn("Bashundhara", self.manager.markets())

    def test_saving_a_threshold_through_the_tab(self):
        self._login()
        tab = self.app._tabs["Admin"]
        tab.settings_tab.vars["z_threshold"].set("3.0")
        tab.settings_tab._save()
        self.assertEqual(self.manager.settings["z_threshold"], 3.0)

    def test_an_out_of_range_threshold_is_refused(self):
        self._login()
        tab = self.app._tabs["Admin"]
        tab.settings_tab.vars["z_threshold"].set("99")
        tab.settings_tab._save()
        self.assertEqual(self.manager.settings["z_threshold"], 2.0)


class TestDropdownLabelsAreUnique(GuiTestCase):
    """Two products with the same name must still be tellable apart."""

    def setUp(self):
        super().setUp()
        self._login("admin", "admin123")

    def _add_product(self, product_id):
        """Add a product through the Admin tab, as a user would."""
        products = self.app._tabs["Admin"].products_tab
        products.product_id_var.set(product_id)
        products.name_var.set("Rice")
        products.name_bn_var.set("চাল")
        products.unit_var.set("kg")
        products.category_var.set("Grains")
        products._add_product()

    def test_the_log_price_dropdown_names_the_product_id(self):
        self._add_product("RICE1")
        self._add_product("RICE2")
        tab = self.app._tabs["Log Price"]
        values = list(tab.product_box["values"])
        self.assertTrue(
            any("RICE1" in value for value in values),
            f"The dropdown does not name the product ID: {values}",
        )
        self.assertTrue(
            any("RICE2" in value for value in values),
            f"The dropdown does not name the product ID: {values}",
        )

    def test_the_two_products_map_back_to_the_right_ids(self):
        self._add_product("RICE1")
        self._add_product("RICE2")
        tab = self.app._tabs["Log Price"]
        ids = {
            tab._product_id_for(label)
            for label in tab.product_box["values"]
            if "Rice" in label
        }
        self.assertEqual(ids, {"RICE1", "RICE2"})

    def test_the_records_filter_names_the_product_id(self):
        self._add_product("RICE1")
        self._add_product("RICE2")
        tab = self.app._tabs["Records"]
        values = list(tab.product_box["values"])
        self.assertTrue(
            any("RICE1" in value for value in values)
            and any("RICE2" in value for value in values),
            f"The filter does not tell the two Rices apart: {values}",
        )

    def test_a_new_product_shows_up_in_the_log_price_dropdown(self):
        # The Admin adds a product; the Log Price tab has to offer it
        # without the user reloading the data by hand.
        self._add_product("MILK2")
        tab = self.app._tabs["Log Price"]
        self.assertIn("MILK2", " ".join(tab.product_box["values"]))

    def test_the_basket_dropdown_shows_the_new_product(self):
        self._add_product("MILK2")
        tab = self.app._tabs["My Basket"]
        self.assertIn("MILK2", " ".join(tab.product_box["values"]))


class TestAdminSelectionSurvivesARefresh(GuiTestCase):
    """The Admin sub-tabs must keep the selected row across a refresh."""

    def setUp(self):
        super().setUp()
        self._login("admin", "admin123")
        self.tab = self.app._tabs["Admin"]

    def test_the_users_selection_survives_a_refresh(self):
        users = self.tab.users_tab
        users.refresh()
        users.table.tree.selection_set("rafi")
        users.refresh()
        self.assertEqual(users.table.selected_id(), "rafi")

    def test_the_products_selection_survives_a_refresh(self):
        products = self.tab.products_tab
        products.refresh()
        products.table.tree.selection_set("ONION")
        products.refresh()
        self.assertEqual(products.table.selected_id(), "ONION")

    def test_the_markets_selection_survives_a_refresh(self):
        markets = self.tab.markets_tab
        markets.refresh()
        markets.table.tree.selection_set("Karwan Bazar")
        markets.refresh()
        self.assertEqual(markets.table.selected_id(), "Karwan Bazar")


class TestSettingsChangesReachTheOtherTabs(GuiTestCase):
    """A setting the Admin changes must show up on the other tabs."""

    def setUp(self):
        super().setUp()
        self._login("admin", "admin123")
        self.tab = self.app._tabs["Admin"]

    def test_turning_off_the_bangla_names_reaches_the_log_price_tab(self):
        settings = self.tab.settings_tab
        settings.vars["show_bangla_names"].set(False)
        settings._save()
        log_price = self.app._tabs["Log Price"]
        labels = list(log_price.product_box["values"])
        # With the Bangla names off a label is "Onion (local) [ONION]".
        self.assertTrue(
            all("দেশি" not in label for label in labels),
            f"The Bangla names are still showing: {labels}",
        )

    def test_the_bangla_names_come_back_when_the_setting_is_reset(self):
        settings = self.tab.settings_tab
        settings.vars["show_bangla_names"].set(False)
        settings._save()
        settings._reset()
        log_price = self.app._tabs["Log Price"]
        labels = list(log_price.product_box["values"])
        self.assertTrue(
            any("দেশি" in label for label in labels),
            f"The Bangla names did not come back: {labels}",
        )

    def test_a_new_market_reaches_the_log_price_dropdown(self):
        markets = self.tab.markets_tab
        markets.market_var.set("Bashundhara")
        markets._add_market()
        log_price = self.app._tabs["Log Price"]
        self.assertIn("Bashundhara", list(log_price.market_box["values"]))


class TestMenuActions(GuiTestCase):
    def test_reload_data_keeps_the_app_running(self):
        self._login()
        self.app._reload_data()
        self.assertTrue(self.app._tabs)

    def test_the_weekly_report_can_be_generated(self):
        self._login()
        with tempfile.TemporaryDirectory() as tmp:
            original = config_module.REPORTS_DIR
            config_module.REPORTS_DIR = Path(tmp)
            try:
                self.app._generate_report()
                files = list(Path(tmp).glob("weekly_report_*.txt"))
                self.assertEqual(len(files), 1)
            finally:
                config_module.REPORTS_DIR = original


if __name__ == "__main__":
    unittest.main()
