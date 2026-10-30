"""The application manager for BazarWatch BD.

:class:`BazarManager` holds all the data and is the only thing the GUI talks
to.  Every permission rule from plan section 3 is enforced here by raising
:class:`~validators.PermissionDeniedError` — the GUI merely hides the buttons
that would fail.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import config
from analytics import alert_level
from auth import hash_password, verify_password
from models import Admin, PerishableProduct, PriceRecord, Product, User
from storage import Storage
from validators import (
    AuthError,
    DuplicateIDError,
    PermissionDeniedError,
    RecordNotFoundError,
    ValidationError,
    validate_budget,
    validate_date,
    validate_market_name,
    validate_password,
    validate_price,
    validate_product_id,
    validate_quantity,
    validate_reference_price,
    validate_threshold,
    validate_username,
)


class BazarManager:
    """Holds every record and enforces the rules of the app."""

    def __init__(self, data_dir=None):
        self.storage = Storage(data_dir or config.DATA_DIR)
        self.storage.clear_warnings()

        self.products: dict[str, Product] = {}
        self.records: list[PriceRecord] = []
        self.users: dict[str, User] = {}
        self.baskets: dict[str, dict] = {}
        self.settings: dict = {}

        self.current_user: User | None = None
        self._next_record_number = 1

        self.reload()

    # -- loading and saving -------------------------------------------------
    def reload(self) -> None:
        """Re-read every file from disk (File -> Reload data)."""
        self.storage.clear_warnings()
        self.products = {p.product_id: p for p in self.storage.load_products()}
        self.users = {u.username: u for u in self.storage.load_users()}
        self.baskets = self.storage.load_baskets()
        self.settings = self.storage.load_settings()
        self.records = self.storage.load_records(set(self.products.keys()))
        self._sync_next_record_number()

    def save_all(self) -> None:
        """Write every file back to disk."""
        self.storage.save_products(list(self.products.values()))
        self.storage.save_users(list(self.users.values()))
        self.storage.save_baskets(self.baskets)
        self.storage.save_settings(self.settings)
        self.storage.save_records(self.records)

    def _sync_next_record_number(self) -> None:
        """Continue the R00001 record numbering after the highest existing ID."""
        highest = 0
        for record in self.records:
            digits = record.record_id[1:] if record.record_id.startswith("R") else ""
            if digits.isdigit():
                highest = max(highest, int(digits))
        self._next_record_number = highest + 1

    @property
    def startup_warnings(self) -> list[str]:
        """Problems found while loading the data files."""
        return list(self.storage.warnings)

    @property
    def user_count(self) -> int:
        """How many accounts exist."""
        return len(self.users)

    # -- permission helpers -------------------------------------------------
    def _require_login(self) -> User:
        if self.current_user is None:
            raise PermissionDeniedError("Please log in first.")
        return self.current_user

    def _require_admin(self) -> User:
        user = self._require_login()
        if not user.can_manage():
            raise PermissionDeniedError("Only an Admin can do that.")
        return user

    def _require_owner(self, basket_owner: str) -> User:
        """Allow a user to touch only their own basket."""
        user = self._require_login()
        if user.username != basket_owner and not user.can_manage():
            raise PermissionDeniedError("You can only change your own basket.")
        return user

    # -- first run and login ------------------------------------------------
    def needs_admin_setup(self) -> bool:
        """True on a fresh install, before the first Admin exists."""
        return not self.users

    def create_admin(self, username: str, password: str) -> Admin:
        """Create the very first Admin.  Allowed only when there are no users."""
        if self.users:
            raise ValidationError(
                "An Admin already exists. Add members from the Admin tab instead."
            )
        username = validate_username(username)
        password = validate_password(password)
        salt, password_hash = hash_password(password)
        admin = Admin(
            username=username,
            role="admin",
            salt=salt,
            password_hash=password_hash,
            created_at=datetime.now().isoformat(timespec="seconds"),
            last_login=None,
        )
        self.users[username] = admin
        self.save_all()
        return admin

    def login(self, username: str, password: str) -> User:
        """Check the credentials and make the user current."""
        username = (username or "").strip()
        user = self.users.get(username)
        if user is None:
            # Same message for an unknown user and a wrong password, so the
            # screen does not reveal which usernames exist.
            raise AuthError("Wrong username or password.")
        if not verify_password(password, user.salt, user.password_hash):
            raise AuthError("Wrong username or password.")
        user.last_login = datetime.now().isoformat(timespec="seconds")
        self.current_user = user
        self.save_all()
        return user

    def logout(self) -> None:
        """Sign the current user out."""
        self.current_user = None

    # -- users --------------------------------------------------------------
    def add_member(self, username: str, password: str) -> User:
        """Add a member account.  Admin only."""
        self._require_admin()
        username = validate_username(username)
        password = validate_password(password)
        if self._username_exists(username):
            raise DuplicateIDError(f"The username '{username}' is already taken.")
        salt, password_hash = hash_password(password)
        member = User(
            username=username,
            role="member",
            salt=salt,
            password_hash=password_hash,
            created_at=datetime.now().isoformat(timespec="seconds"),
            last_login=None,
        )
        self.users[username] = member
        self.save_all()
        return member

    def _username_exists(self, username: str) -> bool:
        """Username check that ignores case, so 'Rafi' and 'rafi' collide."""
        lowered = username.lower()
        return any(name.lower() == lowered for name in self.users)

    def remove_member(self, username: str) -> None:
        """Remove a member, keeping their price records.  Admin only."""
        admin = self._require_admin()
        if username not in self.users:
            raise RecordNotFoundError(f"No user called '{username}'.")
        if username == admin.username:
            raise ValidationError("You cannot remove your own account.")
        if self.users[username].role == "admin":
            raise ValidationError("An Admin account cannot be removed.")
        del self.users[username]
        # Their price records stay, so the price history is not lost, but
        # their basket goes with the account.
        self.baskets.pop(username, None)
        self.save_all()

    def reset_password(self, username: str, new_password: str) -> None:
        """Set a new password for a user.  Admin only."""
        self._require_admin()
        if username not in self.users:
            raise RecordNotFoundError(f"No user called '{username}'.")
        new_password = validate_password(new_password)
        salt, password_hash = hash_password(new_password)
        self.users[username].salt = salt
        self.users[username].password_hash = password_hash
        self.save_all()

    def change_password(
        self, username: str, old_password: str, new_password: str
    ) -> None:
        """Change a password.  A user may change their own; an Admin may change any."""
        user = self._require_login()
        target = self.users.get(username)
        if target is None:
            raise RecordNotFoundError(f"No user called '{username}'.")
        if user.username != username and not user.can_manage():
            raise PermissionDeniedError("You can only change your own password.")
        if not verify_password(old_password, target.salt, target.password_hash):
            raise AuthError("The current password is wrong.")
        new_password = validate_password(new_password)
        salt, password_hash = hash_password(new_password)
        target.salt = salt
        target.password_hash = password_hash
        self.save_all()

    def list_users(self) -> list[User]:
        """All accounts.  Admin only."""
        self._require_admin()
        return sorted(self.users.values(), key=lambda u: u.username.lower())

    def records_per_user(self) -> dict[str, int]:
        """How many records each username has logged."""
        counts: dict[str, int] = dict.fromkeys(self.users, 0)
        for record in self.records:
            counts[record.added_by] = counts.get(record.added_by, 0) + 1
        return counts

    # -- products -----------------------------------------------------------
    def add_product(
        self,
        product_id: str,
        name: str,
        name_bn: str,
        unit: str,
        category: str,
        reference_price=None,
        perishable: bool = False,
    ) -> Product:
        """Add a product to the catalogue.  Admin only."""
        self._require_admin()
        # The duplicate check runs before the format check, so a lowercase
        # repeat of an existing ID reports "already used" rather than a
        # confusing format error.
        if product_id and self._product_id_exists(str(product_id).strip()):
            raise DuplicateIDError(
                f"The product ID '{str(product_id).strip()}' is already used."
            )
        product_id = validate_product_id(product_id)
        if not name or not str(name).strip():
            raise ValidationError("Product name is required.")
        reference = validate_reference_price(reference_price)
        product_cls = PerishableProduct if perishable else Product
        product = product_cls(
            product_id=product_id,
            name=str(name).strip(),
            name_bn=(name_bn or "").strip(),
            unit=unit or "kg",
            category=category or "",
            reference_price=reference,
        )
        self.products[product_id] = product
        self.save_all()
        return product

    def _product_id_exists(self, product_id: str) -> bool:
        """Product ID check that ignores case, so 'rice' and 'RICE' collide."""
        lowered = product_id.lower()
        return any(pid.lower() == lowered for pid in self.products)

    def update_product(self, product_id: str, **changes) -> Product:
        """Edit a product's details.  Admin only."""
        self._require_admin()
        product = self.get_product(product_id)
        if "name" in changes:
            if not changes["name"] or not str(changes["name"]).strip():
                raise ValidationError("Product name is required.")
            product.name = str(changes["name"]).strip()
        if "name_bn" in changes:
            product.name_bn = (changes["name_bn"] or "").strip()
        if "unit" in changes:
            product.unit = changes["unit"] or product.unit
        if "category" in changes:
            product.category = changes["category"] or product.category
        if "reference_price" in changes:
            product.reference_price = validate_reference_price(changes["reference_price"])
        if "perishable" in changes:
            # Rebuild so the class (and therefore the thresholds) matches.
            self.products[product.product_id] = self._build_product(
                product, perishable=bool(changes["perishable"])
            )
        self.save_all()
        return self.products[product.product_id]

    @staticmethod
    def _build_product(product: Product, perishable: bool) -> Product:
        product_cls = PerishableProduct if perishable else Product
        return product_cls(
            product_id=product.product_id,
            name=product.name,
            name_bn=product.name_bn,
            unit=product.unit,
            category=product.category,
            reference_price=product.reference_price,
        )

    def set_reference_price(self, product_id: str, reference_price) -> Product:
        """Set or clear a product's official reference price.  Admin only."""
        self._require_admin()
        product = self.get_product(product_id)
        product.reference_price = validate_reference_price(reference_price)
        self.save_all()
        return product

    def get_product(self, product_id: str) -> Product:
        """Look up a product, or raise RecordNotFoundError."""
        product = self.products.get(product_id)
        if product is None:
            raise RecordNotFoundError(f"No product called '{product_id}'.")
        return product

    def remove_product(self, product_id: str) -> None:
        """Delete a product.  Admin only.  Refused while records exist."""
        self._require_admin()
        self.get_product(product_id)
        if any(r.product_id == product_id for r in self.records):
            raise ValidationError(
                f"'{product_id}' still has price records, so it cannot be deleted."
            )
        del self.products[product_id]
        self.save_all()

    def products_missing_reference_price(self) -> list[Product]:
        """Products that have no official reference price yet."""
        return [p for p in self.products.values() if p.reference_price is None]

    # -- markets ------------------------------------------------------------
    def add_market(self, name: str) -> str:
        """Add a market.  Admin only."""
        self._require_admin()
        name = validate_market_name(name)
        if self._market_exists(name):
            raise DuplicateIDError(f"The market '{name}' already exists.")
        self.settings["markets"].append(name)
        self.save_all()
        return name

    def _market_exists(self, name: str) -> bool:
        """Market check that ignores case and surrounding spaces."""
        lowered = name.strip().lower()
        return any(m.strip().lower() == lowered for m in self.settings["markets"])

    def remove_market(self, name: str) -> None:
        """Remove a market.  Admin only.  Refused while records exist."""
        self._require_admin()
        if not self._market_exists(name):
            raise RecordNotFoundError(f"No market called '{name}'.")
        if any(r.market == name for r in self.records):
            raise ValidationError(
                f"'{name}' still has price records, so it cannot be removed."
            )
        self.settings["markets"] = [m for m in self.settings["markets"] if m != name]
        self.save_all()

    def markets(self) -> list[str]:
        """The list of markets."""
        return list(self.settings["markets"])

    # -- price records ------------------------------------------------------
    def add_record(
        self, product_id: str, market: str, record_date, price
    ) -> PriceRecord:
        """Log a new price.  Any logged-in user may do this."""
        user = self._require_login()
        product = self.get_product(product_id)
        if not self._market_exists(market):
            raise ValidationError(f"'{market}' is not a known market.")
        parsed_date = validate_date(record_date)
        price_value = validate_price(price)

        date_text = parsed_date.isoformat()
        for existing in self.records:
            if existing.key() == (product.product_id, market, date_text, user.username):
                raise DuplicateIDError(
                    f"You already logged {product.name} at {market} on {date_text}."
                )

        record = PriceRecord(
            record_id=f"R{self._next_record_number:05d}",
            product_id=product.product_id,
            market=market,
            date=date_text,
            price=price_value,
            added_by=user.username,
        )
        self._next_record_number += 1
        self.records.append(record)
        self.save_all()
        return record

    def get_record(self, record_id: str) -> PriceRecord:
        """Look up a record by ID, or raise RecordNotFoundError."""
        for record in self.records:
            if record.record_id == record_id:
                return record
        raise RecordNotFoundError(f"No record with ID '{record_id}'.")

    def update_record(self, record_id: str, **changes) -> PriceRecord:
        """Edit a record.  A member may edit their own; an Admin may edit any."""
        user = self._require_login()
        record = self.get_record(record_id)
        if not user.can_edit(record):
            raise PermissionDeniedError("You can only edit your own price records.")

        # Every value is checked before anything is changed, so a
        # refused edit leaves the record exactly as it was.
        new_price = (
            validate_price(changes["price"]) if "price" in changes else record.price
        )
        if "market" in changes:
            if not self._market_exists(changes["market"]):
                raise ValidationError(f"'{changes['market']}' is not a known market.")
            new_market = changes["market"]
        else:
            new_market = record.market
        if "date" in changes:
            new_date = validate_date(changes["date"]).isoformat()
        else:
            new_date = record.date
        if "product_id" in changes:
            product = self.get_product(changes["product_id"])
            new_product_id = product.product_id
        else:
            new_product_id = record.product_id

        # The date, market or product may have changed, so the same-day
        # duplicate rule has to be checked again.
        candidate = PriceRecord(
            record.record_id,
            new_product_id,
            new_market,
            new_date,
            new_price,
            record.added_by,
        )
        duplicate = self._find_duplicate(candidate, ignore_id=record.record_id)
        if duplicate is not None:
            raise DuplicateIDError(
                "Another record already covers that product, market and date."
            )

        record.product_id = new_product_id
        record.market = new_market
        record.date = new_date
        record.price = new_price
        self.save_all()
        return record

    def _find_duplicate(
        self, record: PriceRecord, ignore_id: str | None = None
    ) -> PriceRecord | None:
        """Find another record with the same product, market, date and user.

        ``ignore_id`` names a record that must not count as a duplicate --
        the record being edited, for example, which is compared against a
        throwaway candidate rather than against itself.
        """
        for other in self.records:
            if ignore_id is not None and other.record_id == ignore_id:
                continue
            if other.key() == record.key():
                return other
        return None

    def delete_record(self, record_id: str) -> None:
        """Delete a record.  Admin only."""
        self._require_admin()
        record = self.get_record(record_id)
        self.records.remove(record)
        self.save_all()

    def filter_records(
        self,
        product_id: str | None = None,
        market: str | None = None,
        added_by: str | None = None,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        level: str | None = None,
    ) -> list[PriceRecord]:
        """Filter the records.  Every argument is optional; empty means 'all'."""
        results = self.records
        if product_id:
            results = [r for r in results if r.product_id == product_id]
        if market:
            results = [r for r in results if r.market == market]
        if added_by:
            results = [r for r in results if r.added_by == added_by]
        if date_from:
            results = [r for r in results if r.date >= date_from]
        if date_to:
            results = [r for r in results if r.date <= date_to]
        if search:
            needle = search.strip().lower()
            if needle:
                results = [
                    r
                    for r in results
                    if needle in self._searchable_text(r)
                ]
        if level:
            results = [r for r in results if self.alert_level_for(r)[0] == level]
        return list(results)

    def _searchable_text(self, record: PriceRecord) -> str:
        """The text a free-text search looks at."""
        product = self.products.get(record.product_id)
        name = product.name if product else ""
        name_bn = product.name_bn if product else ""
        return " ".join(
            [record.record_id, record.product_id, name, name_bn, record.market,
             record.added_by, str(record.price)]
        ).lower()

    # -- baskets ------------------------------------------------------------
    def get_basket(self, username: str) -> dict:
        """One user's basket and budget."""
        basket = self.baskets.setdefault(username, {"budget": 0.0, "items": {}})
        return basket

    def set_basket_item(self, username: str, product_id: str, quantity) -> None:
        """Set (or replace) the quantity of a product in a basket."""
        self._require_owner(username)
        product = self.get_product(product_id)
        quantity_value = validate_quantity(quantity)
        basket = self.get_basket(username)
        basket["items"][product.product_id] = quantity_value
        self.save_all()

    def remove_basket_item(self, username: str, product_id: str) -> None:
        """Take a product out of a basket."""
        self._require_owner(username)
        basket = self.get_basket(username)
        basket["items"].pop(product_id, None)
        self.save_all()

    def set_budget(self, username: str, budget) -> None:
        """Set a user's weekly budget in Tk."""
        self._require_owner(username)
        basket = self.get_basket(username)
        basket["budget"] = validate_budget(budget)
        self.save_all()

    def clear_basket(self, username: str) -> None:
        """Empty a basket without touching the budget."""
        self._require_owner(username)
        basket = self.get_basket(username)
        basket["items"] = {}
        self.save_all()

    # -- settings -----------------------------------------------------------
    def update_settings(self, changes: dict) -> dict:
        """Change the alert thresholds and options.  Admin only."""
        self._require_admin()
        for key, value in changes.items():
            if key == "show_bangla_names":
                self.settings["show_bangla_names"] = bool(value)
            elif key == "markets":
                if not isinstance(value, list) or not value:
                    raise ValidationError("At least one market is required.")
                self.settings["markets"] = list(value)
            else:
                self.settings[key] = validate_threshold(key, value)
        self.save_all()
        return self.settings

    def show_bangla_names(self) -> bool:
        """Whether Bangla product names should be shown."""
        return bool(self.settings.get("show_bangla_names", True))

    # -- summaries ----------------------------------------------------------
    def dashboard_summary(self) -> dict:
        """The headline numbers for the dashboard."""
        user = self._require_login()
        today = date.today().isoformat()
        week_start = (date.today() - _days(6)).isoformat()
        my_records = [r for r in self.records if r.added_by == user.username]
        return {
            "products": len(self.products),
            "markets": len(self.settings["markets"]),
            "records": len(self.records),
            "my_records": len(my_records),
            "week_start": week_start,
            "today": today,
        }

    def products_not_priced_today(self) -> list[Product]:
        """Products with no record dated today."""
        today = date.today().isoformat()
        priced = {r.product_id for r in self.records if r.date == today}
        return [p for p in self.products.values() if p.product_id not in priced]

    def alert_level_for(self, record: PriceRecord):
        """The alert level of a record.  Implemented in analytics."""
        return alert_level(record, self.records, self.products, self.settings)


def _days(count: int):
    """A timedelta of ``count`` days (kept in one place for readability)."""
    return timedelta(days=count)
