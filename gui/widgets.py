"""Shared GUI helpers: the colour-coded table, alert colours and error boxes.

These helpers are used by every tab so the app looks and behaves the same
throughout.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, ttk
from typing import Literal

import config
from validators import BazarError

# The anchors Tkinter accepts for a column.
Anchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]

# One column of an AlertTable: the key used in the tree, the heading
# shown to the user, the anchor and the width in pixels.
ColumnDef = tuple[str, str, Anchor, int]


class Tab(ttk.Frame):
    """What every tab in the notebook must be able to do.

    The main window calls ``refresh()`` on each tab whenever the data
    changes, so every tab has to provide it.  Every tab is also a
    ``ttk.Frame``, because that is what the notebook holds.
    """

    def refresh(self) -> None:
        """Reload the tab from the manager."""
        raise NotImplementedError

# -- Colours -----------------------------------------------------------------
# Spike is red, Watch is amber, Normal is plain.
COLOUR_SPIKE = "#c62828"
COLOUR_WATCH = "#ef6c00"
COLOUR_NORMAL = ""
COLOUR_ALT_ROW = "#f5f7f8"

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
    handler: logging.Handler
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

    def __init__(self, parent, columns: list[ColumnDef], height: int = 10,
                 **kwargs):
        """``columns`` is a list of ``(key, heading, anchor, width)`` tuples.

        ``height`` is the number of rows the table shows before it scrolls.
        """
        super().__init__(parent, **kwargs)
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

    @contextmanager
    def preserve_selection(self):
        """Keep the chosen row selected across a rebuild of the table.

        Rebuilding the table deletes the rows, and the selection goes with
        them.  This remembers the chosen row and puts the selection back
        once the new rows are in place.
        """
        chosen = self.tree.selection()
        chosen = chosen[0] if chosen else None
        try:
            yield
        finally:
            if chosen and self.tree.exists(chosen):
                self.tree.selection_set(chosen)

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
        """The ID of the selected row, or None.

        The ID is the one the row was added with, which is the record ID,
        the username or the product ID.  It is not the first column of
        the row: a table that shows a name there would hand back the
        name, and the name is not always what the data is keyed on.
        """
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    def double_click_handler(self, callback):
        """Call ``callback`` when a row is double-clicked."""

        def handler(event):
            if self.tree.selection():
                callback(self.selected_id())

        self.tree.bind("<Double-1>", handler)


def product_id_for(options: list[tuple[str, str]], chosen: str) -> str | None:
    """The product ID a dropdown label stands for, or None if there is none."""
    for label, product_id in options:
        if label == chosen:
            return product_id
    return None


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
