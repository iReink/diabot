import re
from datetime import datetime
from typing import Optional


TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def parse_time(value: str) -> Optional[str]:
    value = value.strip()
    if TIME_RE.match(value):
        return value
    return None


def parse_peak(value: str) -> Optional[int]:
    value = value.strip()
    if not value.isdigit():
        return None
    number = int(value)
    if 1 <= number <= 12:
        return number
    return None


def parse_measure(value: str) -> Optional[float]:
    value = value.replace(",", ".").strip()
    try:
        number = float(value)
    except ValueError:
        return None
    if number < 0:
        return None
    return number


def now_date_time_strings():
    now = datetime.now()
    return now.date().isoformat(), now.time().strftime("%H:%M")
