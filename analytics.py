"""Analytics for BazarWatch BD.

NumPy does the arithmetic (mean, median, min, max, sample standard deviation,
the z-score and the basket dot product), but the *rules* — the alert rule,
the filters, the cheapest-market choice and the permissions — stay in plain
Python so the library never hides the logic.

The alert rule (plan section 5):

* ``history`` = prices of the same product dated on or before the record,
  excluding the record itself.
* ``z = (price - mean(history)) / std(history)`` with the sample standard
  deviation (``ddof=1``), only when there are at least ``min_history`` prices
  and the standard deviation is greater than zero.
* ``pct = (price - reference) / reference * 100``, only when a reference price
  is set.
* Spike when both rules fire, Watch when exactly one fires, Normal otherwise.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from config import BUDGET_CLOSE_PERCENT, BUDGET_FULL_PERCENT


# --- History ----------------------------------------------------------------
def history_for(record, records: list) -> list:
    """The prices that form the history of ``record``.

    Same product, dated on or before the record, and not the record itself.
    """
    result = []
    for other in records:
        if other is record:
            continue
        if other.product_id != record.product_id:
            continue
        if other.date <= record.date:
            result.append(other)
    result.sort(key=lambda r: r.date)
    return result


def _price_array(records: list) -> np.ndarray:
    """The prices of a list of records as a NumPy array."""
    if not records:
        return np.array([], dtype=float)
    return np.array([r.price for r in records], dtype=float)


# --- Statistics -------------------------------------------------------------
def product_statistics(product_id: str, records: list, products=None) -> dict:
    """Summary statistics for one product.

    Returns the count, mean, median, min, max, sample standard deviation, the
    official reference price (when known) and the most recent price.
    """
    matching = [r for r in records if r.product_id == product_id]
    prices = _price_array(matching)

    if prices.size == 0:
        return {
            "product_id": product_id,
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "reference": None,
            "latest": None,
        }

    latest = max(matching, key=lambda r: r.date)
    reference = None
    if products:
        product = products.get(product_id)
        if product is not None:
            reference = product.reference_price

    return {
        "product_id": product_id,
        "count": int(prices.size),
        "mean": float(np.mean(prices)),
        "median": float(np.median(prices)),
        "min": float(np.min(prices)),
        "max": float(np.max(prices)),
        # ddof=1 gives the sample standard deviation, as the plan requires.
        "std": float(np.std(prices, ddof=1)) if prices.size > 1 else 0.0,
        "reference": reference,
        "latest": latest.price,
    }


# --- The alert rule ---------------------------------------------------------
def alert_level(record, records: list, products: dict, settings: dict):
    """The alert level of one record.

    Returns ``(level, z, pct)``.  ``z`` is None when there is too little
    history or the prices never vary; ``pct`` is None when no reference price
    is set.
    """
    product = products.get(record.product_id)
    if product is None:
        return "Normal", None, None

    z_limit, pct_limit = product.spike_thresholds(settings)
    min_history = int(settings.get("min_history", 5))

    # -- the z-score rule
    z_value = None
    history = history_for(record, records)
    if len(history) >= min_history:
        prices = _price_array(history)
        std = float(np.std(prices, ddof=1)) if prices.size > 1 else 0.0
        if std > 0:
            z_value = float((record.price - np.mean(prices)) / std)
    z_hit = z_value is not None and z_value >= z_limit

    # -- the reference price rule
    pct_value = product.percent_over_reference(record.price)
    pct_hit = pct_value is not None and pct_value >= pct_limit

    if z_hit and pct_hit:
        level = "Spike"
    elif z_hit or pct_hit:
        level = "Watch"
    else:
        level = "Normal"
    return level, z_value, pct_value


def alerts_for(records: list, products: dict, settings: dict, level: str | None = None):
    """Every record with its alert level, optionally filtered by level.

    Returns a list of ``(record, level, z, pct)`` tuples.
    """
    results = []
    for record in records:
        record_level, z_value, pct_value = alert_level(
            record, records, products, settings
        )
        if level is None or record_level == level:
            results.append((record, record_level, z_value, pct_value))
    return results


# --- Cheapest market --------------------------------------------------------
def _recent_records(records: list, product_id: str, recent_days: int, today=None):
    """The records of one product inside the recent window.

    The window is the last ``recent_days`` days ending today.  Records dated
    in the future are excluded.
    """
    if today is None:
        today = date.today()
    start = (today - timedelta(days=recent_days - 1)).isoformat()
    end = today.isoformat()
    return [
        r
        for r in records
        if r.product_id == product_id and start <= r.date <= end
    ]


def market_averages(product_id: str, records: list, markets: list, recent_days: int,
                    today=None) -> dict:
    """The average recent price of one product in each market."""
    averages: dict[str, float] = {}
    recent = _recent_records(records, product_id, recent_days, today)
    for market in markets:
        prices = [r.price for r in recent if r.market == market]
        if prices:
            averages[market] = float(np.mean(np.array(prices, dtype=float)))
    return averages


def cheapest_market(product_id: str, records: list, markets: list, recent_days: int,
                    today=None):
    """The market with the lowest average recent price for a product.

    Returns ``(market, average)``.  Both are None when no market has a price
    inside the window.
    """
    averages = market_averages(product_id, records, markets, recent_days, today)
    if not averages:
        return None, None
    # The lowest average wins; the name breaks a tie so the result is stable.
    best = min(averages.items(), key=lambda item: (item[1], item[0]))
    return best[0], best[1]


def cheapest_market_for_all(products: dict, records: list, markets: list,
                             recent_days: int, today=None) -> dict:
    """The cheapest market for every product.

    Returns ``{product_id: (market, average)}``; a product with no recent data
    is left out.
    """
    result = {}
    for product_id in products:
        market, average = cheapest_market(
            product_id, records, markets, recent_days, today
        )
        if market is not None:
            result[product_id] = (market, average)
    return result


# --- The basket -------------------------------------------------------------
def basket_plan(items: dict, records: list, markets: list, recent_days: int,
                today=None) -> dict:
    """Plan a basket against the recent prices.

    ``items`` maps a product ID to a quantity.

    * A market's total is the NumPy dot product of the quantities and that
      market's average recent prices, but only when the market has a recent
      price for *every* basket item (a set intersection).
    * The best single market is the lowest of those totals.
    * The split plan puts each item at its own cheapest market, and the
      saving is the difference between the best single total and the split
      total.
    * Items with no recent price anywhere are listed and left out.
    """
    product_ids = list(items.keys())
    quantities = np.array([float(items[p]) for p in product_ids], dtype=float)

    # The average recent price of each product in each market.
    averages: dict[str, dict[str, float]] = {}
    for product_id in product_ids:
        averages[product_id] = market_averages(
            product_id, records, markets, recent_days, today
        )

    # Markets that price every item: the intersection of the per-item sets.
    if product_ids:
        common = set(averages[product_ids[0]].keys())
        for product_id in product_ids[1:]:
            common &= set(averages[product_id].keys())
    else:
        common = set()

    totals: dict[str, float] = {}
    for market in sorted(common):
        prices = np.array(
            [averages[product_id][market] for product_id in product_ids],
            dtype=float,
        )
        # The dot product gives sum(quantity * price) for the whole basket.
        totals[market] = float(np.dot(quantities, prices))

    if totals:
        best_market, best_total = min(
            totals.items(), key=lambda item: (item[1], item[0])
        )
    else:
        best_market, best_total = None, None

    # The split plan: every item at its own cheapest market.
    split_plan: dict[str, dict] = {}
    split_total = 0.0
    for index, product_id in enumerate(product_ids):
        market, average = cheapest_market(
            product_id, records, markets, recent_days, today
        )
        if market is None:
            continue
        quantity = float(quantities[index])
        split_plan[product_id] = {
            "market": market,
            "average": average,
            "quantity": quantity,
            "cost": quantity * average,
        }
        split_total += quantity * average

    unpriced_items = [
        product_id for product_id in product_ids if product_id not in split_plan
    ]

    saving = None
    if best_total is not None:
        saving = best_total - split_total

    return {
        "totals": totals,
        "best_market": best_market,
        "best_total": best_total,
        "split_plan": split_plan,
        "split_total": split_total,
        "saving": saving,
        "unpriced_items": unpriced_items,
    }


# --- Budget -----------------------------------------------------------------
def budget_status(spent: float, budget: float) -> tuple[str, str]:
    """Compare a total with a budget.

    Returns ``(status, message)`` where the status is "Within budget",
    "Close to budget" or "Over budget".
    """
    spent = float(spent)
    budget = float(budget)
    if budget <= 0:
        if spent <= 0:
            return "Within budget", "Total Tk 0.00 of Tk 0.00"
        return "Over budget", f"Over budget by Tk {spent:.2f} (budget Tk 0.00)"

    percent = spent / budget * 100
    if percent <= BUDGET_CLOSE_PERCENT:
        return "Within budget", (
            f"Tk {spent:.2f} of Tk {budget:.2f} ({percent:.1f}% of budget)"
        )
    if percent <= BUDGET_FULL_PERCENT:
        return "Close to budget", (
            f"Tk {spent:.2f} of Tk {budget:.2f} ({percent:.1f}% of budget)"
        )
    return "Over budget", (
        f"Over budget by Tk {spent - budget:.2f} "
        f"(Tk {spent:.2f} of Tk {budget:.2f})"
    )
