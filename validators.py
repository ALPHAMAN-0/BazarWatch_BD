"""Input validation and the application's exception hierarchy.

Every check raises a :class:`BazarError` subclass, so the GUI can catch one
base class and show the message to the user without ever crashing.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import config


# --- Exceptions -------------------------------------------------------------
class BazarError(Exception):
    """Base class for every error the app raises on purpose."""


class ValidationError(BazarError):
    """A value is missing, malformed or out of range."""


class DuplicateIDError(BazarError):
    """An identifier is already in use."""


class RecordNotFoundError(BazarError):
    """The requested record, product, user or market does not exist."""


class AuthError(BazarError):
    """Wrong username or password."""


class PermissionDeniedError(BazarError):
    """The current role is not allowed to perform this action."""


# --- Helpers ----------------------------------------------------------------
def _to_number(value, field_name: str) -> float:
    """Convert to float or raise ValidationError with a readable message."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{field_name} must be a number")
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a number") from None


# --- Validators -------------------------------------------------------------
def validate_price(value) -> float:
    """A price in Tk per unit.  Must be a number, > 0 and <= 100000."""
    number = _to_number(value, "Price")
    if number < config.MIN_PRICE:
        raise ValidationError("Price must be greater than 0")
    if number > config.MAX_PRICE:
        raise ValidationError(f"Price must not be more than {int(config.MAX_PRICE)}")
    return number


def validate_quantity(value) -> float:
    """A basket quantity.  Must be a number and > 0."""
    number = _to_number(value, "Quantity")
    if number <= 0:
        raise ValidationError("Quantity must be greater than 0")
    if number > config.MAX_QUANTITY:
        raise ValidationError("Quantity is too large")
    return number


def validate_budget(value) -> float:
    """A weekly budget in Tk.  Must be a number and >= 0."""
    number = _to_number(value, "Budget")
    if number < 0:
        raise ValidationError("Budget cannot be negative")
    if number > config.MAX_BUDGET:
        raise ValidationError("Budget is too large")
    return number


def validate_date(value) -> date:
    """A date in YYYY-MM-DD form.  May not be in the future."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValidationError("Date is required")
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("Date must be in YYYY-MM-DD format") from None
    else:
        raise ValidationError("Date must be in YYYY-MM-DD format")

    if parsed > date.today():
        raise ValidationError("Date cannot be in the future")
    return parsed


def validate_date_filter(value) -> str:
    """A date used as a filter boundary.

    Only the format is checked: a filter may name a date in the future,
    because it is a bound and not a record.  The result is the date in
    YYYY-MM-DD form, so it can be compared with a record date as a string.
    """
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValidationError("Date must be in YYYY-MM-DD format")
    text = value.strip()
    if not text:
        raise ValidationError("Date is required")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValidationError("Date must be in YYYY-MM-DD format") from None


def validate_threshold(name: str, value) -> float:
    """Validate an Admin-editable threshold against its allowed range."""
    number = _to_number(value, "Value")
    ranges = {
        "z_threshold": config.Z_THRESHOLD_RANGE,
        "pct_threshold": config.PCT_THRESHOLD_RANGE,
        "perishable_z_threshold": config.Z_THRESHOLD_RANGE,
        "perishable_pct_threshold": config.PCT_THRESHOLD_RANGE,
        "min_history": config.MIN_HISTORY_RANGE,
        "recent_days": config.RECENT_DAYS_RANGE,
    }
    if name not in ranges:
        raise ValidationError(f"Unknown setting: {name}")
    low, high = ranges[name]
    if not low <= number <= high:
        raise ValidationError(f"{name} must be between {low} and {high}")
    # These two count something, so they are whole numbers.  Keeping them
    # as floats would write 5.0 into settings.json where 5 belongs.
    if name in config.COUNT_SETTINGS:
        return int(number)
    return number


def validate_password(value) -> str:
    """A password of at least 6 non-blank characters."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Password is required")
    if len(value) < config.MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters"
        )
    return value


def validate_username(value) -> str:
    """A username of letters, digits, dot, dash or underscore."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Username is required")
    username = value.strip()
    if len(username) > config.MAX_USERNAME_LENGTH:
        raise ValidationError(
            f"Username must be at most {config.MAX_USERNAME_LENGTH} characters"
        )
    if not re.fullmatch(r"[A-Za-z0-9._-]+", username):
        raise ValidationError(
            "Username may only contain letters, digits, dots, dashes and underscores"
        )
    return username


def validate_product_id(value) -> str:
    """A product ID: uppercase letters, digits and underscores."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Product ID is required")
    product_id = value.strip()
    if len(product_id) > config.MAX_PRODUCT_ID_LENGTH:
        raise ValidationError(
            f"Product ID must be at most {config.MAX_PRODUCT_ID_LENGTH} characters"
        )
    if not re.fullmatch(r"[A-Z0-9_]+", product_id):
        raise ValidationError(
            "Product ID may only contain uppercase letters, digits and underscores"
        )
    return product_id


def validate_market_name(value) -> str:
    """A market name: non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Market name is required")
    return value.strip()


def validate_reference_price(value) -> float | None:
    """A reference price, or None to clear it.  Must be > 0 when given."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    number = _to_number(value, "Reference price")
    if number <= 0:
        raise ValidationError("Reference price must be greater than 0")
    if number > config.MAX_PRICE:
        raise ValidationError(f"Reference price must not be more than {int(config.MAX_PRICE)}")
    return number
