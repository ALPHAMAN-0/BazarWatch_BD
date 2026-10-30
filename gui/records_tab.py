"""The 'Records' tab: search, filter, edit and delete price records."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from analytics import alert_level
from gui.widgets import (
    AlertTable,
    ColumnDef,
    Tab,
    confirm,
    handle_error,
    show_info,
)


class EditRecordDialog(tk.Toplevel):
    """The small window used to edit a price record."""

    def __init__(self, parent, manager, record, on_saved):
        super().__init__(parent)
        self.manager = manager
        self.record = record
        self.on_saved = on_saved

        self.title(f"Edit record {record.record_id}")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.product_var = tk.StringVar(value=record.product_id)
        self.market_var = tk.StringVar(value=record.market)
        self.date_var = tk.StringVar(value=record.date)
        self.price_var = tk.StringVar(value=f"{record.price:g}")

        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Product:").grid(row=0, column=0, sticky="w", pady=5)
        self.product_box = ttk.Combobox(
            frame,
            textvariable=self.product_var,
            state="readonly",
            values=sorted(self.manager.products),
            width=24,
        )
        self.product_box.grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(frame, text="Market:").grid(row=1, column=0, sticky="w", pady=5)
        self.market_box = ttk.Combobox(
            frame,
            textvariable=self.market_var,
            state="readonly",
            values=self.manager.markets(),
            width=24,
        )
        self.market_box.grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(frame, text="Date:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=self.date_var, width=24).grid(
            row=2, column=1, sticky="ew", pady=5
        )

        ttk.Label(frame, text="Price (Tk):").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=self.price_var, width=24).grid(
            row=3, column=1, sticky="ew", pady=5
        )

        self.error_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.error_var, foreground="#c62828").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="Save", command=self._save).grid(row=0, column=1)

        self.grab_set()

    def _save(self) -> None:
        """Apply the changes."""
        try:
            self.manager.update_record(
                self.record.record_id,
                product_id=self.product_var.get(),
                market=self.market_var.get(),
                date=self.date_var.get(),
                price=self.price_var.get(),
            )
        except Exception as exc:
            # Keep the dialog open so the user can correct the value.
            self.error_var.set(str(exc))
            return
        self.on_saved()
        self.destroy()


class RecordsTab(Tab):
    """Search and filter the price records, and edit or delete them."""

    COLUMNS: tuple[ColumnDef, ...] = (
        ("record_id", "ID", "center", 70),
        ("product", "Product", "w", 160),
        ("market", "Market", "w", 150),
        ("date", "Date", "center", 100),
        ("price", "Price (Tk)", "e", 90),
        ("user", "Logged by", "w", 100),
        ("level", "Level", "center", 80),
        ("z", "z", "e", 60),
        ("pct", "% over ref", "e", 80),
    )

    def __init__(self, parent, manager, logger=None):
        super().__init__(parent, padding=12)
        self.manager = manager
        self.logger = logger

        self.search_var = tk.StringVar()
        self.product_var = tk.StringVar()
        self.market_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.level_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the tab out."""
        ttk.Label(
            self, text="Price records", font=("TkDefaultFont", 13, "bold")
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        # The filters are laid out in pairs so the table keeps most of the
        # window.
        filters = ttk.LabelFrame(self, text="Search and filters", padding=8)
        filters.grid(row=1, column=0, columnspan=6, sticky="ew")
        for column in (1, 3):
            filters.columnconfigure(column, weight=1)

        ttk.Label(filters, text="Search:").grid(row=0, column=0, sticky="w", pady=3)
        search_entry = ttk.Entry(filters, textvariable=self.search_var, width=24)
        search_entry.grid(row=0, column=1, sticky="ew", pady=3, padx=(4, 12))
        search_entry.bind("<KeyRelease>", lambda event: self.refresh())

        ttk.Label(filters, text="Product:").grid(row=0, column=2, sticky="w", pady=3)
        self.product_box = ttk.Combobox(
            filters, textvariable=self.product_var, state="readonly", width=16
        )
        self.product_box.grid(row=0, column=3, sticky="ew", pady=3, padx=(4, 12))
        self.product_box.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(filters, text="Market:").grid(row=1, column=0, sticky="w", pady=3)
        self.market_box = ttk.Combobox(
            filters, textvariable=self.market_var, state="readonly", width=16
        )
        self.market_box.grid(row=1, column=1, sticky="ew", pady=3, padx=(4, 12))
        self.market_box.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(filters, text="Logged by:").grid(
            row=1, column=2, sticky="w", pady=3
        )
        self.user_box = ttk.Combobox(
            filters, textvariable=self.user_var, state="readonly", width=16
        )
        self.user_box.grid(row=1, column=3, sticky="ew", pady=3, padx=(4, 12))
        self.user_box.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(filters, text="Level:").grid(row=2, column=0, sticky="w", pady=3)
        self.level_box = ttk.Combobox(
            filters,
            textvariable=self.level_var,
            state="readonly",
            values=("", "Spike", "Watch", "Normal"),
            width=16,
        )
        self.level_box.grid(row=2, column=1, sticky="ew", pady=3, padx=(4, 12))
        self.level_box.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(filters, text="From date:").grid(
            row=2, column=2, sticky="w", pady=3
        )
        ttk.Entry(filters, textvariable=self.from_var, width=12).grid(
            row=2, column=3, sticky="w", pady=3, padx=(4, 12)
        )

        ttk.Label(filters, text="To date:").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(filters, textvariable=self.to_var, width=12).grid(
            row=3, column=1, sticky="w", pady=3, padx=(4, 12)
        )

        filter_buttons = ttk.Frame(filters)
        filter_buttons.grid(row=3, column=2, columnspan=2, sticky="e", pady=3)
        ttk.Button(
            filter_buttons, text="Apply filters", command=self.refresh
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            filter_buttons, text="Clear filters", command=self._clear_filters
        ).grid(row=0, column=1)

        # -- the table
        self.table = AlertTable(self, list(self.COLUMNS), height=18)
        self.table.grid(
            row=2, column=0, columnspan=6, sticky="nsew", pady=(12, 0)
        )
        self.table.double_click_handler(self._edit_selected)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # -- the buttons
        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))
        self.edit_button = ttk.Button(
            buttons, text="Edit", command=self._edit_selected
        )
        self.edit_button.grid(row=0, column=0, padx=(0, 8))
        self.delete_button = ttk.Button(
            buttons, text="Delete", command=self._delete_selected
        )
        self.delete_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons, text="Refresh", command=self.refresh
        ).grid(row=0, column=2)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var).grid(
            row=4, column=0, columnspan=6, sticky="w", pady=(8, 0)
        )

    # -- data ----------------------------------------------------------
    def refresh(self) -> None:
        """Reload the table with the current filters."""
        show_bn = self.manager.show_bangla_names()

        self.product_box["values"] = ("", *sorted(self.manager.products))
        self.market_box["values"] = ("", *self.manager.markets())
        self.user_box["values"] = ("", *sorted(self.manager.users))

        try:
            results = self.manager.filter_records(
                product_id=self.product_var.get() or None,
                market=self.market_var.get() or None,
                added_by=self.user_var.get() or None,
                search=self.search_var.get() or None,
                date_from=self.from_var.get().strip() or None,
                date_to=self.to_var.get().strip() or None,
                level=self.level_var.get() or None,
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return

        self.table.clear()
        for record in results:
            level, z_value, pct_value = alert_level(
                record,
                self.manager.records,
                self.manager.products,
                self.manager.settings,
            )
            product = self.manager.products.get(record.product_id)
            name = (
                product.display_name(show_bn) if product else record.product_id
            )
            self.table.add_row(
                [
                    record.record_id,
                    name,
                    record.market,
                    record.date,
                    f"{record.price:.2f}",
                    record.added_by,
                    level,
                    f"{z_value:.2f}" if z_value is not None else "-",
                    f"{pct_value:+.1f}%" if pct_value is not None else "ref not set",
                ],
                level=level,
                item_id=record.record_id,
            )

        self.status_var.set(f"{len(results)} record(s) shown.")
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Enable Edit and Delete only when the action is allowed."""
        user = self.manager.current_user
        if user is None:
            return
        record_id = self.table.selected_id()
        record = None
        if record_id:
            try:
                record = self.manager.get_record(record_id)
            except Exception:
                record = None
        self.edit_button.configure(
            state="normal" if (record and user.can_edit(record)) else "disabled"
        )
        self.delete_button.configure(
            state="normal" if (record and user.can_delete(record)) else "disabled"
        )

    # -- actions --------------------------------------------------------
    def _clear_filters(self) -> None:
        """Empty every filter and show all the records."""
        self.search_var.set("")
        self.product_var.set("")
        self.market_var.set("")
        self.user_var.set("")
        self.level_var.set("")
        self.from_var.set("")
        self.to_var.set("")
        self.refresh()

    def _edit_selected(self, record_id=None) -> None:
        """Open the edit dialog for the selected record."""
        if record_id is None:
            record_id = self.table.selected_id()
        if not record_id:
            show_info(self, "Please select a record first.")
            return
        try:
            record = self.manager.get_record(record_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return

        user = self.manager.current_user
        if user is None or not user.can_edit(record):
            show_info(self, "You can only edit your own price records.")
            return

        EditRecordDialog(
            self.winfo_toplevel(), self.manager, record, self.refresh
        )

    def _delete_selected(self) -> None:
        """Delete the selected record, after a confirmation."""
        record_id = self.table.selected_id()
        if not record_id:
            show_info(self, "Please select a record first.")
            return
        try:
            record = self.manager.get_record(record_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return

        user = self.manager.current_user
        if user is None or not user.can_delete(record):
            show_info(self, "Only an Admin can delete price records.")
            return

        if not confirm(
            self.winfo_toplevel(),
            f"Delete the record for {record.product_id} at {record.market} "
            f"on {record.date} (Tk {record.price:.2f})?\n\n"
            "This cannot be undone.",
        ):
            return
        try:
            self.manager.delete_record(record_id)
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.refresh()
