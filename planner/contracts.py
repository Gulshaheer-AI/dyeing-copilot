"""Schedule artifacts deliberately contain no recorded water fields."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Placement:
    order_id: str
    quantity: Decimal
    virtual_id: str
    cleaning_start: datetime
    process_start: datetime
    process_end: datetime
    cleaning_required: bool


@dataclass(frozen=True)
class TerminalCleanup:
    virtual_id: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Schedule:
    placements: tuple[Placement, ...]
    terminal_cleanups: tuple[TerminalCleanup, ...]


@dataclass(frozen=True)
class Verification:
    errors: tuple[str, ...]

    @property
    def valid(self):
        return not self.errors
