"""Strict fake-only state machine for one vendor GATT transaction.

The engine emits inert actions for a future reviewed adapter.  It cannot perform BLE
I/O, and none of its actions or operations are hardware eligible.  Setup callbacks,
write callbacks, and application notifications are deliberately separate evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import math
from weakref import WeakKeyDictionary

from .protocol import ProtocolError
from .event_contracts import (
    ContractConfidence,
    ContractProvenance,
    DeadlineState,
    DeviceTimeState,
    ObservationWallTimeState,
    OperationCompletion,
    OperationOutcome,
    OperationReason,
    OperationResult,
    OperationStage,
    RecoveryDirective,
    TerminalBasis,
    create_operation_result,
)
from .transport import GattCharacteristicTarget, GattDescriptorTarget
from .uuids import (
    CLIENT_CHARACTERISTIC_CONFIGURATION,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_56FF,
)
from .vendor_gatt_preflight import (
    VendorGattPreflightResult,
    VendorGattRoute,
)
from .vendor_operation_registry import (
    OperationTerminalStatus,
    operation_registry_entry,
)
from .vendor_runtime_eligibility import require_fake_singleton_terminal
from .vendor_transport import OfflineVendorOperation


class VendorGattEnginePhase(str, Enum):
    DISCONNECTED = "disconnected"
    PRIMARY_SUBSCRIPTION_REQUIRED = "primary_subscription_required"
    OPTIONAL_SUBSCRIPTION_REQUIRED = "optional_subscription_required"
    READY = "ready"
    READY_DEGRADED = "ready_degraded"
    OPERATION_IN_PROGRESS = "operation_in_progress"
    RECONNECT_REQUIRED = "reconnect_required"


class GattActionKind(str, Enum):
    ENABLE_PRIMARY_NOTIFICATIONS = "enable_primary_notifications"
    ENABLE_OPTIONAL_RAW_NOTIFICATIONS = "enable_optional_raw_notifications"
    WRITE_OPERATION = "write_operation"


class GattDispatchOutcome(str, Enum):
    DISPATCHED = "dispatched"
    DEFINITELY_NOT_DISPATCHED = "definitely_not_dispatched"
    OUTCOME_UNKNOWN = "outcome_unknown"


class GattCompletionOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VendorGattNotificationDisposition(str, Enum):
    MATCHED_SUCCESS = "matched_success"
    MATCHED_FAILURE = "matched_failure"
    UNRELATED = "unrelated"
    MALFORMED = "malformed"
    STALE = "stale"
    NOT_IN_FLIGHT = "not_in_flight"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, repr=False, eq=False)
class VendorGattConnectionToken:
    generation: int
    _engine_id: int = field(repr=False)

    def __repr__(self) -> str:
        return f"VendorGattConnectionToken(generation={self.generation!r})"


@dataclass(frozen=True, repr=False, eq=False)
class VendorGattActionToken:
    sequence: int
    connection_generation: int
    _engine_id: int = field(repr=False)

    def __repr__(self) -> str:
        return (
            "VendorGattActionToken("
            f"sequence={self.sequence!r}, connection_generation="
            f"{self.connection_generation!r})"
        )


@dataclass(frozen=True, repr=False, eq=False)
class VendorGattOperationToken:
    sequence: int
    connection_generation: int
    _engine_id: int = field(repr=False)

    def __repr__(self) -> str:
        return (
            "VendorGattOperationToken("
            f"sequence={self.sequence!r}, connection_generation="
            f"{self.connection_generation!r})"
        )


@dataclass(frozen=True)
class _VendorGattActionShape:
    kind: GattActionKind
    token: VendorGattActionToken
    connection_token: VendorGattConnectionToken
    descriptor_target: GattDescriptorTarget | None
    characteristic_target: GattCharacteristicTarget | None
    deadline: float
    operation: OfflineVendorOperation | None


_VENDOR_GATT_ACTION_SHAPES: WeakKeyDictionary[
    object, _VendorGattActionShape
] = WeakKeyDictionary()


class VendorGattAction:
    """Inert exact-target action whose internals are not dataclass-serializable."""

    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor GATT actions are engine-owned")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("vendor GATT actions are immutable")

    @classmethod
    def _create(
        cls,
        kind: GattActionKind,
        token: VendorGattActionToken,
        connection_token: VendorGattConnectionToken,
        descriptor_target: GattDescriptorTarget | None,
        characteristic_target: GattCharacteristicTarget | None,
        deadline: float,
        operation: OfflineVendorOperation | None,
    ) -> "VendorGattAction":
        action = object.__new__(cls)
        _VENDOR_GATT_ACTION_SHAPES[action] = _VendorGattActionShape(
            kind,
            token,
            connection_token,
            descriptor_target,
            characteristic_target,
            deadline,
            operation,
        )
        return action

    def _shape(self) -> _VendorGattActionShape:
        try:
            return _VENDOR_GATT_ACTION_SHAPES[self]
        except KeyError as exc:
            raise ValueError("vendor GATT action identity is unavailable") from exc

    @property
    def kind(self) -> GattActionKind:
        return self._shape().kind

    @property
    def token(self) -> VendorGattActionToken:
        return self._shape().token

    @property
    def connection_token(self) -> VendorGattConnectionToken:
        return self._shape().connection_token

    @property
    def descriptor_target(self) -> GattDescriptorTarget | None:
        return self._shape().descriptor_target

    @property
    def characteristic_target(self) -> GattCharacteristicTarget | None:
        return self._shape().characteristic_target

    @property
    def deadline(self) -> float:
        return self._shape().deadline

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_bytes_for_test(self) -> bytes:
        operation = self._shape().operation
        if self.kind is not GattActionKind.WRITE_OPERATION or operation is None:
            raise TypeError("only a fake write action has synthetic bytes")
        return operation.synthetic_request_for_test()

    def public_payload(self) -> dict[str, object]:
        """Return status-only data with no target, identifier, frame, or value."""

        return {
            "kind": self.kind.value,
            "connection_generation": self.connection_token.generation,
            "deadline_defined": True,
            "has_exact_target": True,
            "hardware_eligible": False,
        }

    def __repr__(self) -> str:
        return (
            "VendorGattAction("
            f"kind={self.kind.value!r}, token={self.token!r}, "
            f"connection_token={self.connection_token!r}, "
            f"has_descriptor_target={self.descriptor_target is not None!r}, "
            f"has_characteristic_target={self.characteristic_target is not None!r}, "
            f"deadline={self.deadline!r}, frame=<redacted>, "
            "hardware_eligible=False)"
        )


class VendorGattOperationClosure:
    __slots__ = (
        "_operation_id",
        "_operation_token",
        "_status",
        "_completeness",
        "_response_outcome",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor GATT closures are engine-owned")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("vendor GATT closures are immutable")

    @classmethod
    def _create(
        cls,
        operation_id: str,
        operation_token: VendorGattOperationToken,
        status: str,
        completeness: str,
        response_outcome: str | None,
    ) -> "VendorGattOperationClosure":
        closure = object.__new__(cls)
        object.__setattr__(closure, "_operation_id", operation_id)
        object.__setattr__(closure, "_operation_token", operation_token)
        object.__setattr__(closure, "_status", status)
        object.__setattr__(closure, "_completeness", completeness)
        object.__setattr__(closure, "_response_outcome", response_outcome)
        return closure

    @property
    def operation_id(self) -> str:
        return self._operation_id

    @property
    def operation_token(self) -> VendorGattOperationToken:
        return self._operation_token

    @property
    def status(self) -> str:
        return self._status

    @property
    def completeness(self) -> str:
        return self._completeness

    @property
    def response_outcome(self) -> str | None:
        return self._response_outcome

    @property
    def replay_allowed(self) -> bool:
        return False

    @property
    def automatic_retry(self) -> str:
        return "prohibited"

    @property
    def hardware_verified(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "VendorGattOperationClosure("
            f"operation_id={self.operation_id!r}, status={self.status!r}, "
            f"completeness={self.completeness!r}, replay_allowed=False, "
            "hardware_verified=False)"
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "completeness": self.completeness,
            "response_outcome": self.response_outcome,
            "replay_allowed": False,
            "automatic_retry": "prohibited",
            "hardware_verified": False,
        }


class StrictVendorGattEngineUpdate:
    """Closed status update with parsed values held outside serializable state."""

    __slots__ = (
        "_action",
        "_status",
        "_completeness",
        "_recovery",
        "_unavailable_capabilities",
        "_notification_disposition",
        "_closure",
        "_connection_phase",
        "_operation_stage",
        "_raw_notifications",
        "_operation_result",
        "__weakref__",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor GATT updates are engine-owned")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("vendor GATT updates are immutable")

    @classmethod
    def _create(
        cls,
        *,
        action: VendorGattAction | None,
        status: str,
        completeness: str | None,
        recovery: str,
        unavailable_capabilities: tuple[str, ...],
        notification_disposition: VendorGattNotificationDisposition | None,
        closure: VendorGattOperationClosure | None,
        connection_phase: VendorGattEnginePhase,
        operation_stage: str | None,
        raw_notifications: str,
        operation_result: OperationResult | None,
        parsed_value: object | None,
    ) -> "StrictVendorGattEngineUpdate":
        update = object.__new__(cls)
        values = {
            "_action": action,
            "_status": status,
            "_completeness": completeness,
            "_recovery": recovery,
            "_unavailable_capabilities": unavailable_capabilities,
            "_notification_disposition": notification_disposition,
            "_closure": closure,
            "_connection_phase": connection_phase,
            "_operation_stage": operation_stage,
            "_raw_notifications": raw_notifications,
            "_operation_result": operation_result,
        }
        for name, value in values.items():
            object.__setattr__(update, name, value)
        if parsed_value is not None:
            _STRICT_UPDATE_PARSED_VALUES[update] = parsed_value
        return update

    @property
    def action(self) -> VendorGattAction | None:
        return self._action

    @property
    def status(self) -> str:
        return self._status

    @property
    def completeness(self) -> str | None:
        return self._completeness

    @property
    def recovery(self) -> str:
        return self._recovery

    @property
    def unavailable_capabilities(self) -> tuple[str, ...]:
        return self._unavailable_capabilities

    @property
    def notification_disposition(self) -> VendorGattNotificationDisposition | None:
        return self._notification_disposition

    @property
    def closure(self) -> VendorGattOperationClosure | None:
        return self._closure

    @property
    def connection_phase(self) -> VendorGattEnginePhase:
        return self._connection_phase

    @property
    def operation_stage(self) -> str | None:
        return self._operation_stage

    @property
    def raw_notifications(self) -> str:
        return self._raw_notifications

    @property
    def operation_result(self) -> OperationResult | None:
        return self._operation_result

    @property
    def input_eligible(self) -> bool:
        return False

    @property
    def replay_allowed(self) -> bool:
        return False

    @property
    def automatic_retry(self) -> str:
        return "prohibited"

    @property
    def parsed_value_for_test(self) -> object | None:
        return _STRICT_UPDATE_PARSED_VALUES.get(self)

    @property
    def response_integrity_valid(self) -> bool | None:
        """Expose only an exact parsed response's integrity verdict."""

        parsed = _STRICT_UPDATE_PARSED_VALUES.get(self)
        value = None if parsed is None else getattr(parsed, "integrity_valid", None)
        return value if type(value) is bool else None

    def __repr__(self) -> str:
        disposition = (
            None
            if self.notification_disposition is None
            else self.notification_disposition.value
        )
        return (
            "StrictVendorGattEngineUpdate("
            f"has_action={self.action is not None!r}, status={self.status!r}, "
            f"completeness={self.completeness!r}, notification_disposition="
            f"{disposition!r}, "
            f"has_closure={self.closure is not None!r}, "
            f"has_parsed_value={self.parsed_value_for_test is not None!r})"
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "completeness": self.completeness,
            "recovery": self.recovery,
            "connection_phase": self.connection_phase.value,
            "operation_stage": self.operation_stage,
            "raw_notifications": self.raw_notifications,
            "unavailable_capabilities": list(self.unavailable_capabilities),
            "notification_disposition": (
                None
                if self.notification_disposition is None
                else self.notification_disposition.value
            ),
            "has_action": self.action is not None,
            "has_closure": self.closure is not None,
            "has_operation_result": self.operation_result is not None,
            "input_eligible": False,
            "replay_allowed": False,
            "automatic_retry": "prohibited",
            "hardware_eligible": False,
        }


_STRICT_UPDATE_PARSED_VALUES: WeakKeyDictionary[
    StrictVendorGattEngineUpdate, object
] = WeakKeyDictionary()


@dataclass
class _OperationState:
    token: VendorGattOperationToken
    operation: OfflineVendorOperation
    deadline: float
    write_dispatched: bool = False
    write_completed: bool = False


_ENGINE_IDS = itertools.count(1)


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("operation timeout must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("operation timeout must be finite and positive")
    return result


class StrictVendorGattTransactionEngine:
    """Serialize exact fake descriptor/write callbacks for one connection."""

    def __init__(self, *, operation_timeout: float = 8.0) -> None:
        self._timeout = _timeout(operation_timeout)
        self._engine_id = next(_ENGINE_IDS)
        self._last_now: float | None = None
        self._last_generation = 0
        self._action_sequence = 0
        self._operation_sequence = 0
        self._result_sequence = 0
        self._phase = VendorGattEnginePhase.DISCONNECTED
        self._connection: VendorGattConnectionToken | None = None
        self._main: VendorGattPreflightResult | None = None
        self._raw: VendorGattPreflightResult | None = None
        self._active_action: VendorGattAction | None = None
        self._action_dispatched = False
        self._operation: _OperationState | None = None
        self._status = "disconnected"
        self._unavailable_capabilities: tuple[str, ...] = ()
        self._raw_notifications = "not_requested"

    @property
    def phase(self) -> VendorGattEnginePhase:
        return self._phase

    @property
    def status(self) -> str:
        return self._status

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def active_operation_token(self) -> VendorGattOperationToken | None:
        return None if self._operation is None else self._operation.token

    def __repr__(self) -> str:
        return (
            "StrictVendorGattTransactionEngine("
            f"phase={self._phase.value!r}, status={self._status!r}, "
            f"has_action={self._active_action is not None!r}, "
            f"has_operation={self._operation is not None!r}, "
            "hardware_eligible=False)"
        )

    def _now(self, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("now must be a monotonic number")
        now = float(value)
        if not math.isfinite(now):
            raise ValueError("monotonic time must be finite")
        if self._last_now is not None and now < self._last_now:
            raise ValueError("monotonic time cannot move backwards")
        self._last_now = now
        return now

    def _update(
        self,
        *,
        action: VendorGattAction | None = None,
        status: str | None = None,
        completeness: str | None = None,
        recovery: str = "none",
        disposition: VendorGattNotificationDisposition | None = None,
        closure: VendorGattOperationClosure | None = None,
        parsed_value: object | None = None,
        operation_stage: str | None = None,
        operation_result: OperationResult | None = None,
    ) -> StrictVendorGattEngineUpdate:
        if status is not None and status not in {
            "stale_callback_ignored",
            "unrelated_notification_ignored",
            "notification_before_write_completion",
        }:
            self._status = status
        if operation_stage is None and self._operation is not None:
            operation_stage = (
                "response" if self._operation.write_completed else "write"
            )
        if closure is not None:
            operation_stage = "complete"
        return StrictVendorGattEngineUpdate._create(
            action=action,
            status=self._status if status is None else status,
            completeness=completeness,
            recovery=recovery,
            unavailable_capabilities=self._unavailable_capabilities,
            notification_disposition=disposition,
            closure=closure,
            connection_phase=self._phase,
            operation_stage=operation_stage,
            raw_notifications=self._raw_notifications,
            operation_result=operation_result,
            parsed_value=parsed_value,
        )

    @staticmethod
    def _require_route(
        value: VendorGattPreflightResult,
        route: VendorGattRoute,
        generation: int | None = None,
    ) -> None:
        if type(value) is not VendorGattPreflightResult:
            raise TypeError("preflight must be an exact VendorGattPreflightResult")
        if value.route is not route or not value.structurally_ready:
            raise ProtocolError(f"{route.value} vendor route is not structurally ready")
        if (
            value.request_target is None
            or value.response_target is None
            or value.cccd_target is None
        ):
            raise ProtocolError(
                f"{route.value} vendor route lacks exact target identity"
            )
        if (
            type(value.request_target) is not GattCharacteristicTarget
            or type(value.response_target) is not GattCharacteristicTarget
            or type(value.cccd_target) is not GattDescriptorTarget
            or not value.cccd_advertised
        ):
            raise ProtocolError(
                f"{route.value} vendor route has invalid target evidence"
            )
        request_uuid, response_uuid = (
            (VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4)
            if route is VendorGattRoute.MAIN
            else (VENDOR_CHARACTERISTIC_33F5, VENDOR_CHARACTERISTIC_33F6)
        )
        if (
            value.request_target.service_uuid != VENDOR_SERVICE_56FF
            or value.request_target.uuid != request_uuid
            or value.response_target.service_uuid != VENDOR_SERVICE_56FF
            or value.response_target.uuid != response_uuid
            or value.cccd_target.service_uuid != VENDOR_SERVICE_56FF
            or value.cccd_target.characteristic_uuid != response_uuid
            or value.cccd_target.uuid != CLIENT_CHARACTERISTIC_CONFIGURATION
        ):
            raise ProtocolError(
                f"{route.value} vendor route target does not match route"
            )
        actual = value.request_target.connection_generation
        if (
            value.response_target.connection_generation != actual
            or value.cccd_target.connection_generation != actual
            or (generation is not None and actual != generation)
        ):
            raise ProtocolError("vendor route target generation mismatch")
        if (
            value.cccd_target.characteristic_instance_id
            != value.response_target.instance_id
            or value.cccd_target.characteristic_uuid != value.response_target.uuid
        ):
            raise ProtocolError("vendor CCCD target does not match response target")

    def _new_action(
        self,
        kind: GattActionKind,
        *,
        deadline: float,
        descriptor: GattDescriptorTarget | None = None,
        characteristic: GattCharacteristicTarget | None = None,
        operation: OfflineVendorOperation | None = None,
    ) -> VendorGattAction:
        assert self._connection is not None
        if not math.isfinite(deadline):
            raise ValueError("calculated action deadline must be finite")
        self._action_sequence += 1
        token = VendorGattActionToken(
            self._action_sequence, self._connection.generation, self._engine_id
        )
        action = VendorGattAction._create(
            kind,
            token,
            self._connection,
            descriptor,
            characteristic,
            deadline,
            operation,
        )
        self._active_action = action
        self._action_dispatched = False
        return action

    def begin_connection(
        self,
        main_preflight: VendorGattPreflightResult,
        *,
        raw_preflight: VendorGattPreflightResult | None = None,
        now: float,
    ) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        if self._phase is not VendorGattEnginePhase.DISCONNECTED:
            raise ProtocolError("record disconnect before beginning another connection")
        self._require_route(main_preflight, VendorGattRoute.MAIN)
        assert main_preflight.request_target is not None
        generation = main_preflight.request_target.connection_generation
        if generation <= self._last_generation:
            raise ProtocolError("connection generation must advance")
        if raw_preflight is not None:
            self._require_route(raw_preflight, VendorGattRoute.RAW, generation)
        self._last_generation = generation
        self._connection = VendorGattConnectionToken(generation, self._engine_id)
        self._main = main_preflight
        self._raw = raw_preflight
        self._operation = None
        self._operation_sequence = 0
        self._result_sequence = 0
        self._unavailable_capabilities = ()
        self._raw_notifications = (
            "requested" if raw_preflight is not None else "not_requested"
        )
        self._phase = VendorGattEnginePhase.PRIMARY_SUBSCRIPTION_REQUIRED
        action = self._new_action(
            GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS,
            descriptor=main_preflight.cccd_target,
            deadline=current + self._timeout,
        )
        return self._update(action=action, status="enabling_primary_notifications")

    def _stale_action(self, token: object) -> bool:
        return (
            type(token) is not VendorGattActionToken
            or token._engine_id != self._engine_id
            or self._connection is None
            or token.connection_generation != self._connection.generation
            or self._active_action is None
            or token is not self._active_action.token
        )

    def _close_operation(
        self,
        status: str,
        completeness: str,
        response_outcome: str | None = None,
    ) -> VendorGattOperationClosure | None:
        state = self._operation
        self._operation = None
        self._active_action = None
        self._action_dispatched = False
        if state is None:
            return None
        return VendorGattOperationClosure._create(
            state.operation.operation_id,
            state.token,
            status,
            completeness,
            response_outcome,
        )

    def _normalized_result(
        self,
        *,
        outcome: OperationOutcome,
        stage: OperationStage,
        completion: OperationCompletion,
        terminal_basis: TerminalBasis,
        reason: OperationReason,
        recovery: RecoveryDirective,
        deadline_state: DeadlineState,
    ) -> OperationResult:
        state = self._operation
        if state is None:
            raise RuntimeError("normalized result requires an active operation")
        self._result_sequence += 1
        return create_operation_result(
            operation_id=state.operation.operation_id,
            sequence=self._result_sequence,
            operation_sequence=state.token.sequence,
            connection_generation=state.token.connection_generation,
            outcome=outcome,
            stage=stage,
            completion=completion,
            terminal_basis=terminal_basis,
            reason=reason,
            recovery=recovery,
            provenance=ContractProvenance.SYNTHETIC,
            confidence=ContractConfidence.STATIC_CANDIDATE,
            wall_time_state=ObservationWallTimeState.NOT_RECORDED,
            device_time_state=DeviceTimeState.NOT_PRESENT,
            deadline_state=deadline_state,
        )

    def _expire(self, now: float) -> StrictVendorGattEngineUpdate | None:
        action = self._active_action
        if action is not None and now >= action.deadline:
            if action.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS:
                self._active_action = None
                self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
                return self._update(
                    status="primary_subscription_timed_out",
                    completeness=(
                        "uncertain" if self._action_dispatched else "aborted"
                    ),
                    recovery="reconnect_then_retry_setup",
                )
            if action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS:
                self._active_action = None
                if self._action_dispatched:
                    self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
                    return self._update(
                        status="optional_raw_subscription_timed_out",
                        completeness="uncertain",
                        recovery="reconnect_then_retry_setup",
                    )
                self._phase = VendorGattEnginePhase.READY_DEGRADED
                self._unavailable_capabilities = ("raw_notifications",)
                self._raw_notifications = "unavailable"
                return self._update(
                    status="optional_raw_subscription_timed_out",
                    completeness="aborted",
                    recovery="continue_without_optional_capability",
                )
        state = self._operation
        if state is not None and now >= state.deadline:
            completeness = "uncertain" if state.write_dispatched else "aborted"
            operation_result = self._normalized_result(
                outcome=(
                    OperationOutcome.UNCERTAIN
                    if state.write_dispatched
                    else OperationOutcome.ABORTED
                ),
                stage=(
                    OperationStage.RESPONSE
                    if state.write_completed
                    else OperationStage.WRITE
                ),
                completion=OperationCompletion.UNKNOWN
                if state.write_dispatched
                else OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
                terminal_basis=TerminalBasis.NOT_OBSERVED
                if state.write_dispatched
                else TerminalBasis.NOT_APPLICABLE,
                reason=OperationReason.TIMEOUT,
                recovery=RecoveryDirective.RECONNECT_NO_REPLAY
                if state.write_dispatched
                else RecoveryDirective.RETRY_AFTER_FIX,
                deadline_state=DeadlineState.EXPIRED,
            )
            closure = self._close_operation("operation_timed_out", completeness)
            self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
            return self._update(
                status="operation_timed_out",
                completeness=completeness,
                recovery=(
                    "reconnect_no_replay"
                    if completeness == "uncertain"
                    else "reconnect_then_retry_setup"
                ),
                closure=closure,
                operation_result=operation_result,
            )
        return None

    def record_dispatch(
        self,
        token: VendorGattActionToken,
        *,
        outcome: GattDispatchOutcome,
        now: float,
    ) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        if type(outcome) is not GattDispatchOutcome:
            raise TypeError("outcome must be an exact GattDispatchOutcome")
        expired = self._expire(current)
        if expired is not None:
            return expired
        if self._stale_action(token):
            return self._update(status="stale_callback_ignored")
        assert self._active_action is not None
        action = self._active_action
        if self._action_dispatched:
            raise ProtocolError("action dispatch was already recorded")
        if outcome is GattDispatchOutcome.DISPATCHED:
            self._action_dispatched = True
            if action.kind is GattActionKind.WRITE_OPERATION:
                assert self._operation is not None
                self._operation.write_dispatched = True
            return self._update(status="action_dispatched")
        if action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS and (
            outcome is GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED
        ):
            self._active_action = None
            self._phase = VendorGattEnginePhase.READY_DEGRADED
            self._unavailable_capabilities = ("raw_notifications",)
            self._raw_notifications = "unavailable"
            return self._update(
                status="optional_raw_subscription_dispatch_rejected",
                completeness="aborted",
                recovery="continue_without_optional_capability",
            )
        if action.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS:
            self._active_action = None
            self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
            return self._update(
                status=(
                    "primary_subscription_dispatch_rejected"
                    if outcome is GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED
                    else "primary_subscription_dispatch_unknown"
                ),
                completeness=(
                    "aborted"
                    if outcome is GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED
                    else "uncertain"
                ),
                recovery="reconnect_then_retry_setup",
            )
        if action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS:
            self._active_action = None
            self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
            return self._update(
                status="optional_raw_subscription_dispatch_unknown",
                completeness="uncertain",
                recovery="reconnect_then_retry_setup",
            )
        completeness = (
            "aborted"
            if outcome is GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED
            else "uncertain"
        )
        operation_result = self._normalized_result(
            outcome=(
                OperationOutcome.ABORTED
                if completeness == "aborted"
                else OperationOutcome.UNCERTAIN
            ),
            stage=OperationStage.WRITE,
            completion=(
                OperationCompletion.TERMINAL_WITHOUT_SUCCESS
                if completeness == "aborted"
                else OperationCompletion.UNKNOWN
            ),
            terminal_basis=(
                TerminalBasis.NOT_APPLICABLE
                if completeness == "aborted"
                else TerminalBasis.NOT_OBSERVED
            ),
            reason=(
                OperationReason.PRE_DISPATCH_FAILURE
                if completeness == "aborted"
                else OperationReason.TRANSPORT_FAILURE
            ),
            recovery=(
                RecoveryDirective.RETRY_AFTER_FIX
                if completeness == "aborted"
                else RecoveryDirective.RECONNECT_NO_REPLAY
            ),
            deadline_state=(
                DeadlineState.NOT_APPLICABLE
                if completeness == "aborted"
                else DeadlineState.CANCELLED
            ),
        )
        closure = self._close_operation("operation_write_failed", completeness)
        self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
        return self._update(
            status="operation_write_failed",
            completeness=completeness,
            recovery=(
                "reconnect_no_replay"
                if completeness == "uncertain"
                else "reconnect_then_retry_setup"
            ),
            closure=closure,
            operation_result=operation_result,
        )

    def record_completion(
        self,
        token: VendorGattActionToken,
        *,
        target: GattDescriptorTarget | GattCharacteristicTarget,
        outcome: GattCompletionOutcome,
        now: float,
    ) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        if type(outcome) is not GattCompletionOutcome:
            raise TypeError("outcome must be an exact GattCompletionOutcome")
        expired = self._expire(current)
        if expired is not None:
            return expired
        if self._stale_action(token):
            return self._update(status="stale_callback_ignored")
        assert self._active_action is not None
        action = self._active_action
        expected_target = action.descriptor_target or action.characteristic_target
        if target is not expected_target:
            raise ProtocolError("completion target does not match exact action target")
        if not self._action_dispatched:
            raise ProtocolError("action completion arrived before dispatch")
        if outcome is GattCompletionOutcome.FAILED:
            if action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS:
                self._active_action = None
                self._action_dispatched = False
                self._phase = VendorGattEnginePhase.READY_DEGRADED
                self._unavailable_capabilities = ("raw_notifications",)
                self._raw_notifications = "unavailable"
                return self._update(
                    status="optional_raw_subscription_failed",
                    completeness="aborted",
                    recovery="continue_without_optional_capability",
                )
            if action.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS:
                self._active_action = None
                self._action_dispatched = False
                self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
                return self._update(
                    status="primary_subscription_failed",
                    completeness="aborted",
                    recovery="reconnect_then_retry_setup",
                )
            operation_result = self._normalized_result(
                outcome=OperationOutcome.UNCERTAIN,
                stage=OperationStage.WRITE,
                completion=OperationCompletion.UNKNOWN,
                terminal_basis=TerminalBasis.NOT_OBSERVED,
                reason=OperationReason.TRANSPORT_FAILURE,
                recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
                deadline_state=DeadlineState.CANCELLED,
            )
            closure = self._close_operation("operation_write_failed", "uncertain")
            self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
            return self._update(
                status="operation_write_failed",
                completeness="uncertain",
                recovery="reconnect_no_replay",
                closure=closure,
                operation_result=operation_result,
            )
        self._active_action = None
        self._action_dispatched = False
        if action.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS:
            if self._raw is not None:
                self._phase = VendorGattEnginePhase.OPTIONAL_SUBSCRIPTION_REQUIRED
                self._raw_notifications = "enabling"
                optional = self._new_action(
                    GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS,
                    descriptor=self._raw.cccd_target,
                    deadline=current + self._timeout,
                )
                return self._update(
                    action=optional, status="enabling_optional_raw_notifications"
                )
            self._phase = VendorGattEnginePhase.READY
            return self._update(status="ready")
        if action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS:
            self._phase = VendorGattEnginePhase.READY
            self._raw_notifications = "active"
            return self._update(status="ready")
        assert self._operation is not None
        self._operation.write_completed = True
        self._phase = VendorGattEnginePhase.OPERATION_IN_PROGRESS
        operation_result = self._normalized_result(
            outcome=OperationOutcome.ACCEPTED,
            stage=OperationStage.WRITE,
            completion=OperationCompletion.IN_PROGRESS,
            terminal_basis=TerminalBasis.NOT_OBSERVED,
            reason=OperationReason.NONE,
            recovery=RecoveryDirective.NONE,
            deadline_state=DeadlineState.ACTIVE,
        )
        return self._update(
            status="waiting_for_application_response",
            operation_result=operation_result,
        )

    def start_operation(
        self, operation: OfflineVendorOperation, *, now: float
    ) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        if self._phase is VendorGattEnginePhase.RECONNECT_REQUIRED:
            raise ProtocolError("reconnect before starting another vendor operation")
        if self._phase not in {
            VendorGattEnginePhase.READY,
            VendorGattEnginePhase.READY_DEGRADED,
        }:
            raise ProtocolError("vendor connection is not ready for an operation")
        if type(operation) is not OfflineVendorOperation:
            raise TypeError("operation must be an exact OfflineVendorOperation")
        operation.validate_for_fake_execution()
        require_fake_singleton_terminal(operation.operation_id)
        entry = operation_registry_entry(operation.operation_id)
        if (
            not entry.ring_facing
            or entry.terminal_status is not OperationTerminalStatus.OFFLINE_ONLY
            or entry.interface_route != "main_command"
            or entry.endpoint_role != "main_tx_rx"
            or entry.response_terminal_rule != "single_matched_response"
            or entry.live_eligible
            or entry.hardware_verified
        ):
            raise ProtocolError("operation is not eligible for strict fake execution")
        assert self._connection is not None and self._main is not None
        self._operation_sequence += 1
        token = VendorGattOperationToken(
            self._operation_sequence,
            self._connection.generation,
            self._engine_id,
        )
        deadline = current + self._timeout
        if not math.isfinite(deadline):
            raise ValueError("calculated operation deadline must be finite")
        self._operation = _OperationState(token, operation, deadline)
        self._phase = VendorGattEnginePhase.OPERATION_IN_PROGRESS
        action = self._new_action(
            GattActionKind.WRITE_OPERATION,
            characteristic=self._main.request_target,
            deadline=deadline,
            operation=operation,
        )
        return self._update(action=action, status="operation_write_required")

    def receive_notification(
        self,
        connection_token: VendorGattConnectionToken,
        target: GattCharacteristicTarget,
        data: bytes,
        *,
        now: float,
    ) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        if connection_token is not self._connection:
            return self._update(
                status="stale_callback_ignored",
                disposition=VendorGattNotificationDisposition.STALE,
            )
        expired = self._expire(current)
        if expired is not None:
            return StrictVendorGattEngineUpdate._create(
                action=expired.action,
                status=expired.status,
                completeness=expired.completeness,
                recovery=expired.recovery,
                unavailable_capabilities=expired.unavailable_capabilities,
                notification_disposition=VendorGattNotificationDisposition.TIMED_OUT,
                closure=expired.closure,
                connection_phase=expired.connection_phase,
                operation_stage=expired.operation_stage,
                raw_notifications=expired.raw_notifications,
                operation_result=expired.operation_result,
                parsed_value=None,
            )
        if self._operation is None:
            return self._update(
                status="stale_callback_ignored",
                disposition=VendorGattNotificationDisposition.STALE,
            )
        assert self._main is not None
        if self._raw is not None and target is self._raw.response_target:
            return self._update(
                status="unrelated_notification_ignored",
                disposition=VendorGattNotificationDisposition.UNRELATED,
            )
        if target is not self._main.response_target:
            raise ProtocolError(
                "notification target does not match exact response target"
            )
        if not self._operation.write_completed:
            return self._update(
                status="notification_before_write_completion",
                disposition=VendorGattNotificationDisposition.NOT_IN_FLIGHT,
            )
        try:
            match, parsed = self._operation.operation._match(target.uuid, data)
        except ProtocolError:
            operation_result = self._normalized_result(
                outcome=OperationOutcome.UNCERTAIN,
                stage=OperationStage.RESPONSE,
                completion=OperationCompletion.UNKNOWN,
                terminal_basis=TerminalBasis.NOT_OBSERVED,
                reason=OperationReason.MALFORMED_RESPONSE,
                recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
                deadline_state=DeadlineState.CANCELLED,
            )
            closure = self._close_operation("operation_malformed_response", "uncertain")
            self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
            return self._update(
                status="operation_malformed_response",
                completeness="uncertain",
                recovery="reconnect_no_replay",
                disposition=VendorGattNotificationDisposition.MALFORMED,
                closure=closure,
                operation_result=operation_result,
            )
        if match.value == "unrelated":
            return self._update(
                status="unrelated_notification_ignored",
                disposition=VendorGattNotificationDisposition.UNRELATED,
            )
        disposition = (
            VendorGattNotificationDisposition.MATCHED_SUCCESS
            if match.value == "success"
            else VendorGattNotificationDisposition.MATCHED_FAILURE
        )
        status = (
            "operation_response_matched"
            if match.value == "success"
            else "operation_device_failure_matched"
        )
        completeness = "response_matched"
        response_outcome = (
            "exact_success" if match.value == "success" else "exact_failure"
        )
        operation_result = self._normalized_result(
            outcome=OperationOutcome.RESPONSE_MATCHED,
            stage=OperationStage.COMPLETE,
            completion=(
                OperationCompletion.SUCCEEDED
                if match.value == "success"
                else OperationCompletion.TERMINAL_WITHOUT_SUCCESS
            ),
            terminal_basis=(
                TerminalBasis.EXACT_SUCCESS_RESPONSE
                if match.value == "success"
                else TerminalBasis.EXACT_FAILURE_RESPONSE
            ),
            reason=(
                OperationReason.NONE
                if match.value == "success"
                else OperationReason.DEVICE_REJECTED
            ),
            recovery=RecoveryDirective.NONE,
            deadline_state=DeadlineState.SATISFIED,
        )
        closure = self._close_operation(status, completeness, response_outcome)
        self._phase = VendorGattEnginePhase.RECONNECT_REQUIRED
        return self._update(
            status=status,
            completeness=completeness,
            recovery="disconnect_then_new_connection",
            disposition=disposition,
            closure=closure,
            parsed_value=parsed,
            operation_result=operation_result,
        )

    def record_disconnected(
        self, connection_token: VendorGattConnectionToken, *, now: float
    ) -> StrictVendorGattEngineUpdate:
        self._now(now)
        if connection_token is not self._connection:
            return self._update(status="stale_callback_ignored")
        completeness: str | None = None
        closure = None
        operation_result = None
        status = "disconnected"
        if self._operation is not None:
            state = self._operation
            completeness = (
                "uncertain" if state.write_dispatched else "aborted"
            )
            status = "operation_disconnected"
            operation_result = self._normalized_result(
                outcome=(
                    OperationOutcome.UNCERTAIN
                    if state.write_dispatched
                    else OperationOutcome.ABORTED
                ),
                stage=(
                    OperationStage.RESPONSE
                    if state.write_completed
                    else OperationStage.WRITE
                ),
                completion=(
                    OperationCompletion.UNKNOWN
                    if state.write_dispatched
                    else OperationCompletion.TERMINAL_WITHOUT_SUCCESS
                ),
                terminal_basis=(
                    TerminalBasis.NOT_OBSERVED
                    if state.write_dispatched
                    else TerminalBasis.NOT_APPLICABLE
                ),
                reason=OperationReason.DISCONNECTED,
                recovery=(
                    RecoveryDirective.RECONNECT_NO_REPLAY
                    if state.write_dispatched
                    else RecoveryDirective.RETRY_AFTER_FIX
                ),
                deadline_state=DeadlineState.CANCELLED,
            )
            closure = self._close_operation(status, completeness)
        elif self._active_action is not None and self._active_action.kind in {
            GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS,
            GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS,
        }:
            status = (
                "disconnected_during_primary_subscription"
                if self._active_action.kind
                is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS
                else "disconnected_during_optional_raw_subscription"
            )
            completeness = "uncertain" if self._action_dispatched else "aborted"
        self._active_action = None
        self._action_dispatched = False
        self._operation = None
        self._connection = None
        self._main = None
        self._raw = None
        self._unavailable_capabilities = ()
        self._raw_notifications = "not_requested"
        self._phase = VendorGattEnginePhase.DISCONNECTED
        return self._update(
            status=status,
            completeness=completeness,
            recovery=(
                "reconnect_then_retry_setup"
                if closure is None and completeness is not None
                else
                "reconnect_no_replay"
                if completeness == "uncertain"
                else "reconnect_then_retry_setup"
                if completeness == "aborted"
                else "none"
            ),
            closure=closure,
            operation_result=operation_result,
        )

    def poll(self, *, now: float) -> StrictVendorGattEngineUpdate:
        current = self._now(now)
        expired = self._expire(current)
        return self._update() if expired is None else expired


__all__ = [
    "GattActionKind",
    "GattCompletionOutcome",
    "GattDispatchOutcome",
    "StrictVendorGattEngineUpdate",
    "StrictVendorGattTransactionEngine",
    "VendorGattAction",
    "VendorGattActionToken",
    "VendorGattConnectionToken",
    "VendorGattEnginePhase",
    "VendorGattNotificationDisposition",
    "VendorGattOperationClosure",
    "VendorGattOperationToken",
]
