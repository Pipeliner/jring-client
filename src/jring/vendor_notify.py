"""Privacy-conscious offline planning for the recovered notification sequence.

This module cannot connect, enqueue, retry, or write.  It intentionally models
only deterministic frame construction and duplicate suppression.  Notification
text is present in an ephemeral plan because it is the wire payload, but it is
never copied into planner state or rendered by ``repr``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import secrets
import unicodedata

from .uuids import VENDOR_CHARACTERISTIC_33F3


_OPCODE = 0x12
_TITLE_BYTES = 17
_CONTENT_BYTES_PER_FRAME = 17
_MAX_CONTENT_BYTES = 253 * _CONTENT_BYTES_PER_FRAME
_UID_MODULUS = 9999
_MAX_NOTIFICATION_ID_BYTES = 256
_DIGEST_KEY_BYTES = 32


class NotifyDisposition(str, Enum):
    PLANNED = "planned"
    DEDUPLICATED = "deduplicated"


@dataclass(frozen=True)
class NotifySafety:
    transport_integration: bool = False
    models_caller_throttle: bool = False
    models_acknowledgement: bool = False
    allows_partial_send: bool = False
    planner_state_retains_raw_notification_data: bool = False
    plan_contains_private_wire_payload: bool = True
    logs_raw_notification_data: bool = False
    live_acknowledgement_has_global_overlap_race: bool = True
    live_effect: str = "wearable_notification_display"


_SAFETY = NotifySafety()


def _utf8(value: str, label: str) -> bytes:
    if type(value) is not str:
        raise TypeError(f"{label} must be a string")
    if unicodedata.normalize("NFC", value) != value or not value.isprintable():
        raise ValueError(f"{label} must be normalized printable text")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError(f"{label} cannot contain control or format characters")
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be valid Unicode text") from exc


def _notification_id_bytes(value: str) -> bytes:
    encoded = _utf8(value, "notification id")
    if not encoded:
        raise ValueError("notification id cannot be empty")
    if len(encoded) > _MAX_NOTIFICATION_ID_BYTES:
        raise ValueError("notification id must fit 256 UTF-8 bytes")
    return encoded


def _notification_digest(key: bytes, value: bytes) -> bytes:
    return hmac.new(key, value, hashlib.sha256).digest()


@dataclass(frozen=True, init=False, repr=False)
class NotifyRequest:
    category: int
    _notification_id: bytes = field(repr=False)
    _title: bytes = field(repr=False)
    _content: bytes = field(repr=False)

    def __init__(self) -> None:
        raise TypeError("notification requests use NotifyRequest.create")

    @classmethod
    def create(
        cls,
        *,
        notification_id: str,
        category: int,
        title: str,
        content: str,
    ) -> "NotifyRequest":
        if type(category) is not int:
            raise TypeError("category must be an integer")
        if not 0 <= category <= 0xFF:
            raise ValueError("category must fit one unsigned byte")

        encoded_id = _notification_id_bytes(notification_id)
        title_bytes = _utf8(title, "title")
        content_bytes = _utf8(content, "content")
        if len(title_bytes) > _TITLE_BYTES:
            raise ValueError("UTF-8 title must fit 17 bytes without truncation")
        if len(content_bytes) > _MAX_CONTENT_BYTES:
            raise ValueError(
                "UTF-8 content must fit 4301 bytes so frame counters remain exact"
            )

        request = object.__new__(cls)
        object.__setattr__(request, "category", category)
        object.__setattr__(request, "_notification_id", encoded_id)
        object.__setattr__(request, "_title", title_bytes)
        object.__setattr__(request, "_content", content_bytes)
        return request

    def __repr__(self) -> str:
        return "NotifyRequest(private_data=<redacted>)"


@dataclass(frozen=True, init=False, repr=False)
class NotifyPlannerState:
    _next_uid: int = field(repr=False)
    _digest_key: bytes = field(repr=False)
    _last_notification_digest: bytes | None = field(repr=False)

    def __init__(self) -> None:
        raise TypeError("notification planner states use closed constructors")

    @classmethod
    def _create(
        cls,
        *,
        next_uid: int,
        digest_key: bytes,
        last_notification_digest: bytes | None,
    ) -> "NotifyPlannerState":
        if type(next_uid) is not int or not 0 <= next_uid < _UID_MODULUS:
            raise ValueError("next UID must be between 0 and 9998")
        if type(digest_key) is not bytes or len(digest_key) != _DIGEST_KEY_BYTES:
            raise ValueError("notification digest key must be 32 bytes")
        if last_notification_digest is not None and (
            type(last_notification_digest) is not bytes
            or len(last_notification_digest) != hashlib.sha256().digest_size
        ):
            raise ValueError("last notification digest must be a SHA-256 digest")
        state = object.__new__(cls)
        object.__setattr__(state, "_next_uid", next_uid)
        object.__setattr__(state, "_digest_key", digest_key)
        object.__setattr__(state, "_last_notification_digest", last_notification_digest)
        return state

    @classmethod
    def initial(cls) -> "NotifyPlannerState":
        return cls._create(
            next_uid=0,
            digest_key=secrets.token_bytes(_DIGEST_KEY_BYTES),
            last_notification_digest=None,
        )

    @classmethod
    def synthetic_for_test(
        cls, *, next_uid: int, last_notification_id: str | None = None
    ) -> "NotifyPlannerState":
        digest_key = hashlib.sha256(b"jring-notify-synthetic-test-key").digest()
        digest = (
            None
            if last_notification_id is None
            else _notification_digest(
                digest_key, _notification_id_bytes(last_notification_id)
            )
        )
        return cls._create(
            next_uid=next_uid,
            digest_key=digest_key,
            last_notification_digest=digest,
        )

    def __repr__(self) -> str:
        return "NotifyPlannerState(private_state=<redacted>)"


@dataclass(frozen=True, init=False, repr=False)
class NotifyPlan:
    disposition: NotifyDisposition
    total_frames: int
    internal_uid: str | None
    proposed_state_after_atomic_enqueue: NotifyPlannerState
    _frames: tuple[bytes, ...] = field(repr=False)

    def __init__(self) -> None:
        raise TypeError("notification plans are produced by plan_notify")

    @classmethod
    def _create(
        cls,
        *,
        disposition: NotifyDisposition,
        internal_uid: str | None,
        proposed_state_after_atomic_enqueue: NotifyPlannerState,
        frames: tuple[bytes, ...],
    ) -> "NotifyPlan":
        if any(len(frame) != 20 for frame in frames):
            raise ValueError("all notification frames must be twenty bytes")
        plan = object.__new__(cls)
        object.__setattr__(plan, "disposition", disposition)
        object.__setattr__(plan, "total_frames", len(frames))
        object.__setattr__(plan, "internal_uid", internal_uid)
        object.__setattr__(
            plan,
            "proposed_state_after_atomic_enqueue",
            proposed_state_after_atomic_enqueue,
        )
        object.__setattr__(plan, "_frames", frames)
        return plan

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def parity_scope(self) -> str:
        return "offline_sequence_and_dedup_only"

    @property
    def safety(self) -> NotifySafety:
        return _SAFETY

    @property
    def known_live_blockers(self) -> tuple[str, ...]:
        return (
            "atomic_multi_frame_delivery",
            "acknowledgement_and_overlap_serialization",
            "caller_throttle_policy",
            "planner_state_serialization",
            "commit_only_after_atomic_delivery",
        )

    def synthetic_frames_for_test(self) -> tuple[bytes, ...]:
        return tuple(bytes(frame) for frame in self._frames)

    def __repr__(self) -> str:
        return (
            "NotifyPlan("
            f"disposition={self.disposition.value!r}, private_frames=<redacted>, "
            "hardware_eligible=False, hardware_verified=False)"
        )


def _frame(*prefix: int, payload: bytes = b"") -> bytes:
    encoded = bytes(prefix) + payload
    if len(encoded) > 20:
        raise ValueError("notification frame exceeds twenty bytes")
    return encoded + bytes(20 - len(encoded))


def plan_notify(state: NotifyPlannerState, request: NotifyRequest) -> NotifyPlan:
    if type(state) is not NotifyPlannerState:
        raise TypeError("state must be a NotifyPlannerState")
    if type(request) is not NotifyRequest:
        raise TypeError("request must be a NotifyRequest")

    state = NotifyPlannerState._create(
        next_uid=state._next_uid,
        digest_key=state._digest_key,
        last_notification_digest=state._last_notification_digest,
    )
    for label, value in (
        ("notification id", request._notification_id),
        ("title", request._title),
        ("content", request._content),
    ):
        if type(value) is not bytes:
            raise ValueError(f"{label} must be encoded bytes")
    notification_id = title = content = None
    try:
        notification_id = request._notification_id.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        pass
    if notification_id is None:
        raise ValueError("notification id must be valid UTF-8 text")
    try:
        title = request._title.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        pass
    if title is None:
        raise ValueError("title must be valid UTF-8 text")
    try:
        content = request._content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        pass
    if content is None:
        raise ValueError("content must be valid UTF-8 text")
    request = NotifyRequest.create(
        notification_id=notification_id,
        category=request.category,
        title=title,
        content=content,
    )

    request_digest = _notification_digest(state._digest_key, request._notification_id)
    if state._last_notification_digest == request_digest:
        return NotifyPlan._create(
            disposition=NotifyDisposition.DEDUPLICATED,
            internal_uid=None,
            proposed_state_after_atomic_enqueue=state,
            frames=(),
        )

    content_chunks = tuple(
        request._content[offset : offset + _CONTENT_BYTES_PER_FRAME]
        for offset in range(0, len(request._content), _CONTENT_BYTES_PER_FRAME)
    ) or (b"",)
    total = 2 + len(content_chunks)
    uid = f"{state._next_uid:04d}"
    frames = [
        _frame(_OPCODE, total, 1, 0, request.category, payload=uid.encode("ascii")),
        _frame(_OPCODE, total, 2, payload=request._title),
    ]
    frames.extend(
        _frame(_OPCODE, total, sequence, payload=chunk)
        for sequence, chunk in enumerate(content_chunks, start=3)
    )
    next_state = NotifyPlannerState._create(
        next_uid=(state._next_uid + 1) % _UID_MODULUS,
        digest_key=state._digest_key,
        last_notification_digest=request_digest,
    )
    return NotifyPlan._create(
        disposition=NotifyDisposition.PLANNED,
        internal_uid=uid,
        proposed_state_after_atomic_enqueue=next_state,
        frames=tuple(frames),
    )
