from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from db import get_daily_measures, get_measures_between


def average_glucose(rows) -> float | None:
    if not rows:
        return None
    return sum(row["amount"] for row in rows) / len(rows)


def daily_nadir(rows_by_date: dict[str, list]) -> dict[str, float]:
    result = {}
    for day, rows in rows_by_date.items():
        result[day] = min(row["amount"] for row in rows)
    return result


def average_nadir_last_days(chat_id: int, name: str, days: int) -> float | None:
    rows_by_date = get_daily_measures(chat_id, name, days)
    nadirs = daily_nadir(rows_by_date)
    if not nadirs:
        return None
    return sum(nadirs.values()) / len(nadirs)


def consecutive_nadir(chat_id: int, name: str, days: int, compare) -> bool:
    rows_by_date = get_daily_measures(chat_id, name, days)
    if len(rows_by_date) < days:
        return False
    ordered_days = sorted(rows_by_date.keys(), reverse=True)[:days]
    ordered_dates = [datetime.strptime(day, "%Y-%m-%d").date() for day in ordered_days]
    for idx in range(len(ordered_dates) - 1):
        if ordered_dates[idx] - ordered_dates[idx + 1] != timedelta(days=1):
            return False
    for day in ordered_days:
        values = [row["amount"] for row in rows_by_date[day]]
        if not compare(min(values)):
            return False
    return True


def amps_peak_difference_low(chat_id: int, name: str, days: int, threshold: float = 2) -> bool:
    rows_by_date = get_daily_measures(chat_id, name, days)
    if len(rows_by_date) < days:
        return False
    ordered_days = sorted(rows_by_date.keys(), reverse=True)[:days]
    ordered_dates = [datetime.strptime(day, "%Y-%m-%d").date() for day in ordered_days]
    for idx in range(len(ordered_dates) - 1):
        if ordered_dates[idx] - ordered_dates[idx + 1] != timedelta(days=1):
            return False
    for day in ordered_days:
        day_rows = sorted(rows_by_date[day], key=lambda r: r["time"])
        amps = None
        peak = None
        for row in day_rows:
            if row["tag"] == "AMPS":
                amps = row["amount"]
            if row["tag"] == "PEAK":
                peak = row["amount"]
        if amps is None:
            amps = day_rows[0]["amount"]
        if peak is None:
            return False
        if abs(amps - peak) >= threshold:
            return False
    return True


def average_glucose_last_days(chat_id: int, name: str, days: int) -> float | None:
    rows = get_measures_between(
        chat_id,
        name,
        date.today() - timedelta(days=days - 1),
        date.today(),
    )
    return average_glucose(rows)
