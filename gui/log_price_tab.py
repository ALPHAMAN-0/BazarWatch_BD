"""The 'Log Price' tab: record a price and see its alert level."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from analytics import alert_level
from gui.widgets import Tab, handle_error, level_label, show_info


class LogPriceTab(Tab):
    """Choose a product and market, type a price and save it.

    After saving, the alert level is shown in colour together with the
    z-score and the percentage over the reference price.
    """

    def __init__(self, parent, manager, logger=None):
        super().__init__(parent, padding=12)
        self.manager = manager
        self.logger = logger

        self.product_var = tk.StringVar()
        self.market_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.price_var = tk.StringVar()

        self.result_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.result_label = None
        # The dropdown labels and the product IDs they stand for.
        self._product_options: list[tuple[str, str]] = []

        self._build()
        self.refresh_choices()

    def _build(self) -> None:
        """Lay the form out."""
        title = ttk.Label(
            self, text="Log a price", font=("TkDefaultFont", 13, "bold")
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        form = ttk.LabelFrame(self, text="Price details", padding=10)
        form.grid(row=1, column=0, columnspan=2, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Product:").grid(row=0, column=0, sticky="w", pady=5)
        self.product_box = ttk.Combobox(
            form, textvariable=self.product_var, state="readonly", width=40
        )
        self.product_box.grid(row=0, column=1, sticky="ew", pady=5)
        self.product_box.bind("<<ComboboxSelected>>", lambda event: self._on_product())

        ttk.Label(form, text="Market:").grid(row=1, column=0, sticky="w", pady=5)
        self.market_box = ttk.Combobox(
            form, textvariable=self.market_var, state="readonly", width=40
        )
        self.market_box.grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(form, text="Date:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.date_var, width=20).grid(
            row=2, column=1, sticky="w", pady=5
        )
        ttk.Label(form, text="(YYYY-MM-DD)").grid(
            row=2, column=1, sticky="w", padx=(160, 0), pady=5
        )

        ttk.Label(form, text="Price per unit (Tk):").grid(
            row=3, column=0, sticky="w", pady=5
        )
        self.price_entry = ttk.Entry(form, textvariable=self.price_var, width=20)
        self.price_entry.grid(row=3, column=1, sticky="w", pady=5)

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))
        self.save_button = ttk.Button(
            buttons, text="Save price", command=self._save
        )
        self.save_button.grid(row=0, column=0, padx=(0, 8))

        self.clear_button = ttk.Button(
            buttons, text="Clear", command=self._clear
        )
        self.clear_button.grid(row=0, column=1)

        # -- the result area
        result_frame = ttk.LabelFrame(self, text="Result", padding=10)
        result_frame.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0)
        )
        self.result_label = level_label(result_frame, "", "Normal")
        self.result_label.grid(row=0, column=0, sticky="w")
        ttk.Label(result_frame, textvariable=self.detail_var).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

        self.columnconfigure(0, weight=1)

    # -- data ----------------------------------------------------------
    def refresh(self) -> None:
        """Reload the tab.

        The main window calls this whenever the data changes, so the
        dropdowns have to be rebuilt here as well.
        """
        self.refresh_choices()

    def refresh_choices(self) -> None:
        """Reload the product and market dropdowns."""
        # The labels carry the product ID, so two products that share a
        # name can still be told apart in the list.
        self._product_options = self.manager.product_options()
        labels = [label for label, _ in self._product_options]
        self.product_box["values"] = labels
        if labels and self.product_var.get() not in labels:
            self.product_var.set(labels[0])

        markets = self.manager.markets()
        self.market_box["values"] = markets
        if markets and not self.market_var.get():
            self.market_var.set(markets[0])

    def _product_id_for(self, label: str) -> str | None:
        """The product ID a dropdown label stands for."""
        for option_label, product_id in self._product_options:
            if option_label == label:
                return product_id
        return None

    def _selected_product_id(self) -> str | None:
        """The ID of the product chosen in the dropdown."""
        return self._product_id_for(self.product_var.get())

    def _on_product(self) -> None:
        """Show the reference price of the chosen product."""
        product_id = self._selected_product_id()
        if product_id is None:
            return
        product = self.manager.products[product_id]
        if product.reference_price:
            self.detail_var.set(
                f"Official reference price for {product.name}: "
                f"Tk {product.reference_price:.2f} per {product.unit}"
            )
        else:
            self.detail_var.set(
                f"No reference price set for {product.name} yet "
                "(an Admin can add it in Admin -> Products)."
            )

    # -- actions --------------------------------------------------------
    def _save(self) -> None:
        """Save the price and show the alert level."""
        product_id = self._selected_product_id()
        if product_id is None:
            show_info(self, "Please choose a product first.")
            return
        try:
            record = self.manager.add_record(
                product_id,
                self.market_var.get(),
                self.date_var.get(),
                self.price_var.get(),
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return

        level, z_value, pct_value = alert_level(
            record,
            self.manager.records,
            self.manager.products,
            self.manager.settings,
        )
        self._show_result(record, level, z_value, pct_value)
        self.price_var.set("")
        self.price_entry.focus_set()

    def _show_result(self, record, level, z_value, pct_value) -> None:
        """Show the alert level of the saved record."""
        self.result_label.configure(text=f"{level}")
        self.result_label.configure(
            foreground={"Spike": "#c62828", "Watch": "#ef6c00"}.get(level, "")
        )
        details = []
        if z_value is not None:
            details.append(f"z = {z_value:.2f}")
        else:
            details.append("z = not enough history yet")
        if pct_value is not None:
            details.append(f"{pct_value:+.1f}% over the reference price")
        else:
            details.append("ref not set")
        self.detail_var.set(
            f"{record.record_id}: {record.product_id} at {record.market} on "
            f"{record.date}, Tk {record.price:.2f}  ({'; '.join(details)})"
        )

    def _clear(self) -> None:
        """Empty the form."""
        self.price_var.set("")
        self.date_var.set(date.today().isoformat())
        self.result_label.configure(text="")
        self.detail_var.set("")
        self.price_entry.focus_set()
