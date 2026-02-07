from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingMeasure:
    tag: str
    name: str


_PENDING_MEASURES: dict[int, PendingMeasure] = {}


def set_pending_measure(chat_id: int, tag: str, name: str) -> None:
    _PENDING_MEASURES[chat_id] = PendingMeasure(tag=tag, name=name)


def get_pending_measure(chat_id: int) -> PendingMeasure | None:
    return _PENDING_MEASURES.get(chat_id)


def clear_pending_measure(chat_id: int) -> None:
    _PENDING_MEASURES.pop(chat_id, None)
