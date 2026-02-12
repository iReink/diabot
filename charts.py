from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Iterable

import matplotlib
from matplotlib.patches import Rectangle

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
    dates = sorted(grouped.keys(), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
    fig, ax = plt.subplots(figsize=(10, 4))

    x_values = []
    y_values = []
    widths = []
    labels = []
    day_span = 0.8
    for day_index, day in enumerate(dates):
        day_rows = sorted(grouped[day], key=lambda r: r["time"])
        count = len(day_rows)
        if count == 0:
            continue
        bar_width = day_span / count
        left_edge = day_index - day_span / 2
        for idx, row in enumerate(day_rows):
            x = left_edge + bar_width * (idx + 0.5)
            x_values.append(x)
            y_values.append(row["amount"])
            widths.append(bar_width)
        labels.append(day)

    ax.bar(x_values, y_values, width=widths, color="#4dabf7", align="center")
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


def stats_table(rows, max_rows: int = 18, labels: dict[str, str] | None = None) -> list[BytesIO]:
    grouped = _group_by_date(rows)
    dates = sorted(grouped.keys())
    tables = []
    insulin_mark_color = "#d0ebff"

    def _row_values(day_rows, other_columns: int):
        by_tag = {}
        for row in day_rows:
            tag = row["tag"]
            if tag not in by_tag:
                by_tag[tag] = row
        amps = by_tag.get("AMPS")
        peak = by_tag.get("PEAK")
        pmps = by_tag.get("PMPS")
        other_rows = [row for row in day_rows if row["tag"] == "OTHER"]
        other_cells = [
            f"{row['amount']:.1f} ({row['time']})"
            for row in other_rows
        ]
        if len(other_cells) < other_columns:
            other_cells.extend([""] * (other_columns - len(other_cells)))
        return {
            "amps": f"{amps['amount']:.1f}" if amps else "",
            "peak": f"{peak['amount']:.1f}" if peak else "",
            "pmps": f"{pmps['amount']:.1f}" if pmps else "",
            "other_cells": other_cells,
            "amps_insulin": bool(amps and amps["amount"] > 10),
            "pmps_insulin": bool(pmps and pmps["amount"] > 10),
        }

    other_counts = [
        len([row for row in grouped[day] if row["tag"] == "OTHER"])
        for day in dates
    ]
    max_other = max(other_counts) if other_counts else 0

    rows_data = []
    highlighted_rows = []
    for day in dates:
        day_rows = sorted(grouped[day], key=lambda r: r["time"])
        values = _row_values(day_rows, max_other)
        rows_data.append([day, values["amps"], values["peak"], values["pmps"], *values["other_cells"]])
        highlighted_rows.append(
            {
                "amps": values["amps_insulin"],
                "pmps": values["pmps_insulin"],
            }
        )

    for start in range(0, len(rows_data), max_rows):
        chunk = rows_data[start : start + max_rows]
        chunk_highlights = highlighted_rows[start : start + max_rows]
        total_columns = 4 + max_other
        fig, ax = plt.subplots(figsize=(max(8, 1.4 * total_columns), 0.4 * (len(chunk) + 3)))
        ax.axis("off")
        label_map = labels or {}
        table = ax.table(
            cellText=chunk,
            colLabels=[
                "Дата",
                label_map.get("AMPS", "AMPS"),
                label_map.get("PEAK", "PEAK"),
                label_map.get("PMPS", "PMPS"),
                *[""] * max_other,
            ],
            loc="center",
        )
        for row_idx, highlights in enumerate(chunk_highlights, start=1):
            if highlights["amps"]:
                table[(row_idx, 1)].set_facecolor(insulin_mark_color)
                table[(row_idx, 1)].set_alpha(0.45)
            if highlights["pmps"]:
                table[(row_idx, 3)].set_facecolor(insulin_mark_color)
                table[(row_idx, 3)].set_alpha(0.45)

        table.scale(1, 1.3)
        ax.set_title("Статистика измерений")
        ax.add_patch(
            Rectangle(
                (0.02, -0.06),
                0.03,
                0.03,
                transform=ax.transAxes,
                color=insulin_mark_color,
                alpha=0.45,
                clip_on=False,
            )
        )
        ax.text(
            0.06,
            -0.045,
            "после измерения был введён инсулин",
            transform=ax.transAxes,
            ha="left",
            va="center",
            fontsize=9,
        )
        fig.tight_layout()
        buffer = BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        plt.close(fig)
        tables.append(buffer)

    return tables
