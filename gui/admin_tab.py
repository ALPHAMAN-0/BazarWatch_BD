"""The 'Admin' tab: manage users, products, markets and settings.

An Admin only.  The tab itself is never added for a member, and every action
inside it still goes through the manager, which raises PermissionDeniedError
if the rule does not allow it.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk

import config
from gui.widgets import (
    AlertTable,
    Tab,
    confirm,
    handle_error,
    show_info,
)


class AdminSubTab(ttk.Frame):
    """What every Admin sub-page has in common.

    A sub-page that changes shared data -- the product list, the market
    list, the settings -- tells the rest of the app about it, so the
    dropdowns on the other tabs do not keep offering the old list.
    """

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, padding=10)
        self.manager = manager
        self.logger = logger
        self.on_data_changed = on_data_changed

    def _changed(self) -> None:
        """Tell the other tabs that the data has changed."""
        if self.on_data_changed is not None:
            self.on_data_changed()


class UsersSubTab(AdminSubTab):
    """Add and remove members, and reset passwords."""

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, manager, logger, on_data_changed)

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the sub-tab out."""
        add_frame = ttk.LabelFrame(self, text="Add a member", padding=10)
        add_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        add_frame.columnconfigure(1, weight=1)

        ttk.Label(add_frame, text="Username:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(add_frame, textvariable=self.username_var, width=24).grid(
            row=0, column=1, sticky="w", pady=5
        )

        ttk.Label(add_frame, text="Password:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(add_frame, textvariable=self.password_var, show="*", width=24).grid(
            row=1, column=1, sticky="w", pady=5
        )

        ttk.Button(
            add_frame, text="Add member", command=self._add_member
        ).grid(row=2, column=1, sticky="w", pady=(8, 0))

        self.table = AlertTable(
            self,
            [
                ("username", "Username", "w", 150),
                ("role", "Role", "center", 90),
                ("created", "Created", "center", 130),
                ("last_login", "Last login", "center", 160),
                ("records", "Records logged", "e", 110),
            ],
            height=10,
        )
        self.table.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        self.table.double_click_handler(self._reset_password)

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(
            buttons, text="Remove member", command=self._remove_member
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            buttons, text="Reset password", command=self._reset_password
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Refresh", command=self.refresh).grid(row=0, column=2)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload the user table."""
        try:
            users = self.manager.list_users()
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        counts = self.manager.records_per_user()
        # The chosen row stays selected across the rebuild.
        with self.table.preserve_selection():
            self.table.clear()
            for user in users:
                self.table.add_row(
                    [
                        user.username,
                        user.role,
                        user.created_at or "-",
                        user.last_login or "never",
                        counts.get(user.username, 0),
                    ],
                    level="Normal",
                    item_id=user.username,
                )

    def _add_member(self) -> None:
        """Add a new member."""
        try:
            self.manager.add_member(
                self.username_var.get(), self.password_var.get()
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.username_var.set("")
        self.password_var.set("")
        self.refresh()

    def _remove_member(self) -> None:
        """Remove the selected member."""
        username = self.table.selected_id()
        if not username:
            show_info(self, "Please select a member first.")
            return
        if not confirm(
            self.winfo_toplevel(),
            f"Remove the member '{username}'?\n\n"
            "Their price records are kept, but their basket is deleted.",
        ):
            return
        try:
            self.manager.remove_member(username)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()

    def _reset_password(self, username=None) -> None:
        """Reset the password of the selected member."""
        if username is None:
            username = self.table.selected_id()
        if not username:
            show_info(self, "Please select a member first.")
            return
        new_password = simpledialog.askstring(
            "Reset password",
            f"New password for '{username}' (at least 6 characters):",
            parent=self.winfo_toplevel(),
            show="*",
        )
        if not new_password:
            return
        try:
            self.manager.reset_password(username, new_password)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        show_info(
            self.winfo_toplevel(), f"The password for '{username}' was reset."
        )


class ProductsSubTab(AdminSubTab):
    """Add, edit and remove products, and set the reference prices."""

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, manager, logger, on_data_changed)

        self.product_id_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.name_bn_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="kg")
        self.category_var = tk.StringVar(value=config.CATEGORIES[0])
        self.reference_var = tk.StringVar()
        self.perishable_var = tk.BooleanVar(value=False)

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the sub-tab out."""
        add_frame = ttk.LabelFrame(self, text="Add a product", padding=10)
        add_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        add_frame.columnconfigure(1, weight=1)

        ttk.Label(add_frame, text="Product ID:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(add_frame, textvariable=self.product_id_var, width=18).grid(
            row=0, column=1, sticky="w", pady=4
        )
        ttk.Label(
            add_frame, text="(uppercase, e.g. MILK)", foreground="#555555"
        ).grid(row=0, column=2, sticky="w", padx=6)

        ttk.Label(add_frame, text="Name:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(add_frame, textvariable=self.name_var, width=30).grid(
            row=1, column=1, sticky="w", pady=4
        )

        ttk.Label(add_frame, text="Bangla name:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Entry(add_frame, textvariable=self.name_bn_var, width=30).grid(
            row=2, column=1, sticky="w", pady=4
        )

        ttk.Label(add_frame, text="Unit:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            add_frame,
            textvariable=self.unit_var,
            state="readonly",
            values=config.UNITS,
            width=14,
        ).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(add_frame, text="Category:").grid(
            row=4, column=0, sticky="w", pady=4
        )
        ttk.Combobox(
            add_frame,
            textvariable=self.category_var,
            state="readonly",
            values=config.CATEGORIES,
            width=18,
        ).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(add_frame, text="Reference price (Tk):").grid(
            row=5, column=0, sticky="w", pady=4
        )
        ttk.Entry(add_frame, textvariable=self.reference_var, width=14).grid(
            row=5, column=1, sticky="w", pady=4
        )
        ttk.Label(
            add_frame,
            text="(leave empty if there is no official price)",
            foreground="#555555",
        ).grid(row=5, column=2, sticky="w", padx=6)

        ttk.Checkbutton(
            add_frame, text="Perishable (looser spike limits)", variable=self.perishable_var
        ).grid(row=6, column=1, sticky="w", pady=4)

        ttk.Button(add_frame, text="Add product", command=self._add_product).grid(
            row=7, column=1, sticky="w", pady=(8, 0)
        )

        self.table = AlertTable(
            self,
            [
                ("id", "ID", "center", 80),
                ("name", "Name", "w", 160),
                ("name_bn", "Bangla name", "w", 150),
                ("unit", "Unit", "center", 70),
                ("category", "Category", "w", 110),
                ("reference", "Reference price", "e", 110),
                ("perishable", "Perishable", "center", 90),
                ("records", "Records", "e", 80),
            ],
            height=10,
        )
        self.table.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(14, 0))
        self.table.double_click_handler(self._set_reference)

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Button(
            buttons, text="Set reference price", command=self._set_reference
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            buttons, text="Remove product", command=self._remove_product
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Refresh", command=self.refresh).grid(row=0, column=2)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload the product table."""
        counts: dict[str, int] = {}
        for record in self.manager.records:
            counts[record.product_id] = counts.get(record.product_id, 0) + 1
        # The chosen row stays selected across the rebuild.
        with self.table.preserve_selection():
            self.table.clear()
            for product_id, product in sorted(self.manager.products.items()):
                self.table.add_row(
                    [
                        product.product_id,
                        product.name,
                        product.name_bn,
                        product.unit,
                        product.category,
                        f"{product.reference_price:.2f}"
                        if product.reference_price is not None
                        else "-",
                        "yes" if product.perishable else "no",
                        counts.get(product_id, 0),
                    ],
                    level="Normal",
                    item_id=product_id,
                )

    def _add_product(self) -> None:
        """Add a product to the catalogue."""
        try:
            self.manager.add_product(
                self.product_id_var.get(),
                self.name_var.get(),
                self.name_bn_var.get(),
                self.unit_var.get(),
                self.category_var.get(),
                self.reference_var.get() or None,
                self.perishable_var.get(),
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.product_id_var.set("")
        self.name_var.set("")
        self.name_bn_var.set("")
        self.reference_var.set("")
        self.perishable_var.set(False)
        self.refresh()
        self._changed()

    def _set_reference(self, product_id=None) -> None:
        """Set or clear the reference price of a product."""
        if product_id is None:
            product_id = self.table.selected_id()
        if not product_id:
            show_info(self, "Please select a product first.")
            return
        product = self.manager.products.get(product_id)
        current = (
            f"{product.reference_price:.2f}" if product and product.reference_price else ""
        )
        value = simpledialog.askstring(
            "Reference price",
            f"Official reference price for {product_id} (leave empty to clear):",
            initialvalue=current,
            parent=self.winfo_toplevel(),
        )
        if value is None:
            return
        try:
            self.manager.set_reference_price(product_id, value.strip() or None)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()
        self._changed()

    def _remove_product(self) -> None:
        """Remove the selected product."""
        product_id = self.table.selected_id()
        if not product_id:
            show_info(self, "Please select a product first.")
            return
        if not confirm(
            self.winfo_toplevel(),
            f"Remove the product '{product_id}'?\n\n"
            "A product that still has price records cannot be removed.",
        ):
            return
        try:
            self.manager.remove_product(product_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()
        self._changed()


class MarketsSubTab(AdminSubTab):
    """Add and remove markets."""

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, manager, logger, on_data_changed)

        self.market_var = tk.StringVar()

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the sub-tab out."""
        add_frame = ttk.LabelFrame(self, text="Add a market", padding=10)
        add_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        add_frame.columnconfigure(1, weight=1)

        ttk.Label(add_frame, text="Market name:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        ttk.Entry(add_frame, textvariable=self.market_var, width=32).grid(
            row=0, column=1, sticky="w", pady=5
        )
        ttk.Button(add_frame, text="Add market", command=self._add_market).grid(
            row=1, column=1, sticky="w", pady=(8, 0)
        )

        self.table = AlertTable(
            self,
            [
                ("market", "Market", "w", 220),
                ("records", "Price records", "e", 110),
            ],
            height=10,
        )
        self.table.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(14, 0))

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(
            buttons, text="Remove market", command=self._remove_market
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Refresh", command=self.refresh).grid(row=0, column=1)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload the market table."""
        counts: dict[str, int] = {}
        for record in self.manager.records:
            counts[record.market] = counts.get(record.market, 0) + 1
        # The chosen row stays selected across the rebuild.
        with self.table.preserve_selection():
            self.table.clear()
            for market in self.manager.markets():
                self.table.add_row(
                    [market, counts.get(market, 0)], level="Normal", item_id=market
                )

    def _add_market(self) -> None:
        """Add a market."""
        try:
            self.manager.add_market(self.market_var.get())
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.market_var.set("")
        self.refresh()
        self._changed()

    def _remove_market(self) -> None:
        """Remove the selected market."""
        market = self.table.selected_id()
        if not market:
            show_info(self, "Please select a market first.")
            return
        if not confirm(
            self.winfo_toplevel(),
            f"Remove the market '{market}'?\n\n"
            "A market that still has price records cannot be removed.",
        ):
            return
        try:
            self.manager.remove_market(market)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()
        self._changed()


class SettingsSubTab(AdminSubTab):
    """Change the alert thresholds and the other options."""

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, manager, logger, on_data_changed)

        self.vars = {
            "z_threshold": tk.StringVar(),
            "pct_threshold": tk.StringVar(),
            "perishable_z_threshold": tk.StringVar(),
            "perishable_pct_threshold": tk.StringVar(),
            "min_history": tk.StringVar(),
            "recent_days": tk.StringVar(),
            "show_bangla_names": tk.BooleanVar(),
        }

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the sub-tab out."""
        frame = ttk.LabelFrame(self, text="Alert thresholds", padding=10)
        frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        frame.columnconfigure(1, weight=1)

        rows = [
            ("z_threshold", "Normal: z-score limit",
             "A price this many standard deviations above the mean is a Spike"),
            ("pct_threshold", "Normal: percent limit",
             "A price this far above the reference price is a Spike"),
            ("perishable_z_threshold", "Perishable: z-score limit",
             "The looser limit used for perishable products"),
            ("perishable_pct_threshold", "Perishable: percent limit",
             "The looser limit used for perishable products"),
            ("min_history", "Minimum history",
             "How many earlier prices are needed before a z-score is calculated"),
            ("recent_days", "Recent window (days)",
             "The window used for the cheapest market and the basket"),
        ]
        for index, (key, label, hint) in enumerate(rows):
            ttk.Label(frame, text=f"{label}:").grid(
                row=index, column=0, sticky="w", pady=4
            )
            ttk.Entry(frame, textvariable=self.vars[key], width=12).grid(
                row=index, column=1, sticky="w", pady=4
            )
            ttk.Label(frame, text=hint, foreground="#555555").grid(
                row=index, column=2, sticky="w", padx=8
            )

        ttk.Checkbutton(
            frame,
            text="Show Bangla product names",
            variable=self.vars["show_bangla_names"],
        ).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="Save settings", command=self._save).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="Reset to defaults", command=self._reset).grid(
            row=0, column=1
        )

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var).grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )

        self.columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Load the current settings into the form."""
        settings = self.manager.settings
        for key, var in self.vars.items():
            if key == "show_bangla_names":
                var.set(bool(settings.get(key, True)))
            else:
                var.set(f"{settings.get(key, 0):g}")

    def _save(self) -> None:
        """Save the settings."""
        changes = {}
        for key, var in self.vars.items():
            if key == "show_bangla_names":
                changes[key] = var.get()
            else:
                changes[key] = var.get()
        try:
            self.manager.update_settings(changes)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.status_var.set("The settings were saved.")
        self.refresh()
        self._changed()

    def _reset(self) -> None:
        """Put the default settings back."""
        try:
            self.manager.update_settings(
                {
                    key: value
                    for key, value in config.DEFAULT_SETTINGS.items()
                    if key != "markets"
                }
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.status_var.set("The default settings were restored.")
        self.refresh()


class AdminTab(Tab):
    """The Admin tab, with the Users, Products, Markets and Settings pages."""

    def __init__(self, parent, manager, logger=None, on_data_changed=None):
        super().__init__(parent, padding=8)
        self.manager = manager
        self.logger = logger
        # Called after a change that other tabs have to know about, such as
        # adding a product: the Log Price dropdown would otherwise keep
        # offering the old list.
        self.on_data_changed = on_data_changed

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.users_tab = UsersSubTab(
            self.notebook, manager, logger, on_data_changed
        )
        self.products_tab = ProductsSubTab(
            self.notebook, manager, logger, on_data_changed
        )
        self.markets_tab = MarketsSubTab(
            self.notebook, manager, logger, on_data_changed
        )
        self.settings_tab = SettingsSubTab(
            self.notebook, manager, logger, on_data_changed
        )

        self.notebook.add(self.users_tab, text="Users")
        self.notebook.add(self.products_tab, text="Products")
        self.notebook.add(self.markets_tab, text="Markets")
        self.notebook.add(self.settings_tab, text="Settings")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload every sub-tab."""
        self.users_tab.refresh()
        self.products_tab.refresh()
        self.markets_tab.refresh()
        self.settings_tab.refresh()
