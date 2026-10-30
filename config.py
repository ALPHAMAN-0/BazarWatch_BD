"""Configuration for BazarWatch BD.

Holds the immutable vocabulary of the app (units, categories, alert levels, roles),
the starter markets and product catalogue, the default settings, and the paths of
the data files.  Every path is resolved relative to this file so the app runs from
any working folder.
"""

from pathlib import Path
from typing import TypedDict

# --- Paths -------------------------------------------------------------------
# BASE_DIR is the folder holding this file; data/ and reports/ sit next to it.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

PRODUCTS_FILE = DATA_DIR / "products.json"
RECORDS_FILE = DATA_DIR / "price_records.csv"
USERS_FILE = DATA_DIR / "users.json"
BASKETS_FILE = DATA_DIR / "baskets.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ERROR_LOG_FILE = DATA_DIR / "error.log"

# --- Vocabulary (tuples) ----------------------------------------------------
UNITS = ("kg", "litre", "hali", "piece", "dozen")
CATEGORIES = (
    "Grains",
    "Pulses",
    "Oil",
    "Grocery",
    "Vegetables",
    "Spices",
    "Protein",
)
ALERT_LEVELS = ("Normal", "Watch", "Spike")
ROLES = ("admin", "member")

# --- Limits -----------------------------------------------------------------
MAX_PRICE = 100000.0
MIN_PRICE = 0.01
MAX_QUANTITY = 100000.0
MAX_BUDGET = 10000000.0
MAX_USERNAME_LENGTH = 32
MAX_PRODUCT_ID_LENGTH = 16
MIN_PASSWORD_LENGTH = 6

# Threshold bounds used by validators.validate_threshold.
Z_THRESHOLD_RANGE = (0.5, 5.0)
PCT_THRESHOLD_RANGE = (1.0, 200.0)
MIN_HISTORY_RANGE = (2, 50)
RECENT_DAYS_RANGE = (1, 90)

# How a basket total is compared with the weekly budget: up to
# BUDGET_CLOSE_PERCENT of the budget is "Within budget", up to
# BUDGET_FULL_PERCENT is "Close to budget", and above that is over.
BUDGET_CLOSE_PERCENT = 90
BUDGET_FULL_PERCENT = 100

# --- Starter data -----------------------------------------------------------
DEFAULT_MARKETS = (
    "Karwan Bazar",
    "Mohammadpur Krishi Market",
    "Shwapno",
)


class ProductEntry(TypedDict):
    """One entry of the starter product catalogue."""

    product_id: str
    name: str
    name_bn: str
    unit: str
    category: str
    reference_price: float | None
    perishable: bool


# The product catalogue.  Reference prices start empty: the Admin fills them in
# from the Trading Corporation of Bangladesh daily market price list.
DEFAULT_PRODUCTS: tuple[ProductEntry, ...] = (
    {
        "product_id": "RICE",
        "name": "Coarse rice",
        "name_bn": "মোটা চাল",
        "unit": "kg",
        "category": "Grains",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "ATTA",
        "name": "Atta (loose)",
        "name_bn": "খোলা আটা",
        "unit": "kg",
        "category": "Grains",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "DAL",
        "name": "Masoor dal (coarse)",
        "name_bn": "মসুর ডাল",
        "unit": "kg",
        "category": "Pulses",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "OIL",
        "name": "Soybean oil (bottled)",
        "name_bn": "সয়াবিন তেল",
        "unit": "litre",
        "category": "Oil",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "SUGAR",
        "name": "Sugar",
        "name_bn": "চিনি",
        "unit": "kg",
        "category": "Grocery",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "ONION",
        "name": "Onion (local)",
        "name_bn": "দেশি পেঁয়াজ",
        "unit": "kg",
        "category": "Vegetables",
        "reference_price": None,
        "perishable": True,
    },
    {
        "product_id": "POTATO",
        "name": "Potato",
        "name_bn": "আলু",
        "unit": "kg",
        "category": "Vegetables",
        "reference_price": None,
        "perishable": True,
    },
    {
        "product_id": "GARLIC",
        "name": "Garlic (local)",
        "name_bn": "দেশি রসুন",
        "unit": "kg",
        "category": "Spices",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "CHILLI",
        "name": "Green chilli",
        "name_bn": "কাঁচা মরিচ",
        "unit": "kg",
        "category": "Vegetables",
        "reference_price": None,
        "perishable": True,
    },
    {
        "product_id": "EGG",
        "name": "Egg (farm)",
        "name_bn": "ফার্মের ডিম",
        "unit": "hali",
        "category": "Protein",
        "reference_price": None,
        "perishable": False,
    },
    {
        "product_id": "CHICKEN",
        "name": "Broiler chicken",
        "name_bn": "ব্রয়লার মুরগি",
        "unit": "kg",
        "category": "Protein",
        "reference_price": None,
        "perishable": True,
    },
    {
        "product_id": "PANGAS",
        "name": "Pangas fish",
        "name_bn": "পাঙাশ মাছ",
        "unit": "kg",
        "category": "Protein",
        "reference_price": None,
        "perishable": True,
    },
)

# --- Default settings -------------------------------------------------------
DEFAULT_SETTINGS = {
    "markets": list(DEFAULT_MARKETS),
    "z_threshold": 2.0,
    "pct_threshold": 15.0,
    "perishable_z_threshold": 2.5,
    "perishable_pct_threshold": 25.0,
    "min_history": 5,
    "recent_days": 14,
    "show_bangla_names": True,
}
