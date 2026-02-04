from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _dates_from_rows(rows) -> list[date]:
    dates = {datetime.strptime(row["date"], "%Y-%m-%d").date() for row in rows}
    return sorted(dates)


def _group_by_date(rows):
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)
    return grouped


def _shade_ranges(ax, low: float, high: float):
    ax.axhspan(0, low, color="#ff6b6b", alpha=0.15)
    ax.axhspan(high, max(high + 1, 20), color="#ffd166", alpha=0.15)


def daily_curve(rows) -> BytesIO:
    # Столбчатая диаграмма всех замеров за день
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys())
    fig, ax = plt.subplots(figsize=(10, 4))

    x_values = []
    y_values = []
    labels = []
    for day_index, day in enumerate(dates):
        day_rows = sorted(grouped[day], key=lambda r: r["time"])
        count = len(day_rows)
        for idx, row in enumerate(day_rows):
            x = day_index + (idx + 1) / (count + 1)
            x_values.append(x)
            y_values.append(row["amount"])
        labels.append(day)

    ax.bar(x_values, y_values, color="#4dabf7")
    _shade_ranges(ax, 4, 10)
    ax.set_title("Суточная кривая")
    ax.set_ylabel("Уровень сахара")
    ax.set_xlabel("Дата")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylim(bottom=0)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)
    return buffer


def nadir_chart(rows) -> BytesIO:
    # Линия минимальных значений по дням
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys())
    nadirs = []
    for day in dates:
        values = [row["amount"] for row in grouped[day]]
        nadirs.append(min(values))

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dates, nadirs, marker="o", color="#845ef7")
    _shade_ranges(ax, 4, 9)
    ax.set_title("Nadir за день")
    ax.set_ylabel("Минимальный сахар")
    ax.set_xlabel("Дата")
    ax.set_ylim(bottom=0)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)
    return buffer


def _pick_tag_or_fallback(day_rows, tag: str, fallback: str):
    for row in day_rows:
        if row["tag"] == tag:
            return row["amount"]
    if fallback == "first":
        return day_rows[0]["amount"]
    return day_rows[-1]["amount"]


def amps_pmps_chart(rows) -> tuple[BytesIO, BytesIO]:
    # Два графика: утренние и вечерние замеры
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys())

    amps = []
    pmps = []
    for day in dates:
        day_rows = sorted(grouped[day], key=lambda r: r["time"])
        amps.append(_pick_tag_or_fallback(day_rows, "AMPS", "first"))
        pmps.append(_pick_tag_or_fallback(day_rows, "PMPS", "last"))

    fig1, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(dates, amps, marker="o", color="#12b886")
    ax1.set_title("AMPS по дням")
    ax1.set_ylabel("Уровень сахара")
    ax1.set_xlabel("Дата")
    ax1.set_ylim(bottom=0)
    fig1.autofmt_xdate(rotation=45)
    fig1.tight_layout()

    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.plot(dates, pmps, marker="o", color="#fab005")
    ax2.set_title("PMPS по дням")
    ax2.set_ylabel("Уровень сахара")
    ax2.set_xlabel("Дата")
    ax2.set_ylim(bottom=0)
    fig2.autofmt_xdate(rotation=45)
    fig2.tight_layout()

    buf1 = BytesIO()
    fig1.savefig(buf1, format="png")
    buf1.seek(0)
    buf2 = BytesIO()
    fig2.savefig(buf2, format="png")
    buf2.seek(0)
    plt.close(fig1)
    plt.close(fig2)
    return buf1, buf2


def range_percent_chart(rows) -> BytesIO:
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys())
    if not dates:
        dates = []
    percent_values = []

    parsed_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    for day in parsed_dates:
        start = day - timedelta(days=6)
        window_rows = [row for row in rows if start <= datetime.strptime(row["date"], "%Y-%m-%d").date() <= day]
        if not window_rows:
            percent_values.append(0)
            continue
        good = [row for row in window_rows if 4 < row["amount"] < 10]
        percent = round(len(good) / len(window_rows) * 100, 1)
        percent_values.append(percent)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(dates, percent_values, color="#228be6")
    ax.set_title("% в диапазоне 4–10 (скользящее окно 7 дней)")
    ax.set_ylabel("Процент")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Дата")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)
    return buffer


def stats_table(rows, max_rows: int = 18) -> list[BytesIO]:
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys(), reverse=True)
    tables = []

    def _row_values(day_rows):
        # Берём ранний, средний по времени и поздний замеры
        first = day_rows[0]["amount"]
        last = day_rows[-1]["amount"]
        middle = day_rows[len(day_rows) // 2]["amount"]
        return first, middle, last

    rows_data = []
    for day in dates:
        day_rows = sorted(grouped[day], key=lambda r: r["time"])
        first, middle, last = _row_values(day_rows)
        rows_data.append([day, f"{first:.1f}", f"{middle:.1f}", f"{last:.1f}"])

    for start in range(0, len(rows_data), max_rows):
        chunk = rows_data[start : start + max_rows]
        fig, ax = plt.subplots(figsize=(8, 0.4 * (len(chunk) + 2)))
        ax.axis("off")
        table = ax.table(
            cellText=chunk,
            colLabels=["Дата", "Ранний", "Средний", "Поздний"],
            loc="center",
        )
        table.scale(1, 1.3)
        ax.set_title("Статистика измерений")
        fig.tight_layout()
        buffer = BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        plt.close(fig)
        tables.append(buffer)

    return tables
