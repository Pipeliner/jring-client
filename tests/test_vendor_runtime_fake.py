import asyncio

import pytest

from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_runtime_fake import (
    ScriptGate,
    ScriptedVendorFakeTransport,
)


CCCD = uuid16(0x2902)


def run(coro):
    return asyncio.run(coro)


def test_default_route_metadata_is_explicit_but_never_hardware_eligible():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        await transport.connect()
        assert await transport.service_uuids() == {VENDOR_SERVICE_56FF}
        metadata = await transport.gatt_characteristics()
        assert [(item.service_uuid, item.uuid) for item in metadata] == [
            (VENDOR_SERVICE_56FF, VENDOR_CHARACTERISTIC_33F3),
            (VENDOR_SERVICE_56FF, VENDOR_CHARACTERISTIC_33F4),
        ]
        assert metadata[0].properties == ("write",)
        assert metadata[1].properties == ("notify",)
        assert metadata[1].descriptor_uuids == (CCCD,)

    run(scenario())
    assert transport.simulation_only is True
    assert transport.hardware_eligible is False
    assert "simulation_only=True" in repr(transport)


def test_subscribe_installs_callback_before_the_call_is_allowed_to_finish():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(subscribe_gate=gate)
    received = []

    async def scenario():
        await transport.connect()
        task = asyncio.create_task(
            transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        )
        await gate.wait_until_entered()

        assert transport.subscribe_count == 1
        assert transport.active_callback_count == 1
        transport.emit(VENDOR_CHARACTERISTIC_33F4, b"early")
        assert received == [b"early"]
        assert not task.done()

        gate.release()
        await task

    run(scenario())


def test_response_write_is_recorded_before_hook_gate_and_completion():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    received = []

    async def before_write(fake, call):
        assert call.response_requested is True
        assert fake.write_count == 1
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"response-before-write-return")

    transport.before_write = before_write

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        task = asyncio.create_task(
            transport.write(VENDOR_CHARACTERISTIC_33F3, b"request")
        )
        await gate.wait_until_entered()

        assert received == [b"response-before-write-return"]
        assert transport.response_write_calls[0].characteristic_uuid == (
            VENDOR_CHARACTERISTIC_33F3
        )
        assert transport.response_write_calls[0].data_for_test() == b"request"
        assert not task.done()

        gate.release()
        await task

    run(scenario())
    assert "request" not in repr(transport.response_write_calls[0])


def test_injected_subscribe_error_occurs_after_callback_installation():
    error = OSError("start-notify failed")
    transport = ScriptedVendorFakeTransport.vendor_route(subscribe_error=error)
    received = []

    async def scenario():
        await transport.connect()
        with pytest.raises(OSError, match="start-notify"):
            await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)

        assert transport.active_callback_count == 1
        transport.emit(VENDOR_CHARACTERISTIC_33F4, b"late")
        assert received == [b"late"]

    run(scenario())


def test_injected_write_error_still_records_an_attempt_and_early_response():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=TimeoutError("write acknowledgement missing")
    )
    received = []

    def before_write(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"device-may-have-acted")

    transport.before_write = before_write

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        with pytest.raises(TimeoutError, match="acknowledgement"):
            await transport.write(VENDOR_CHARACTERISTIC_33F3, b"request")

    run(scenario())
    assert received == [b"device-may-have-acted"]
    assert transport.write_count == 1
    assert len(transport.response_write_calls) == 1


def test_unsubscribe_gate_and_error_leave_callback_active_for_cleanup_tests():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=gate,
        unsubscribe_error=OSError("stop-notify uncertain"),
    )
    received = []

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        task = asyncio.create_task(transport.unsubscribe(VENDOR_CHARACTERISTIC_33F4))
        await gate.wait_until_entered()
        assert transport.unsubscribe_count == 1
        assert transport.active_callback_count == 1
        gate.release()
        with pytest.raises(OSError, match="stop-notify"):
            await task
        assert transport.active_callback_count == 1

    run(scenario())


def test_stale_callback_can_be_retained_and_emitted_after_unsubscribe():
    transport = ScriptedVendorFakeTransport.vendor_route()
    received = []

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        await transport.unsubscribe(VENDOR_CHARACTERISTIC_33F4)

        assert transport.active_callback_count == 0
        assert transport.retained_callback_count == 1
        transport.emit_stale(0, b"stale-generation")

    run(scenario())
    assert received == [b"stale-generation"]


def test_disconnect_event_listener_and_counts_are_explicit_fake_extensions():
    transport = ScriptedVendorFakeTransport.vendor_route()
    observed = []

    async def scenario():
        await transport.connect()
        transport.add_disconnect_listener(observed.append)
        marker = ConnectionError("simulated link loss")
        transport.emit_disconnect(marker)

        await transport.disconnect_event.wait()
        assert transport.connected is False
        assert transport.disconnect_count == 1
        assert observed == [marker]

    run(scenario())


def test_metadata_route_variants_and_inventory_exceptions_are_scriptable():
    transport = ScriptedVendorFakeTransport.vendor_route(
        services=set(),
        write_properties=("write-without-response",),
        notify_properties=("indicate",),
        response_descriptors=(),
        metadata_error=LookupError("metadata unavailable"),
    )

    async def scenario():
        await transport.connect()
        assert await transport.service_uuids() == set()
        with pytest.raises(LookupError, match="metadata unavailable"):
            await transport.gatt_characteristics()

    run(scenario())
    metadata = transport.metadata_snapshot_for_test()
    assert metadata[0].properties == ("write-without-response",)
    assert metadata[1].properties == ("indicate",)
    assert metadata[1].descriptor_uuids == ()
    assert transport.service_inventory_count == 1
    assert transport.metadata_inventory_count == 1


def test_close_clears_active_callbacks_but_keeps_stale_handles_for_race_tests():
    transport = ScriptedVendorFakeTransport.vendor_route()
    received = []

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        await transport.close()
        assert transport.close_count == 1
        assert transport.active_callback_count == 0
        assert transport.retained_callback_count == 1
        transport.emit_stale(0, b"after-close")

    run(scenario())
    assert received == [b"after-close"]


@pytest.mark.parametrize(
    "action",
    [
        lambda fake: fake.read(VENDOR_CHARACTERISTIC_33F3),
        lambda fake: fake.write(VENDOR_CHARACTERISTIC_33F3, b"request"),
        lambda fake: fake.write_with_response(VENDOR_CHARACTERISTIC_33F3, b"request"),
        lambda fake: fake.subscribe(VENDOR_CHARACTERISTIC_33F4, lambda _data: None),
        lambda fake: fake.unsubscribe(VENDOR_CHARACTERISTIC_33F4),
        lambda fake: fake.service_uuids(),
        lambda fake: fake.gatt_characteristics(),
    ],
)
def test_disconnected_io_is_rejected(action):
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        with pytest.raises(ConnectionError, match="not connected"):
            await action(transport)

    run(scenario())


def test_duplicate_connect_is_rejected_without_advancing_generation():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        await transport.connect()
        with pytest.raises(ConnectionError, match="already connected"):
            await transport.connect()

    run(scenario())
    assert transport.connect_count == 1
    assert transport.connection_generation == 1


def test_disconnect_clears_active_callback_and_requires_stale_emitter():
    transport = ScriptedVendorFakeTransport.vendor_route()
    received = []

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, received.append)
        transport.emit_disconnect()
        assert transport.active_callback_count == 0
        with pytest.raises(KeyError):
            transport.emit(VENDOR_CHARACTERISTIC_33F4, b"ordinary")
        transport.emit_stale(0, b"explicit-stale")

    run(scenario())
    assert received == [b"explicit-stale"]


def test_disconnect_listeners_are_removable_and_isolated():
    transport = ScriptedVendorFakeTransport.vendor_route()
    observed = []

    async def scenario():
        await transport.connect()
        remove = transport.add_disconnect_listener(
            lambda _error: (_ for _ in ()).throw(RuntimeError("listener bug"))
        )
        transport.add_disconnect_listener(lambda error: observed.append(error))
        remove()
        marker = ConnectionError("lost")
        transport.emit_disconnect(marker)

    run(scenario())
    assert len(observed) == 1
    assert str(observed[0]) == "lost"


def test_sensitive_fake_state_has_explicit_irreversible_cleanup():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        await transport.connect()
        await transport.subscribe(VENDOR_CHARACTERISTIC_33F4, lambda _data: None)
        await transport.write_with_response(
            VENDOR_CHARACTERISTIC_33F3, b"private-request"
        )

    run(scenario())
    assert transport.response_write_calls
    assert transport.retained_callback_count == 1

    transport.clear_sensitive_test_state()

    assert transport.response_write_calls == []
    assert transport.subscription_calls == []
    assert transport.unsubscribe_calls == []
    assert transport.retained_callback_count == 0
    assert transport.last_disconnect_error is None
