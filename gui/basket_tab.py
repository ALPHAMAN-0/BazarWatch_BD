"""The 'My Basket' tab: plan a weekly basket against a budget."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from analytics import basket_plan, budget_status
from gui.widgets import (
    AlertTable,
    Tab,
    format_price,
    handle_error,
    product_id_for,
    show_info,
)


class BasketTab(Tab):
    """Add items to the basket, set a budget and see the shopping plan.

    The plan shows the total per market, the best single market, the split
    plan (each item at its own cheapest market), the saving and the budget
    status.
    """

    def __init__(self, parent, manager, logger=None):
        super().__init__(parent, padding=12)
        self.manager = manager
        self.logger = logger

        self.product_var = tk.StringVar()
        self.quantity_var = tk.StringVar(value="1")
        self.budget_var = tk.StringVar(value="0")
        # The dropdown labels and the product IDs they stand for.
        self._product_options: list[tuple[str, str]] = []

        # Set while the user is typing in the budget field.  A rebuild
        # of the table must not throw away a budget that has not been
        # saved yet, so the field is left alone until it is saved.
        self._budget_edited = False
        self.budget_var.trace_add("write", self._budget_changed)

        self._build()
        self.refresh()

    def _budget_changed(self, *_args) -> None:
        """Note that the user has typed in the budget field."""
        self._budget_edited = True

    def _build(self) -> None:
        """Lay the tab out."""
        ttk.Label(
            self, text="My basket", font=("TkDefaultFont", 13, "bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        # -- the add-item form
        add_frame = ttk.LabelFrame(self, text="Add an item", padding=10)
        add_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
        add_frame.columnconfigure(1, weight=1)

        ttk.Label(add_frame, text="Product:").grid(row=0, column=0, sticky="w", pady=5)
        self.product_box = ttk.Combobox(
            add_frame, textvariable=self.product_var, state="readonly", width=32
        )
        self.product_box.grid(row=0, column=1, sticky="w", pady=5)

        ttk.Label(add_frame, text="Quantity:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(add_frame, textvariable=self.quantity_var, width=14).grid(
            row=1, column=1, sticky="w", pady=5
        )

        ttk.Label(add_frame, text="Weekly budget (Tk):").grid(
            row=2, column=0, sticky="w", pady=5
        )
        ttk.Entry(add_frame, textvariable=self.budget_var, width=14).grid(
            row=2, column=1, sticky="w", pady=5
        )

        buttons = ttk.Frame(add_frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Add / update item", command=self._add_item).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="Remove item", command=self._remove_item).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(buttons, text="Save budget", command=self._save_budget).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(buttons, text="Clear basket", command=self._clear_basket).grid(
            row=0, column=3
        )

        # -- the basket contents
        ttk.Label(
            self, text="Items in my basket", font=("TkDefaultFont", 11, "bold")
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(16, 6))

        self.items_table = AlertTable(
            self,
            [
                ("product", "Product", "w", 190),
                ("quantity", "Quantity", "e", 90),
                ("cheapest", "Cheapest market", "w", 180),
                ("price", "Price per unit", "e", 110),
                ("cost", "Line total", "e", 100),
            ],
            height=7,
        )
        self.items_table.grid(row=3, column=0, columnspan=4, sticky="nsew")
        self.items_table.double_click_handler(self._remove_by_id)

        # -- the totals per market
        ttk.Label(
            self, text="Total per market", font=("TkDefaultFont", 11, "bold")
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(16, 6))

        self.totals_table = AlertTable(
            self,
            [
                ("market", "Market", "w", 200),
                ("total", "Basket total", "e", 120),
            ],
            height=4,
        )
        self.totals_table.grid(row=5, column=0, columnspan=4, sticky="nsew")

        # -- the plan summary
        summary = ttk.LabelFrame(self, text="Shopping plan", padding=10)
        summary.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(16, 0))

        self.best_var = tk.StringVar(value="-")
        self.split_var = tk.StringVar(value="-")
        self.saving_var = tk.StringVar(value="-")
        self.budget_var_out = tk.StringVar(value="-")
        self.unpriced_var = tk.StringVar(value="")

        ttk.Label(summary, text="Best single market:").grid(
            row=0, column=0, sticky="w", pady=3
        )
        ttk.Label(summary, textvariable=self.best_var).grid(
            row=0, column=1, sticky="w", pady=3
        )

        ttk.Label(summary, text="Split plan (each item at its cheapest market):").grid(
            row=1, column=0, sticky="w", pady=3
        )
        ttk.Label(summary, textvariable=self.split_var).grid(
            row=1, column=1, sticky="w", pady=3
        )

        ttk.Label(summary, text="Saving from splitting:").grid(
            row=2, column=0, sticky="w", pady=3
        )
        ttk.Label(summary, textvariable=self.saving_var).grid(
            row=2, column=1, sticky="w", pady=3
        )

        ttk.Label(summary, text="Budget status:").grid(
            row=3, column=0, sticky="w", pady=3
        )
        self.budget_label = ttk.Label(
            summary, textvariable=self.budget_var_out, font=("TkDefaultFont", 10, "bold")
        )
        self.budget_label.grid(row=3, column=1, sticky="w", pady=3)

        ttk.Label(summary, textvariable=self.unpriced_var, foreground="#ef6c00").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        self.rowconfigure(3, weight=1)
        self.rowconfigure(5, weight=1)
        self.columnconfigure(0, weight=1)

    # -- data ----------------------------------------------------------
    def _username(self) -> str | None:
        """The name of the user whose basket is shown."""
        user = self.manager.current_user
        return user.username if user else None

    def refresh(self) -> None:
        """Reload the basket, the totals and the plan."""
        manager = self.manager
        username = self._username()
        if username is None:
            return
        show_bn = manager.show_bangla_names()

        # The labels carry the product ID, so two products that share a
        # name can still be told apart in the dropdown.
        self._product_options = manager.product_options()
        self.product_box["values"] = [
            label for label, _ in self._product_options
        ]

        basket = manager.get_basket(username)
        # The budget field is left alone while the user has unsaved
        # changes in it, so adding or removing an item does not throw
        # away what they typed.
        if not self._budget_edited:
            # Filling the field in is not the user editing it, so the
            # flag is put back the way it was.
            self.budget_var.set(f"{basket.get('budget', 0.0):g}")
            self._budget_edited = False

        recent_days = int(manager.settings.get("recent_days", 14))
        markets = manager.markets()
        plan = basket_plan(basket["items"], manager.records, markets, recent_days)

        # -- the items
        self.items_table.clear()
        for product_id, quantity in sorted(basket["items"].items()):
            product = manager.products.get(product_id)
            name = (
                product.display_name(show_bn) if product else product_id
            )
            entry = plan["split_plan"].get(product_id)
            if entry:
                self.items_table.add_row(
                    [
                        name,
                        f"{quantity:g}",
                        entry["market"],
                        format_price(entry["average"]),
                        format_price(entry["cost"]),
                    ],
                    level="Normal",
                    item_id=product_id,
                )
            else:
                self.items_table.add_row(
                    [name, f"{quantity:g}", "no recent price", "-", "-"],
                    level="Watch",
                    item_id=product_id,
                )

        # -- the totals per market
        self.totals_table.clear()
        for market, total in sorted(
            plan["totals"].items(), key=lambda item: item[1]
        ):
            self.totals_table.add_row(
                [market, format_price(total)], level="Normal", item_id=market
            )
        if not plan["totals"]:
            self.totals_table.add_row(
                ["no market prices every item", "-"], level="Watch"
            )

        # -- the plan summary
        if plan["best_market"]:
            self.best_var.set(
                f"{plan['best_market']} - {format_price(plan['best_total'])}"
            )
        else:
            self.best_var.set(
                "(none) - no market has a recent price for every item"
            )

        self.split_var.set(format_price(plan["split_total"]))
        if plan["saving"] is None:
            self.saving_var.set("Not available (no complete single-market total)")
        else:
            self.saving_var.set(format_price(plan["saving"]))

        if plan["unpriced_items"]:
            names = []
            for product_id in plan["unpriced_items"]:
                product = manager.products.get(product_id)
                names.append(
                    product.display_name(show_bn) if product else product_id
                )
            self.unpriced_var.set(
                "No recent price for: " + ", ".join(names) + " (left out of the totals)"
            )
        else:
            self.unpriced_var.set("")

        status, message = budget_status(plan["split_total"], basket.get("budget", 0.0))
        self.budget_var_out.set(f"{status} - {message}")
        self.budget_label.configure(
            foreground={"Over budget": "#c62828", "Close to budget": "#ef6c00"}.get(
                status, ""
            )
        )

    # -- actions --------------------------------------------------------
    def _selected_product_id(self) -> str | None:
        """The ID of the product chosen in the dropdown."""
        return product_id_for(self._product_options, self.product_var.get())

    def _add_item(self) -> None:
        """Add or update an item in the basket."""
        username = self._username()
        product_id = self._selected_product_id()
        if product_id is None:
            show_info(self, "Please choose a product first.")
            return
        try:
            self.manager.set_basket_item(
                username, product_id, self.quantity_var.get()
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()

    def _remove_item(self) -> None:
        """Remove the item chosen in the dropdown."""
        username = self._username()
        product_id = self._selected_product_id()
        if product_id is None:
            show_info(self, "Please choose a product first.")
            return
        try:
            self.manager.remove_basket_item(username, product_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()

    def _remove_by_id(self, product_id) -> None:
        """Remove an item by double-clicking its row."""
        username = self._username()
        if not product_id:
            return
        try:
            self.manager.remove_basket_item(username, product_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()

    def _save_budget(self) -> None:
        """Save the weekly budget."""
        username = self._username()
        try:
            self.manager.set_budget(username, self.budget_var.get())
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        # The budget is saved now, so the field is back in step with the
        # basket and a later rebuild may fill it in again.
        self._budget_edited = False
        self.refresh()

    def _clear_basket(self) -> None:
        """Empty the basket."""
        username = self._username()
        try:
            self.manager.clear_basket(username)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()
