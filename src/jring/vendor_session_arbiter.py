"""Pure generation-bound arbitration between a transaction and neutral events."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vendor_callback_event_registry import recovered_callback_event_registry


class ArbiterRoute(str, Enum):
    TRANSACTION = "transaction"
    NEUTRAL_EVENT = "neutral_event"
    STALE = "stale"
    OVERFLOW = "overflow"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, init=False, repr=False)
class ArbiterToken:
    generation: int
    _owner: int

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("arbiter tokens are owned")


class VendorSessionArbiter:
    """One in-memory connection generation; never a transport or event executor."""

    def __init__(self, *, maximum_neutral_events: int = 64) -> None:
        if type(maximum_neutral_events) is not int or not 1 <= maximum_neutral_events <= 1024:
            raise ValueError("invalid_neutral_event_limit")
        self._owner = id(self)
        self._generation = 0
        self._closed = True
        self._subscriptions: set[str] = set()
        self._transaction_callback: str | None = None
        self._neutral_count = 0
        self._limit = maximum_neutral_events
        self._known_callbacks = frozenset(
            row.callback_id for row in recovered_callback_event_registry()
        )

    def begin(self) -> ArbiterToken:
        if not self._closed:
            raise RuntimeError("connection_generation_active")
        self._generation += 1
        self._closed = False
        self._subscriptions.clear()
        self._transaction_callback = None
        self._neutral_count = 0
        return self._token()

    def subscribe(self, token: ArbiterToken, *, target: str) -> None:
        self._require(token)
        if type(target) is not str or target not in {"main", "raw"}:
            raise ValueError("unknown_subscription_target")
        if target in self._subscriptions:
            raise RuntimeError("duplicate_subscription")
        self._subscriptions.add(target)

    def claim_transaction_callback(self, token: ArbiterToken, *, callback_id: str) -> None:
        self._require(token)
        if (
            not self._subscriptions
            or type(callback_id) is not str
            or callback_id not in self._known_callbacks
        ):
            raise ValueError("invalid_transaction_callback")
        if self._transaction_callback is not None:
            raise RuntimeError("transaction_already_claimed")
        self._transaction_callback = callback_id

    def route_callback(self, token: ArbiterToken, *, callback_id: str) -> ArbiterRoute:
        if not self._valid(token):
            return ArbiterRoute.STALE
        if self._closed:
            return ArbiterRoute.CLOSED
        if type(callback_id) is not str or callback_id not in self._known_callbacks:
            return ArbiterRoute.UNKNOWN
        if callback_id == self._transaction_callback:
            return ArbiterRoute.TRANSACTION
        self._neutral_count += 1
        return ArbiterRoute.OVERFLOW if self._neutral_count > self._limit else ArbiterRoute.NEUTRAL_EVENT

    def close(self, token: ArbiterToken) -> None:
        self._require(token)
        self._closed = True
        self._subscriptions.clear()
        self._transaction_callback = None

    def _token(self) -> ArbiterToken:
        token = object.__new__(ArbiterToken)
        object.__setattr__(token, "generation", self._generation)
        object.__setattr__(token, "_owner", self._owner)
        return token

    def _valid(self, token: object) -> bool:
        return type(token) is ArbiterToken and token._owner == self._owner and token.generation == self._generation

    def _require(self, token: object) -> None:
        if not self._valid(token):
            raise ValueError("stale_or_forged_generation")
        if self._closed:
            raise RuntimeError("connection_generation_closed")
