"""Shared GUI helpers: the colour-coded table, alert colours and error boxes.

These helpers are used by every tab so the app looks and behaves the same
throughout.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import config
from validators import BazarError

# -- Colours -----------------------------------------------------------------
# Spike is red, Watch is amber, Normal is plain.
COLOUR_SPIKE = "#c62828"
COLOUR_WATCH = "#ef6c00"
COLOUR_NORMAL = ""
COLOUR_HEADER_BG = "#eceff1"
COLOUR_ALT_ROW = "#f5f7f8"
COLOUR_SELECTION = "#bbdefb"

# The colours of each alert level.
LEVEL_COLOURS = {
    "Spike": COLOUR_SPIKE,
    "Watch": COLOUR_WATCH,
    "Normal": COLOUR_NORMAL,
}

# The tag names used on the table rows.
LEVEL_TAGS = {
    "Spike": "spike",
    "Watch": "watch",
    "Normal": "normal",
}


def setup_error_log() -> logging.Logger:
    """Send unexpected errors to ``data/error.log``.

    The GUI shows a friendly message; the traceback goes to the log so a
    problem can still be investigated after the fact.
    """
    logger = logging.getLogger("bazarwatch")
    if logger.handlers:
        return logger
    logger.setLevel(logging.ERROR)
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(config.ERROR_LOG_FILE, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    return logger


def apply_theme(root: tk.Misc) -> None:
    """Use the 'clam' theme so the row colours also show on Windows."""
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
    except tk.TclError:
        # 'clam' is missing on some builds; the default theme still works.
        pass


def show_error(parent, message: str, title: str = "Error") -> None:
    """Show an error message to the user."""
    messagebox.showerror(title, message, parent=parent)


def show_info(parent, message: str, title: str = "BazarWatch BD") -> None:
    """Show an information message to the user."""
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent, message: str, title: str = "Warning") -> None:
    """Show a warning message to the user."""
    messagebox.showwarning(title, message, parent=parent)


def confirm(parent, question: str, title: str = "Please confirm") -> bool:
    """Ask the user to confirm a destructive action."""
    return bool(
        messagebox.askyesno(title, question, parent=parent)
    )


def handle_error(parent, error: Exception, logger=None) -> None:
    """Deal with an exception without ever closing the app.

    A :class:`BazarError` shows its message, because it is an expected user
    mistake.  Anything else is unexpected: it shows a friendly message and
    writes the traceback to the error log.
    """
    if isinstance(error, BazarError):
        show_error(parent, str(error))
        return
    if logger is None:
        logger = setup_error_log()
    logger.exception("Unexpected error: %s", error)
    show_error(
        parent,
        "Something went wrong and the action could not be completed.\n\n"
        "The details were written to data/error.log.\n"
        "The app is still running; please try again.",
    )


class AlertTable(ttk.Frame):
    """A read-only table whose rows are coloured by alert level.

    The table is a Treeview with a ``level`` tag on each row, so the colour
    follows the alert level of the record.
    """

    def __init__(self, parent, columns: list[tuple[str, str, int]], height: int = 10,
                 **kwargs):
        """``columns`` is a list of ``(heading, anchor, width)`` tuples.

        ``height`` is the number of rows the table shows before it scrolls.
        """
        super().__init__(parent, **kwargs)
        self.column_defs = columns
        self.tree = ttk.Treeview(
            self,
            columns=[c[0] for c in columns],
            show="headings",
            selectmode="browse",
            height=height,
        )
        for key, heading, anchor, width in columns:
            self.tree.heading(key, text=heading, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor, stretch=True)

        self.tree.tag_configure("spike", foreground=COLOUR_SPIKE)
        self.tree.tag_configure("watch", foreground=COLOUR_WATCH)
        self.tree.tag_configure("normal", foreground=COLOUR_NORMAL)
        self.tree.tag_configure("odd", background=COLOUR_ALT_ROW)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def clear(self) -> None:
        """Remove every row."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def add_row(self, values: list, level: str = "Normal", item_id=None) -> None:
        """Add a row, coloured by its alert level."""
        tags = [LEVEL_TAGS.get(level, "normal")]
        # Alternate the background so long tables stay readable.
        existing = len(self.tree.get_children())
        if existing % 2 == 1:
            tags.append("odd")
        self.tree.insert(
            "", "end", iid=item_id, values=values, tags=tuple(tags)
        )

    def selected_id(self) -> str | None:
        """The first column of the selected row, or None."""
        selection = self.tree.selection()
        if not selection:
            return None
        return self.tree.item(selection[0], "values")[0]

    def double_click_handler(self, callback):
        """Call ``callback`` when a row is double-clicked."""

        def handler(event):
            if self.tree.selection():
                callback(self.selected_id())

        self.tree.bind("<Double-1>", handler)


def label_value_frame(parent, rows: list[tuple[str, str]], **kwargs):
    """A small two-column frame of label/value pairs.

    Returns ``(frame, value_labels)`` where ``value_labels`` maps each label
    to the StringVar holding its value, so the caller can update it.
    """
    frame = ttk.Frame(parent, **kwargs)
    value_labels = {}
    for index, (label, value) in enumerate(rows):
        ttk.Label(frame, text=f"{label}:", width=22).grid(
            row=index, column=0, sticky="w", padx=(6, 4), pady=3
        )
        var = tk.StringVar(value=value)
        ttk.Label(frame, textvariable=var, width=40).grid(
            row=index, column=1, sticky="w", padx=(0, 6), pady=3
        )
        value_labels[label] = var
    return frame, value_labels


def format_price(value) -> str:
    """Format a price for the GUI."""
    if value is None:
        return "-"
    return f"Tk {float(value):,.2f}"


def level_label(parent, text: str, level: str) -> ttk.Label:
    """A label coloured by its alert level."""
    label = ttk.Label(parent, text=text, font=("TkDefaultFont", 11, "bold"))
    colour = LEVEL_COLOURS.get(level)
    if colour:
        label.configure(foreground=colour)
    return label
