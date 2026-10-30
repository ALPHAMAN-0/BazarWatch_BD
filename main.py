"""BazarWatch BD - entry point.

Run the app with:

    python main.py

The data folder is found relative to this file, so the app works from any
working directory.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Start the graphical application."""
    try:
        from gui.app import BazarApp
    except ImportError as exc:
        # A missing tkinter is the usual cause, and it is worth explaining
        # rather than showing a raw traceback.
        if "tkinter" in str(exc):
            print(
                "Error: tkinter is not available.\n\n"
                "On Debian or Ubuntu install it with:\n"
                "    sudo apt install python3-tk\n\n"
                "On Windows and macOS it comes with Python itself.",
                file=sys.stderr,
            )
            return 1
        raise

    app = BazarApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
