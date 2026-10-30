"""The 'Statistics & Alerts' tab: per-product statistics, alerts and the
weekly report."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from analytics import alerts_for, product_statistics
from gui.widgets import AlertTable, handle_error, show_info
from reports import build_weekly_report, save_weekly_report


class StatsTab(ttk.Frame):
    """Statistics per product, the Spike/Watch list and the weekly report."""

    def __init__(self, parent, manager, logger=None):
        super().__init__(parent, padding=12)
        self.manager = manager
        self.logger = logger

        self._build()
        self.refresh()

    def _build(self) -> None:
        """Lay the tab out."""
        ttk.Label(
            self,
            text="Statistics and alerts",
            font=("TkDefaultFont", 13, "bold"),
        ).grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 10))

        # -- the statistics table
        ttk.Label(
            self, text="Per-product statistics", font=("TkDefaultFont", 11, "bold")
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(0, 6))

        self.stats_table = AlertTable(
            self,
            [
                ("product", "Product", "w", 170),
                ("count", "Count", "e", 60),
                ("mean", "Mean", "e", 80),
                ("median", "Median", "e", 80),
                ("min", "Min", "e", 70),
                ("max", "Max", "e", 70),
                ("std", "Std dev", "e", 80),
                ("reference", "Reference", "e", 90),
                ("latest", "Latest", "e", 80),
            ],
            height=9,
        )
        self.stats_table.grid(row=2, column=0, columnspan=7, sticky="nsew")

        # -- the alerts table
        ttk.Label(
            self,
            text="Spike and Watch records",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=3, column=0, columnspan=7, sticky="w", pady=(16, 6))

        self.alerts_table = AlertTable(
            self,
            [
                ("level", "Level", "center", 70),
                ("id", "ID", "center", 70),
                ("product", "Product", "w", 160),
                ("market", "Market", "w", 150),
                ("date", "Date", "center", 100),
                ("price", "Price (Tk)", "e", 90),
                ("z", "z", "e", 60),
                ("pct", "% over ref", "e", 80),
            ],
            height=9,
        )
        self.alerts_table.grid(row=4, column=0, columnspan=7, sticky="nsew")

        # -- the weekly report
        report_frame = ttk.LabelFrame(self, text="Weekly report", padding=10)
        report_frame.grid(
            row=5, column=0, columnspan=7, sticky="ew", pady=(16, 0)
        )
        report_frame.columnconfigure(1, weight=1)

        ttk.Label(report_frame, text="Report date:").grid(
            row=0, column=0, sticky="w"
        )
        self.report_date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(report_frame, textvariable=self.report_date_var, width=14).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Label(
            report_frame, text="(the 7 days ending on this date)"
        ).grid(row=0, column=1, sticky="w", padx=(160, 0))

        buttons = ttk.Frame(report_frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(
            buttons, text="Preview report", command=self._preview_report
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            buttons, text="Save report to file", command=self._save_report
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons, text="Refresh", command=self.refresh
        ).grid(row=0, column=2)

        self.preview_var = tk.StringVar()
        self.preview = tk.Text(
            report_frame, height=12, width=110, wrap="none", font=("TkFixedFont", 10)
        )
        self.preview.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.preview.configure(state="disabled")

        self.rowconfigure(2, weight=1)
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

    # -- data ----------------------------------------------------------
    def refresh(self) -> None:
        """Reload the statistics and the alerts."""
        manager = self.manager
        show_bn = manager.show_bangla_names()

        self.stats_table.clear()
        for product_id, product in sorted(manager.products.items()):
            stats = product_statistics(
                product_id, manager.records, manager.products
            )
            self.stats_table.add_row(
                [
                    product.display_name(show_bn),
                    stats["count"],
                    f"{stats['mean']:.2f}" if stats["mean"] is not None else "-",
                    f"{stats['median']:.2f}" if stats["median"] is not None else "-",
                    f"{stats['min']:.2f}" if stats["min"] is not None else "-",
                    f"{stats['max']:.2f}" if stats["max"] is not None else "-",
                    f"{stats['std']:.2f}" if stats["std"] is not None else "-",
                    f"{stats['reference']:.2f}" if stats["reference"] is not None else "-",
                    f"{stats['latest']:.2f}" if stats["latest"] is not None else "-",
                ],
                level="Normal",
                item_id=product_id,
            )

        self.alerts_table.clear()
        found = alerts_for(manager.records, manager.products, manager.settings)
        found = [entry for entry in found if entry[1] != "Normal"]
        found.sort(key=lambda entry: (entry[1] != "Spike", entry[0].date))
        for record, level, z_value, pct_value in found:
            product = manager.products.get(record.product_id)
            name = (
                product.display_name(show_bn) if product else record.product_id
            )
            self.alerts_table.add_row(
                [
                    level,
                    record.record_id,
                    name,
                    record.market,
                    record.date,
                    f"{record.price:.2f}",
                    f"{z_value:.2f}" if z_value is not None else "-",
                    f"{pct_value:+.1f}%" if pct_value is not None else "ref not set",
                ],
                level=level,
                item_id=record.record_id,
            )

    # -- the weekly report ---------------------------------------------
    def _report_date(self) -> date:
        """The date the report ends on."""
        try:
            return date.fromisoformat(self.report_date_var.get().strip())
        except ValueError:
            raise ValueError("The report date must be in YYYY-MM-DD format.")

    def _preview_report(self) -> None:
        """Show the report in the text box."""
        try:
            end_date = self._report_date()
        except ValueError as exc:
            show_info(self, str(exc))
            return
        try:
            text = build_weekly_report(
                self.manager.records,
                self.manager.products,
                self.manager.settings,
                markets=self.manager.markets(),
                end_date=end_date,
                show_bangla=self.manager.show_bangla_names(),
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _save_report(self) -> None:
        """Save the report to the reports folder."""
        try:
            end_date = self._report_date()
        except ValueError as exc:
            show_info(self, str(exc))
            return
        try:
            path = save_weekly_report(
                self.manager.records,
                self.manager.products,
                self.manager.settings,
                markets=self.manager.markets(),
                end_date=end_date,
                show_bangla=self.manager.show_bangla_names(),
            )
        except Exception as exc:
            handle_error(self.winfo_toplevel(), exc, self.logger)
            return
        show_info(
            self.winfo_toplevel(),
            f"The weekly report was saved to:\n{path}",
        )
