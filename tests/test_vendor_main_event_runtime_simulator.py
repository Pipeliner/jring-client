import asyncio
from copy import copy, deepcopy
from dataclasses import asdict, replace
import json

import pytest

import jring.vendor_main_event_runtime_simulator as main_event_runtime
from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_history_runtime_simulator import FakeVendorHistorySimulator
from jring.input import InputMapper
from jring.vendor_main_event_runtime_simulator import (
    FakeVendorMainEventSimulator,
    MainEventCollectionCompleteness,
    MainEventKind,
    MainEventSimulationReason,
    UnknownMotionChannelProjection,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport
from jring.vendor_protocol import Static45Notification, StaticQuery, encode_day_query


def run(coro):
    return asyncio.run(coro)


def _frame(opcode: int, body: bytes = b"") -> bytes:
    return bytes((opcode,)) + body.ljust(19, b"\x00")


def test_unknown_motion_projection_is_an_explicit_module_export():
    assert "UnknownMotionChannelProjection" in main_event_runtime.__all__


def test_collects_only_closed_passive_main_events_without_any_write():
    transport = ScriptedVendorFakeTransport.vendor_route()
    frames = (
        _frame(0x06, bytes((68,))),
        _frame(0x22, bytes((99,))),
        _frame(0x51, (123_456).to_bytes(4, "little")),
        _frame(0x49),
    )

    def emit(fake, _call):
        for frame in frames:
            fake.emit(VENDOR_CHARACTERISTIC_33F4, frame)

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=4,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 4
    assert result.unrelated_frame_count == 0
    assert result.event_kinds == (
        MainEventKind.DEVICE_ACTION,
        MainEventKind.DEVICE_ACTION,
        MainEventKind.CUMULATIVE_STEP,
        MainEventKind.PHONE_VOLUME_REQUEST,
    )
    events = result.events_for_test()
    assert events[0].value_for_test().label == "volume_up"
    assert events[1].value_for_test().label == "weather_location_refresh"
    assert events[2].value_for_test().cumulative_steps == 123_456
    assert events[3].value_for_test().requests_host_volume_state is True
    assert all(event.simulation_only is True for event in events)
    assert all(event.hardware_eligible is False for event in events)
    assert all(event.input_eligible is False for event in events)
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert result.input_eligible is False
    assert result.hardware_verified is False
    assert result.wire_terminal_observed is False
    assert result.quiet_means_success is False
    assert transport.subscribe_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.subscription_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert transport.subscription_calls[0].target_instance_id is not None
    assert (
        transport.subscription_calls[0].target_instance_id
        == transport.unsubscribe_calls[0].target_instance_id
    )
    assert transport.unsubscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0
    assert transport.close_count == 1
    rendered = repr(result)
    assert "123456" not in rendered
    assert "volume_up" not in rendered
    assert "weather" not in rendered
    assert "events=<redacted>" in rendered
    assert "123456" not in repr(events[2])
    assert "volume_up" not in repr(events[0])


def test_collects_redacted_classic_info_and_name_without_attachment_or_write():
    transport = ScriptedVendorFakeTransport.vendor_route()
    private_name = b"private-ring-name"

    def emit(fake, _call):
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            _frame(0x45, bytes((0x00, 7, 8)) + bytes(range(3, 19))),
        )
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            _frame(0x45, bytes((0x01,)) + private_name),
        )

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=2,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_kinds == (
        MainEventKind.CLASSIC_INFO,
        MainEventKind.CLASSIC_NAME,
    )
    events = result.events_for_test()
    assert events[0].value_for_test().values == (7, 8)
    assert events[0].value_for_test().identifiers_redacted is True
    assert events[1].value_for_test().content_redacted is True
    assert not hasattr(events[1].value_for_test(), "content")
    assert private_name.decode() not in repr(result)
    assert private_name.decode() not in repr(events[1])
    assert private_name.decode() not in repr(asdict(events[1].value_for_test()))
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0


def test_collects_redacted_app_id_without_correlating_setter_or_writing():
    transport = ScriptedVendorFakeTransport.vendor_route()
    private_app_id = b"private-app-id-12"
    ignored_trailing_byte = b"Z"
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((0x45, 0x02)) + private_app_id + ignored_trailing_byte,
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_kinds == (MainEventKind.APP_ID,)
    event = result.events_for_test()[0]
    assert event.value_for_test().kind is Static45Notification.APP_ID
    assert event.value_for_test().consumed_content_bytes == 17
    assert event.value_for_test().trailing_byte_ignored_by_sdk is True
    assert event.value_for_test().content_redacted is True
    assert not hasattr(event.value_for_test(), "content")
    assert private_app_id.decode() not in repr(result)
    assert private_app_id.decode() not in repr(event)
    assert private_app_id.decode() not in repr(asdict(event.value_for_test()))
    assert private_app_id.decode() not in json.dumps(asdict(result), default=str)
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0


@pytest.mark.parametrize("selector", (0x03, 0xFF))
def test_unknown_45_selectors_count_as_unrelated(selector):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x45, bytes((selector,)) + bytes(18)),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.01,
    ))

    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 0
    assert result.unrelated_frame_count == 1
    assert transport.write_count == 0


def test_selectorless_45_cannot_be_attributed_to_classic_and_does_not_rollback():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            _frame(0x45, bytes((0x00, 7, 8))),
        )
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x45,)))

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=2,
        quiet_timeout=0.01,
    ))

    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_kinds == (MainEventKind.CLASSIC_INFO,)
    assert result.unrelated_frame_count == 1
    assert transport.write_count == 0


def test_collects_exact_touch_mode_as_neutral_passive_projection_without_any_write():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x78, bytes((0x09, 0xA7))),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 1
    assert result.unrelated_frame_count == 0
    assert result.event_kinds == (MainEventKind.TOUCH_MODE_SETTING_PROJECTION,)
    event = result.events_for_test()[0]
    assert event.value_for_test().value_for_test() == 0xA7
    assert event.value_for_test().projection_role == "touch_mode_setting_value_or_event"
    assert event.value_for_test().acknowledgement_state == "not_proven"
    assert event.value_for_test().setting_application_state == "unknown"
    assert event.value_for_test().terminal_observed is False
    assert event.value_for_test().gesture_semantics == "not_proven"
    assert event.value_for_test().touch_event_observed is False
    assert event.value_for_test().sensor_event_observed is False
    assert event.value_for_test().hardware_verified is False
    assert event.hardware_eligible is False
    assert event.input_eligible is False
    assert "167" not in repr(event)
    assert "167" not in repr(result)
    result_payload = asdict(result)
    event_payload = asdict(event)
    rendered_payload = json.dumps(result_payload, default=str, sort_keys=True)
    assert "167" not in rendered_payload
    assert "0xa7" not in rendered_payload.lower()
    assert "_events" not in result_payload
    assert "_value" not in event_payload
    assert result_payload["simulation_only"] is True
    assert result_payload["transport_write_invoked"] is False
    assert result_payload["setter_invoked"] is False
    assert result_payload["setter_causation_observed"] is False
    assert result_payload["acknowledgement_observed"] is False
    assert result_payload["wire_terminal_observed"] is False
    assert result_payload["quiet_means_success"] is False
    assert result_payload["live_available"] is False
    assert result_payload["ring_contacted"] is False
    assert result_payload["gesture_semantics"] == "not_proven"
    assert result_payload["touch_event_observed"] is False
    assert result_payload["touch_sensor_event_observed"] is False
    assert result_payload["host_input_emitted"] is False
    assert result_payload["decoded_values_redacted"] is True
    assert result_payload["event_storage_serialized"] is False
    assert result_payload["hardware_eligible"] is False
    assert result_payload["hardware_verified"] is False
    assert result_payload["input_eligible"] is False
    assert InputMapper(()).action_for(event) is None
    for cloned in (copy(result), deepcopy(result)):
        assert cloned.event_count == 1
        assert cloned.event_kinds == (MainEventKind.TOUCH_MODE_SETTING_PROJECTION,)
        assert cloned.events_for_test()[0].value_for_test().value_for_test() == 0xA7
        cloned_payload = json.dumps(asdict(cloned), default=str, sort_keys=True)
        assert "167" not in cloned_payload
        assert "_events" not in cloned_payload
    for cloned_event in (copy(event), deepcopy(event)):
        assert cloned_event.kind is MainEventKind.TOUCH_MODE_SETTING_PROJECTION
        assert cloned_event.value_for_test().value_for_test() == 0xA7
        assert "167" not in json.dumps(asdict(cloned_event), default=str)
    # dataclasses uses ValueError on 3.10 and TypeError on newer CPython here.
    with pytest.raises((TypeError, ValueError), match="_decoded_events"):
        replace(result)
    with pytest.raises((TypeError, ValueError), match="_decoded_value"):
        replace(event)
    replaced_event = replace(event, _decoded_value=event.value_for_test())
    replaced_result = replace(result, _decoded_events=result.events_for_test())
    assert replaced_event.value_for_test().value_for_test() == 0xA7
    assert replaced_result.event_count == 1
    assert replaced_result.event_kinds == (
        MainEventKind.TOUCH_MODE_SETTING_PROJECTION,
    )
    assert "167" not in json.dumps(asdict(replaced_result), default=str)
    with pytest.raises(TypeError, match="does not match"):
        replace(
            event,
            kind=MainEventKind.DEVICE_ACTION,
            _decoded_value=event.value_for_test(),
        )
    with pytest.raises(TypeError, match="does not match"):
        replace(event, _decoded_value=None)
    with pytest.raises(ValueError, match="event count"):
        replace(
            result,
            event_count=2,
            _decoded_events=result.events_for_test(),
        )
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0


@pytest.mark.parametrize("selector", (0x00, 0x01))
def test_collects_exact_unknown_motion_channel_projection_without_write_or_input(selector):
    transport = ScriptedVendorFakeTransport.vendor_route()
    channels = (-32_768, -12_345, -1, 0, 1, 12_345, 30_000, 32_767, -22_222)
    body = bytes((selector,)) + b"".join(
        value.to_bytes(2, "little", signed=True) for value in channels
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x78, body),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 1
    assert result.unrelated_frame_count == 0
    assert result.event_kinds == (
        MainEventKind.UNKNOWN_MOTION_CHANNEL_PROJECTION,
    )
    event = result.events_for_test()[0]
    projection = event.value_for_test()
    assert projection.selector_for_test() == selector
    assert projection.channels_for_test() == channels
    assert projection.projection_role == "source_labeled_g_sensor_callback_payload"
    assert projection.selector_scope == "exact_78_00_or_01"
    assert projection.channel_count == 9
    assert projection.channel_meaning == "unknown"
    assert projection.selector_meaning == "unknown"
    assert projection.axes == "not_proven"
    assert projection.units == "not_proven"
    assert projection.sample_interval == "not_proven"
    assert projection.gesture_semantics == "not_proven"
    assert projection.sensor_event_promoted is False
    assert projection.simulation_only is True
    assert projection.transport_write_invoked is False
    assert projection.setter_causation_observed is False
    assert projection.acknowledgement_observed is False
    assert projection.wire_terminal_observed is False
    assert projection.live_available is False
    assert projection.ring_contacted is False
    assert projection.host_input_emitted is False
    assert projection.private_motion_channels_redacted is True
    assert projection.hardware_verified is False
    assert projection.input_eligible is False
    assert event.hardware_eligible is False
    assert event.input_eligible is False
    assert InputMapper(()).action_for(event) is None
    assert result.transport_write_invoked is False
    assert result.setter_invoked is False
    assert result.setter_causation_observed is False
    assert result.acknowledgement_observed is False
    assert result.wire_terminal_observed is False
    assert result.motion_sensor_event_promoted is False
    assert result.host_input_emitted is False
    assert result.live_available is False
    assert result.ring_contacted is False
    assert result.hardware_verified is False
    assert result.input_eligible is False
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0


def test_motion_projection_redacts_private_values_across_copy_and_serialization():
    transport = ScriptedVendorFakeTransport.vendor_route()
    channels = (
        -31_337, -29_111, -27_503, -24_019, 18_613,
        21_127, 23_693, 25_699, 28_201,
    )
    body = bytes((0x01,)) + b"".join(
        value.to_bytes(2, "little", signed=True) for value in channels
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x78, body),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))
    event = result.events_for_test()[0]
    projection = event.value_for_test()
    private_canaries = tuple(str(value) for value in channels)

    rendered = (
        repr(projection),
        repr(event),
        repr(result),
        json.dumps(asdict(event), default=str, sort_keys=True),
        json.dumps(asdict(result), default=str, sort_keys=True),
    )
    for canary in private_canaries:
        assert all(canary not in value for value in rendered)
    assert all('"_channels"' not in value for value in rendered)
    assert all('"_selector"' not in value for value in rendered)
    assert "channels=<redacted>" in repr(projection)

    for cloned in (copy(event), deepcopy(event)):
        assert cloned.value_for_test().channels_for_test() == channels
        payload = json.dumps(asdict(cloned), default=str, sort_keys=True)
        assert all(canary not in payload for canary in private_canaries)
    for cloned in (copy(result), deepcopy(result)):
        assert cloned.events_for_test()[0].value_for_test().channels_for_test() == channels
        payload = json.dumps(asdict(cloned), default=str, sort_keys=True)
        assert all(canary not in payload for canary in private_canaries)
    replaced_event = replace(event, _decoded_value=projection)
    replaced_result = replace(result, _decoded_events=result.events_for_test())
    assert replaced_event.value_for_test().channels_for_test() == channels
    assert replaced_result.event_count == 1
    assert all(
        canary not in json.dumps(asdict(replaced_result), default=str, sort_keys=True)
        for canary in private_canaries
    )
    with pytest.raises((TypeError, ValueError), match="_decoded_value"):
        replace(event)
    with pytest.raises((TypeError, ValueError), match="_decoded_events"):
        replace(result)
    with pytest.raises(TypeError, match="does not match"):
        replace(
            event,
            kind=MainEventKind.TOUCH_MODE_SETTING_PROJECTION,
            _decoded_value=projection,
        )


def test_unknown_motion_projection_is_decoder_owned_and_rejects_forged_shape():
    with pytest.raises(TypeError, match="decoder-owned"):
        UnknownMotionChannelProjection(0x00, (0,) * 9)
    for selector in (-1, 0x02, 0x100, True, "0"):
        with pytest.raises((TypeError, ValueError), match="selector"):
            UnknownMotionChannelProjection._create(selector, (0,) * 9)
    for channels in ((0,) * 8, (0,) * 10, [0] * 9):
        with pytest.raises((TypeError, ValueError), match="nine-value tuple"):
            UnknownMotionChannelProjection._create(0x00, channels)
    for value in (-32_769, 32_768, True, 1.0):
        forged = (0,) * 8 + (value,)
        with pytest.raises((TypeError, ValueError), match="signed 16-bit"):
            UnknownMotionChannelProjection._create(0x00, forged)
    projection = UnknownMotionChannelProjection._create(0x00, (0,) * 9)
    with pytest.raises(AttributeError, match="immutable"):
        projection._channels = (1,) * 9


def test_mixed_touch_and_unknown_motion_projections_keep_distinct_semantics():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x78, bytes((0x09, 7))))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x78, bytes((0x00,)) + bytes(18)))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x78, bytes((0x01,)) + bytes(18)))

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.event_kinds == (
        MainEventKind.TOUCH_MODE_SETTING_PROJECTION,
        MainEventKind.UNKNOWN_MOTION_CHANNEL_PROJECTION,
        MainEventKind.UNKNOWN_MOTION_CHANNEL_PROJECTION,
    )
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.wire_terminal_observed is False
    assert result.acknowledgement_observed is False
    assert transport.write_count == 0


@pytest.mark.parametrize("selector", (0x02, 0x03, 0x07, 0x08, 0x0B, 0x0C, 0x22, 0xFF))
def test_other_78_selectors_are_unrelated_without_becoming_motion(selector):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x78, bytes((selector, 7))),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.01,
    ))

    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 0
    assert result.unrelated_frame_count == 1
    assert result.events_for_test() == ()
    assert transport.write_count == 0


@pytest.mark.parametrize("selector", (0x00, 0x01))
@pytest.mark.parametrize("length", (19, 21))
def test_malformed_exact_motion_selector_rolls_back_prior_event(selector, length):
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((16,))))
        candidate = bytes((0x78, selector)) + bytes(19)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, candidate[:length])

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_selectorless_78_does_not_rollback_a_prior_touch_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x78, bytes((0x09, 7))))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x78,)))

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=2,
        quiet_timeout=0.01,
    ))

    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert result.event_kinds == (MainEventKind.TOUCH_MODE_SETTING_PROJECTION,)
    assert result.unrelated_frame_count == 1
    assert transport.write_count == 0


@pytest.mark.parametrize("length", (19, 21))
def test_malformed_exact_touch_selector_rolls_back_prior_event(length):
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((16,))))
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            (bytes((0x78, 0x09, 7)) + bytes(18))[:length],
        )

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


@pytest.mark.parametrize("opcode", (0x06, 0x22, 0x45, 0x51, 0x49))
def test_malformed_matching_event_aborts_without_exposing_a_value(opcode):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((opcode,)) + bytes(18),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


@pytest.mark.parametrize("selector", (0x00, 0x01, 0x02))
def test_overlong_matching_45_event_aborts_without_private_projection(selector):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((0x45, selector)) + bytes(19),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


@pytest.mark.parametrize("length", (19, 21))
def test_malformed_app_id_rolls_back_a_prior_valid_event(length):
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((16,))))
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            (bytes((0x45, 0x02)) + bytes(19))[:length],
        )

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_queue_overflow_aborts_and_discards_partial_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()
    event = _frame(0x06, bytes((16,)))

    def overflow(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)

    transport.before_subscribe = overflow
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_late_malformed_event_discards_an_earlier_decoded_event():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_valid_then_malformed(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((68,))))
        asyncio.get_running_loop().call_later(
            0.001,
            fake.emit,
            VENDOR_CHARACTERISTIC_33F4,
            bytes((0x51,)) + bytes(18),
        )

    transport.before_subscribe = emit_valid_then_malformed
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()


def test_cleanup_failure_discards_an_earlier_decoded_event():
    transport = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_error=RuntimeError("private cleanup detail")
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x06, bytes((68,))),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.CLEANUP_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert "private" not in repr(result)


def test_exact_fake_main_response_target_and_route_are_required():
    class UnsafeFakeSubclass(ScriptedVendorFakeTransport):
        pass

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorMainEventSimulator(UnsafeFakeSubclass(services=set(), metadata=()))

    wrong_route = ScriptedVendorFakeTransport.raw_vendor_route()
    result = run(FakeVendorMainEventSimulator(wrong_route).collect(quiet_timeout=0.01))
    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert wrong_route.targeted_subscribe_count == 0
    assert wrong_route.write_count == 0

    missing_target = ScriptedVendorFakeTransport.vendor_route()
    real_inventory = missing_target.gatt_characteristics

    async def inventory_without_response_target():
        records = await real_inventory()
        return tuple(
            replace(record, target=None)
            if record.uuid == VENDOR_CHARACTERISTIC_33F4
            else record
            for record in records
        )

    missing_target.gatt_characteristics = inventory_without_response_target
    result = run(FakeVendorMainEventSimulator(missing_target).collect())
    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert missing_target.targeted_subscribe_count == 0
    assert missing_target.write_count == 0


def test_revoked_response_target_after_structural_preflight_fails_closed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    real_owns_target = transport.owns_target
    transport.owns_target = lambda target: (
        target.uuid != VENDOR_CHARACTERISTIC_33F4 and real_owns_target(target)
    )

    result = run(FakeVendorMainEventSimulator(transport).collect())

    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert transport.targeted_subscribe_count == 0
    assert transport.write_count == 0
    assert transport.close_count == 1


def test_stage_overall_and_cleanup_deadlines_abort_with_stable_reasons():
    stage_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(stage_blocked).collect(
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))
    assert result.reason is MainEventSimulationReason.STAGE_TIMEOUT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED

    overall_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(overall_blocked).collect(
        stage_timeout=1.0,
        overall_timeout=0.01,
    ))
    assert result.reason is MainEventSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(cleanup_blocked).collect(
        quiet_timeout=0.01,
        cleanup_timeout=0.01,
    ))
    assert result.reason is MainEventSimulationReason.CLEANUP_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False


@pytest.mark.parametrize(
    "controls",
    (
        {"connect_error": RuntimeError("private connect detail")},
        {"service_inventory_error": RuntimeError("private inventory detail")},
        {"metadata_error": RuntimeError("private metadata detail")},
        {"subscribe_error": RuntimeError("private subscribe detail")},
    ),
)
def test_ordinary_transport_errors_map_to_redacted_preflight_failure(controls):
    transport = ScriptedVendorFakeTransport.vendor_route(**controls)

    result = run(FakeVendorMainEventSimulator(transport).collect())

    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert "private" not in repr(result)
    assert transport.write_count == 0


def test_disconnect_aborts_without_consuming_an_already_queued_event():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_then_disconnect(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((2,))))
        asyncio.get_running_loop().call_soon(fake.emit_disconnect)

    transport.before_subscribe = emit_then_disconnect
    result = run(FakeVendorMainEventSimulator(transport).collect(quiet_timeout=0.1))

    assert result.reason is MainEventSimulationReason.DISCONNECTED
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_concurrent_collection_is_rejected_without_second_transport_io():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        first = asyncio.create_task(simulator.collect(
            quiet_timeout=0.01,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        with pytest.raises(RuntimeError, match="already in progress"):
            await simulator.collect()
        assert transport.connect_count == 1
        gate.release()
        return await first

    result = run(scenario())
    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert transport.write_count == 0


def test_two_simulators_cannot_share_one_transport_concurrently():
    transport = ScriptedVendorFakeTransport.vendor_route()
    first_simulator = FakeVendorMainEventSimulator(transport)
    second_simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        first = asyncio.create_task(first_simulator.collect(quiet_timeout=1.0))
        while transport.subscribe_count == 0:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await second_simulator.collect()
        assert transport.connect_count == 1
        assert transport.close_count == 0
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    run(scenario())
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_preconnected_transport_is_rejected_without_closing_caller_connection():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        await transport.connect()
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await FakeVendorMainEventSimulator(transport).collect()

    run(scenario())
    assert transport.connected is True
    assert transport.connect_count == 1
    assert transport.close_count == 0
    assert transport.subscribe_count == 0


def test_transport_lease_blocks_a_different_fake_coordinator_without_interference():
    transport = ScriptedVendorFakeTransport.vendor_route()
    passive = FakeVendorMainEventSimulator(transport)
    history = FakeVendorHistorySimulator(transport)

    async def scenario():
        first = asyncio.create_task(passive.collect(quiet_timeout=1.0))
        while transport.subscribe_count == 0:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await history.collect(
                request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0)
            )
        assert transport.connect_count == 1
        assert transport.close_count == 0
        assert transport.write_count == 0
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    run(scenario())
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert transport.write_count == 0


def test_cancellation_cleans_up_releases_single_flight_and_stales_callback():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorMainEventSimulator(transport)
    original_subscribe = transport.subscribe_target

    async def scenario():
        subscribed = asyncio.Event()

        async def observed_subscribe(target, callback):
            await original_subscribe(target, callback)
            subscribed.set()

        transport.subscribe_target = observed_subscribe
        task = asyncio.create_task(simulator.collect(quiet_timeout=1.0))
        await subscribed.wait()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        reused = await simulator.collect(quiet_timeout=0.01)
        return reused

    result = run(scenario())
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]

    assert transport.unsubscribe_count == 2
    assert transport.close_count == 2
    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, _frame(0x06, bytes((68,))))
    assert retained_queues[0].qsize() == 0
    assert transport.write_count == 0


def test_cancellation_during_postevent_unsubscribe_finishes_bounded_close():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(unsubscribe_gate=gate)
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((0x45, 0x02)) + b"private-app-id-12Z",
    )
    simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            event_limit=1,
            cleanup_timeout=0.02,
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert transport.connected is False


def test_cancellation_during_preflight_close_remains_bounded():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(
        connect_error=RuntimeError("private setup detail"),
        close_gate=gate,
    )
    simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.collect(cleanup_timeout=0.02))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert transport.write_count == 0
    assert transport.close_count == 1


@pytest.mark.parametrize(
    "kwargs,error",
    (
        ({"event_limit": True}, TypeError),
        ({"event_limit": 0}, ValueError),
        ({"event_limit": 4097}, ValueError),
        ({"quiet_timeout": float("nan")}, ValueError),
        ({"overall_timeout": 0}, ValueError),
        ({"stage_timeout": "soon"}, TypeError),
        ({"cleanup_timeout": -1}, ValueError),
    ),
)
def test_collection_bounds_are_validated_before_transport_io(kwargs, error):
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises(error):
        run(FakeVendorMainEventSimulator(transport).collect(**kwargs))

    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0
