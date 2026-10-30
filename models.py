"""Data model for BazarWatch BD.

Four small classes plus two subclasses:

* ``Product`` / ``PerishableProduct`` — the catalogue.  ``PerishableProduct``
  overrides :meth:`Product.spike_thresholds` so the alert code never has to
  check the product type itself.
* ``PriceRecord`` — one logged price.
* ``User`` / ``Admin`` — accounts.  ``Admin`` overrides the permission methods.

The models are plain data holders; they never touch tkinter, so the whole
model layer is unit-testable without a display.
"""

from __future__ import annotations

import config


def _setting(settings: dict, key: str, default):
    """One setting, or its default when the setting is missing or unusable.

    A hand-edited settings file must not be able to crash the alert
    code, so a missing, null or non-numeric value falls back to the
    default.
    """
    value = settings.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class Product:
    """An item in the catalogue, e.g. onion."""

    def __init__(
        self,
        product_id: str,
        name: str,
        name_bn: str,
        unit: str,
        category: str,
        reference_price: float | None = None,
        perishable: bool = False,
    ):
        self.product_id = product_id
        self.name = name
        self.name_bn = name_bn
        self.unit = unit
        self.category = category
        self.reference_price = reference_price
        self.perishable = bool(perishable)

    # -- display ------------------------------------------------------------
    def display_name(self, show_bn: bool = True) -> str:
        """Name for the GUI.  Bangla is appended in brackets when available."""
        if show_bn and self.name_bn:
            return f"{self.name} ({self.name_bn})"
        return self.name

    # -- calculations -------------------------------------------------------
    def percent_over_reference(self, price: float) -> float | None:
        """How far ``price`` sits above the official reference price, in percent.

        Returns ``None`` when no usable reference price is set, because then
        the percentage rule cannot fire.
        """
        if not self.reference_price or self.reference_price <= 0:
            return None
        return (price - self.reference_price) / self.reference_price * 100

    def spike_thresholds(self, settings: dict) -> tuple[float, float]:
        """Return ``(z_limit, pct_limit)`` for this product.

        Normal products use the standard limits; :class:`PerishableProduct`
        overrides this method with the looser perishable limits.

        A setting that is missing falls back to its default, so a
        hand-edited settings file cannot crash the alert code.
        """
        return (
            float(_setting(settings, "z_threshold", config.DEFAULT_Z_THRESHOLD)),
            float(
                _setting(settings, "pct_threshold", config.DEFAULT_PCT_THRESHOLD)
            ),
        )

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "name_bn": self.name_bn,
            "unit": self.unit,
            "category": self.category,
            "reference_price": self.reference_price,
            "perishable": self.perishable,
        }

    def is_perishable(self) -> bool:
        return self.perishable

    @classmethod
    def from_dict(cls, data: dict) -> Product:
        """Rebuild a product, returning a PerishableProduct when flagged."""
        product_cls = PerishableProduct if data.get("perishable") else Product
        reference = data.get("reference_price")
        if reference is not None:
            reference = float(reference)
        return product_cls(
            product_id=data["product_id"],
            name=data.get("name", ""),
            name_bn=data.get("name_bn", ""),
            unit=data.get("unit", "kg"),
            category=data.get("category", ""),
            reference_price=reference,
            perishable=bool(data.get("perishable", False)),
        )

    def __eq__(self, other):
        if not isinstance(other, Product):
            return NotImplemented
        return self.product_id == other.product_id

    def __hash__(self):
        return hash(self.product_id)

    def __repr__(self):
        return f"{type(self).__name__}({self.product_id!r}, {self.name!r})"


class PerishableProduct(Product):
    """A product that spoils quickly, so it gets looser spike limits."""

    def __init__(
        self,
        product_id: str,
        name: str,
        name_bn: str,
        unit: str,
        category: str,
        reference_price: float | None = None,
        perishable: bool = True,
    ):
        super().__init__(
            product_id, name, name_bn, unit, category, reference_price, perishable=True
        )

    def spike_thresholds(self, settings: dict) -> tuple[float, float]:
        return (
            float(
                _setting(
                    settings,
                    "perishable_z_threshold",
                    config.DEFAULT_PERISHABLE_Z_THRESHOLD,
                )
            ),
            float(
                _setting(
                    settings,
                    "perishable_pct_threshold",
                    config.DEFAULT_PERISHABLE_PCT_THRESHOLD,
                )
            ),
        )

    def is_perishable(self) -> bool:
        return True


class PriceRecord:
    """One price logged for a product at a market on a date."""

    def __init__(
        self,
        record_id: str,
        product_id: str,
        market: str,
        date: str,
        price: float,
        added_by: str,
    ):
        self.record_id = record_id
        self.product_id = product_id
        self.market = market
        self.date = date
        self.price = float(price)
        self.added_by = added_by

    def key(self) -> tuple[str, str, str, str]:
        """Identity used for the same-day duplicate check.

        Two different users may log the same product/market/date; the same
        user may not do it twice.
        """
        return (self.product_id, self.market, self.date, self.added_by)

    def to_row(self) -> list:
        """Row layout for the CSV file."""
        return [
            self.record_id,
            self.product_id,
            self.market,
            self.date,
            self.price,
            self.added_by,
        ]

    @classmethod
    def from_row(cls, row: list) -> PriceRecord:
        return cls(
            record_id=row[0],
            product_id=row[1],
            market=row[2],
            date=row[3],
            price=float(row[4]),
            added_by=row[5],
        )

    def __eq__(self, other):
        if not isinstance(other, PriceRecord):
            return NotImplemented
        return self.record_id == other.record_id

    def __hash__(self):
        return hash(self.record_id)

    def __repr__(self):
        return (
            f"PriceRecord({self.record_id!r}, {self.product_id!r}, "
            f"{self.market!r}, {self.date!r}, {self.price!r}, {self.added_by!r})"
        )


class User:
    """A logged-in account.  Members may only edit their own records."""

    def __init__(
        self,
        username: str,
        role: str,
        salt: str,
        password_hash: str,
        created_at: str,
        last_login: str | None = None,
    ):
        self.username = username
        self.role = role
        self.salt = salt
        self.password_hash = password_hash
        self.created_at = created_at
        self.last_login = last_login

    # -- permissions --------------------------------------------------------
    def can_edit(self, record: PriceRecord) -> bool:
        """Members edit their own records only."""
        return record is not None and record.added_by == self.username

    def can_delete(self, record: PriceRecord) -> bool:
        """Members never delete."""
        return False

    def can_manage(self) -> bool:
        """Members never manage users, products, markets or settings."""
        return False

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "role": self.role,
            "salt": self.salt,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }

    @classmethod
    def from_dict(cls, data: dict) -> User:
        """Rebuild a user, returning an Admin when the role says admin."""
        user_cls = Admin if data.get("role") == "admin" else User
        return user_cls(
            username=data["username"],
            role=data.get("role", "member"),
            salt=data.get("salt", ""),
            password_hash=data.get("password_hash", ""),
            created_at=data.get("created_at", ""),
            last_login=data.get("last_login"),
        )

    def __eq__(self, other):
        if not isinstance(other, User):
            return NotImplemented
        return self.username == other.username

    def __hash__(self):
        return hash(self.username)

    def __repr__(self):
        return f"{type(self).__name__}({self.username!r}, {self.role!r})"


class Admin(User):
    """An administrator: may edit and delete any record and manage everything."""

    def can_edit(self, record: PriceRecord) -> bool:
        return True

    def can_delete(self, record: PriceRecord) -> bool:
        return True

    def can_manage(self) -> bool:
        return True
