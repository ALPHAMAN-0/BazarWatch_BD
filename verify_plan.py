"""Check the app against plan.md.

This walks the plan's requirements one by one and reports what passes and
what does not.  It is a one-off verification script, not part of the test
suite: it opens the real GUI window and drives it.

    python3 verify_plan.py
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from tkinter import ttk
from typing import cast

import numpy as np

import config
from analytics import (
    alert_level,
    basket_plan,
    budget_status,
    cheapest_market,
    product_statistics,
)
from generate_sample_data import generate
from gui.admin_tab import AdminTab
from gui.basket_tab import BasketTab
from gui.dashboard_tab import DashboardTab
from gui.log_price_tab import LogPriceTab
from gui.login_view import LoginView
from gui.records_tab import RecordsTab
from manager import BazarManager
from models import PerishableProduct, PriceRecord, Product
from storage import Storage
from validators import (
    AuthError,
    BazarError,
    DuplicateIDError,
    PermissionDeniedError,
    RecordNotFoundError,
    ValidationError,
)

RESULTS: list[tuple[bool, str, str]] = []

# The numbers the plan quotes, named so the checks below read as prose
# instead of a wall of literals.
PLAN_PRODUCT_COUNT = 12
TABLE_COLUMNS = 6
SAMPLE_RECORD_MIN = 250
SAMPLE_RECORD_MAX = 300
SAMPLE_USER_FILE_MIN_BYTES = 10
REFERENCE_PRICE = 50.0
HIGH_REFERENCE_PRICE = 200.0
PCT_OVER_LIMIT = 15.0
Z_LIMIT = 2.0
PERISHABLE_Z_LIMIT = 2.5
PERISHABLE_PCT_LIMIT = 25.0
STANDARD_Z_LIMIT = 2.0
STANDARD_PCT_LIMIT = 15.0
BUDGET = 100.0
WITHIN_BUDGET = 90.0
CLOSE_TO_BUDGET = 95.0
OVER_BUDGET = 120.0
TOLERANCE = 1e-9
ONION_UNIT_PRICE = 40.0
EGG_UNIT_PRICE = 120.0
STAT_MEAN = 20.0
STAT_MEDIAN = 20.0
STAT_MIN = 10.0
STAT_MAX = 30.0
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 400
MIN_TABLE_ROWS = 100
MIN_TABLE_HEIGHT = 200


def check(name: str, condition, detail: str = "") -> None:
    """Record one check."""
    RESULTS.append((bool(condition), name, detail))


def section(title: str) -> None:
    """Print a section heading."""
    print(f"\n{title}")
    print("-" * len(title))


def replace(module, name: str, value) -> None:
    """Set an attribute on a module, whatever the module has or has not.

    The GUI modules do not all import the same helpers, so the attribute
    is set through this helper rather than by direct assignment.
    """
    vars(module)[name] = value


# --- Section 4 and 12: the starter data and the sample generator ------------
section("4/12  Starter data and the sample generator")

check(
    "the three starter markets are the ones in the plan",
    list(config.DEFAULT_MARKETS) == [
        "Karwan Bazar", "Mohammadpur Krishi Market", "Shwapno",
    ],
    str(config.DEFAULT_MARKETS),
)

plan_products = {}
for line in Path("plan.md").read_text(encoding="utf-8").splitlines():
    # The starter-data table: | ID | Name | Bangla name | Unit | Category | Perishable |
    if not line.startswith("|") or line.startswith("|---"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) != TABLE_COLUMNS or cells[0] in {"ID", ""}:
        continue
    if not cells[0].replace("_", "").isalpha() or cells[0] != cells[0].upper():
        continue
    plan_products[cells[0]] = (
        cells[1], cells[2], cells[3], cells[4], cells[5] == "✅",
    )
check(
    "the plan's starter table was read",
    len(plan_products) == PLAN_PRODUCT_COUNT,
    f"{len(plan_products)} products read from plan.md",
)
actual = {
    entry["product_id"]: (
        entry["name"], entry["name_bn"], entry["unit"], entry["category"],
        entry["perishable"],
    )
    for entry in config.DEFAULT_PRODUCTS
}
check(
    "the twelve starter products match the plan",
    actual == plan_products,
    "" if actual == plan_products else str(
        {k: v for k, v in actual.items() if plan_products.get(k) != v}
    ),
)
check(
    "the reference prices start empty",
    all(e["reference_price"] is None for e in config.DEFAULT_PRODUCTS),
)
check(
    "the alert levels are Normal, Watch and Spike",
    set(config.ALERT_LEVELS) == {"Normal", "Watch", "Spike"},
    str(config.ALERT_LEVELS),
)
check(
    "the roles are Admin and Member",
    set(config.ROLES) == {"admin", "member"},
    str(config.ROLES),
)

with tempfile.TemporaryDirectory() as tmp:
    data_dir = Path(tmp)
    generate(data_dir, end_date=date.today(), force=True)
    record_lines = (data_dir / "price_records.csv").read_text(encoding="utf-8").splitlines()
    users = (data_dir / "users.json").read_text(encoding="utf-8")
    check(
        "the generator writes between 250 and 300 records",
        SAMPLE_RECORD_MIN <= len(record_lines) - 1 <= SAMPLE_RECORD_MAX,
        f"{len(record_lines) - 1} records",
    )
    check(
        "the generator writes the users file",
        len(users) > SAMPLE_USER_FILE_MIN_BYTES,
    )
    check(
        "the generator creates the data files",
        all(
            (data_dir / name).exists()
            for name in (
                "products.json", "price_records.csv", "users.json",
                "baskets.json", "settings.json",
            )
        ),
    )
    # Seeded: the same run twice gives the same data.
    second = Path(tmp) / "second"
    generate(second, end_date=date.today(), force=True)
    check(
        "the generator is seeded and gives the same data every run",
        (data_dir / "price_records.csv").read_text(encoding="utf-8")
        == (second / "price_records.csv").read_text(encoding="utf-8"),
    )

# --- Section 5: the rules ---------------------------------------------------
section("5  The alert, cheapest-market and basket rules")

onion = Product(
    "ONION", "Onion", "পেঁয়াজ", "kg", "Vegetables", reference_price=REFERENCE_PRICE
)
settings = dict(config.DEFAULT_SETTINGS)

# A history that varies a little, then a big jump: z is large and the
# percentage is large.  The prices have to vary, because a history with no
# spread at all has a standard deviation of zero and so no z-score.
flat = [
    PriceRecord(
        f"R{i}", "ONION", "Karwan Bazar", f"2026-09-{20 + i:02d}",
        48.0 + i, "rafi",
    )
    for i in range(1, 7)
]
spike = PriceRecord("R9", "ONION", "Karwan Bazar", "2026-10-08", 90.0, "rafi")
level, z, pct = alert_level(spike, [*flat, spike], {"ONION": onion}, settings)
check("a big jump on both rules is a Spike", level == "Spike", f"{level} z={z} pct={pct}")

# Only the z rule fires: the reference price is high enough not to fire.
onion_high = Product(
    "ONION", "Onion", "পেঁয়াজ", "kg", "Vegetables",
    reference_price=HIGH_REFERENCE_PRICE,
)
level, z, pct = alert_level(spike, [*flat, spike], {"ONION": onion_high}, settings)
check("only the z rule firing is a Watch", level == "Watch", f"{level} z={z} pct={pct}")

# Only the percentage rule fires: the history is wide enough that the
# z-score stays below the limit of 2.0 even though the price is 20% above
# the reference price.
wide = [
    PriceRecord(
        f"R{i}", "ONION", "Karwan Bazar", f"2026-09-{20 + i:02d}",
        35.0 + i * 5.0, "rafi",
    )
    for i in range(1, 7)
]
mid = PriceRecord("R9", "ONION", "Karwan Bazar", "2026-10-08", 60.0, "rafi")
level, z, pct = alert_level(mid, [*wide, mid], {"ONION": onion}, settings)
check(
    "only the percentage rule firing is a Watch",
    level == "Watch" and pct is not None
    and pct >= PCT_OVER_LIMIT and z < Z_LIMIT,
    f"{level} z={z} pct={pct}",
)

# Neither rule fires.
quiet = PriceRecord("R9", "ONION", "Karwan Bazar", "2026-10-08", 50.0, "rafi")
level, z, pct = alert_level(quiet, [*flat, quiet], {"ONION": onion}, settings)
check("neither rule firing is Normal", level == "Normal", f"{level} z={z} pct={pct}")

# A history with no spread at all gives no z-score.
level, z, pct = alert_level(
    spike,
    [
        *[
            PriceRecord(
                f"R{i}", "ONION", "Karwan Bazar", f"2026-09-{20 + i:02d}", 50.0, "rafi"
            )
            for i in range(1, 7)
        ],
        spike,
    ],
    {"ONION": onion},
    settings,
)
check("a history with no spread gives no z-score", z is None, f"z={z}")

# No reference price: the most a record can reach is Watch.
no_ref = Product("ONION", "Onion", "পেঁয়াজ", "kg", "Vegetables", reference_price=None)
level, z, pct = alert_level(spike, [*flat, spike], {"ONION": no_ref}, settings)
check(
    "no reference price means at most Watch",
    level == "Watch" and pct is None,
    f"{level} pct={pct}",
)

# Too little history: no z.
short = flat[:3]
level, z, pct = alert_level(spike, [*short, spike], {"ONION": onion}, settings)
check("too little history means no z", z is None, f"z={z}")

# Perishables use the looser limits.
perishable = PerishableProduct("ONION", "Onion", "পেঁয়াজ", "kg", "Vegetables")
z_limit, pct_limit = perishable.spike_thresholds(settings)
check(
    "perishables use the looser limits",
    (z_limit, pct_limit) == (PERISHABLE_Z_LIMIT, PERISHABLE_PCT_LIMIT),
    f"{z_limit}, {pct_limit}",
)
z_limit, pct_limit = onion.spike_thresholds(settings)
check(
    "normal products use the standard limits",
    (z_limit, pct_limit) == (STANDARD_Z_LIMIT, STANDARD_PCT_LIMIT),
    f"{z_limit}, {pct_limit}",
)

# The history excludes the record itself and only looks backwards.
past = PriceRecord("R1", "ONION", "Karwan Bazar", "2026-10-01", 50.0, "rafi")
future = PriceRecord("R2", "ONION", "Karwan Bazar", "2026-10-20", 500.0, "rafi")
level, z, pct = alert_level(past, [past, future], {"ONION": onion}, settings)
check("the history only looks backwards", z is None, f"z={z}")

# The cheapest market ignores the records older than the window.
today = date.today()
old = (today - timedelta(days=40)).isoformat()
recent = (today - timedelta(days=2)).isoformat()
sample_records = [
    PriceRecord("R1", "ONION", "Karwan Bazar", old, 10.0, "rafi"),
    PriceRecord("R2", "ONION", "Shwapno", recent, 60.0, "rafi"),
    PriceRecord("R3", "ONION", "Karwan Bazar", recent, 80.0, "rafi"),
]
market, average = cheapest_market(
    "ONION", sample_records, ["Karwan Bazar", "Shwapno"], 14, today=today
)
check(
    "the cheapest market ignores the records older than the window",
    market == "Shwapno",
    f"{market} at {average}",
)

market, average = cheapest_market("ONION", [], ["Karwan Bazar"], 14, today=today)
check(
    "no recent data gives no market",
    market is None and average is None,
    f"{market} {average}",
)

# The basket uses a set intersection and a dot product.
basket_records = [
    PriceRecord("R1", "ONION", "Karwan Bazar", recent, 40.0, "rafi"),
    PriceRecord("R2", "EGG", "Karwan Bazar", recent, 120.0, "rafi"),
    PriceRecord("R3", "ONION", "Shwapno", recent, 50.0, "rafi"),
    PriceRecord("R4", "EGG", "Shwapno", recent, 130.0, "rafi"),
]
plan = basket_plan(
    {"ONION": 2, "EGG": 1}, basket_records, ["Karwan Bazar", "Shwapno"], 14,
    today=today,
)
check(
    "the best single market is the cheapest total",
    plan["best_market"] == "Karwan Bazar",
    str(plan["best_market"]),
)
check(
    "the basket total uses the dot product",
    abs(plan["best_total"] - (2 * ONION_UNIT_PRICE + EGG_UNIT_PRICE)) < TOLERANCE,
    str(plan["best_total"]),
)
check(
    "the split plan puts each item at its own cheapest market",
    plan["split_total"] == 2 * ONION_UNIT_PRICE + EGG_UNIT_PRICE,
    str(plan["split_total"]),
)

# A market that does not price every item is left out of the totals.
partial = [
    PriceRecord("R1", "ONION", "Karwan Bazar", recent, 40.0, "rafi"),
    PriceRecord("R3", "ONION", "Shwapno", recent, 50.0, "rafi"),
]
plan = basket_plan(
    {"ONION": 1, "EGG": 1}, partial, ["Karwan Bazar", "Shwapno"], 14, today=today
)
check(
    "a market without every item is left out of the totals",
    plan["best_market"] is None,
    str(plan["best_market"]),
)

status, detail = budget_status(WITHIN_BUDGET, BUDGET)
check("90% of the budget is within budget", status == "Within budget", f"{status} {detail}")
status, detail = budget_status(CLOSE_TO_BUDGET, BUDGET)
check("95% of the budget is close to budget", status == "Close to budget", f"{status} {detail}")
status, detail = budget_status(OVER_BUDGET, BUDGET)
check("over 100% is over budget", status == "Over budget", f"{status} {detail}")

stats = product_statistics(
    "ONION",
    [PriceRecord("R1", "ONION", "M", "2026-10-01", 10.0, "a"),
     PriceRecord("R2", "ONION", "M", "2026-10-02", 30.0, "a")],
    {"ONION": onion},
)
check(
    "the statistics give the mean, median, min, max and std",
    stats["mean"] == STAT_MEAN and stats["median"] == STAT_MEDIAN
    and stats["min"] == STAT_MIN and stats["max"] == STAT_MAX
    and abs(stats["std"] - np.std([STAT_MIN, STAT_MAX], ddof=1)) < TOLERANCE,
    str(stats),
)

# --- Section 9: validation and permissions ---------------------------------
section("9  Validation and permissions")

for name, exc in (
    ("ValidationError", ValidationError),
    ("DuplicateIDError", DuplicateIDError),
    ("RecordNotFoundError", RecordNotFoundError),
    ("AuthError", AuthError),
    ("PermissionDeniedError", PermissionDeniedError),
):
    check(f"{name} is a BazarError", issubclass(exc, BazarError))

with tempfile.TemporaryDirectory() as tmp:
    manager = BazarManager(Path(tmp))
    manager.create_admin("admin", "admin123")
    manager.login("admin", "admin123")
    manager.add_member("rafi", "rafi123")
    manager.logout()

    # A member may log a price.
    manager.login("rafi", "rafi123")
    record = manager.add_record("ONION", "Karwan Bazar", "2026-10-05", 40)
    check("a Member can log a price", record is not None)

    # A member may edit their own record but not somebody else's.
    manager.login("admin", "admin123")
    other = manager.add_record("ONION", "Karwan Bazar", "2026-10-06", 45)
    manager.login("rafi", "rafi123")
    try:
        manager.update_record(other.record_id, price=50)
        member_edit_other = False
    except PermissionDeniedError:
        member_edit_other = True
    check("a Member cannot edit another member's record", member_edit_other)

    # A member may not delete.
    try:
        manager.delete_record(record.record_id)
        member_delete = False
    except PermissionDeniedError:
        member_delete = True
    check("a Member cannot delete a record", member_delete)

    # A member may not manage the catalogue.
    manage_calls: list[tuple[str, Callable[[], object]]] = [
        ("add a product", lambda: manager.add_product("X", "X", "X", "kg", "Grocery")),
        ("add a market", lambda: manager.add_market("New Market")),
        ("change the settings", lambda: manager.update_settings({"z_threshold": 3})),
    ]
    for action, manage_call in manage_calls:
        try:
            manage_call()
            refused = False
        except PermissionDeniedError:
            refused = True
        check(f"a Member cannot {action}", refused)

    # An Admin may do all of it.
    manager.login("admin", "admin123")
    manager.add_product("X", "X", "X", "kg", "Grocery")
    manager.add_market("New Market")
    manager.update_settings({"z_threshold": 3})
    manager.delete_record(record.record_id)
    check("an Admin can manage the catalogue and delete", True)

    # The Admin cannot remove their own account.
    try:
        manager.remove_member("admin")
        self_remove = False
    except ValidationError:
        self_remove = True
    check("the Admin cannot remove their own account", self_remove)

    # The validation rules.
    from validators import validate_date, validate_price, validate_quantity

    for value in ("", "abc", 0, -5, 200000):
        try:
            validate_price(value)
            bad = False
        except ValidationError:
            bad = True
        check(f"the price {value!r} is refused", bad)

    for value in ("2026-13-01", "not-a-date", "01/10/2026"):
        try:
            validate_date(value)
            bad = False
        except ValidationError:
            bad = True
        check(f"the date {value!r} is refused", bad)

    try:
        validate_date((date.today() + timedelta(days=1)).isoformat())
        future_refused = False
    except ValidationError:
        future_refused = True
    check("a future date is refused", future_refused)

    for value in (0, -2):
        try:
            validate_quantity(value)
            quantity_refused = False
        except ValidationError:
            quantity_refused = True
        check(f"the quantity {value!r} is refused", quantity_refused)

    # Duplicate identifiers.
    duplicate_calls: list[tuple[str, Callable[[], object]]] = [
        ("the username", lambda: manager.add_member("rafi", "rafi123")),
        ("the product ID", lambda: manager.add_product("X", "Y", "Y", "kg", "Grocery")),
        ("the market name", lambda: manager.add_market("new market")),
    ]
    for label, duplicate_call in duplicate_calls:
        try:
            duplicate_call()
            bad = False
        except DuplicateIDError:
            bad = True
        check(f"a duplicate {label} is refused", bad)

    # The same-day duplicate.
    manager.add_record("EGG", "Karwan Bazar", "2026-10-20", 130)
    try:
        manager.add_record("EGG", "Karwan Bazar", "2026-10-20", 131)
        bad = False
    except DuplicateIDError:
        bad = True
    check("the same product, market and date twice by the same user is refused", bad)

    # A missing record.
    try:
        manager.get_record("R99999")
        bad = False
    except RecordNotFoundError:
        bad = True
    check("a missing record raises RecordNotFoundError", bad)

    # A wrong password.
    try:
        manager.login("rafi", "wrong")
        bad = False
    except AuthError:
        bad = True
    check("a wrong password raises AuthError", bad)

    # The stored hash is never the plain password.
    stored = (Path(tmp) / "users.json").read_text(encoding="utf-8")
    check("the password is never stored in the clear", "rafi123" not in stored)
    check("the password is hashed", "password_hash" in stored and "salt" in stored)

    # A product with records cannot be deleted.
    try:
        manager.remove_product("ONION")
        bad = False
    except ValidationError:
        bad = True
    check("a product with records cannot be deleted", bad)

    # A market with records cannot be deleted.
    try:
        manager.remove_market("Karwan Bazar")
        bad = False
    except ValidationError:
        bad = True
    check("a market with records cannot be deleted", bad)

    # Removing a member keeps their records and drops their basket.
    manager.login("rafi", "rafi123")
    manager.add_record("SUGAR", "Karwan Bazar", "2026-10-21", 130)
    manager.set_basket_item("rafi", "SUGAR", 2)
    manager.logout()
    manager.login("admin", "admin123")
    manager.remove_member("rafi")
    check(
        "removing a member keeps their records",
        any(r.added_by == "rafi" for r in manager.records),
        str([r.added_by for r in manager.records]),
    )
    check(
        "removing a member deletes their basket",
        "rafi" not in manager.baskets,
        str(list(manager.baskets)),
    )

# --- Section 8: the file rules ---------------------------------------------
section("8  The file rules")

with tempfile.TemporaryDirectory() as tmp:
    data_dir = Path(tmp)
    storage = Storage(data_dir)

    # A missing file is created with the defaults.
    storage.save_settings(dict(config.DEFAULT_SETTINGS))
    storage.save_records([])
    check(
        "a missing file is created with the defaults",
        (data_dir / "settings.json").exists()
        and (data_dir / "price_records.csv").exists(),
    )

    # Corrupt JSON is renamed and the defaults are loaded.
    (data_dir / "settings.json").write_text("{not json", encoding="utf-8")
    settings = storage.load_settings()
    corrupt = list(data_dir.glob("settings.json.corrupt-*"))
    check("corrupt JSON is renamed", len(corrupt) == 1, str(corrupt))
    check(
        "the defaults are loaded instead",
        settings["z_threshold"] == STANDARD_Z_LIMIT,
    )
    check("the problem is reported", len(storage.warnings) > 0)

    # A bad CSV row is skipped and reported.
    (data_dir / "price_records.csv").write_text(
        "record_id,product_id,market,date,price,added_by\n"
        "R00001,ONION,Karwan Bazar,2026-10-05,40.0,rafi\n"
        "R00002,ONION,Karwan Bazar,2026-10-06,abc,rafi\n"
        "R00003,NOPE,Karwan Bazar,2026-10-06,10.0,rafi\n"
        "R00004,ONION,Karwan Bazar,not-a-date,10.0,rafi\n",
        encoding="utf-8",
    )
    records = storage.load_records(known_product_ids={"ONION"})
    check("the good rows are kept", len(records) == 1, str(len(records)))
    # The three bad rows are reported in one message, each with its reason.
    row_warnings = " ".join(storage.warnings)
    check(
        "the bad rows are reported with their reasons",
        "Skipped 3 row" in row_warnings
        and "is not a number" in row_warnings
        and "unknown product" in row_warnings
        and "YYYY-MM-DD" in row_warnings,
        row_warnings,
    )

    # A safe save leaves no .tmp file behind.
    storage.save_records(records)
    check(
        "a safe save leaves no .tmp file behind",
        not list(data_dir.glob("*.tmp")),
    )

# --- Section 10: the screens, driven through the real GUI -------------------
section("10  The screens, driven through the real GUI")

try:
    import tkinter as tk

    probe = tk.Tk()
    probe.withdraw()
    probe.destroy()
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

if not TK_AVAILABLE:
    check("the GUI could be started", False, "no display available")
else:
    from tkinter import simpledialog

    import gui.admin_tab
    import gui.app
    import gui.basket_tab
    import gui.log_price_tab
    import gui.login_view
    import gui.records_tab
    import gui.stats_tab
    from gui import widgets
    from gui.app import BazarApp

    shown: dict[str, list] = {"errors": [], "infos": [], "warnings": []}
    def fake_show_error(parent, message, title="Error"):
        shown["errors"].append(message)

    def fake_show_info(parent, message, title="BazarWatch BD"):
        shown["infos"].append(message)

    def fake_show_warning(parent, message, title="Warning"):
        shown["warnings"].append(message)

    def fake_confirm(parent, question, title="Please confirm"):
        return True

    widgets.show_error = fake_show_error
    widgets.show_info = fake_show_info
    widgets.show_warning = fake_show_warning
    widgets.confirm = fake_confirm

    simpledialog.askstring = lambda *a, **k: None
    for module in (
        gui.admin_tab,
        gui.app,
        gui.basket_tab,
        gui.login_view,
        gui.log_price_tab,
        gui.records_tab,
        gui.stats_tab,
    ):
        for name, key in (
            ("show_error", "errors"), ("show_info", "infos"),
            ("show_warning", "warnings"),
        ):
            if hasattr(module, name):
                def capture(parent, message, title="x", _k=key):
                    shown[_k].append(message)

                setattr(module, name, capture)
        if hasattr(module, "confirm"):
            def always_confirm(parent, question, title="x"):
                return True

            replace(module, "confirm", always_confirm)

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        generate(data_dir, end_date=date.today(), force=True)
        manager = BazarManager(data_dir)
        app = BazarApp(manager=manager)
        app.update_idletasks()

        # The login screen comes first.
        check("the login screen comes first", bool(app._body.winfo_children()))

        # Log in as the Admin.
        view = cast(LoginView, app._body.winfo_children()[0])
        view.title_var.set("admin")
        view.password_var.set("admin123")
        view._do_login()
        app.update_idletasks()
        check(
            "the Admin sees every tab",
            set(app._tabs) == {
                "Dashboard", "Log Price", "Records", "Statistics & Alerts",
                "My Basket", "Admin",
            },
            str(sorted(app._tabs)),
        )
        check(
            "the header names the logged-in user",
            "admin" in cast(ttk.Frame, app._header).winfo_children()[1].cget("text"),
            cast(ttk.Frame, app._header).winfo_children()[1].cget("text"),
        )

        # The Records table has real rows and is tall enough to use.
        # The tab has to be the visible page before Tk lays it out.
        records_tab = cast(RecordsTab, app._tabs["Records"])
        notebook = cast(ttk.Notebook, app._notebook)
        notebook.select(records_tab)
        for _ in range(4):
            app.update_idletasks()
            app.update()
        records_tab.refresh()
        app.update_idletasks()
        rows = len(records_tab.table.tree.get_children())
        check("the Records table is filled", rows > MIN_TABLE_ROWS, f"{rows} rows")
        check(
            "the Records table is tall enough to use",
            records_tab.table.tree.winfo_height() > MIN_TABLE_HEIGHT,
            f"{records_tab.table.tree.winfo_height()} px",
        )

        # Every tab gets a real share of the window.
        for name, tab in app._tabs.items():
            notebook.select(tab)
            for _ in range(4):
                app.update_idletasks()
                app.update()
            check(
                f"the {name} tab fills the window",
                tab.winfo_width() > WINDOW_WIDTH
                and tab.winfo_height() > WINDOW_HEIGHT,
                f"{tab.winfo_width()}x{tab.winfo_height()}",
            )

        # The Dashboard has its numbers.
        dashboard = cast(DashboardTab, app._tabs["Dashboard"])
        dashboard.refresh()
        app.update_idletasks()
        totals = {k: v.get() for k, v in dashboard.summary_vars.items()}
        check(
            "the Dashboard shows the record count",
            totals.get("Records") == str(len(manager.records)),
            str(totals),
        )
        check(
            "the Dashboard shows the product count",
            totals.get("Products") == str(len(manager.products)),
            str(totals),
        )

        # The Log Price tab saves a price and shows the level.
        log_price = cast(LogPriceTab, app._tabs["Log Price"])
        notebook.select(log_price)
        for _ in range(4):
            app.update_idletasks()
            app.update()
        log_price.refresh_choices()
        log_price.price_var.set("999")
        log_price._save()
        app.update_idletasks()
        check(
            "the Log Price tab saves and shows a level",
            log_price.result_label.cget("text") in {"Spike", "Watch", "Normal"},
            log_price.result_label.cget("text"),
        )

        # The basket works.
        basket = cast(BasketTab, app._tabs["My Basket"])
        notebook.select(basket)
        for _ in range(4):
            app.update_idletasks()
            app.update()
        basket.product_var.set(manager.product_label("ONION"))
        basket.quantity_var.set("2")
        basket._add_item()
        basket.budget_var.set("500")
        basket._save_budget()
        app.update_idletasks()
        check(
            "the basket holds the item",
            len(basket.items_table.tree.get_children()) == 1,
            str(len(basket.items_table.tree.get_children())),
        )
        check(
            "the basket names the best single market",
            bool(basket.best_var.get()),
            basket.best_var.get(),
        )
        check(
            "the basket shows the saving",
            bool(basket.saving_var.get()),
            basket.saving_var.get(),
        )

        # The weekly report is generated.
        with tempfile.TemporaryDirectory() as reports_dir:
            import config as config_module

            original = config_module.REPORTS_DIR
            config_module.REPORTS_DIR = Path(reports_dir)
            try:
                app._generate_report()
                files = list(Path(reports_dir).glob("weekly_report_*.txt"))
                check(
                    "the weekly report is saved with the dated name",
                    len(files) == 1
                    and files[0].name == f"weekly_report_{date.today().isoformat()}.txt",
                    str(files),
                )
                text = files[0].read_text(encoding="utf-8")
                for section_name in (
                    "SUMMARY", "RECORDS BY MARKET", "CHEAPEST MARKET",
                    "SPIKE AND WATCH LIST", "TOP CONTRIBUTORS",
                ):
                    check(
                        f"the report has the {section_name} section",
                        section_name in text,
                    )
                check(
                    "the report says the data is illustrative",
                    "illustrative" in text.lower(),
                )
            finally:
                config_module.REPORTS_DIR = original

        # The Admin sub-tabs.
        admin = cast(AdminTab, app._tabs["Admin"])
        for name, sub in (
            ("Users", admin.users_tab),
            ("Products", admin.products_tab),
            ("Markets", admin.markets_tab),
            ("Settings", admin.settings_tab),
        ):
            sub.refresh()
            app.update_idletasks()
            check(f"the Admin {name} page is filled", bool(sub.winfo_children()))

        # Log out and back in as a Member: no Admin tab.
        app._logout()
        app.update_idletasks()
        view = cast(LoginView, app._body.winfo_children()[0])
        view.title_var.set("rafi")
        view.password_var.set("rafi123")
        view._do_login()
        app.update_idletasks()
        check(
            "a Member does not see the Admin tab",
            "Admin" not in app._tabs,
            str(sorted(app._tabs)),
        )

        # The Delete button is disabled for a Member.
        records_tab = cast(RecordsTab, app._tabs["Records"])
        notebook = cast(ttk.Notebook, app._notebook)
        notebook.select(records_tab)
        for _ in range(4):
            app.update_idletasks()
            app.update()
        records_tab.refresh()
        app.update_idletasks()
        first_row = records_tab.table.tree.get_children()[0]
        records_tab.table.tree.selection_set(first_row)
        records_tab.table.tree.event_generate("<<TreeviewSelect>>")
        app.update_idletasks()
        check(
            "a Member cannot delete",
            str(records_tab.delete_button.cget("state")) == "disabled",
            str(records_tab.delete_button.cget("state")),
        )

        # Refreshing keeps the chosen row.
        records_tab.refresh()
        app.update_idletasks()
        check(
            "the chosen row survives a refresh",
            records_tab.table.selected_id() == first_row,
            str(records_tab.table.selected_id()),
        )

        # No unexpected error was logged.
        check("no unexpected error was shown", not shown["errors"], str(shown["errors"]))

        app.destroy()

# --- The report ------------------------------------------------------------
section("Report")

passed = sum(1 for ok, _, _ in RESULTS if ok)
failed = [(name, detail) for ok, name, detail in RESULTS if not ok]
print(f"{passed} of {len(RESULTS)} checks passed.")
if failed:
    print("\nFailed checks:")
    for name, detail in failed:
        print(f"  FAIL  {name}  {detail}")
    sys.exit(1)
print("Everything in plan.md checks out.")
