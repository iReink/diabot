import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterable, Optional


DB_PATH = "data.db"


@contextmanager
def get_connection():
    # Контекст для безопасного открытия/закрытия SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# --- Коты ---

def get_cat_by_chat(chat_id: int):
    # Для MVP берём первого найденного кота в чате
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM cats
            WHERE chat_id = ?
            LIMIT 1
            """,
            (chat_id,),
        )
        return cursor.fetchone()


def get_cat_by_chat_and_name(chat_id: int, name: str):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM cats
            WHERE chat_id = ? AND name = ?
            LIMIT 1
            """,
            (chat_id, name),
        )
        return cursor.fetchone()


def create_cat(
    chat_id: int,
    user_id: int,
    name: str,
    am_time: str,
    peak: int,
    pm_time: str,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cats (chat_id, user_id, name, am_time, peak, pm_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, name, am_time, peak, pm_time),
        )
        conn.commit()


def update_cat_field(chat_id: int, name: str, field: str, value):
    # Поле приходит из кода, а не от пользователя
    with get_connection() as conn:
        conn.execute(
            f"UPDATE cats SET {field} = ? WHERE chat_id = ? AND name = ?",
            (value, chat_id, name),
        )
        conn.commit()


def rename_cat(chat_id: int, old_name: str, new_name: str):
    with get_connection() as conn:
        # Временно отключаем проверки, чтобы синхронно переименовать записи
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "UPDATE cats SET name = ? WHERE chat_id = ? AND name = ?",
            (new_name, chat_id, old_name),
        )
        conn.execute(
            "UPDATE measure SET name = ? WHERE chat_id = ? AND name = ?",
            (new_name, chat_id, old_name),
        )
        conn.commit()


# --- Замеры ---

def add_measure(
    chat_id: int,
    user_id: int,
    name: str,
    amount: float,
    tag: str,
    when: Optional[datetime] = None,
):
    when = when or datetime.now()
    # Храним дату и время отдельно, чтобы удобнее группировать
    date_str = when.date().isoformat()
    time_str = when.time().strftime("%H:%M")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO measure (chat_id, user_id, name, date, time, amount, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, name, date_str, time_str, amount, tag),
        )
        conn.commit()


def get_measures(chat_id: int, name: str, days: int):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM measure
            WHERE chat_id = ? AND name = ? AND date >= ?
            ORDER BY date ASC, time ASC
            """,
            (chat_id, name, date_from),
        )
        return cursor.fetchall()


def get_measures_between(chat_id: int, name: str, start_date: date, end_date: date):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM measure
            WHERE chat_id = ? AND name = ? AND date BETWEEN ? AND ?
            ORDER BY date ASC, time ASC
            """,
            (chat_id, name, start_date.isoformat(), end_date.isoformat()),
        )
        return cursor.fetchall()


def get_daily_measures(chat_id: int, name: str, days: int):
    measures = get_measures(chat_id, name, days)
    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in measures:
        by_date.setdefault(row["date"], []).append(row)
    return by_date


def get_last_measures(chat_id: int, name: str, count: int = 1):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM measure
            WHERE chat_id = ? AND name = ?
            ORDER BY date DESC, time DESC
            LIMIT ?
            """,
            (chat_id, name, count),
        )
        return cursor.fetchall()


def get_last_days(chat_id: int, name: str, days: int):
    date_from = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM measure
            WHERE chat_id = ? AND name = ? AND date >= ?
            ORDER BY date ASC, time ASC
            """,
            (chat_id, name, date_from),
        )
        return cursor.fetchall()


def list_chats():
    with get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT chat_id, name FROM cats WHERE is_active = 1")
        return cursor.fetchall()
