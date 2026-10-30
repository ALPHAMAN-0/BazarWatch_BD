"""The weekly text report for BazarWatch BD.

The report covers the 7 days ending on a chosen date (today by default) and
compares them with the 7 days before that.  It is plain text so it can be
saved, opened in any editor and pasted into the project report.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np

import config
from analytics import alert_level, cheapest_market


def _date_range(end_date: date) -> tuple[str, str, str, str]:
    """The two 7-day windows: this week and the week before."""
    this_start = (end_date - timedelta(days=6)).isoformat()
    previous_end = (end_date - timedelta(days=7)).isoformat()
    previous_start = (end_date - timedelta(days=13)).isoformat()
    return this_start, end_date.isoformat(), previous_start, previous_end


def _average(prices: list[float]) -> float | None:
    """The mean of a list of prices, or None when the list is empty."""
    if not prices:
        return None
    return float(np.mean(np.array(prices, dtype=float)))


def build_weekly_report(
    records: list,
    products: dict,
    settings: dict,
    markets: list | None = None,
    end_date: date | None = None,
    show_bangla: bool = False,
) -> str:
    """Build the weekly report as text.

    The report contains the record count by market, the average price and
    percentage change per product, the cheapest market per product, the
    Spike/Watch list, the products that were not priced this week and the top
    contributors.
    """
    if end_date is None:
        end_date = date.today()
    if markets is None:
        markets = list(settings.get("markets", []))

    this_start, this_end, previous_start, previous_end = _date_range(end_date)

    this_week = [r for r in records if this_start <= r.date <= this_end]
    previous_week = [
        r for r in records if previous_start <= r.date <= previous_end
    ]

    lines: list[str] = []
    lines.append("=" * 68)
    lines.append("BazarWatch BD - Weekly Report")
    lines.append("=" * 68)
    lines.append(f"This week : {this_start} to {this_end}")
    lines.append(f"Last week : {previous_start} to {previous_end}")
    lines.append(f"Generated : {date.today().isoformat()}")
    lines.append("Note: sample data is illustrative, not real market prices.")
    lines.append("")

    # -- summary --------------------------------------------------------
    lines.append("-" * 68)
    lines.append("SUMMARY")
    lines.append("-" * 68)
    lines.append(f"Records this week : {len(this_week)}")
    lines.append(f"Records last week : {len(previous_week)}")
    lines.append("")

    # -- records by market ----------------------------------------------
    lines.append("-" * 68)
    lines.append("RECORDS BY MARKET")
    lines.append("-" * 68)
    if this_week:
        counts: dict[str, int] = {}
        for record in this_week:
            counts[record.market] = counts.get(record.market, 0) + 1
        for market in sorted(counts):
            lines.append(f"{market:<32} {counts[market]:>4}")
    else:
        lines.append("No records were logged this week.")
    lines.append("")

    # -- price change per product ---------------------------------------
    lines.append("-" * 68)
    lines.append("AVERAGE PRICE AND CHANGE PER PRODUCT")
    lines.append("-" * 68)
    lines.append(
        f"{'Product':<20}{'This week':>12}{'Last week':>12}{'Change':>12}"
    )
    this_prices: dict[str, list[float]] = {}
    previous_prices: dict[str, list[float]] = {}
    for record in this_week:
        this_prices.setdefault(record.product_id, []).append(record.price)
    for record in previous_week:
        previous_prices.setdefault(record.product_id, []).append(record.price)

    for product_id in sorted(products):
        product = products[product_id]
        this_average = _average(this_prices.get(product_id, []))
        previous_average = _average(previous_prices.get(product_id, []))
        name = product.display_name(show_bangla)
        this_text = f"{this_average:.2f}" if this_average is not None else "-"
        previous_text = f"{previous_average:.2f}" if previous_average is not None else "-"
        if this_average is not None and previous_average:
            change = (this_average - previous_average) / previous_average * 100
            change_text = f"{change:+.1f}%"
        else:
            change_text = "-"
        lines.append(
            f"{name[:19]:<20}{this_text:>12}{previous_text:>12}{change_text:>12}"
        )
    lines.append("")

    # -- cheapest market -------------------------------------------------
    recent_days = int(settings.get("recent_days", 14))
    lines.append("-" * 68)
    lines.append(f"CHEAPEST MARKET PER PRODUCT (last {recent_days} days)")
    lines.append("-" * 68)
    for product_id in sorted(products):
        product = products[product_id]
        # The window ends on the report date, so this section matches the
        # week the rest of the report covers.
        market, average = cheapest_market(
            product_id, records, markets, recent_days, today=end_date
        )
        name = product.display_name(show_bangla)
        if market is None:
            lines.append(f"{name[:19]:<20} no recent data")
        else:
            lines.append(f"{name[:19]:<20} {market:<24} Tk {average:.2f}")
    lines.append("")

    # -- spikes and watches ----------------------------------------------
    lines.append("-" * 68)
    lines.append("SPIKE AND WATCH LIST (this week)")
    lines.append("-" * 68)
    spikes: list[str] = []
    watches: list[str] = []
    for record in this_week:
        level, z_value, pct_value = alert_level(record, records, products, settings)
        if level == "Normal":
            continue
        product = products.get(record.product_id)
        name = product.display_name(show_bangla) if product else record.product_id
        details = []
        if z_value is not None:
            details.append(f"z={z_value:.2f}")
        if pct_value is not None:
            details.append(f"{pct_value:+.1f}%")
        else:
            details.append("ref not set")
        entry = (
            f"  {level:<6} {record.record_id}  {name[:18]:<19} "
            f"{record.market:<24} Tk {record.price:>8.2f}  ({', '.join(details)})"
        )
        if level == "Spike":
            spikes.append(entry)
        else:
            watches.append(entry)

    if spikes:
        lines.append("Spikes:")
        lines.extend(spikes)
    else:
        lines.append("Spikes: none")
    if watches:
        lines.append("Watch:")
        lines.extend(watches)
    else:
        lines.append("Watch: none")
    lines.append("")

    # -- products not priced ----------------------------------------------
    lines.append("-" * 68)
    lines.append("PRODUCTS NOT PRICED THIS WEEK")
    lines.append("-" * 68)
    priced = set(this_prices.keys())
    missing = [
        products[pid].display_name(show_bangla)
        for pid in sorted(products)
        if pid not in priced
    ]
    if missing:
        for name in missing:
            lines.append(f"  {name}")
    else:
        lines.append("  Every product was priced this week.")
    lines.append("")

    # -- top contributors --------------------------------------------------
    lines.append("-" * 68)
    lines.append("TOP CONTRIBUTORS")
    lines.append("-" * 68)
    contributor_counts: dict[str, int] = {}
    for record in this_week:
        contributor_counts[record.added_by] = (
            contributor_counts.get(record.added_by, 0) + 1
        )
    if contributor_counts:
        for username, count in sorted(
            contributor_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"  {username:<24} {count:>4} record(s)")
    else:
        lines.append("  No records were logged this week.")
    lines.append("")

    lines.append("=" * 68)
    lines.append("End of report")
    lines.append("=" * 68)
    return "\n".join(lines) + "\n"


def weekly_report(
    records: list,
    products: dict,
    settings: dict,
    markets: list | None = None,
    end_date: date | None = None,
    show_bangla: bool = False,
) -> str:
    """Build the weekly report.  An alias of :func:`build_weekly_report`."""
    return build_weekly_report(
        records, products, settings, markets, end_date, show_bangla
    )


def save_weekly_report(
    records: list,
    products: dict,
    settings: dict,
    markets: list | None = None,
    end_date: date | None = None,
    show_bangla: bool = False,
    reports_dir=None,
) -> Path:
    """Build the weekly report and save it, returning the file path.

    The file is named ``weekly_report_YYYY-MM-DD.txt`` after the day the
    report ends on.
    """
    if end_date is None:
        end_date = date.today()
    if reports_dir is None:
        reports_dir = config.REPORTS_DIR

    directory = Path(reports_dir)
    directory.mkdir(parents=True, exist_ok=True)

    text = build_weekly_report(
        records, products, settings, markets, end_date, show_bangla
    )
    path = directory / f"weekly_report_{end_date.isoformat()}.txt"
    path.write_text(text, encoding="utf-8")
    return path
