# BazarWatch BD

A household price tracker and basket optimiser for everyday essentials in Bangladesh.
Log what you paid at the market, see when a price is unusually high, and work out the
cheapest place to buy your weekly basket.

Built with Python and Tkinter, with NumPy for the statistics.

> **The bundled sample data is illustrative, not real market prices.** It is generated
> by `generate_sample_data.py` so the app has something to show on the first run. Enter
> your own prices, and the reference prices from TCB, to get real results.

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

The app runs from any working directory: the `data/` and `reports/` folders are found
relative to `main.py`.

The repository includes the sample data in `data/`. The cheapest market and the basket
only use prices from the last 14 days, so refresh the sample before a demo or a
submission. This replaces everything in `data/`, including any prices you have entered:

```bash
python generate_sample_data.py --force
```

### Demo accounts

The sample-data generator creates these users. **They are for the demo only.**

| Username | Password   | Role   |
|----------|------------|--------|
| `admin`  | `admin123` | Admin  |
| `rafi`   | `rafi123`  | Member |
| `sadia`  | `sadia123` | Member |
| `tanvir` | `tanvir123`| Member |

On a brand new install with no `data/` folder, the app asks you to create the first
Admin account instead of showing the login screen.

---

## What it does

### Log a price
Pick a product, a market and a date, type the price, and save. The app immediately tells
you whether the price is **Normal**, a **Watch** or a **Spike**.

The product dropdown carries the product ID in brackets — `Rice (চাল) [RICE1]` — so two
products that share a name can still be told apart.

### Search and filter records
The Records tab searches across the product, market and date, and filters by product,
market, who logged the price, alert level, and a date range. Records can be edited by
the member who logged them and deleted by an Admin.

### Statistics and alerts
Per product: count, mean, median, min, max, standard deviation, the reference price and
the latest price. The Spike/Watch list shows every record that needs attention.

### Cheapest market and basket planning
For each product the app finds the cheapest market over the last 14 days. Your basket
gets a shopping plan: the best single market, the split plan that puts each item at its
own cheapest market, how much the split saves, and how you stand against your weekly
budget.

### Weekly report
A plain-text report with the summary, records grouped by market, average price and change
per product, the cheapest market per product, the Spike/Watch list, and the products that
were not priced this week. Save it to `reports/weekly_report_YYYY-MM-DD.txt`.

### Admin tab
Manage users, products, markets and the alert thresholds. Only an Admin sees this tab,
and the same check runs inside the manager, not just in the interface.

A product, market or setting changed here reaches the other tabs straight away, so the
Log Price and basket dropdowns never offer a stale list.

---

## How the alerts work

For a record, the **history** is every price of the same product dated on or before the
record, excluding the record itself.

- **z-score** `z = (price - mean(history)) / std(history)`, used only when there are at
  least `min_history` prices and the standard deviation is not zero.
- **percent over reference** `(price - reference) / reference × 100`, used only when a
  reference price has been set.

| Level   | Meaning                                                     |
|---------|-------------------------------------------------------------|
| `Spike` | Both rules fire.                                            |
| `Watch` | Exactly one rule fires.                                     |
| `Normal`| Neither rule fires.                                         |

Perishable products (onion, potato, chilli, chicken, pangas) use looser limits than the
others (2.5 SD and 25% instead of 2.0 SD and 15%), because their prices move around
more. An Admin can change the
thresholds, the minimum history length and the recent-days window under **Admin →
Settings**.

Reference prices start out empty, so the percent rule stays switched off until you fill
them in.

---

## Roles and permissions

| Action                              | Admin | Member |
|-------------------------------------|-------|--------|
| Log a price                         | yes   | yes    |
| Edit a price record                 | yes   | only their own |
| Delete a price record               | yes   | no     |
| Manage users, products and markets  | yes   | no     |
| Change the alert thresholds         | yes   | no     |
| See their own basket and budget     | yes   | yes    |

Every one of these is enforced in `BazarManager`, so it holds even if the interface is
bypassed.

---

## The data files

All of them live in `data/` and are plain text you can read and edit.

| File               | What it holds                                        |
|--------------------|------------------------------------------------------|
| `products.json`    | The catalogue: id, name, Bangla name, unit, category, reference price, perishable flag |
| `price_records.csv`| Every price: id, product, market, date, price, who logged it |
| `users.json`       | Usernames, roles and salted password hashes          |
| `baskets.json`     | Each user's basket items and weekly budget           |
| `settings.json`    | The alert thresholds and display options             |

Writes are safe: the app writes a temporary file and then renames it over the old one,
so an interrupted save cannot leave a half-written file behind. If a JSON file is
corrupted, or any data file cannot be read, it is moved aside as
`<name>.corrupt-<timestamp>` and the app starts with defaults, telling you what happened
instead of crashing.

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a random salt, and are compared
with `hmac.compare_digest`.

---

## Running the tests

```bash
python -m unittest discover -s tests -v
```

454 tests. They all use temporary folders, so your real data is never touched. The
interface tests drive the real Tk widgets and are skipped automatically when there is no
display available (a headless CI machine).

There is also a script that checks the app against the project plan, section by section,
by driving the real interface:

```bash
python verify_plan.py
```

It reports `105 of 105 checks passed` when everything in the plan holds.

---

## Project layout

```
main.py                 entry point
config.py               paths, limits, thresholds, the default catalogue
models.py               Product, PerishableProduct, PriceRecord, User, Admin
validators.py           validation and the exception hierarchy
auth.py                 password hashing and verification
storage.py              reading and writing the data files safely
manager.py              the business rules and the permission checks
analytics.py            statistics, alerts, cheapest market, basket planning
reports.py              the weekly text report
generate_sample_data.py seeded demo data
gui/                    the tkinter interface
tests/                  the unittest suite
```

The core modules never import tkinter, so they can be tested without a display.

---

## Requirements

- Python 3.10 or newer (developed on Python 3.14 with Tk 9.0)
- Tk 8.6 or newer
- NumPy

On Debian or Ubuntu, install Tk with `sudo apt install python3-tk`.

---

## Notes for the report

- Section 10 of the report covers the future work that was deliberately left out:
  a price-index line chart, importing prices from the TCB website, moving-average
  trends, a console menu and an online multi-device version.
- The `docs/` folder holds the TDD evidence report for this project.
