"""The login window, including the first-run 'Create Admin account' screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.widgets import handle_error, show_error, show_info
from validators import AuthError, ValidationError


class LoginView(ttk.Frame):
    """The login form.

    On a fresh install there is no user yet, so the same screen shows a
    'Create Admin account' form instead of the login form.
    """

    def __init__(self, parent, manager, on_success):
        """``on_success`` is called with the logged-in user."""
        super().__init__(parent, padding=30)
        self.manager = manager
        self.on_success = on_success

        self.is_first_run = manager.needs_admin_setup()

        self.title_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()

        self._build()

    def _build(self) -> None:
        """Lay the form out."""
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        heading = ttk.Label(
            container,
            text="BazarWatch BD",
            font=("TkDefaultFont", 20, "bold"),
        )
        heading.grid(row=0, column=0, pady=(0, 4))

        subtitle = ttk.Label(
            container,
            text="Household price tracker and basket optimiser",
        )
        subtitle.grid(row=1, column=0, pady=(0, 20))

        if self.is_first_run:
            self._build_first_run(container)
        else:
            self._build_login(container)

    def _build_login(self, container) -> None:
        """The normal login form."""
        ttk.Label(container, text="Welcome back. Please log in.").grid(
            row=2, column=0, sticky="w", pady=(0, 10)
        )

        form = ttk.Frame(container)
        form.grid(row=3, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Username:").grid(
            row=0, column=0, sticky="w", pady=6
        )
        self.username_entry = ttk.Entry(form, textvariable=self.title_var, width=30)
        self.username_entry.grid(row=0, column=1, sticky="ew", pady=6)
        self.username_entry.focus_set()

        ttk.Label(form, text="Password:").grid(
            row=1, column=0, sticky="w", pady=6
        )
        self.password_entry = ttk.Entry(
            form, textvariable=self.password_var, show="*", width=30
        )
        self.password_entry.grid(row=1, column=1, sticky="ew", pady=6)

        self.error_var = tk.StringVar()
        ttk.Label(form, textvariable=self.error_var, foreground="#c62828").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        button = ttk.Button(container, text="Log in", command=self._do_login)
        button.grid(row=4, column=0, pady=(14, 0), ipadx=20)

        # Enter logs in from either field.
        for widget in (self.username_entry, self.password_entry):
            widget.bind("<Return>", lambda event: self._do_login())

    def _build_first_run(self, container) -> None:
        """The 'Create Admin account' form shown on the very first run."""
        ttk.Label(
            container,
            text="Welcome! This is the first run, so there is no account yet.\n"
            "Please create the Admin account.",
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        form = ttk.Frame(container)
        form.grid(row=3, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Admin username:").grid(
            row=0, column=0, sticky="w", pady=6
        )
        self.username_entry = ttk.Entry(form, textvariable=self.title_var, width=30)
        self.username_entry.grid(row=0, column=1, sticky="ew", pady=6)
        self.username_entry.focus_set()

        ttk.Label(form, text="Password:").grid(
            row=1, column=0, sticky="w", pady=6
        )
        self.password_entry = ttk.Entry(
            form, textvariable=self.password_var, show="*", width=30
        )
        self.password_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Confirm password:").grid(
            row=2, column=0, sticky="w", pady=6
        )
        self.confirm_entry = ttk.Entry(
            form, textvariable=self.confirm_var, show="*", width=30
        )
        self.confirm_entry.grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(
            form,
            text="The password must be at least 6 characters.",
            foreground="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.error_var = tk.StringVar()
        ttk.Label(form, textvariable=self.error_var, foreground="#c62828").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        button = ttk.Button(container, text="Create Admin", command=self._do_create)
        button.grid(row=5, column=0, pady=(14, 0), ipadx=20)

        for widget in (self.username_entry, self.password_entry, self.confirm_entry):
            widget.bind("<Return>", lambda event: self._do_create())

    # -- actions ---------------------------------------------------------
    def _do_login(self) -> None:
        """Check the credentials and hand over to the main window."""
        username = self.title_var.get().strip()
        password = self.password_var.get()
        if not username:
            self.error_var.set("Please enter your username.")
            return
        if not password:
            self.error_var.set("Please enter your password.")
            return
        try:
            user = self.manager.login(username, password)
        except AuthError as exc:
            self.error_var.set(str(exc))
            self.password_var.set("")
            return
        except Exception as exc:  # pragma: no cover - defensive
            handle_error(self.winfo_toplevel(), exc)
            return
        self.error_var.set("")
        self.on_success(user)

    def _do_create(self) -> None:
        """Create the first Admin account."""
        username = self.title_var.get().strip()
        password = self.password_var.get()
        confirm = self.confirm_var.get()
        if password != confirm:
            self.error_var.set("The two passwords do not match.")
            return
        try:
            self.manager.create_admin(username, password)
        except ValidationError as exc:
            self.error_var.set(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            handle_error(self.winfo_toplevel(), exc)
            return
        show_info(
            self.winfo_toplevel(),
            f"The Admin account '{username}' was created.\n"
            "Please log in with it.",
        )
        # Rebuild the form so it now shows the login fields.
        self.is_first_run = False
        self.title_var.set("")
        self.password_var.set("")
        self.confirm_var.set("")
        for child in self.winfo_children():
            child.destroy()
        self._build()
