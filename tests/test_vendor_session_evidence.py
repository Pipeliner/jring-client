from dataclasses import FrozenInstanceError, fields
import inspect

import pytest

import jring.vendor_session_evidence as session_module
from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)
from jring.vendor_session_evidence import (
    BindingReactionEvidence,
    EvidenceLane,
    EvidenceState,
    RecoveredSessionEvidence,
    SessionRaceCode,
    SessionRaceEvidence,
    SessionTransitionCode,
    SessionTransitionEvidence,
    SourceBindingAction,
    StaticSessionSafety,
    recovered_session_evidence,
)


def _transitions():
    return {item.code: item for item in recovered_session_evidence().transitions}


def test_session_evidence_is_a_closed_immutable_singleton():
    evidence = recovered_session_evidence()

    assert evidence is recovered_session_evidence()
    for closed_type in (
        StaticSessionSafety,
        SessionTransitionEvidence,
        SessionRaceEvidence,
        BindingReactionEvidence,
        RecoveredSessionEvidence,
    ):
        with pytest.raises(TypeError):
            closed_type()
    with pytest.raises(TypeError):
        recovered_session_evidence("target")
    with pytest.raises(FrozenInstanceError):
        evidence.transitions = ()


def test_session_evidence_has_no_runtime_authority_or_sensitive_inputs():
    evidence = recovered_session_evidence()

    assert evidence.maturity == "static_apk_only"
    assert evidence.evidence_scope == "recovered_android_session_ordering"
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.owner_authorized is False
    assert all(value is False for value in (
        evidence.safety.radio_access,
        evidence.safety.network_access,
        evidence.safety.filesystem_access,
        evidence.safety.accepts_device_identity,
        evidence.safety.accepts_credentials,
        evidence.safety.exposes_frame_bytes,
        evidence.safety.transport_integration,
        evidence.safety.owner_authority,
    ))

    forbidden_methods = {
        "advance", "authorize", "bind", "connect", "encode", "execute", "parse",
        "subscribe", "write",
    }
    assert forbidden_methods.isdisjoint(dir(evidence))
    assert forbidden_methods.isdisjoint(dir(SessionTransitionEvidence))

    forbidden_fields = {
        "address", "callback", "credential", "device_name", "frame", "payload",
        "request_body", "secret", "timestamp", "uuid",
    }
    for model in (
        StaticSessionSafety,
        SessionTransitionEvidence,
        SessionRaceEvidence,
        BindingReactionEvidence,
        RecoveredSessionEvidence,
    ):
        assert forbidden_fields.isdisjoint(field.name for field in fields(model))

    source = inspect.getsource(session_module).lower()
    for dependency in (
        "import bleak", "import http", "import pathlib", "import socket",
        "import subprocess", "vendor_commands", "encode_binding_info", "open(",
    ):
        assert dependency not in source


def test_session_graph_has_closed_unique_codes_and_only_known_interface_links():
    evidence = recovered_session_evidence()
    request_names = {entry.name for entry in static_vendor_operation_coverage()}
    callback_names = {entry.name for entry in static_vendor_callback_coverage()}

    assert len(evidence.transitions) == len({item.code for item in evidence.transitions})
    assert len(evidence.races) == len({item.code for item in evidence.races})
    assert all(type(item.code) is SessionTransitionCode for item in evidence.transitions)
    assert all(type(item.lane) is EvidenceLane for item in evidence.transitions)
    assert all(type(item.result) is EvidenceState for item in evidence.transitions)
    assert all(set(item.related_requests) <= request_names for item in evidence.transitions)
    assert all(set(item.related_callbacks) <= callback_names for item in evidence.transitions)
    assert len(static_vendor_operation_coverage()) == 112
    assert len(static_vendor_callback_coverage()) == 105


def test_reconnect_and_registration_do_not_invent_a_fresh_validation_gate():
    transitions = _transitions()
    reconnect = transitions[SessionTransitionCode.REMEMBERED_TARGET_RECONNECT]
    connect_gate = transitions[SessionTransitionCode.CHECK_MANUAL_CONNECT_GATE]
    validation = transitions[SessionTransitionCode.APPLY_SDK_VALIDATION_RESULT]

    assert reconnect.prerequisites == (
        EvidenceState.SERVICE_CREATED_WITH_DEFAULT_SDK_STATUS,
    )
    assert EvidenceState.CALLBACK_REGISTERED not in reconnect.prerequisites
    assert EvidenceState.SDK_VALIDATION_RESULT_APPLIED not in connect_gate.prerequisites
    assert "transport_error_callback_does_not_replace_shared_status" in validation.source_effects
    assert {
        SessionRaceCode.STARTUP_RECONNECT_PRECEDES_CALLBACK,
        SessionRaceCode.MANUAL_CONNECT_DOES_NOT_AWAIT_VALIDATION,
        SessionRaceCode.VALIDATION_ERROR_PRESERVES_GATE,
    } <= {item.code for item in recovered_session_evidence().races}


def test_source_connected_is_dispatch_acceptance_not_descriptor_acknowledgement():
    transitions = _transitions()
    source_connected = transitions[SessionTransitionCode.REPORT_SOURCE_CONNECTED]
    descriptor_other = transitions[SessionTransitionCode.OBSERVE_DESCRIPTOR_OTHER_RESULT]
    clock = transitions[SessionTransitionCode.QUEUE_STARTUP_CLOCK_SYNC]

    assert source_connected.prerequisites == (
        EvidenceState.MAIN_NOTIFICATION_DISPATCH_ACCEPTED,
    )
    assert source_connected.source_readiness_claim.value == "connected"
    assert all(item.descriptor_acknowledged is False for item in transitions.values())
    assert "including_other_failures" in "_".join(descriptor_other.source_effects)
    assert clock.prerequisites == (EvidenceState.DESCRIPTOR_OTHER_RESULT_OBSERVED,)
    assert clock.related_requests == ("setDeviceTime",)
    assert clock.source_performs_vendor_write is True
    assert clock.owner_authorized is False


def test_device_policy_occurs_after_connected_and_does_not_become_owner_authority():
    transitions = _transitions()
    cache = transitions[SessionTransitionCode.CHECK_DEVICE_POLICY_CACHE]
    request = transitions[SessionTransitionCode.REQUEST_DEVICE_POLICY]
    deny = transitions[SessionTransitionCode.CLOSE_ON_DEVICE_DENY]

    assert cache.prerequisites == (EvidenceState.SOURCE_CONNECTED_REPORTED,)
    assert request.prerequisites == (EvidenceState.DEVICE_POLICY_CACHE_CHECKED,)
    assert request.directly_touches_cloud is True
    assert deny.result is EvidenceState.DEVICE_POLICY_DENY_CLOSES_LINK
    assert deny.directly_touches_bluetooth is True
    assert all(item.owner_authorized is False for item in transitions.values())


def test_recovered_discovery_limits_are_explicit_without_claiming_readiness():
    retry = _transitions()[SessionTransitionCode.RETRY_SERVICE_DISCOVERY]

    assert retry.source_effects == (
        "at_most_three_discovery_attempts",
        "each_attempt_has_a_30_second_timer",
        "failure_or_exhaustion_enters_recovery",
    )
    assert retry.source_readiness_claim.value == "none"


def test_binding_reactions_are_exact_source_labels_not_verified_meanings():
    evidence = recovered_session_evidence()
    reactions = evidence.binding_reactions

    assert {action.value for action in SourceBindingAction} == {
        "source_named_init", "source_named_app_start", "source_named_ack",
        "source_named_ack_cancel", "source_named_success", "source_named_unbind",
        "source_named_unbind_ack",
    }
    assert [
        (
            item.inbound_action,
            item.inbound_source_code,
            item.required_second_value,
            item.outbound_action,
            item.outbound_source_code,
            item.outbound_neutral_tail,
        )
        for item in reactions
    ] == [
        (SourceBindingAction.INIT, 0, 0, SourceBindingAction.APP_START, 1, (0, 1)),
        (SourceBindingAction.ACK, 2, None, SourceBindingAction.SUCCESS, 4, (0, 1)),
        (SourceBindingAction.ACK_CANCEL, 3, None, None, None, None),
        (SourceBindingAction.SUCCESS, 4, None, None, None, None),
        (SourceBindingAction.UNBIND_ACK, 6, None, None, None, None),
        (None, None, None, SourceBindingAction.UNBIND, 5, (0, 1)),
    ]
    assert all(item.app_label_only is True for item in reactions)
    assert all(item.hardware_verified is False for item in reactions)
    assert "source_named" not in repr(evidence)
    assert "neutral_tail" not in repr(evidence)


def test_all_adversarial_session_races_have_python_safety_rules():
    races = recovered_session_evidence().races

    assert {item.code for item in races} == set(SessionRaceCode)
    assert len(races) == 22
    assert all(item.observation for item in races)
    assert all(item.unsafe_inference for item in races)
    assert all(item.required_python_rule for item in races)
    classic = next(
        item for item in races
        if item.code is SessionRaceCode.CLASSIC_BOND_IS_ORTHOGONAL
    )
    assert set(classic.lanes) == {EvidenceLane.CLASSIC_BOND, EvidenceLane.VENDOR_BINDING}
    assert "independently" in classic.required_python_rule
