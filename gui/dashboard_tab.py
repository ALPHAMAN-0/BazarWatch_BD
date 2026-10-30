"""The 'Dashboard' tab: the headline numbers and the cheapest markets."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from analytics import alert_level, cheapest_market_for_all
from gui.widgets import AlertTable, format_price


class DashboardTab(ttk.Frame):
    """The overview shown when the app opens.

    It shows the totals, the cheapest market for each product, the products
    that were not priced today, the top contributors and, for an Admin, the
    products that still have no official reference price.
    """

    def __init__(self, parent, manager, logger=None):
        super().__init__(parent, padding=12)
        self.manager = manager
        self.logger = logger

        self.summary_vars = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the tab out."""
        ttk.Label(
            self, text="Dashboard", font=("TkDefaultFont", 13, "bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        # -- the summary tiles
        tiles = ttk.LabelFrame(self, text="Totals", padding=10)
        tiles.grid(row=1, column=0, columnspan=4, sticky="ew")
        for index, name in enumerate(
            ["Products", "Markets", "Records", "My records", "Spikes this week",
             "Watches this week"]
        ):
            tiles.columnconfigure(index, weight=1)
            ttk.Label(tiles, text=name, foreground="#555555").grid(
                row=0, column=index, padx=10, sticky="w"
            )
            var = tk.StringVar(value="-")
            ttk.Label(
                tiles, textvariable=var, font=("TkDefaultFont", 15, "bold")
            ).grid(row=1, column=index, padx=10, sticky="w")
            self.summary_vars[name] = var

        # -- the cheapest markets
        ttk.Label(
            self, text="Cheapest market per product (last 14 days)",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(16, 6))

        self.cheapest_table = AlertTable(
            self,
            [
                ("product", "Product", "w", 180),
                ("market", "Cheapest market", "w", 200),
                ("average", "Average price", "e", 110),
                ("status", "Status", "center", 90),
            ],
            height=9,
        )
        self.cheapest_table.grid(
            row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 0)
        )

        # -- the right hand column
        right = ttk.Frame(self)
        right.grid(row=2, column=3, rowspan=2, sticky="nsew", padx=(16, 0))

        ttk.Label(
            right, text="Not priced today", font=("TkDefaultFont", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(16, 4))
        self.not_priced_var = tk.StringVar(value="None")
        ttk.Label(right, textvariable=self.not_priced_var, wraplength=280).grid(
            row=1, column=0, sticky="w"
        )

        ttk.Label(
            right, text="Top contributors", font=("TkDefaultFont", 11, "bold")
        ).grid(row=2, column=0, sticky="w", pady=(14, 4))
        self.contributors_var = tk.StringVar(value="None")
        ttk.Label(right, textvariable=self.contributors_var, wraplength=280).grid(
            row=3, column=0, sticky="w"
        )

        self.missing_ref_var = tk.StringVar(value="")
        self.missing_ref_label = ttk.Label(
            right, textvariable=self.missing_ref_var, wraplength=280
        )
        self.missing_ref_label.grid(row=4, column=0, sticky="w", pady=(14, 4))

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    # -- data ----------------------------------------------------------
    def refresh(self) -> None:
        """Reload every part of the dashboard."""
        manager = self.manager
        user = manager.current_user
        if user is None:
            return

        show_bn = manager.show_bangla_names()
        summary = manager.dashboard_summary()
        week_start = (date.today() - timedelta(days=6)).isoformat()
        today = date.today().isoformat()

        this_week = [r for r in manager.records if r.date >= week_start]
        spikes = []
        watches = []
        for record in this_week:
            level, _, _ = alert_level(
                record, manager.records, manager.products, manager.settings
            )
            if level == "Spike":
                spikes.append(record)
            elif level == "Watch":
                watches.append(record)

        self.summary_vars["Products"].set(str(summary["products"]))
        self.summary_vars["Markets"].set(str(summary["markets"]))
        self.summary_vars["Records"].set(str(summary["records"]))
        self.summary_vars["My records"].set(str(summary["my_records"]))
        self.summary_vars["Spikes this week"].set(str(len(spikes)))
        self.summary_vars["Watches this week"].set(str(len(watches)))

        # -- the cheapest market table
        self.cheapest_table.clear()
        markets = manager.markets()
        recent_days = int(manager.settings.get("recent_days", 14))
        cheapest = cheapest_market_for_all(
            manager.products, manager.records, markets, recent_days
        )
        for product_id, product in sorted(manager.products.items()):
            name = product.display_name(show_bn)
            if product_id in cheapest:
                market, average = cheapest[product_id]
                self.cheapest_table.add_row(
                    [name, market, format_price(average), "priced"],
                    level="Normal",
                    item_id=product_id,
                )
            else:
                self.cheapest_table.add_row(
                    [name, "no recent data", "-", "not priced"],
                    level="Watch",
                    item_id=product_id,
                )

        # -- the not-priced list
        not_priced = manager.products_not_priced_today()
        if not_priced:
            self.not_priced_var.set(
                ", ".join(p.display_name(show_bn) for p in not_priced)
            )
        else:
            self.not_priced_var.set(
                "Every product has a price logged today."
            )

        # -- the top contributors
        counts = manager.records_per_user()
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ordered = [item for item in ordered if item[1] > 0]
        if ordered:
            self.contributors_var.set(
                "\n".join(f"{name}: {count} record(s)" for name, count in ordered[:6])
            )
        else:
            self.contributors_var.set("No records have been logged yet.")

        # -- the missing reference prices (Admin only)
        if user.can_manage():
            missing = manager.products_missing_reference_price()
            if missing:
                names = ", ".join(
                    p.display_name(show_bn) for p in missing
                )
                self.missing_ref_var.set(
                    "Products still missing an official reference price "
                    f"(set them in Admin -> Products):\n{names}"
                )
            else:
                self.missing_ref_var.set(
                    "Every product has an official reference price."
                )
        else:
            self.missing_ref_var.set("")
