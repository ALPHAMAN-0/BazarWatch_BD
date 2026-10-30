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
            _module.show_error = _fake_showerror
        if hasattr(_module, "show_info"):
            _module.show_info = _fake_showinfo
        if hasattr(_module, "show_warning"):
            _module.show_warning = _fake_showwarning
        if hasattr(_module, "confirm"):
            _module.confirm = _fake_confirm


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

    def test_search_filters_the_table(self):
        tab = self.app._tabs["Records"]
        tab.search_var.set("onion")
        tab.refresh()
        self.assertEqual(len(tab.table.tree.get_children()), 1)
        tab.search_var.set("nothing matches this")
        tab.refresh()
        self.assertEqual(len(tab.table.tree.get_children()), 0)


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
