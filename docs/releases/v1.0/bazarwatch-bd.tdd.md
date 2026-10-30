# BazarWatch BD — TDD evidence report

**Version:** v1.0 · **Date:** 2026-10-30 · **Branch:** `main`

This report records what the test suite proves about BazarWatch BD, and how
the work was done: a failing test first, then the smallest change that made
it pass, then a commit.

---

## 1. Source plan

The plan is [`plan.md`](../../../plan.md) in the repository root. It is the
specification for the whole project: 19 sections covering the problem, the
roles and permissions, the starter data, the alert and basket rules, the
data files, the validation table, the screens, the sample data, the tests
and the build order.

Every behaviour in this report traces back to a section of that plan.

## 2. User journeys

Derived from the plan's screens (§10), permissions (§3), rules (§5) and
demo script (§16).

| # | As a… | I want to… | so that… |
|---|---|---|---|
| J1 | first-time user | create the first Admin account and log in | there is always an Admin, and no one can sign themselves up |
| J2 | Member | log a price with a product and market picked from dropdowns | typos cannot split the data |
| J3 | Member | see whether my price was Normal, Watch or a Spike | I know whether the price was fair |
| J4 | Member | search and filter the records by product, market, user, level and date | I can find the record I want |
| J5 | Member | edit my own price record | I can correct a mistake |
| J6 | Member | be unable to delete a record or manage the catalogue | the data stays trustworthy |
| J7 | Admin | edit and delete any record, and manage products, markets, users and settings | I can keep the data correct |
| J8 | Admin | see who has been logging prices and when they last logged in | I can follow the mess's activity |
| J9 | user | see the cheapest market for each product | I shop where it is cheap |
| J10 | user | plan my weekly basket against a budget and see the saving from splitting it | I spend less |
| J11 | user | read a weekly report comparing this week with last week | I can put it in the project report |
| J12 | user | close the app and come back later with the data intact | my work is saved |
| J13 | user | have a corrupt data file or a malformed CSV row handled gracefully | the app still starts and tells me what it skipped |
| J14 | user | make a mistake in a field | I get a message and the app stays open |

## 3. Task report

Each row is one module. The RED and GREEN columns are the real output of
the commands named in them.

### Day 1 — config, models, validators

| | |
|---|---|
| **Behaviour** | The starter catalogue, the markets, the alert levels and the roles are defined in one place; every input is checked before it reaches the data; the price, date, quantity, budget, threshold and password rules are enforced with the custom exception tree. |
| **Plan** | §4, §7, §9 |
| **RED** | `python3 -m unittest tests.test_config tests.test_models tests.test_validators` → failures for the missing models and validators |
| **GREEN** | `python3 -m unittest tests.test_config tests.test_models tests.test_validators` → OK |
| **Commit** | `2a01b17` Add config, models and validators with test coverage |

### Day 2 — storage, auth, manager

| | |
|---|---|
| **Behaviour** | The data files load and save with UTF-8; a missing file is created, a corrupt JSON file is renamed and the defaults are loaded, a malformed CSV row is skipped and reported; a safe write goes through a `.tmp` file and `os.replace`; passwords are stored as a PBKDF2 hash with a random salt; the manager enforces every permission from §3 and raises `PermissionDeniedError` rather than only hiding buttons. |
| **Plan** | §3, §7, §8, §9 |
| **RED** | `python3 -m unittest tests.test_storage tests.test_auth tests.test_manager` → failures for the missing storage, auth and manager |
| **GREEN** | `python3 -m unittest tests.test_storage tests.test_auth tests.test_manager` → OK |
| **Commit** | `ecadbe4` Add storage, auth and manager with permission enforcement |

### Day 3 — analytics, reports, sample data

| | |
|---|---|
| **Behaviour** | The z-score and the percentage over the reference price decide the alert level; `PerishableProduct` overrides `spike_thresholds` so the alert code never checks the product type; the cheapest market averages the last 14 days and skips markets with no data; the basket total is a NumPy dot product over the markets that price every item; the weekly report covers the 7 days ending on a chosen date against the 7 days before; the generator is seeded, plants one onion spike and refuses to overwrite without `--force`. |
| **Plan** | §5, §7, §12 |
| **RED** | `python3 -m unittest tests.test_analytics tests.test_reports tests.test_sample_data` → failures for the missing analytics, reports and generator |
| **GREEN** | `python3 -m unittest tests.test_analytics tests.test_reports tests.test_sample_data` → OK |
| **Commit** | `a21e358` Add analytics, reports and the sample data generator |

### Day 4–5 — the GUI

| | |
|---|---|
| **Behaviour** | The login screen comes first; the first run offers "Create Admin"; after logging in the header names the user; the six tabs are there, with the Admin tab only for an Admin; the tables are colour-coded by alert level; every button handler catches `BazarError` and shows a message, and an unexpected error is logged to `data/error.log` without closing the app. |
| **Plan** | §9, §10 |
| **RED** | `python3 -m unittest tests.test_gui` → failures for the missing GUI |
| **GREEN** | `python3 -m unittest tests.test_gui` → OK |
| **Commit** | `371425e` Add the tkinter interface and fix the window layout |

### The window layout bug

The tables came up 1×1 pixels. A first guess — that the filter panel was
eating the vertical space — was wrong. Measuring the widgets showed the
cause: the login view's frame was never destroyed, so a second frame was
packed beside it and the notebook got 376 px of the 740 px window.

| | |
|---|---|
| **RED** | `python3 -m unittest tests.test_gui.TestWindowLayout` → `AssertionError: 1 != 1137` (the Records table was 1 px wide) |
| **GREEN** | same command → OK; the Records table is now 1137×410 px and every tab is 1176×710 px |
| **Commit** | `2585908` (reproducer) then `371425e` (fix) |

### The three interface defects from the review pass

The review pass after the build found three defects that a user would hit
within a minute of using the app.

| Defect | RED evidence | GREEN evidence |
|---|---|---|
| `LogPriceTab` had no `refresh`, so logging in raised `NotImplementedError` and popped an error box | `AssertionError: 'errors' unexpectedly contains [...]` | the same test → OK |
| The Edit and Delete buttons stayed disabled, because the tree never reported a selection | `AssertionError: 'disabled' != 'normal'` | the same test → OK |
| A refused edit still changed the record and wrote the bad value to the CSV | `AssertionError: '2026-10-05' != '2026-10-06'` and `AssertionError: '999' unexpectedly found in '...'` | the same tests → OK |
| **Commits** | `dec5f8e` | `3f4f1c0` |

The duplicate check in `update_record` compares a throwaway candidate
against the stored records, so it had to exclude the record being edited by
ID. The first version of the fix compared by object identity, which made
every edit look like a duplicate; the test suite caught it immediately.

### The review-pass findings

A second review pass found more. Each fix below has a test that fails
without it.

| Finding | Test | Before | After |
|---|---|---|---|
| Two products with the same name were indistinguishable in a dropdown | `test_the_log_price_dropdown_names_the_product_id` | the label was `"Rice (চাল)"` twice | the label is `"Rice (চাল) [RICE1]"` |
| A product added in the Admin tab never reached the Log Price or Basket dropdowns | `test_a_new_product_shows_up_in_the_log_price_dropdown` | the dropdown kept the old list | the Admin tab tells the other tabs to reload |
| The weekly report priced the cheapest market against today, not against the week it covered | `test_a_report_for_an_older_week_ignores_later_prices` | a September price changed the March report | the window ends on the report date |
| A malformed date filter was compared as text instead of being refused | `test_a_malformed_from_date_is_refused` | no error raised | `ValidationError` |
| The Admin sub-tabs lost the selected row on refresh | `test_the_users_selection_survives_a_refresh` | `AssertionError: None != 'rafi'` | the row stays selected |
| `min_history` and `recent_days` were stored as `5.0` and `14.0` | `test_min_history_is_a_whole_number` | `AssertionError: 6.0 is not an instance of int` | they are whole numbers |
| A missing or null threshold in `settings.json` crashed the alert code | `test_a_missing_threshold_falls_back_to_the_default` | `KeyError` | the default is used |
| Turning off the Bangla names did not reach the other tabs | `test_turning_off_the_bangla_names_reaches_the_log_price_tab` | the Bangla names were still showing | the other tabs reload |
| **Commit** | | | `fbf948f`, `fd40964` |

### The plan check

`verify_plan.py` walks the plan section by section and drives the real GUI
window.

| | |
|---|---|
| **Command** | `python3 verify_plan.py` |
| **Result** | `105 of 105 checks passed.` / `Everything in plan.md checks out.` |
| **Commit** | `61f98e1` |

### The second review pass — the data layer

A review pass over the storage, manager and config modules found five
defects that all involve data silently going missing or settings quietly
changing. Each fix has a test that fails without it.

| Finding | Test | Before | After |
|---|---|---|---|
| A record naming a product that is not in the catalogue was dropped and never written back, so the history was destroyed on the next save | `test_the_orphan_row_is_still_in_the_file_after_a_save` | the row was gone from the CSV | the row is kept and the reason is reported |
| Removing a market compared the name one way and filtered it another, so a different case did nothing | `test_a_market_can_be_removed_with_a_different_case` | the market stayed | the market is removed |
| Two corrupt saves of the same file in one second overwrote each other's backup | `test_two_corrupt_files_get_two_different_names` | one backup, the other lost | two backups, each with its own content |
| A hand-edited settings file with a text threshold crashed every alert computation | `test_a_text_threshold_falls_back_to_the_default` | `ValueError` | the default is used and the bad value is reported |
| Adding a market permanently changed the default settings for everybody | `test_the_default_markets_are_unchanged_after_adding_one` | `DEFAULT_SETTINGS["markets"]` grew | the defaults stay as they were |
| A count setting of `2.4` was quietly rounded down to `2` | `test_a_fractional_count_is_refused` | `2` | `ValidationError` |
| **Commits** | `e12cce4` (RED) | | `9d45a4c` (GREEN) |

### The third review pass — the interface

A review pass over the GUI modules found three more defects that a user
would hit within a minute.

| Finding | Test | Before | After |
|---|---|---|---|
| Typing a budget and then adding an item threw the budget away | `test_the_budget_survives_a_rebuild` | the field was empty again | the unsaved budget is left alone |
| Double-clicking a basket row did nothing, because the table handed back the display name instead of the product ID | `test_double_clicking_a_basket_row_removes_it` | the item stayed | the item is removed |
| Removing a market left it in the Log Price dropdown | `test_the_stale_market_is_dropped_from_the_dropdown` | the dropdown kept it | the dropdown is rebuilt |
| **Commits** | `7ea24d3` (RED) | | `c752615` (GREEN) |

## 4. Test specification

| # | What is guaranteed | Test file or command | Type | Result |
|---|---|---|---|---|
| 1 | A price of 0, a negative price, a price over 100,000 and a non-number are all refused | `tests/test_validators.py` | unit | PASS |
| 2 | A malformed date and a future date are refused | `tests/test_validators.py` | unit | PASS |
| 3 | A quantity of 0 or less is refused | `tests/test_validators.py` | unit | PASS |
| 4 | A threshold outside its allowed range is refused | `tests/test_validators.py` | unit | PASS |
| 5 | A password under 6 characters is refused | `tests/test_validators.py` | unit | PASS |
| 6 | `ValidationError`, `DuplicateIDError`, `RecordNotFoundError`, `AuthError` and `PermissionDeniedError` all descend from `BazarError` | `tests/test_validators.py` | unit | PASS |
| 7 | A product knows its display name, its percentage over the reference price and its thresholds | `tests/test_models.py` | unit | PASS |
| 8 | `from_dict` returns a `PerishableProduct` for a perishable product | `tests/test_models.py` | unit | PASS |
| 9 | A password is stored as a PBKDF2 hash with a random salt, never in the clear | `tests/test_auth.py` | unit | PASS |
| 10 | The wrong password raises `AuthError` | `tests/test_auth.py` | unit | PASS |
| 11 | A missing data file is created with the defaults | `tests/test_storage.py` | integration | PASS |
| 12 | A corrupt JSON file is renamed and the defaults are loaded, with a warning | `tests/test_storage.py` | integration | PASS |
| 13 | A malformed CSV row is skipped and reported with its reason | `tests/test_storage.py` | integration | PASS |
| 14 | A safe save leaves no `.tmp` file behind | `tests/test_storage.py` | integration | PASS |
| 15 | Saving and loading gives the same data back | `tests/test_storage.py` | integration | PASS |
| 16 | The alert rule gives Spike when both rules fire, Watch when exactly one fires and Normal otherwise | `tests/test_analytics.py` | unit | PASS |
| 17 | With no reference price the highest level is Watch | `tests/test_analytics.py` | unit | PASS |
| 18 | With too little history there is no z-score | `tests/test_analytics.py` | unit | PASS |
| 19 | Perishables use the looser limits | `tests/test_analytics.py` | unit | PASS |
| 20 | The cheapest market ignores the records older than the window | `tests/test_analytics.py` | unit | PASS |
| 21 | The basket total is a dot product and only covers the markets that price every item | `tests/test_analytics.py` | unit | PASS |
| 22 | The budget status is Within budget, Close to budget or Over budget at 90% and 100% | `tests/test_analytics.py` | unit | PASS |
| 23 | The report has every section the plan lists | `tests/test_reports.py` | integration | PASS |
| 24 | The report is saved as `weekly_report_YYYY-MM-DD.txt` | `tests/test_reports.py` | integration | PASS |
| 25 | The generator is seeded, writes 250–300 records and plants one spike | `tests/test_sample_data.py` | integration | PASS |
| 26 | A Member cannot delete a record | `tests/test_manager.py` | integration | PASS |
| 27 | A Member can edit their own record but not another member's | `tests/test_manager.py` | integration | PASS |
| 28 | An Admin can edit and delete any record | `tests/test_manager.py` | integration | PASS |
| 29 | A duplicate username, product ID, market name and same-day record are all refused | `tests/test_manager.py` | integration | PASS |
| 30 | A missing record raises `RecordNotFoundError` | `tests/test_manager.py` | integration | PASS |
| 31 | A refused edit leaves the record and the file untouched | `tests/test_manager.py` | integration | PASS |
| 32 | A malformed date filter is refused | `tests/test_review_fixes.py` | integration | PASS |
| 33 | The count settings are stored as whole numbers | `tests/test_review_fixes.py` | integration | PASS |
| 34 | A missing threshold falls back to the default | `tests/test_review_fixes.py` | integration | PASS |
| 35 | The report's cheapest market matches the week it covers | `tests/test_review_fixes.py` | integration | PASS |
| 36 | The login screen comes first and the first run offers Create Admin | `tests/test_gui.py` | E2E | PASS |
| 37 | The Admin sees all six tabs and a Member does not see the Admin tab | `tests/test_gui.py` | E2E | PASS |
| 38 | Logging in shows no error | `tests/test_gui.py` | E2E | PASS |
| 39 | Clicking a row enables the Edit button, and a Member's Delete stays disabled | `tests/test_gui.py` | E2E | PASS |
| 40 | The chosen row survives a refresh | `tests/test_gui.py` | E2E | PASS |
| 41 | Every tab fills the window and the Records table is 1137 px wide | `tests/test_gui.py` | E2E | PASS |
| 42 | A product added in the Admin tab reaches the other dropdowns | `tests/test_gui.py` | E2E | PASS |
| 43 | The Bangla-name switch reaches the other tabs | `tests/test_gui.py` | E2E | PASS |
| 44 | The weekly report can be generated from the File menu | `tests/test_gui.py` | E2E | PASS |
| 45 | Every requirement in plan.md holds | `python3 verify_plan.py` | E2E | PASS (105/105) |
| 46 | A record naming an unknown product is kept in the file and reported, and never reaches the records list | `tests/test_review_round_two.py` | integration | PASS |
| 47 | A market can be removed with any capitalisation, and a market that is not there is refused | `tests/test_review_round_two.py` | integration | PASS |
| 48 | Two corrupt saves of the same file produce two different backups, each keeping its own content | `tests/test_review_round_two.py` | integration | PASS |
| 49 | A non-numeric threshold falls back to the default, is reported, and the alert code still runs | `tests/test_review_round_two.py` | unit | PASS |
| 50 | A fractional count setting is refused, and a whole number written as a float is kept | `tests/test_review_round_two.py` | unit | PASS |
| 51 | Adding a market leaves the default settings, and a fresh copy, exactly as they were | `tests/test_review_round_two.py` | integration | PASS |
| 52 | A typed budget survives a rebuild of the basket | `tests/test_gui.py` | E2E | PASS |
| 53 | Double-clicking a basket row removes that item | `tests/test_gui.py` | E2E | PASS |
| 54 | Removing a market drops it from the Log Price dropdown | `tests/test_gui.py` | E2E | PASS |

## 5. Coverage

Command:

```
python3 -m coverage run --source=. -m unittest discover -s tests
python3 -m coverage report
```

Result: **87%** over the application code — above the 80% target.

The number above is the application code on its own, measured with

```
python3 -m coverage run --source=. --omit="tests/*,verify_plan.py" \
    -m unittest discover -s tests -t .
python3 -m coverage report --omit="tests/*,verify_plan.py"
```

which gives `2663` statements, `356` missed, **87%**. The test files and
`verify_plan.py` are left out of that figure on purpose: the tests are the
thing being measured, and `verify_plan.py` is a one-off script that is
run, not unit-tested. Including them gives 77%, because `verify_plan.py`
alone is 458 statements at 0%.

| Module | Coverage | Module | Coverage |
|---|---|---|---|
| `analytics.py` | 100% | `gui/basket_tab.py` | 89% |
| `config.py` | 100% | `gui/dashboard_tab.py` | 95% |
| `gui/records_tab.py` | 91% | `gui/log_price_tab.py` | 94% |
| `gui/stats_tab.py` | 90% | `gui/admin_tab.py` | 80% |
| `manager.py` | 92% | `gui/app.py` | 74% |
| `models.py` | 87% | `gui/login_view.py` | 78% |
| `reports.py` | 89% | `gui/widgets.py` | 79% |
| `storage.py` | 87% | `validators.py` | 89% |
| `auth.py` | 89% | `generate_sample_data.py` | 76% |

### Known gaps

- `main.py` (0%) is an entry point. It only starts the app; the app itself
  is covered by the GUI tests.
- `verify_plan.py` (0%) is a one-off verification script. It is run by
  `python3 verify_plan.py`, which drives the real GUI and reports 105 of
  105 checks passing; it is not part of the unit-test suite.
- `gui/app.py` at 74%: the untested lines are the window teardown and the
  `Exit` menu handler.
- `gui/login_view.py` at 78%: the untested lines are the message-box
  branches of the error handlers, which need a modal dialog to reach.
- `generate_sample_data.py` at 76%: the untested lines are the `--force`
  refusal path and a few of the random-walk branches.
- `storage.py` at 87%: the untested lines are the corrupt-file branches of
  the loaders for the files the plan does not exercise.

None of the gaps hide a rule from the plan. Every rule in §5 and every
permission in §3 is covered.

## 6. Merge evidence

The checkpoint commits are kept separate on `main`, so the RED and GREEN
evidence stays visible in the history:

| Commit | Stage |
|---|---|
| `2a01b17` | Day 1 — models and validators (GREEN) |
| `ecadbe4` | Day 2 — storage, auth, manager (GREEN) |
| `a21e358` | Day 3 — analytics, reports, sample data (GREEN) |
| `2585908` | RED — the window layout reproducer |
| `371425e` | GREEN — the window layout fix |
| `dec5f8e` | RED — the three interface-defect reproducers |
| `3f4f1c0` | GREEN — the three interface fixes |
| `d97a27f` | Extra coverage for the untested interface paths |
| `d1adbe6` | The lint, type-check and documentation pass |
| `fbf948f` | GREEN — the dropdown, report and date-filter fixes |
| `fd40964` | GREEN — the settings-type and missing-setting fixes |
| `61f98e1` | The plan verification script |
| `0b9f46a` | This evidence report |
| `8489008` | The plan script made to pass lint and the type checker |
| `e12cce4` | RED — the second review pass (the data layer) |
| `9d45a4c` | GREEN — the second review pass |
| `7ea24d3` | RED — the third review pass (the interface) |
| `c752615` | GREEN — the third review pass |

The RED messages quoted in section 3 are the actual output of the failing
runs, not reconstructions. Where a fix was written before its test — the
settings-type and missing-threshold fixes — the test was checked against
the old code by reverting the fix; it failed with
`AssertionError: 6.0 is not an instance of int` and a `KeyError`, and
passed again once the fix was restored.

### Summary

- **RED validations:** 6 (window layout, the three interface defects, the first review pass, the second review pass, the third review pass)
- **GREEN validations:** 6 module checkpoints plus the three review passes
- **Tests:** 444 passing
- **Coverage:** 87% over the application code
- **Plan checks:** 105 of 105 passing
- **Lint:** ruff, all checks passed
- **Types:** mypy, no issues in 34 source files
