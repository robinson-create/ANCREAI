"""Budget manager — tracks token consumption within an agent run.

Provides:
- Global token budget per run (set at creation, decremented per LLM call)
- Reservation envelopes for delegation (carve out a sub-budget for child runs)
- Budget exhaustion detection (raises BudgetExhausted before over-spending)

The BudgetManager is a lightweight in-memory object, one per run.  It does NOT
persist state itself — the caller is responsible for flushing remaining budget
back to the DB (via run_service) when the run completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Default budgets per profile ─────────────────────────────────────

_PROFILE_BUDGETS: dict[str, int] = {
    "reactive": 8_000,
    "balanced": 30_000,
    "pro": 80_000,
    "exec": 200_000,
}


def default_budget_for_profile(profile: str) -> int:
    """Return the default token budget for a given profile."""
    return _PROFILE_BUDGETS.get(profile, _PROFILE_BUDGETS["reactive"])


# ── Exceptions ──────────────────────────────────────────────────────


class BudgetExhausted(Exception):
    """Raised when a run has exhausted its token budget."""

    def __init__(self, requested: int, remaining: int) -> None:
        self.requested = requested
        self.remaining = remaining
        super().__init__(
            f"Budget exhausted: requested {requested} tokens, "
            f"only {remaining} remaining"
        )


class ReservationError(Exception):
    """Raised when a budget reservation cannot be made."""


# ── Reservation envelope ────────────────────────────────────────────


@dataclass
class Reservation:
    """A carved-out sub-budget for delegation or tool execution."""

    label: str
    allocated: int
    consumed: int = 0

    @property
    def remaining(self) -> int:
        return self.allocated - self.consumed

    def consume(self, tokens: int) -> None:
        if tokens > self.remaining:
            raise BudgetExhausted(requested=tokens, remaining=self.remaining)
        self.consumed += tokens


# ── Budget manager ──────────────────────────────────────────────────


@dataclass
class BudgetManager:
    """In-memory budget tracker for a single agent run.

    Usage::

        bm = BudgetManager(total=30_000)

        # Before each LLM call, check & consume
        bm.consume(prompt_tokens + completion_tokens)

        # For delegation, reserve a chunk
        res = bm.reserve("child_search", 5_000)
        # ... child run uses res.consume() ...
        bm.release(res)  # return unused tokens
    """

    total: int
    consumed: int = 0
    _reservations: dict[str, Reservation] = field(default_factory=dict)

    # ── Core budget ─────────────────────────────────────────────

    @property
    def remaining(self) -> int:
        """Tokens available (minus active reservations)."""
        reserved = sum(r.remaining for r in self._reservations.values())
        return self.total - self.consumed - reserved

    @property
    def hard_remaining(self) -> int:
        """Tokens remaining ignoring reservations (total - consumed)."""
        return self.total - self.consumed

    def check(self, tokens: int) -> bool:
        """Check if `tokens` can be consumed without raising."""
        return tokens <= self.remaining

    def consume(self, tokens: int) -> None:
        """Consume tokens from the global budget.

        Raises BudgetExhausted if insufficient budget.
        """
        if tokens > self.remaining:
            raise BudgetExhausted(requested=tokens, remaining=self.remaining)
        self.consumed += tokens

    def consume_safe(self, tokens: int) -> bool:
        """Consume tokens if available, return False if not (no exception)."""
        if tokens > self.remaining:
            return False
        self.consumed += tokens
        return True

    # ── Reservations ────────────────────────────────────────────

    def reserve(self, label: str, tokens: int) -> Reservation:
        """Reserve tokens for a sub-task (e.g. delegation).

        Reserved tokens are subtracted from `remaining` but not from `consumed`.
        Call `release()` when the sub-task completes to return unused tokens.
        """
        if label in self._reservations:
            raise ReservationError(f"Reservation '{label}' already exists")
        if tokens > self.remaining:
            raise BudgetExhausted(requested=tokens, remaining=self.remaining)

        reservation = Reservation(label=label, allocated=tokens)
        self._reservations[label] = reservation
        return reservation

    def release(self, reservation: Reservation) -> int:
        """Release a reservation, consuming only what was used.

        Returns the number of tokens returned to the pool.
        """
        if reservation.label not in self._reservations:
            raise ReservationError(
                f"Reservation '{reservation.label}' not found"
            )

        # The consumed part of the reservation becomes consumed in global budget
        self.consumed += reservation.consumed
        returned = reservation.remaining

        del self._reservations[reservation.label]

        logger.debug(
            "budget_reservation_released",
            label=reservation.label,
            allocated=reservation.allocated,
            consumed=reservation.consumed,
            returned=returned,
        )

        return returned

    # ── Introspection ───────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return a serializable snapshot of the budget state."""
        return {
            "total": self.total,
            "consumed": self.consumed,
            "remaining": self.remaining,
            "hard_remaining": self.hard_remaining,
            "reservations": {
                label: {
                    "allocated": r.allocated,
                    "consumed": r.consumed,
                    "remaining": r.remaining,
                }
                for label, r in self._reservations.items()
            },
        }
