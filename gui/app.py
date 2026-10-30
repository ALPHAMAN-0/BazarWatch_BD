"""The main window of BazarWatch BD.

Shows the login screen first, then the tabs.  The Admin tab is only added for
an Admin, and the menu offers Reload data, Generate weekly report and Exit.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import simpledialog, ttk

from gui.admin_tab import AdminTab
from gui.basket_tab import BasketTab
from gui.dashboard_tab import DashboardTab
from gui.log_price_tab import LogPriceTab
from gui.login_view import LoginView
from gui.records_tab import RecordsTab
from gui.stats_tab import StatsTab
from gui.widgets import (
    apply_theme,
    handle_error,
    setup_error_log,
    show_info,
    show_warning,
)
from manager import BazarManager
from reports import save_weekly_report


class BazarApp(tk.Tk):
    """The main application window."""

    def __init__(self, manager: BazarManager | None = None, data_dir=None):
        super().__init__()

        self.manager = manager or BazarManager(data_dir)
        self.logger = setup_error_log()

        self.title("BazarWatch BD - Household price tracker")
        self.geometry("1180x740")
        self.minsize(940, 600)

        apply_theme(self)

        self._tabs = {}
        self._notebook = None
        self._header = None
        self._body = None

        self._build_menu()
        self._show_login()

        self._warn_about_data_problems()

    # -- layout ------------------------------------------------------------
    def _build_menu(self) -> None:
        """The File menu."""
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Reload data", command=self._reload_data
        )
        file_menu.add_command(
            label="Generate weekly report", command=self._generate_report
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        self.config(menu=menubar)

    def _clear_body(self) -> None:
        """Remove everything from the content area.

        The body frame itself is kept: it is packed into the root window and
        must stay there, otherwise the new body would be packed next to the
        old one and the window would be split in two.
        """
        for child in self._body.winfo_children():
            child.destroy()

    def _show_login(self) -> None:
        """Show the login screen."""
        if self._body is None:
            self._body = ttk.Frame(self, padding=0)
            self._body.pack(fill="both", expand=True)
            self._body.rowconfigure(0, weight=1)
            self._body.columnconfigure(0, weight=1)
        self._clear_body()

        login = LoginView(self._body, self.manager, self._on_login_success)
        login.grid(row=0, column=0, sticky="nsew")

    def _on_login_success(self, user) -> None:
        """Build the main window once the user is logged in."""
        self._clear_body()
        # The header lives inside the body so that the body is the only
        # thing packed into the root window.
        self._body.rowconfigure(1, weight=1)

        # -- the header
        self._header = ttk.Frame(self._body, padding=(12, 10))
        self._header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            self._header,
            text="BazarWatch BD",
            font=("TkDefaultFont", 15, "bold"),
        ).pack(side="left")
        ttk.Label(
            self._header,
            text=f"Logged in as {user.username} ({user.role.capitalize()})",
        ).pack(side="left", padx=20)
        ttk.Button(
            self._header, text="Change password", command=self._change_password
        ).pack(side="right", padx=4)
        ttk.Button(
            self._header, text="Logout", command=self._logout
        ).pack(side="right", padx=4)

        # -- the tabs
        self._notebook = ttk.Notebook(self._body)
        self._notebook.grid(row=1, column=0, sticky="nsew")

        self._tabs["Dashboard"] = DashboardTab(self._notebook, self.manager, self.logger)
        self._tabs["Log Price"] = LogPriceTab(self._notebook, self.manager, self.logger)
        self._tabs["Records"] = RecordsTab(self._notebook, self.manager, self.logger)
        self._tabs["Statistics & Alerts"] = StatsTab(self._notebook, self.manager, self.logger)
        self._tabs["My Basket"] = BasketTab(self._notebook, self.manager, self.logger)

        for name, tab in self._tabs.items():
            self._notebook.add(tab, text=name)

        # The Admin tab is only for an Admin.
        if user.can_manage():
            admin_tab = AdminTab(self._notebook, self.manager, self.logger)
            self._tabs["Admin"] = admin_tab
            self._notebook.add(admin_tab, text="Admin")

        self.refresh_all()

    def refresh_all(self) -> None:
        """Reload every tab."""
        for tab in self._tabs.values():
            try:
                tab.refresh()
            except Exception as exc:  # pragma: no cover - defensive
                handle_error(self, exc, self.logger)

    # -- menu actions ------------------------------------------------------
    def _reload_data(self) -> None:
        """Re-read every data file."""
        try:
            self.manager.reload()
        except Exception as exc:
            handle_error(self, exc, self.logger)
            return
        self.refresh_all()
        warnings = self.manager.startup_warnings
        if warnings:
            show_warning(self, "\n".join(warnings), "Data problems")
        else:
            show_info(self, "The data was reloaded from disk.")

    def _generate_report(self) -> None:
        """Save the weekly report for today."""
        try:
            path = save_weekly_report(
                self.manager.records,
                self.manager.products,
                self.manager.settings,
                markets=self.manager.markets(),
                end_date=date.today(),
                show_bangla=self.manager.show_bangla_names(),
            )
        except Exception as exc:
            handle_error(self, exc, self.logger)
            return
        show_info(self, f"The weekly report was saved to:\n{path}")

    def _change_password(self) -> None:
        """Let the current user change their password."""
        old_password = simpledialog.askstring(
            "Change password",
            "Current password:",
            show="*",
            parent=self,
        )
        if old_password is None:
            return
        new_password = simpledialog.askstring(
            "Change password",
            "New password (at least 6 characters):",
            show="*",
            parent=self,
        )
        if new_password is None:
            return
        username = self.manager.current_user.username
        try:
            self.manager.change_password(username, old_password, new_password)
        except Exception as exc:
            handle_error(self, exc, self.logger)
            return
        show_info(self, "Your password was changed.")

    def _logout(self) -> None:
        """Sign out and show the login screen again."""
        self.manager.logout()
        self._tabs.clear()
        self._notebook = None
        self._header = None
        self._show_login()

    def _on_exit(self) -> None:
        """Save and close the app."""
        try:
            self.manager.save_all()
        except Exception as exc:
            handle_error(self, exc, self.logger)
            return
        self.destroy()

    # -- startup -----------------------------------------------------------
    def _warn_about_data_problems(self) -> None:
        """Tell the user about any problems found while loading the data."""
        warnings = self.manager.startup_warnings
        if warnings:
            show_warning(
                self,
                "Some data files had problems:\n\n" + "\n".join(warnings),
                "Data problems",
            )


def main() -> int:
    """Start the application."""
    app = BazarApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
