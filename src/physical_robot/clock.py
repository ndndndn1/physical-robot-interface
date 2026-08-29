"""Injectable clocks keep mock behavior deterministic and tests free of sleeps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class ManualClock:
    current: datetime

    def __post_init__(self) -> None:
        if self.current.tzinfo is None:
            raise ValueError("ManualClock requires a timezone-aware datetime")

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        if delta.total_seconds() < 0:
            raise ValueError("clock cannot move backwards")
        self.current += delta
