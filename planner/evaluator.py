"""Same deterministic scenario arithmetic for baseline and proposal."""

from dataclasses import dataclass
from decimal import Decimal

from planner.verifier import verify_schedule


@dataclass(frozen=True)
class ResourceUse:
    process_a: Decimal
    process_b: Decimal
    cleaning_before_orders: Decimal
    terminal_cleaning: Decimal
    cleaning_events: int

    @property
    def total(self):
        return self.process_a + self.process_b + self.cleaning_before_orders + self.terminal_cleaning


def evaluate_resources(orders, config, schedule):
    verification = verify_schedule(orders, config, schedule)
    if not verification.valid:
        raise ValueError("Cannot evaluate an invalid schedule: " + "; ".join(verification.errors))
    quantity = sum((o.quantity for o in orders), Decimal(0))
    washes = sum(p.cleaning_required for p in schedule.placements)
    terminal = len(schedule.terminal_cleanups)
    return ResourceUse(quantity * config.process_a_per_quantity, quantity * config.process_b_per_quantity,
                       washes * config.cleaning_water, terminal * config.cleaning_water, washes + terminal)
