# BazarWatch BD: Project Plan

Household price tracker and basket optimizer for everyday essentials (Python, Tkinter, NumPy).
CSC 4162 Programming in Python, AIUB, Fall 2026–27 midterm group project (40 marks).

## 1. Problem and users
- **Problem:** food prices keep rising, and households and students can't easily tell whether a price
  they paid was fair, or which market is cheapest. Evidence from earlier research (verify the sources
  before citing): BBS food inflation 7.22% in September 2026 (7.02% in August); government monitoring
  in March 2024 found potatoes at Tk 35–40/kg against a reference price of Tk 28.55.
- **Users:** a **student mess**. The mess manager is the Admin; members log prices when they shop.
  It also works for a family household.
- **What it does:** users record prices (product, market, date, price). The app compares each price with
  the item's history and with an official reference price (TCB), labels it Normal / Watch / Spike,
  shows the cheapest market for each product, and plans each user's weekly basket against a budget.
- **Responsible use:** stores only usernames, hashed passwords, roles and price data. No real names,
  phone numbers, emails or addresses. Sample data is generated and labelled illustrative.
- **PDF fit:** "price-comparison record system" in Personal finance and consumer awareness (§3);
  Hybrid application (§2).

## 2. Scope (deadline: within 1 week)
**In:** product catalogue and markets list · log price · search, filter, edit, delete records ·
per-product statistics · Spike / Watch / Normal alerts with Admin-editable thresholds ·
cheapest market · one basket + weekly budget per user · multi-user login (Admin + Member) ·
weekly text report · auto-save with safe writes · sample-data generator · unit tests · README.

**Out (future work, report section 10):** price-index line chart, TCB website auto-import,
moving-average trend, console menu, online multi-device version.

## 3. Roles and permissions
| Action | Member | Admin |
|---|---|---|
| Log a price | ✅ | ✅ |
| Edit a price record | Own records only | Any |
| Delete a price record | ❌ | ✅ |
| View records, statistics, alerts, cheapest market | ✅ | ✅ |
| Own basket + budget (add and remove own items) | ✅ | ✅ |
| Add / edit / delete products (incl. reference prices) | ❌ | ✅ |
| Add / remove markets | ❌ | ✅ |
| Change spike thresholds and settings | ❌ | ✅ |
| See all users (role, created, last login, records logged); add member, remove member, reset password | ❌ | ✅ |
| Change own password | ✅ | ✅ |

- No self sign-up. First run (no `users.json`) shows a "Create Admin account" screen.
- Permissions are enforced in `BazarManager` (raises `PermissionDeniedError`), not only hidden in the GUI.
- The Admin can't remove their own account, so an Admin always exists.
- A product or market that still has price records can't be deleted (clear message instead).
- Removing a member keeps their price records (history stays) and deletes their basket.

## 4. Starter data
**Markets** (`settings.json`, Admin can change): Karwan Bazar, Mohammadpur Krishi Market, Shwapno (supermarket).
Users pick markets and products from dropdowns, never free text, so typos can't split the data.

**Products** (Admin can change). **Reference prices start empty.** Fill them in later from TCB's daily
market price list via Admin → Products, and note the TCB list date for the report.

| ID | Name | Bangla name | Unit | Category | Perishable |
|---|---|---|---|---|---|
| RICE | Coarse rice | মোটা চাল | kg | Grains | |
| ATTA | Atta (loose) | খোলা আটা | kg | Grains | |
| DAL | Masoor dal (coarse) | মসুর ডাল | kg | Pulses | |
| OIL | Soybean oil (bottled) | সয়াবিন তেল | litre | Oil | |
| SUGAR | Sugar | চিনি | kg | Grocery | |
| ONION | Onion (local) | দেশি পেঁয়াজ | kg | Vegetables | ✅ |
| POTATO | Potato | আলু | kg | Vegetables | ✅ |
| GARLIC | Garlic (local) | দেশি রসুন | kg | Spices | |
| CHILLI | Green chilli | কাঁচা মরিচ | kg | Vegetables | ✅ |
| EGG | Egg (farm) | ফার্মের ডিম | hali | Protein | |
| CHICKEN | Broiler chicken | ব্রয়লার মুরগি | kg | Protein | ✅ |
| PANGAS | Pangas fish | পাঙাশ মাছ | kg | Protein | ✅ |

**Language:** screens in English; product names also show Bangla, e.g. "Onion (দেশি পেঁয়াজ)".
A `show_bangla_names` switch in Settings hides Bangla if a lab PC draws it broken.

## 5. Rules
**Alert level** of a price record:
- `history` = prices of the same product dated on or before this record, excluding the record itself.
- `z = (price − mean(history)) / std(history)` (sample std, `ddof=1`), only when
  `len(history) ≥ min_history` (default 5) and std > 0; otherwise there is no z.
- `pct = (price − reference) / reference × 100`, only when a reference price is set.
- `z_hit = z ≥ z_limit`, `ref_hit = pct ≥ pct_limit`.
- **Spike** if both are true · **Watch** if exactly one is true · **Normal** otherwise.
- Limits (Admin-editable in Settings): normal items 2.0 SD and 15%; perishables 2.5 SD and 25%.
  `PerishableProduct` overrides `spike_thresholds()`, so the alert code never checks the type.
- No reference price set: the most a record can reach is Watch, and the screen shows "ref not set".

**Cheapest market:** for each product, average each market's prices from the last `recent_days`
(default 14) up to today; the lowest average wins. Markets with no record in that window are skipped;
if none have data, show "no recent data".

**Basket (one per user, with a weekly budget):**
- Total per market = NumPy `dot(quantities, 14-day average prices)`, only for markets that have a recent
  price for every basket item (set intersection).
- Best single market = the lowest of those totals.
- Split plan = each item at its own cheapest market; saving = best single total − split total.
- Budget status: up to 90% "Within budget" · 90–100% "Close to budget" · over 100% "Over budget by Tk X".
- Items with no recent price anywhere are listed and left out of the totals.

**Weekly report:** the 7 days ending on a chosen date (default today) compared with the 7 days before:
record count by market, average price and % change per product, cheapest market, Spike/Watch list,
products not priced this week, top contributors. Saved as `reports/weekly_report_YYYY-MM-DD.txt`.

## 6. Project structure
```
BazarWatch_BD/
├── main.py                  # entry point: python main.py
├── config.py                # paths, tuples (UNITS, CATEGORIES, ALERT_LEVELS, ROLES), default settings and markets
├── models.py                # Product, PerishableProduct, PriceRecord, User, Admin
├── validators.py            # custom exceptions + input checks
├── auth.py                  # password hashing and checking (hashlib, hmac, os)
├── storage.py               # Storage class: JSON/CSV load, safe save, bad-row handling
├── analytics.py             # NumPy: stats, z-score, alert level, cheapest market, basket maths
├── reports.py               # weekly text report
├── manager.py               # BazarManager: CRUD, login, permissions, sets/dicts, summaries
├── gui/
│   ├── app.py               # main window, menu, login flow, tabs by role
│   ├── login_view.py        # login + first-run "Create Admin"
│   ├── dashboard_tab.py
│   ├── log_price_tab.py
│   ├── records_tab.py       # includes the edit dialog
│   ├── stats_tab.py         # statistics, alerts, weekly report
│   ├── basket_tab.py
│   ├── admin_tab.py         # Users, Products, Markets, Settings
│   └── widgets.py           # shared table, colour and error helpers
├── generate_sample_data.py  # seeded illustrative data
├── data/                    # products.json, price_records.csv, users.json, baskets.json, settings.json
├── reports/                 # generated weekly reports
├── tests/                   # unittest
├── requirements.txt         # numpy
├── README.md
└── plan.md
```
- Core modules never import tkinter, so they can be tested without the GUI.
- Target Python 3.10+ and Tk 8.6+ (developed on Python 3.14 / Tk 9.0, macOS) so teammates on Windows
  can run it. `data/` is found relative to the code, so the app works from any folder.

## 7. Classes
- **Product:** `product_id, name, name_bn, unit, category, reference_price (None until set)`.
  Methods: `display_name(show_bn)`, `percent_over_reference(price)`, `spike_thresholds(settings)` →
  `(z_limit, pct_limit)`, `to_dict()`, `from_dict()` (returns a `PerishableProduct` when perishable).
- **PerishableProduct(Product):** overrides `spike_thresholds()` to use the perishable limits.
- **PriceRecord:** `record_id (R00001…), product_id, market, date, price, added_by`.
  Methods: `key()` → `(product_id, market, date, added_by)`, `to_row()`, `from_row()`.
- **User:** `username, role, salt, password_hash, created_at, last_login`. Methods: `can_edit(record)`
  (own only), `can_delete(record)` → False, `can_manage()` → False, `to_dict()`, `from_dict()`
  (returns an `Admin` when the role is admin).
- **Admin(User):** overrides `can_edit`, `can_delete`, `can_manage` → True.
- **Storage:** the only class that reads and writes files; takes `data_dir`, so tests use a temp folder.
- **BazarManager:** holds all data; every GUI action calls it. Login/logout, create Admin, add/remove
  member, reset/change password, product and market CRUD, record add/update/delete, filter, statistics,
  alerts, cheapest markets, basket, settings, weekly report.

## 8. Data files (all UTF-8)
- `products.json`: list of `{product_id, name, name_bn, unit, category, reference_price, perishable}`
- `price_records.csv`: `record_id,product_id,market,date,price,added_by`
- `users.json`: list of `{username, role, salt, password_hash, created_at, last_login}`
- `baskets.json`: `{username: {budget, items: {product_id: quantity}}}`
- `settings.json`: `markets, z_threshold, pct_threshold, perishable_z_threshold, perishable_pct_threshold,
  min_history, recent_days, show_bangla_names`

File rules:
- Missing file → created with defaults.
- Corrupt JSON, or any data file that can't be read → renamed to `*.corrupt-<timestamp>`, defaults
  loaded, warning shown at startup.
- Bad CSV row (missing field, non-number price, bad date, unknown product, duplicate ID) → skipped and
  reported at startup, e.g. "Skipped 2 rows: line 14: price 'abc' is not a number".
- Safe save: write `file.tmp`, then `os.replace()`, so a crash mid-save never leaves a half-written file.
- Auto-save after every change; File → Reload data re-reads every file.
- Always `encoding="utf-8"` (Windows' default encoding would crash on Bangla).

## 9. Validation and exceptions
Custom exceptions in `validators.py`: `BazarError` (base) → `ValidationError`, `DuplicateIDError`,
`RecordNotFoundError`, `AuthError`, `PermissionDeniedError`.

| PDF §9 case | How it's handled |
|---|---|
| Invalid action | Forbidden buttons disabled for members, and the manager also raises `PermissionDeniedError`; dropdowns are read-only |
| Non-numeric input | Price, quantity, budget, thresholds → `ValidationError` ("Price must be a number") |
| Out-of-range value | Price ≤ 0 or > 100,000; date not `YYYY-MM-DD` or in the future; quantity ≤ 0; thresholds outside z 0.5–5.0, percent 1–200, min_history 2–50, recent_days 1–90; password under 6 characters |
| Duplicate identifier | Product ID, username, market name (case-insensitive), and the same product + market + date + user logged twice (checked with sets) |
| Record not found | Find, edit or delete with a missing ID → `RecordNotFoundError` |
| File error | Rules in section 8; a failed write (`PermissionError`/`OSError`) shows a message and the app keeps running |

In the GUI, every button handler catches `BazarError` and shows a message box. Any unexpected error shows
a friendly message and writes the traceback to `data/error.log` (logging). A user mistake never closes the app (FR-7).

## 10. Screens
Login (first run: Create Admin) → main window. Header: "Logged in as rafi (Member)", Change password,
Logout. Menu: File → Reload data, Generate weekly report, Exit.

| Tab | Who | Contents |
|---|---|---|
| Dashboard | All | Totals (products, markets, records, my records, this week's Spikes/Watches); cheapest market per product; not priced today; top contributors; Admin also sees products missing a reference price |
| Log Price | All | Product and market dropdowns, date (default today), price per unit; after saving, shows the alert level in colour with z and % |
| Records | All | Search + filters (product, market, user, level, date range); colour-coded table; Edit (own, or any for Admin); Delete (Admin, with confirmation) |
| Statistics & Alerts | All | Per-product stats (count, mean, median, min, max, std, reference, latest); Spike/Watch list; weekly report button + preview |
| My Basket | All | Add/remove items with quantity; budget; total per market; best single market; split plan and saving; budget status |
| Admin | Admin only | Users, Products, Markets, Settings sub-tabs |

Colours: Spike red, Watch amber, Normal plain. ttk "clam" theme (row colours also show on Windows).

## 11. Python concepts map (report sections 4–8)
- **Variables/types:** str IDs and names, float prices, int counts, `date`, bool `perishable`, `None` reference.
- **Operators:** % over reference, z-score, totals, saving, budget %, comparisons in validation.
- **Conditionals:** alert level `if/elif/else`, budget status, permission checks, validation.
- **Loops:** reading CSV rows, filtering, stats per product, building the report, sample data.
- **Functions:** validators, analytics, storage, reports, plus class methods (far more than 5).
- **List:** `manager.records`; price lists passed to NumPy; filter results.
- **Tuple:** `UNITS, CATEGORIES, ALERT_LEVELS, ROLES, DEFAULT_MARKETS`; `record.key()`;
  `alert_level()` returns `(level, z, pct)`; `cheapest_market()` returns `(market, average)`.
- **Set:** `record_ids`; `record_keys` (same-day duplicates); usernames;
  not priced today = `all_products − priced_today`; markets with every basket item = intersection;
  products missing a reference price.
- **Dict:** `products[id]`, `users[username]`, `baskets[username]`, `settings`, `history_by_product`,
  `market_avg[market]`, `records_per_user[username]`.
- **Files:** JSON, CSV, TXT (section 8). **Exceptions:** custom ones + `ValueError`, `FileNotFoundError`,
  `json.JSONDecodeError`, `KeyError`, `OSError`.
- **OOP:** 7 core classes, 2 inheritance pairs with method overriding.
- **NumPy:** mean, median, min, max, std, z-score, dot product for basket totals. The alert rule,
  filters, cheapest-market choice and permissions stay in plain Python, so the library doesn't hide the
  logic (PDF §10).
- **Standard library:** csv, json, os, datetime, hashlib, hmac, random, logging, pathlib. hashlib, hmac,
  logging and pathlib aren't in the PDF's example list, so mention them to the instructor.

## 12. Sample data (`generate_sample_data.py`)
- Seeded, so it gives the same data every run; refuses to overwrite existing data unless `--force`.
- 12 products, 3 markets, about 8 weeks ending today (or `--end-date`), about 250–300 records spread
  across 4 demo users (1 Admin, 3 Members), one basket per member.
- Price = illustrative typical price × market factor (Shwapno slightly higher) × small weekly drift ×
  random noise (perishables noisier).
- One planted spike: Onion at Karwan Bazar on the last day, about 45% above normal, so the alert demo
  always works. It shows **Watch** until ONION's reference price is entered, then **Spike**.
- Reference prices stay empty (you fill them from TCB later).
- Demo usernames and passwords are listed in the README (demo only).
- README and report label the sample data "illustrative, not real market prices".

## 13. Tests (`python -m unittest discover -s tests -v`)
About 20 tests, all using temp folders so real data is never touched:
- **validators:** empty, text, zero and negative prices rejected; bad and future dates rejected.
- **analytics:** Spike / Watch / Normal cases; no reference → at most Watch; fewer than `min_history`
  → no z; perishables use looser limits; cheapest market ignores records older than 14 days; basket
  totals, intersection, saving and budget status.
- **storage:** missing file created; malformed CSV rows skipped and reported; corrupt JSON backed up;
  save/load round trip.
- **manager:** Member can't delete (`PermissionDeniedError`); Member edits own but not others' records;
  Admin deletes; duplicate username, product ID and same-day record rejected; wrong password →
  `AuthError`; stored hash is never the plain password.

## 14. Build order (7 days)
| Day | Work | Done when |
|---|---|---|
| 1 | config, models, validators + tests | model and validator tests pass |
| 2 | storage, auth, manager (CRUD, login, permissions) + tests | data saves and reloads; permission tests pass |
| 3 | analytics, reports, sample-data generator + tests | stats/alert/basket tests pass; `data/` filled |
| 4 | GUI: login and first run, main window, Log Price, Records | can log, filter, edit and delete in the GUI |
| 5 | GUI: Dashboard, Statistics & Alerts, Basket, Admin; weekly report | every feature reachable from the GUI |
| 6 | Full test run, bug fixes, README, screenshots, report draft (10 sections) | all tests pass; report complete |
| 7 | Viva rehearsal | every member can explain every module |

Team split for 4 members (adjust to your team size): A models + manager + auth · B storage + validators
+ sample data · C analytics + reports + tests · D GUI + report. Everyone reads every module.

## 15. Git
- You commit and push yourselves; no automated commits or pushes.
- Suggested: one commit per finished module ("Add models and validators", …).
- `.gitignore`: `__pycache__/`, `*.pyc`, `*.tmp`, `data/error.log`, `.DS_Store`.
- The repo is public right now. Consider making it private until marks are out so other groups can't copy it.

## 16. Demo and viva prep
**Demo (about 5 minutes):**
1. Log in as Admin → Users tab (see members, last login) → Settings (thresholds).
2. Log out → log in as a Member → Log Price (a high onion price → alert) → Records filters → try Delete (blocked).
3. My Basket: best market, saving, budget status.
4. Statistics & Alerts → generate the weekly report → open the .txt file.
5. Close and reopen → data is still there. Rename a data file → the app recreates it or shows a warning.

**Every member must be able to explain:** the alert rule (z + %), why perishables differ (overriding),
the set operations, malformed-row handling, safe save, password hashing, the dot product for basket totals.

**Practise live changes:** thresholds (in Settings and in `config.py`), the 14-day window, a new
validation rule (e.g. max price Tk 5,000 for vegetables), a new category in `CATEGORIES`.

**Before the demo:**
- Enter reference prices (at least ONION) so a real Spike appears.
- If the sample data is more than 14 days old, re-run the generator with `--end-date` near the demo day
  (this overwrites `data/`).
- Check that the Bangla names display correctly on the demo PC; if not, turn off `show_bangla_names`.
- PDF §15: every member must be able to explain and modify all the code. Check whether your course asks
  you to declare any AI help.

## 17. Report outline (PDF §13)
1. Title and members · 2. Problem, objectives, users · 3. Features and workflow · 4. Python concepts ·
5. Data structures · 6. OOP design · 7. File and exception handling · 8. NumPy and Tkinter justification ·
9. Screenshots and sample input/output · 10. Limitations, societal benefit, future work.

## 18. PDF coverage check
| PDF requirement | Covered by |
|---|---|
| FR-1 User interaction | Tkinter GUI (section 10) |
| FR-2 At least 5 operations | add, view, search/filter, edit, delete, statistics, alerts, basket, report, save/load |
| FR-3 Persistent data | Section 8 |
| FR-4 Validation | Section 9 |
| FR-5 Analysis | Section 5 |
| FR-6 Structured implementation | Sections 6–7 |
| FR-7 Error recovery | Section 9 |
| §7 Program structure | models.py (data model), manager.py (manager), validators.py (validation), analytics.py (calculation), storage.py (files), gui/ (interface) |
| §8 At least 10 records | about 250–300 sample records |
| §6 Library use | NumPy (stats, z-score, dot product), Tkinter (GUI) |

## 19. Future work (report section 10)
TCB price auto-import · price-index line chart (Canvas) · moving-average trend · per-market baselines for
the z-score · online multi-device version (server + database) · full Bangla interface · export to
Excel/PDF (needs instructor approval).
