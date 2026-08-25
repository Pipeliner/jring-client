"""Closed static evidence for the recovered Android SDK session sequencing.

This graph documents source ordering and races.  It accepts no device identity,
credentials, time, UUID, payload, or callback and has no transport, network, encoder,
or parser integration.  Source behavior is evidence, not a recommended runtime plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceLane(str, Enum):
    SDK_VALIDATION = "sdk_validation"
    CALLBACK_REGISTRATION = "callback_registration"
    BLE_LINK = "ble_link"
    SERVICE_DISCOVERY = "service_discovery"
    MAIN_NOTIFICATION = "main_notification"
    STARTUP_CLOCK_SYNC = "startup_clock_sync"
    DEVICE_POLICY = "device_policy"
    VENDOR_BINDING = "vendor_binding"
    CLASSIC_BOND = "classic_bond"
    COMMAND_QUEUE = "command_queue"
    RECONNECT = "reconnect"


class EvidenceState(str, Enum):
    SERVICE_CREATED_WITH_DEFAULT_SDK_STATUS = "service_created_with_default_sdk_status"
    REMEMBERED_TARGET_RECONNECT_STARTED = "remembered_target_reconnect_started"
    CALLBACK_REGISTERED = "callback_registered"
    SDK_VALIDATION_CACHE_REPORTED = "sdk_validation_cache_reported"
    SDK_VALIDATION_REQUEST_PENDING = "sdk_validation_request_pending"
    SDK_VALIDATION_RESULT_APPLIED = "sdk_validation_result_applied"
    MANUAL_CONNECT_GATE_CHECKED = "manual_connect_gate_checked"
    GATT_CONNECTING = "gatt_connecting"
    LINK_CONNECTED = "link_connected"
    SERVICE_DISCOVERY_PENDING = "service_discovery_pending"
    SERVICE_DISCOVERY_RETRYING = "service_discovery_retrying"
    SERVICES_ACCEPTED_AND_QUEUE_CLEARED = "services_accepted_and_queue_cleared"
    CHARACTERISTIC_INITIALIZATION_DELAYED = "characteristic_initialization_delayed"
    MAIN_NOTIFICATION_DISPATCH_ACCEPTED = "main_notification_dispatch_accepted"
    SOURCE_CONNECTED_REPORTED = "source_connected_reported"
    DESCRIPTOR_SPECIAL_FAILURE = "descriptor_special_failure"
    DESCRIPTOR_OTHER_RESULT_OBSERVED = "descriptor_other_result_observed"
    STARTUP_CLOCK_SYNC_QUEUED = "startup_clock_sync_queued"
    DEVICE_POLICY_CACHE_CHECKED = "device_policy_cache_checked"
    DEVICE_POLICY_CACHED_ALLOW_REPORTED = "device_policy_cached_allow_reported"
    DEVICE_POLICY_REQUEST_PENDING = "device_policy_request_pending"
    DEVICE_POLICY_ALLOW_RECORDED = "device_policy_allow_recorded"
    DEVICE_POLICY_DENY_CLOSES_LINK = "device_policy_deny_closes_link"
    BINDING_NOTIFICATION_OBSERVED = "binding_notification_observed"
    VENDOR_BINDING_START_SENT = "vendor_binding_start_sent"
    VENDOR_BINDING_SUCCESS_SENT = "vendor_binding_success_sent"
    VENDOR_BINDING_CONFIRMED = "vendor_binding_confirmed"
    VENDOR_UNBIND_SENT = "vendor_unbind_sent"
    VENDOR_UNBOUND_ACKNOWLEDGED = "vendor_unbound_acknowledged"
    DISCONNECTED = "disconnected"
    RECONNECT_SCHEDULED = "reconnect_scheduled"


class SessionTransitionCode(str, Enum):
    DEFAULT_SDK_STATUS = "default_sdk_status"
    REMEMBERED_TARGET_RECONNECT = "remembered_target_reconnect"
    REGISTER_BUNDLED_CREDENTIAL_CALLBACK = "register_bundled_credential_callback"
    REGISTER_CALLER_CREDENTIAL_CALLBACK = "register_caller_credential_callback"
    REPORT_CACHED_SDK_STATUS = "report_cached_sdk_status"
    REQUEST_BUNDLED_SDK_VALIDATION = "request_bundled_sdk_validation"
    REQUEST_CALLER_SDK_VALIDATION = "request_caller_sdk_validation"
    APPLY_SDK_VALIDATION_RESULT = "apply_sdk_validation_result"
    CHECK_MANUAL_CONNECT_GATE = "check_manual_connect_gate"
    START_GATT_CONNECT = "start_gatt_connect"
    OBSERVE_GATT_LINK = "observe_gatt_link"
    START_SERVICE_DISCOVERY = "start_service_discovery"
    RETRY_SERVICE_DISCOVERY = "retry_service_discovery"
    ACCEPT_SERVICES = "accept_services"
    DELAY_CHARACTERISTIC_INITIALIZATION = "delay_characteristic_initialization"
    ACCEPT_NOTIFICATION_DISPATCH = "accept_notification_dispatch"
    REPORT_SOURCE_CONNECTED = "report_source_connected"
    CHECK_DEVICE_POLICY_CACHE = "check_device_policy_cache"
    REPORT_CACHED_DEVICE_ALLOW = "report_cached_device_allow"
    REQUEST_DEVICE_POLICY = "request_device_policy"
    RECORD_DEVICE_ALLOW = "record_device_allow"
    CLOSE_ON_DEVICE_DENY = "close_on_device_deny"
    HANDLE_DESCRIPTOR_SPECIAL_FAILURE = "handle_descriptor_special_failure"
    OBSERVE_DESCRIPTOR_OTHER_RESULT = "observe_descriptor_other_result"
    QUEUE_STARTUP_CLOCK_SYNC = "queue_startup_clock_sync"
    OBSERVE_BINDING_NOTIFICATION = "observe_binding_notification"
    SEND_BINDING_START = "send_binding_start"
    SEND_BINDING_SUCCESS = "send_binding_success"
    CONFIRM_VENDOR_BINDING = "confirm_vendor_binding"
    SEND_VENDOR_UNBIND = "send_vendor_unbind"
    ACKNOWLEDGE_VENDOR_UNBOUND = "acknowledge_vendor_unbound"
    RECORD_DISCONNECT = "record_disconnect"
    SCHEDULE_RECONNECT = "schedule_reconnect"


class SourceReadinessClaim(str, Enum):
    NONE = "none"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CALLBACK_RESULT_ONLY = "callback_result_only"


class SourceBindingAction(str, Enum):
    INIT = "source_named_init"
    APP_START = "source_named_app_start"
    ACK = "source_named_ack"
    ACK_CANCEL = "source_named_ack_cancel"
    SUCCESS = "source_named_success"
    UNBIND = "source_named_unbind"
    UNBIND_ACK = "source_named_unbind_ack"


class SessionRaceCode(str, Enum):
    CONCURRENT_REGISTRATION_REPLACES_CALLBACK = "concurrent_registration_replaces_callback_slot"
    FUTURE_VALIDATION_TIMESTAMP_PASSES_CACHE = "future_validation_timestamp_passes_cache_check"
    STARTUP_RECONNECT_PRECEDES_CALLBACK = "startup_reconnect_precedes_callback_registration"
    MANUAL_CONNECT_DOES_NOT_AWAIT_VALIDATION = "manual_connect_does_not_await_sdk_validation"
    VALIDATION_ERROR_PRESERVES_GATE = "sdk_validation_transport_error_does_not_replace_runtime_gate"
    CONNECTED_PRECEDES_DESCRIPTOR_CALLBACK = "source_connected_precedes_descriptor_callback"
    DEVICE_POLICY_AFTER_CONNECTED = "device_authorization_starts_after_source_connected"
    DEVICE_POLICY_CALLBACK_CONFLATES_DOMAINS = "device_authorization_callback_conflates_status_domains"
    DYNAMIC_DESCRIPTORS_NOT_SERIALIZED = "conditional_dynamic_descriptor_writes_are_not_serialized"
    NON_SPECIAL_DESCRIPTOR_STARTS_CLOCK = "descriptor_non_special_status_triggers_clock_sync"
    BINDING_INTERLEAVES_COMMAND_QUEUE = "binding_response_can_interleave_with_command_queue"
    CALLBACKS_HAVE_NO_GENERATION = "callbacks_are_not_connection_generation_bound"
    LATE_CLOUD_RESULT = "late_cloud_result_can_affect_a_later_connection"
    CLASSIC_BOND_IS_ORTHOGONAL = "classic_bonding_is_orthogonal_to_vendor_binding"
    DISCOVERY_EXHAUSTION_ENTERS_RECOVERY = "discovery_exhaustion_enters_recovery"
    MISSING_ENDPOINTS_ENTER_DELAYED_RECOVERY = "missing_endpoints_enter_delayed_recovery"
    DESCRIPTOR_DISPATCH_FALSE_DISCONNECTS = "descriptor_dispatch_false_disconnects"
    STALE_GATT_CALLBACK_TARGETS_CURRENT_LINK = "stale_gatt_callback_can_target_current_link"
    WRITE_FALSE_RETRY_STORM = "synchronous_write_false_retries_up_to_31_calls"
    WRITE_CALLBACK_STATUS_IGNORED = "write_callback_status_is_ignored"
    ACCEPTED_WRITE_CALLBACK_LOSS = "accepted_write_without_callback_has_uncertain_outcome"
    DORMANT_RESPONSE_MATCHING_IS_GLOBAL = "dormant_response_matching_is_global_not_operation_bound"


def _closed_instance(cls: type, **values: object) -> object:
    instance = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


@dataclass(frozen=True, init=False, repr=False)
class StaticSessionSafety:
    radio_access: bool
    network_access: bool
    filesystem_access: bool
    accepts_device_identity: bool
    accepts_credentials: bool
    exposes_frame_bytes: bool
    transport_integration: bool
    owner_authority: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("session safety is closed static evidence")


@dataclass(frozen=True, init=False, repr=False)
class SessionTransitionEvidence:
    code: SessionTransitionCode
    lane: EvidenceLane
    prerequisites: tuple[EvidenceState, ...]
    result: EvidenceState
    related_requests: tuple[str, ...]
    related_callbacks: tuple[str, ...]
    source_effects: tuple[str, ...]
    source_readiness_claim: SourceReadinessClaim
    directly_touches_cloud: bool
    directly_touches_bluetooth: bool
    source_performs_vendor_write: bool
    descriptor_acknowledged: bool
    owner_authorized: bool
    hardware_verified: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("session transitions are closed static evidence")


@dataclass(frozen=True, init=False, repr=False)
class SessionRaceEvidence:
    code: SessionRaceCode
    lanes: tuple[EvidenceLane, ...]
    observation: str
    unsafe_inference: str
    required_python_rule: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("session races are closed static evidence")


@dataclass(frozen=True, init=False, repr=False)
class BindingReactionEvidence:
    inbound_action: SourceBindingAction | None
    inbound_source_code: int | None
    required_second_value: int | None
    outbound_action: SourceBindingAction | None
    outbound_source_code: int | None
    outbound_neutral_tail: tuple[int, int] | None
    local_effects: tuple[str, ...]
    owner_mutation: bool
    app_label_only: bool
    hardware_verified: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("binding reactions are closed static evidence")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredSessionEvidence:
    transitions: tuple[SessionTransitionEvidence, ...]
    races: tuple[SessionRaceEvidence, ...]
    binding_reactions: tuple[BindingReactionEvidence, ...]
    safety: StaticSessionSafety

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use recovered_session_evidence()")

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "recovered_android_session_ordering"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def python_callable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def owner_authorized(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "RecoveredSessionEvidence("
            f"transition_count={len(self.transitions)}, race_count={len(self.races)}, "
            f"binding_reaction_count={len(self.binding_reactions)}, runnable=False, "
            "hardware_eligible=False, hardware_verified=False, owner_authorized=False)"
        )


def _transition(
    code: SessionTransitionCode,
    lane: EvidenceLane,
    result: EvidenceState,
    *,
    prerequisites: tuple[EvidenceState, ...] = (),
    requests: tuple[str, ...] = (),
    callbacks: tuple[str, ...] = (),
    effects: tuple[str, ...],
    claim: SourceReadinessClaim = SourceReadinessClaim.NONE,
    cloud: bool = False,
    bluetooth: bool = False,
    vendor_write: bool = False,
) -> SessionTransitionEvidence:
    return _closed_instance(
        SessionTransitionEvidence,
        code=code,
        lane=lane,
        prerequisites=prerequisites,
        result=result,
        related_requests=requests,
        related_callbacks=callbacks,
        source_effects=effects,
        source_readiness_claim=claim,
        directly_touches_cloud=cloud,
        directly_touches_bluetooth=bluetooth,
        source_performs_vendor_write=vendor_write,
        descriptor_acknowledged=False,
        owner_authorized=False,
        hardware_verified=False,
    )


_T = SessionTransitionCode
_L = EvidenceLane
_S = EvidenceState
_C = SourceReadinessClaim


_TRANSITIONS = (
    _transition(_T.DEFAULT_SDK_STATUS, _L.SDK_VALIDATION, _S.SERVICE_CREATED_WITH_DEFAULT_SDK_STATUS,
                effects=("shared_sdk_status_starts_as_200",)),
    _transition(_T.REMEMBERED_TARGET_RECONNECT, _L.RECONNECT, _S.REMEMBERED_TARGET_RECONNECT_STARTED,
                prerequisites=(_S.SERVICE_CREATED_WITH_DEFAULT_SDK_STATUS,),
                effects=("remembered_target_can_reconnect_before_callback_registration",),
                claim=_C.CONNECTING, bluetooth=True),
    _transition(_T.REGISTER_BUNDLED_CREDENTIAL_CALLBACK, _L.CALLBACK_REGISTRATION,
                _S.CALLBACK_REGISTERED, requests=("registerCallback",),
                effects=("installs_global_callback_before_cache_or_network_branch", "loads_bundled_sdk_credentials_on_expired_cache")),
    _transition(_T.REGISTER_CALLER_CREDENTIAL_CALLBACK, _L.CALLBACK_REGISTRATION,
                _S.CALLBACK_REGISTERED, requests=("registerCallback2",),
                effects=("installs_global_callback_before_cache_or_network_branch", "accepts_caller_supplied_sdk_credentials_on_expired_cache")),
    _transition(_T.REPORT_CACHED_SDK_STATUS, _L.SDK_VALIDATION, _S.SDK_VALIDATION_CACHE_REPORTED,
                prerequisites=(_S.CALLBACK_REGISTERED,), callbacks=("onAuthSdkResult",),
                effects=("fresh_timestamp_reports_current_shared_status_without_network",), claim=_C.CALLBACK_RESULT_ONLY),
    _transition(_T.REQUEST_BUNDLED_SDK_VALIDATION, _L.SDK_VALIDATION, _S.SDK_VALIDATION_REQUEST_PENDING,
                prerequisites=(_S.CALLBACK_REGISTERED,), requests=("registerCallback",),
                effects=("expired_cache_posts_developer_validation_with_bundled_credentials", "source_logs_sensitive_request_body"), cloud=True),
    _transition(_T.REQUEST_CALLER_SDK_VALIDATION, _L.SDK_VALIDATION, _S.SDK_VALIDATION_REQUEST_PENDING,
                prerequisites=(_S.CALLBACK_REGISTERED,), requests=("registerCallback2",),
                effects=("expired_cache_posts_developer_validation_with_caller_credentials", "source_logs_sensitive_request_body"), cloud=True),
    _transition(_T.APPLY_SDK_VALIDATION_RESULT, _L.SDK_VALIDATION, _S.SDK_VALIDATION_RESULT_APPLIED,
                prerequisites=(_S.SDK_VALIDATION_REQUEST_PENDING,), callbacks=("onAuthSdkResult",),
                effects=("successful_body_updates_shared_status_and_expiry", "transport_error_callback_does_not_replace_shared_status"), claim=_C.CALLBACK_RESULT_ONLY),
    _transition(_T.CHECK_MANUAL_CONNECT_GATE, _L.SDK_VALIDATION, _S.MANUAL_CONNECT_GATE_CHECKED,
                prerequisites=(_S.SERVICE_CREATED_WITH_DEFAULT_SDK_STATUS,), requests=("connectBt",),
                effects=("manual_connect_reads_current_shared_status_without_awaiting_validation",)),
    _transition(_T.START_GATT_CONNECT, _L.BLE_LINK, _S.GATT_CONNECTING,
                prerequisites=(_S.MANUAL_CONNECT_GATE_CHECKED,), requests=("connectBt",),
                effects=("status_200_branch_persists_target_and_starts_reconnect_flow",), claim=_C.CONNECTING, bluetooth=True),
    _transition(_T.OBSERVE_GATT_LINK, _L.BLE_LINK, _S.LINK_CONNECTED,
                prerequisites=(_S.GATT_CONNECTING,), effects=("android_gatt_link_connected_but_vendor_route_not_ready",), bluetooth=True),
    _transition(_T.START_SERVICE_DISCOVERY, _L.SERVICE_DISCOVERY, _S.SERVICE_DISCOVERY_PENDING,
                prerequisites=(_S.LINK_CONNECTED,), effects=("starts_retry_managed_service_discovery", "no_effective_initial_gatt_connect_timeout_was_recovered"), bluetooth=True),
    _transition(_T.RETRY_SERVICE_DISCOVERY, _L.SERVICE_DISCOVERY, _S.SERVICE_DISCOVERY_RETRYING,
                prerequisites=(_S.SERVICE_DISCOVERY_PENDING,), effects=("at_most_three_discovery_attempts", "each_attempt_has_a_30_second_timer", "failure_or_exhaustion_enters_recovery"), bluetooth=True),
    _transition(_T.ACCEPT_SERVICES, _L.SERVICE_DISCOVERY, _S.SERVICES_ACCEPTED_AND_QUEUE_CLEARED,
                prerequisites=(_S.SERVICE_DISCOVERY_PENDING,), effects=("clears_command_queue_before_useful_characteristic_check",), bluetooth=True),
    _transition(_T.DELAY_CHARACTERISTIC_INITIALIZATION, _L.MAIN_NOTIFICATION, _S.CHARACTERISTIC_INITIALIZATION_DELAYED,
                prerequisites=(_S.SERVICES_ACCEPTED_AND_QUEUE_CLEARED,), effects=("delays_primary_characteristic_initialization_by_500ms",)),
    _transition(_T.ACCEPT_NOTIFICATION_DISPATCH, _L.MAIN_NOTIFICATION, _S.MAIN_NOTIFICATION_DISPATCH_ACCEPTED,
                prerequisites=(_S.CHARACTERISTIC_INITIALIZATION_DELAYED,), effects=("local_notification_enable_and_descriptor_write_submission_returned_true",), bluetooth=True),
    _transition(_T.REPORT_SOURCE_CONNECTED, _L.BLE_LINK, _S.SOURCE_CONNECTED_REPORTED,
                prerequisites=(_S.MAIN_NOTIFICATION_DISPATCH_ACCEPTED,), callbacks=("onConnectStateChanged",),
                effects=("source_reports_state_2_before_descriptor_callback_and_device_policy_result",), claim=_C.CONNECTED),
    _transition(_T.CHECK_DEVICE_POLICY_CACHE, _L.DEVICE_POLICY, _S.DEVICE_POLICY_CACHE_CHECKED,
                prerequisites=(_S.SOURCE_CONNECTED_REPORTED,), effects=("checks_per_target_flag_and_fixed_24_hour_timestamp",)),
    _transition(_T.REPORT_CACHED_DEVICE_ALLOW, _L.DEVICE_POLICY, _S.DEVICE_POLICY_CACHED_ALLOW_REPORTED,
                prerequisites=(_S.DEVICE_POLICY_CACHE_CHECKED,), callbacks=("onAuthDeviceResult",),
                effects=("cached_zero_flag_reports_shared_sdk_status",), claim=_C.CALLBACK_RESULT_ONLY),
    _transition(_T.REQUEST_DEVICE_POLICY, _L.DEVICE_POLICY, _S.DEVICE_POLICY_REQUEST_PENDING,
                prerequisites=(_S.DEVICE_POLICY_CACHE_CHECKED,), effects=("posts_target_and_phone_identifiers_to_gear_policy_endpoint", "source_logs_sensitive_request_body"), cloud=True),
    _transition(_T.RECORD_DEVICE_ALLOW, _L.DEVICE_POLICY, _S.DEVICE_POLICY_ALLOW_RECORDED,
                prerequisites=(_S.DEVICE_POLICY_REQUEST_PENDING,), callbacks=("onAuthDeviceResult",),
                effects=("zero_or_missing_flag_keeps_link_open_but_callback_reports_shared_sdk_status",), claim=_C.CALLBACK_RESULT_ONLY),
    _transition(_T.CLOSE_ON_DEVICE_DENY, _L.DEVICE_POLICY, _S.DEVICE_POLICY_DENY_CLOSES_LINK,
                prerequisites=(_S.DEVICE_POLICY_REQUEST_PENDING,), callbacks=("onAuthDeviceResult",),
                effects=("nonzero_policy_flag_closes_ble_link", "callback_does_not_expose_policy_flag_unambiguously"), bluetooth=True),
    _transition(_T.HANDLE_DESCRIPTOR_SPECIAL_FAILURE, _L.MAIN_NOTIFICATION, _S.DESCRIPTOR_SPECIAL_FAILURE,
                prerequisites=(_S.MAIN_NOTIFICATION_DISPATCH_ACCEPTED,), effects=("one_special_status_disconnects_and_refreshes_cache",), bluetooth=True),
    _transition(_T.OBSERVE_DESCRIPTOR_OTHER_RESULT, _L.MAIN_NOTIFICATION, _S.DESCRIPTOR_OTHER_RESULT_OBSERVED,
                prerequisites=(_S.MAIN_NOTIFICATION_DISPATCH_ACCEPTED,), effects=("every_non_special_primary_descriptor_status_continues_including_other_failures",), bluetooth=True),
    _transition(_T.QUEUE_STARTUP_CLOCK_SYNC, _L.STARTUP_CLOCK_SYNC, _S.STARTUP_CLOCK_SYNC_QUEUED,
                prerequisites=(_S.DESCRIPTOR_OTHER_RESULT_OBSERVED,), requests=("setDeviceTime",), callbacks=("onSetDeviceTime",),
                effects=("queues_existing_opcode_01_device_time_mutation", "uses_total_offset_for_epoch_but_raw_offset_for_separate_hour_byte"), vendor_write=True),
    _transition(_T.OBSERVE_BINDING_NOTIFICATION, _L.VENDOR_BINDING, _S.BINDING_NOTIFICATION_OBSERVED,
                callbacks=("onNotifyBindedInfo",), effects=("observes_source_labeled_binding_action_and_neutral_second_value",)),
    _transition(_T.SEND_BINDING_START, _L.VENDOR_BINDING, _S.VENDOR_BINDING_START_SENT,
                prerequisites=(_S.BINDING_NOTIFICATION_OBSERVED,), requests=("setBindedInfo",), effects=("init_zero_branch_queues_source_action_1_with_neutral_tail_0_1",), vendor_write=True),
    _transition(_T.SEND_BINDING_SUCCESS, _L.VENDOR_BINDING, _S.VENDOR_BINDING_SUCCESS_SENT,
                prerequisites=(_S.BINDING_NOTIFICATION_OBSERVED,), requests=("setBindedInfo",), effects=("ack_branch_queues_source_action_4_with_neutral_tail_0_1",), vendor_write=True),
    _transition(_T.CONFIRM_VENDOR_BINDING, _L.VENDOR_BINDING, _S.VENDOR_BINDING_CONFIRMED,
                prerequisites=(_S.BINDING_NOTIFICATION_OBSERVED,), callbacks=("onNotifyBindedInfo",), effects=("source_action_4_is_logged_as_confirmation_without_proving_owner_identity",)),
    _transition(_T.SEND_VENDOR_UNBIND, _L.VENDOR_BINDING, _S.VENDOR_UNBIND_SENT,
                requests=("setBindedInfo",), effects=("explicit_ui_path_queues_source_action_5_with_neutral_tail_0_1",), vendor_write=True),
    _transition(_T.ACKNOWLEDGE_VENDOR_UNBOUND, _L.VENDOR_BINDING, _S.VENDOR_UNBOUND_ACKNOWLEDGED,
                prerequisites=(_S.BINDING_NOTIFICATION_OBSERVED,), callbacks=("onNotifyBindedInfo",), effects=("source_actions_3_or_6_clear_local_sync_state",)),
    _transition(_T.RECORD_DISCONNECT, _L.BLE_LINK, _S.DISCONNECTED,
                requests=("disconnectBt", "closeConnection"), callbacks=("onConnectStateChanged",), effects=("clears_or_retains_target_according_to_separate_source policy",), bluetooth=True),
    _transition(_T.SCHEDULE_RECONNECT, _L.RECONNECT, _S.RECONNECT_SCHEDULED,
                prerequisites=(_S.DISCONNECTED,), effects=("non_user_disconnect_schedules_delayed_reconnect",), claim=_C.CONNECTING, bluetooth=True),
)


def _race(
    code: SessionRaceCode,
    lanes: tuple[EvidenceLane, ...],
    observation: str,
    unsafe_inference: str,
    rule: str,
) -> SessionRaceEvidence:
    return _closed_instance(SessionRaceEvidence, code=code, lanes=lanes,
                            observation=observation, unsafe_inference=unsafe_inference,
                            required_python_rule=rule)


_RACES = (
    _race(SessionRaceCode.CONCURRENT_REGISTRATION_REPLACES_CALLBACK, (_L.CALLBACK_REGISTRATION, _L.SDK_VALIDATION), "each registration replaces one shared callback before independently starting cache or network work", "a completion is delivered to the callback that launched its request", "bind each asynchronous result to one immutable request and reject superseded generations"),
    _race(SessionRaceCode.FUTURE_VALIDATION_TIMESTAMP_PASSES_CACHE, (_L.SDK_VALIDATION,), "the cache comparison accepts a future source timestamp and reports the initialized shared status", "a cache hit proves a fresh authoritative vendor decision", "treat recovered cache behavior as advisory evidence and use monotonic local deadlines in Python"),
    _race(SessionRaceCode.STARTUP_RECONNECT_PRECEDES_CALLBACK, (_L.RECONNECT, _L.CALLBACK_REGISTRATION), "remembered-target reconnect may start before callback installation", "callback registration authorizes or owns that connection", "require an explicit owner-selected connection generation"),
    _race(SessionRaceCode.MANUAL_CONNECT_DOES_NOT_AWAIT_VALIDATION, (_L.SDK_VALIDATION, _L.BLE_LINK), "manual connect reads the shared status while validation may still be pending", "connect implies a fresh successful cloud decision", "never use vendor cloud validation as ring-owner authority"),
    _race(SessionRaceCode.VALIDATION_ERROR_PRESERVES_GATE, (_L.SDK_VALIDATION,), "a validation transport failure is reported without replacing the initialized shared gate", "the reported error necessarily blocks later connect", "model transport status and stored policy state separately"),
    _race(SessionRaceCode.CONNECTED_PRECEDES_DESCRIPTOR_CALLBACK, (_L.BLE_LINK, _L.MAIN_NOTIFICATION), "source state 2 follows descriptor dispatch acceptance", "source connected means descriptor acknowledgement", "require transport-call completion and response readiness as separate facts"),
    _race(SessionRaceCode.DEVICE_POLICY_AFTER_CONNECTED, (_L.BLE_LINK, _L.DEVICE_POLICY), "device policy begins after source connected", "source connected proves device policy approval", "keep device policy outside vendor command readiness"),
    _race(SessionRaceCode.DEVICE_POLICY_CALLBACK_CONFLATES_DOMAINS, (_L.SDK_VALIDATION, _L.DEVICE_POLICY), "device callback can report HTTP or shared SDK status rather than the policy flag", "callback value is a reliable owner-authorization result", "preserve the result as ambiguous static evidence"),
    _race(SessionRaceCode.DYNAMIC_DESCRIPTORS_NOT_SERIALIZED, (_L.MAIN_NOTIFICATION,), "primary and caller-configured notification setup can overlap", "one descriptor callback identifies one ordered setup transaction", "serialize subscriptions and bind callbacks to exact endpoints"),
    _race(SessionRaceCode.NON_SPECIAL_DESCRIPTOR_STARTS_CLOCK, (_L.MAIN_NOTIFICATION, _L.STARTUP_CLOCK_SYNC), "all non-special primary descriptor statuses queue clock sync", "clock mutation proves descriptor success", "never reproduce the automatic mutation or infer readiness from it"),
    _race(SessionRaceCode.BINDING_INTERLEAVES_COMMAND_QUEUE, (_L.VENDOR_BINDING, _L.STARTUP_CLOCK_SYNC), "binding responses can share the ordinary command queue", "binding completion serializes every other session action", "require explicit operation matching and owner consent"),
    _race(SessionRaceCode.CALLBACKS_HAVE_NO_GENERATION, (_L.BLE_LINK, _L.MAIN_NOTIFICATION, _L.VENDOR_BINDING), "callbacks are not uniformly bound to an immutable connection generation", "a late callback belongs to the current link", "discard callbacks from invalidated generations"),
    _race(SessionRaceCode.LATE_CLOUD_RESULT, (_L.DEVICE_POLICY, _L.RECONNECT), "cloud completion can arrive after disconnect or reconnect", "the result applies to the newest connection", "bind asynchronous policy observations to a target-free generation token"),
    _race(SessionRaceCode.CLASSIC_BOND_IS_ORTHOGONAL, (_L.CLASSIC_BOND, _L.VENDOR_BINDING), "Android classic bonding occurs in separate app and audio paths", "OS bond success proves vendor binding or vice versa", "report classic bond and vendor binding independently"),
    _race(SessionRaceCode.DISCOVERY_EXHAUSTION_ENTERS_RECOVERY, (_L.SERVICE_DISCOVERY, _L.RECONNECT), "service discovery allows three attempts with a 30-second timer per attempt before recovery", "one service-discovery failure is final or one success proves endpoint presence", "use one bounded deadline and validate required endpoints separately"),
    _race(SessionRaceCode.MISSING_ENDPOINTS_ENTER_DELAYED_RECOVERY, (_L.SERVICE_DISCOVERY, _L.RECONNECT), "service discovery can succeed before the required characteristics are found and delayed recovery starts", "a successful Android service callback establishes the vendor route", "validate the exact selected route before reporting any readiness"),
    _race(SessionRaceCode.DESCRIPTOR_DISPATCH_FALSE_DISCONNECTS, (_L.MAIN_NOTIFICATION, _L.RECONNECT), "a synchronous descriptor-dispatch rejection schedules disconnection", "a failed dispatch is an acknowledged device rejection", "classify it as definitely not dispatched and do not infer a peer response"),
    _race(SessionRaceCode.STALE_GATT_CALLBACK_TARGETS_CURRENT_LINK, (_L.BLE_LINK, _L.SERVICE_DISCOVERY, _L.MAIN_NOTIFICATION), "late callbacks from an old Android GATT object can trigger work through the current shared link field", "closing an old link prevents all stale callback effects", "bind every callback to the selected transport object and immutable connection generation"),
    _race(SessionRaceCode.WRITE_FALSE_RETRY_STORM, (_L.COMMAND_QUEUE,), "a synchronous characteristic-write rejection is retried up to 31 total calls with blocking delays", "blind retries are safe because the first call returned false", "make dispatch failure terminal for one operation and require a new explicit attempt"),
    _race(SessionRaceCode.WRITE_CALLBACK_STATUS_IGNORED, (_L.COMMAND_QUEUE,), "the Android write callback releases the global send gate without checking its status", "callback arrival proves the write succeeded", "classify non-success status explicitly and never promote callback arrival alone to success"),
    _race(SessionRaceCode.ACCEPTED_WRITE_CALLBACK_LOSS, (_L.COMMAND_QUEUE,), "a write accepted for dispatch can lose its callback and end with an uncertain outcome", "timeout proves the command did not reach or mutate the ring", "return outcome_unknown and never retry a possibly dispatched mutation automatically"),
    _race(SessionRaceCode.DORMANT_RESPONSE_MATCHING_IS_GLOBAL, (_L.COMMAND_QUEUE,), "the dormant response-wait mode uses a global completion signal without operation matching", "any recognized notification is the response to the pending command", "match a response to its operation and generation or leave the result uncertain"),
)


def _binding(
    inbound: SourceBindingAction | None,
    inbound_code: int | None,
    second: int | None,
    outbound: SourceBindingAction | None,
    outbound_code: int | None,
    tail: tuple[int, int] | None,
    effects: tuple[str, ...],
    *,
    owner_mutation: bool,
) -> BindingReactionEvidence:
    return _closed_instance(BindingReactionEvidence, inbound_action=inbound,
                            inbound_source_code=inbound_code, required_second_value=second,
                            outbound_action=outbound, outbound_source_code=outbound_code,
                            outbound_neutral_tail=tail, local_effects=effects,
                            owner_mutation=owner_mutation, app_label_only=True,
                            hardware_verified=False)


_BINDING_REACTIONS = (
    _binding(SourceBindingAction.INIT, 0, 0, SourceBindingAction.APP_START, 1, (0, 1), ("queue_source_labeled_app_start",), owner_mutation=True),
    _binding(SourceBindingAction.ACK, 2, None, SourceBindingAction.SUCCESS, 4, (0, 1), ("queue_source_labeled_success",), owner_mutation=True),
    _binding(SourceBindingAction.ACK_CANCEL, 3, None, None, None, None, ("clear_local_sync_state", "signal_local_unbind_completion"), owner_mutation=False),
    _binding(SourceBindingAction.SUCCESS, 4, None, None, None, None, ("record_source_labeled_confirmation",), owner_mutation=False),
    _binding(SourceBindingAction.UNBIND_ACK, 6, None, None, None, None, ("clear_local_sync_state", "signal_local_unbind_completion"), owner_mutation=False),
    _binding(None, None, None, SourceBindingAction.UNBIND, 5, (0, 1), ("requires_explicit_owner_ui_confirmation",), owner_mutation=True),
)


_SAFETY = _closed_instance(StaticSessionSafety, radio_access=False,
                           network_access=False, filesystem_access=False,
                           accepts_device_identity=False, accepts_credentials=False,
                           exposes_frame_bytes=False, transport_integration=False,
                           owner_authority=False)

_EVIDENCE = _closed_instance(RecoveredSessionEvidence, transitions=_TRANSITIONS,
                             races=_RACES, binding_reactions=_BINDING_REACTIONS,
                             safety=_SAFETY)


def recovered_session_evidence() -> RecoveredSessionEvidence:
    """Return the immutable singleton recovered-session evidence graph."""

    return _EVIDENCE


__all__ = [
    "BindingReactionEvidence",
    "EvidenceLane",
    "EvidenceState",
    "RecoveredSessionEvidence",
    "SessionRaceCode",
    "SessionRaceEvidence",
    "SessionTransitionCode",
    "SessionTransitionEvidence",
    "SourceBindingAction",
    "SourceReadinessClaim",
    "StaticSessionSafety",
    "recovered_session_evidence",
]
