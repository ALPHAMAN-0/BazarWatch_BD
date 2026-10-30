"""Generate the illustrative sample data for BazarWatch BD.

The data is **seeded**, so every run produces exactly the same records, and it
is **illustrative, not real market prices**.

Run it with:

    python generate_sample_data.py                 # writes into data/
    python generate_sample_data.py --force         # overwrite existing data
    python generate_sample_data.py --end-date 2026-10-30
    python generate_sample_data.py --data-dir /tmp/demo

One spike is planted on purpose: onion at Karwan Bazar on the last day, about
45% above its normal price.  It shows as Watch until the ONION reference price
is filled in, and as a Spike afterwards.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import config
import numpy as np
from auth import hash_password
from models import PerishableProduct, PriceRecord, Product, User
from storage import Storage

# The seed makes the generated data identical on every run.
SEED = 20261030

# How many weeks of history to generate.
WEEKS = 8

# The demo accounts.  The passwords are in the README and are demo only.
DEMO_USERS = (
    ("admin", "admin123", "admin"),
    ("rafi", "rafi123", "member"),
    ("sadia", "sadia123", "member"),
    ("tanvir", "tanvir123", "member"),
)

# A typical price for each product, used as the base of the generated prices.
# These are round illustrative numbers, not real market prices.
BASE_PRICES = {
    "RICE": 60.0,
    "ATTA": 70.0,
    "DAL": 130.0,
    "OIL": 190.0,
    "SUGAR": 140.0,
    "ONION": 40.0,
    "POTATO": 30.0,
    "GARLIC": 120.0,
    "CHILLI": 80.0,
    "EGG": 135.0,
    "CHICKEN": 220.0,
    "PANGAS": 380.0,
}

# Each market has its own price level.  Shwapno is a supermarket, so it is
# a little more expensive than the open-air markets.
MARKET_FACTORS = {
    "Karwan Bazar": 1.00,
    "Mohammadpur Krishi Market": 0.95,
    "Shwapno": 1.08,
}

# How noisy each product's price is.  Perishables move around much more.
NOISE = {
    "ONION": 0.12,
    "POTATO": 0.11,
    "CHILLI": 0.15,
    "CHICKEN": 0.09,
    "PANGAS": 0.08,
}

# The planted spike: this much above the normal onion price.
SPIKE_FACTOR = 1.45

# The spike is measured against the generated history rather than the base
# price, so it stays clearly above the noise whatever the random draw gives.
SPIKE_Z_HEADROOM = 2.8


def _drift(rng: random.Random, week_index: int) -> float:
    """A small weekly upward drift, plus a little wobble."""
    return 1.0 + 0.004 * week_index + rng.uniform(-0.015, 0.015)


def build_products() -> list[Product]:
    """The product catalogue for the sample data."""
    products = []
    for entry in config.DEFAULT_PRODUCTS:
        product_cls = PerishableProduct if entry["perishable"] else Product
        products.append(
            product_cls(
                product_id=entry["product_id"],
                name=entry["name"],
                name_bn=entry["name_bn"],
                unit=entry["unit"],
                category=entry["category"],
                # Reference prices stay empty: the Admin fills them in from
                # the TCB daily market price list.
                reference_price=None,
            )
        )
    return products


def build_records(rng: random.Random, end_date: date, markets: list[str]):
    """The sample price records, including the planted onion spike."""
    records: list[PriceRecord] = []
    counter = 0
    members = [name for name, _, role in DEMO_USERS if role == "member"]

    # The planted spike owns this slot, so the random part must not use it.
    spike_key = ("ONION", "Karwan Bazar", end_date.isoformat())

    for week_index in range(WEEKS):
        # Week 0 is the most recent week, so the dates run backwards.
        week_start = end_date - timedelta(days=7 * (week_index + 1) - 1)
        for product_id, base_price in BASE_PRICES.items():
            noise = NOISE.get(product_id, 0.05)
            # Not every product is priced in every market in every week.
            for market in markets:
                if rng.random() < 0.12:
                    continue
                factor = MARKET_FACTORS.get(market, 1.0)
                price = base_price * factor * _drift(rng, WEEKS - week_index)
                price *= 1.0 + rng.gauss(0, noise)
                price = round(price, 2)
                if price <= 0:
                    continue
                counter += 1
                day = week_start + timedelta(days=rng.randint(0, 6))
                if day > end_date:
                    day = end_date
                # Leave the planted spike's slot free.
                if (product_id, market, day.isoformat()) == spike_key:
                    day = day - timedelta(days=1)
                    if (product_id, market, day.isoformat()) == spike_key:
                        continue
                records.append(
                    PriceRecord(
                        record_id=f"R{counter:05d}",
                        product_id=product_id,
                        market=market,
                        date=day.isoformat(),
                        price=price,
                        added_by=rng.choice(members),
                    )
                )

    # -- the planted spike ------------------------------------------------
    # Onion at Karwan Bazar on the last day, clearly above the generated
    # onion history.  The price is worked out from the history that was
    # actually produced, so the spike is always well above the noise and the
    # alert demo works whatever the random draw gives.
    onion_history = [
        r.price for r in records
        if r.product_id == "ONION" and r.market == "Karwan Bazar"
    ]
    if onion_history:
        history_mean = sum(onion_history) / len(onion_history)
        history_std = (
            float(np.std(np.array(onion_history, dtype=float), ddof=1))
            if len(onion_history) > 1
            else 0.0
        )
    else:
        history_mean = BASE_PRICES["ONION"]
        history_std = 0.0

    spike_price = round(history_mean * SPIKE_FACTOR, 2)
    # Make sure the z-score clears the perishable limit of 2.5 even when the
    # generated history happens to be very wide.
    if history_std > 0:
        needed = history_mean + SPIKE_Z_HEADROOM * history_std
        spike_price = round(max(spike_price, needed), 2)

    counter += 1
    records.append(
        PriceRecord(
            record_id=f"R{counter:05d}",
            product_id="ONION",
            market="Karwan Bazar",
            date=end_date.isoformat(),
            price=spike_price,
            added_by=members[0],
        )
    )

    records.sort(key=lambda r: (r.date, r.record_id))
    # Renumber so the record IDs follow the date order.
    for index, record in enumerate(records, start=1):
        record.record_id = f"R{index:05d}"
    return records


def build_users():
    """The demo accounts, with hashed passwords."""
    users = []
    for username, password, role in DEMO_USERS:
        salt, password_hash = hash_password(password)
        users.append(
            {
                "username": username,
                "role": role,
                "salt": salt,
                "password_hash": password_hash,
                "created_at": date.today().isoformat(),
                "last_login": None,
            }
        )
    return users


def build_baskets(rng: random.Random, products: list[Product]) -> dict:
    """One basket per member."""
    baskets = {}
    product_ids = [p.product_id for p in products]
    for username, _, role in DEMO_USERS:
        if role != "member":
            continue
        items = {}
        for product_id in rng.sample(product_ids, 5):
            items[product_id] = round(rng.uniform(1, 4), 1)
        baskets[username] = {
            "budget": float(rng.choice([800, 1000, 1200, 1500])),
            "items": items,
        }
    return baskets


def generate(data_dir=None, end_date=None, force=False, quiet=False) -> Path:
    """Write the sample data into ``data_dir``.

    Refuses to overwrite existing data unless ``force`` is True.
    """
    if data_dir is None:
        data_dir = config.DATA_DIR
    if end_date is None:
        end_date = date.today()

    data_dir = Path(data_dir)
    existing = [
        data_dir / name
        for name in (
            "products.json",
            "price_records.csv",
            "users.json",
            "baskets.json",
            "settings.json",
        )
        if (data_dir / name).exists()
    ]
    if existing and not force:
        names = ", ".join(path.name for path in existing)
        raise SystemExit(
            f"Refusing to overwrite existing data ({names}).\n"
            f"Run again with --force to replace it."
        )

    rng = random.Random(SEED)
    storage = Storage(data_dir)
    products = build_products()
    markets = list(config.DEFAULT_MARKETS)
    records = build_records(rng, end_date, markets)
    users = build_users()
    baskets = build_baskets(rng, products)

    storage.save_products(products)
    storage.save_records(records)
    storage.save_users([User.from_dict(entry) for entry in users])
    storage.save_baskets(baskets)

    settings = dict(config.DEFAULT_SETTINGS)
    settings["markets"] = markets
    storage.save_settings(settings)

    if not quiet:
        print(f"Sample data written to {data_dir}")
        print(f"  products : {len(products)}")
        print(f"  markets  : {len(markets)}")
        print(f"  records  : {len(records)}")
        print(f"  users    : {len(users)}")
        print(f"  baskets  : {len(baskets)}")
        print(f"  end date : {end_date.isoformat()}")
        print(
            f"  planted spike: ONION at Karwan Bazar on {end_date.isoformat()} "
            f"(Tk {BASE_PRICES['ONION'] * SPIKE_FACTOR:.2f})"
        )
        print("  Data is illustrative, not real market prices.")
    return data_dir


def main(argv=None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        description="Generate the illustrative sample data for BazarWatch BD."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing data files",
    )
    parser.add_argument(
        "--end-date",
        help="the last day of the generated data (YYYY-MM-DD), default today",
    )
    parser.add_argument(
        "--data-dir",
        help="where to write the data, default the app's data/ folder",
    )
    args = parser.parse_args(argv)

    end_date = date.today()
    if args.end_date:
        try:
            end_date = date.fromisoformat(args.end_date)
        except ValueError:
            print("Error: --end-date must be in YYYY-MM-DD format.")
            return 1

    try:
        generate(args.data_dir, end_date, args.force)
    except SystemExit as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
