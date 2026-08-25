import asyncio
from dataclasses import replace

import pytest

from jring.client import JRingClient
from jring.protocol import ProtocolError
from jring.transport import FakeTransport, GattCharacteristicMetadata
from jring.uuids import (
    HEART_RATE_MEASUREMENT,
    HEART_RATE_SERVICE,
    CLIENT_CHARACTERISTIC_CONFIGURATION,
)


def run(coro):
    return asyncio.run(coro)


async def _wait_for_subscription(transport):
    while transport.heart_rate_subscription_count == 0:
        await asyncio.sleep(0)
    # The fake's counter is updated inside the awaited transport call; give the
    # client one turn to confirm the returned token before injecting data.
    await asyncio.sleep(0)


def test_exact_standard_target_yields_one_sample_then_cleans_up():
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport, timeout=0.1) as client:
            task = asyncio.create_task(client.heart_rate_sample())
            await _wait_for_subscription(transport)
            transport.emit(HEART_RATE_MEASUREMENT, b"\x06\x48")
            return await task

    result = run(scenario())
    assert result.bpm == 72
    assert result.contact_detected is True
    assert transport.heart_rate_subscription_count == 1
    assert transport.heart_rate_unsubscription_count == 1
    assert transport.callbacks == {}
    assert transport.write_count == 0


@pytest.mark.parametrize(
    "records",
    (
        (
            GattCharacteristicMetadata(
                HEART_RATE_SERVICE,
                HEART_RATE_MEASUREMENT,
                ("read",),
                (CLIENT_CHARACTERISTIC_CONFIGURATION,),
            ),
        ),
        (
            GattCharacteristicMetadata(
                HEART_RATE_SERVICE,
                HEART_RATE_MEASUREMENT,
                ("notify",),
                (),
            ),
        ),
        (
            GattCharacteristicMetadata(
                "0000180f-0000-1000-8000-00805f9b34fb",
                HEART_RATE_MEASUREMENT,
                ("notify",),
                (CLIENT_CHARACTERISTIC_CONFIGURATION,),
            ),
        ),
        (
            GattCharacteristicMetadata(
                HEART_RATE_SERVICE,
                HEART_RATE_MEASUREMENT,
                ("notify",),
                (CLIENT_CHARACTERISTIC_CONFIGURATION,),
            ),
            GattCharacteristicMetadata(
                HEART_RATE_SERVICE,
                HEART_RATE_MEASUREMENT,
                ("notify",),
                (CLIENT_CHARACTERISTIC_CONFIGURATION,),
            ),
        ),
    ),
)
def test_wrong_nonnotify_missing_cccd_or_duplicate_target_never_subscribes(records):
    transport = FakeTransport({}, {HEART_RATE_SERVICE}, gatt_metadata=records)

    async def scenario():
        async with JRingClient(transport, timeout=0.05) as client:
            with pytest.raises(ProtocolError, match="heart-rate endpoint"):
                await client.heart_rate_sample()

    run(scenario())
    assert transport.heart_rate_subscription_count == 0
    assert transport.write_count == 0


def test_unowned_current_snapshot_target_never_subscribes():
    transport = FakeTransport.standard_ring()
    transport.owns_target = lambda _target: False

    async def scenario():
        async with JRingClient(transport, timeout=0.05) as client:
            with pytest.raises(ProtocolError, match="heart-rate endpoint"):
                await client.heart_rate_sample()

    run(scenario())
    assert transport.heart_rate_subscription_count == 0


def test_notification_before_subscription_confirmation_is_ignored():
    class EarlyTransport(FakeTransport):
        async def subscribe_heart_rate_measurement(self, target, callback):
            callback(b"\x00\x63")
            return await super().subscribe_heart_rate_measurement(target, callback)

    source = FakeTransport.standard_ring()
    transport = EarlyTransport(
        source.values,
        source.services,
        gatt_metadata=source.gatt_metadata,
    )

    async def scenario():
        async with JRingClient(transport, timeout=0.01) as client:
            with pytest.raises(TimeoutError, match="heart-rate measurement"):
                await client.heart_rate_sample()

    run(scenario())
    assert transport.heart_rate_unsubscription_count == 1


def test_malformed_or_overflowed_attempt_exposes_no_measurement():
    async def malformed():
        transport = FakeTransport.standard_ring()
        async with JRingClient(transport, timeout=0.1) as client:
            task = asyncio.create_task(client.heart_rate_sample())
            await _wait_for_subscription(transport)
            transport.emit(HEART_RATE_MEASUREMENT, b"\x00")
            with pytest.raises(ProtocolError, match="heart-rate measurement"):
                await task
        return transport

    async def overflow():
        transport = FakeTransport.standard_ring()
        async with JRingClient(transport, timeout=0.1) as client:
            task = asyncio.create_task(client.heart_rate_sample())
            await _wait_for_subscription(transport)
            transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x48")
            transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x49")
            with pytest.raises(ProtocolError, match="overflow"):
                await task
        return transport

    malformed_transport = run(malformed())
    overflow_transport = run(overflow())
    assert malformed_transport.heart_rate_unsubscription_count == 1
    assert overflow_transport.heart_rate_unsubscription_count == 1


def test_disconnect_wins_over_an_already_queued_value():
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport, timeout=0.1) as client:
            task = asyncio.create_task(client.heart_rate_sample())
            await _wait_for_subscription(transport)
            transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x48")
            transport.emit_disconnect()
            with pytest.raises(ConnectionError, match="disconnected"):
                await task

    run(scenario())
    assert transport.write_count == 0


def test_cleanup_failure_discards_a_parsed_value_and_close_still_runs_once():
    class CleanupFailure(FakeTransport):
        async def unsubscribe_heart_rate_measurement(self, subscription):
            await super().unsubscribe_heart_rate_measurement(subscription)
            raise OSError("private cleanup detail")

    source = FakeTransport.standard_ring()
    transport = CleanupFailure(
        source.values,
        source.services,
        gatt_metadata=source.gatt_metadata,
    )

    async def scenario():
        with pytest.raises(ConnectionError, match="cleanup"):
            async with JRingClient(transport, timeout=0.1) as client:
                task = asyncio.create_task(client.heart_rate_sample())
                await _wait_for_subscription(transport)
                transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x48")
                await task

    run(scenario())
    assert transport.close_count == 1
    assert transport.callbacks == {}


def test_cancellation_cleans_up_and_stale_callback_cannot_enter_reuse():
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport, timeout=0.1) as client:
            first = asyncio.create_task(client.heart_rate_sample())
            await _wait_for_subscription(transport)
            stale = tuple(transport.retained_heart_rate_callbacks)[0]
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first

            second = asyncio.create_task(client.heart_rate_sample())
            while transport.heart_rate_subscription_count < 2:
                await asyncio.sleep(0)
            stale(b"\x00\x63")
            await asyncio.sleep(0)
            transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x48")
            return await second

    result = run(scenario())
    assert result.bpm == 72
    assert transport.heart_rate_unsubscription_count == 2


def test_capability_inventory_reports_structural_heart_rate_readiness_without_io():
    class MetadataOnly(FakeTransport):
        async def read(self, _characteristic):
            raise AssertionError("capability inventory must not read")

        async def subscribe_heart_rate_measurement(self, _target, _callback):
            raise AssertionError("capability inventory must not subscribe")

    source = FakeTransport.standard_ring()
    transport = MetadataOnly(
        {}, source.services, gatt_metadata=source.gatt_metadata
    )

    async def scenario():
        async with JRingClient(transport) as client:
            return await client.capability_inventory()

    inventory = run(scenario())
    heart_rate = inventory.standard_heart_rate
    assert heart_rate.service_state == "advertised"
    assert heart_rate.measurement_characteristic_state == "notify_advertised"
    assert heart_rate.instance_count == 1
    assert heart_rate.instance_resolution_state == "uuid_unique"
    assert heart_rate.cccd_state == "advertised"
    assert heart_rate.targeting_state == "structurally_ready"
    assert heart_rate.value_state == "not_read"
    assert heart_rate.subscription_state == "not_attempted"
    assert heart_rate.live_delivery_state == "not_tested"


def test_failed_inventory_drains_blocked_sibling_before_context_close():
    class SplitFailure(FakeTransport):
        def __init__(self):
            source = FakeTransport.standard_ring()
            super().__init__(
                source.values,
                source.services,
                gatt_metadata=source.gatt_metadata,
            )
            self.metadata_started = asyncio.Event()
            self.metadata_cancelled = False
            self.close_while_metadata_active = False

        async def service_uuids(self):
            await self.metadata_started.wait()
            raise LookupError("private discovery detail")

        async def gatt_characteristics(self):
            self.metadata_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.metadata_cancelled = True
                raise

        async def close(self):
            self.close_while_metadata_active = not self.metadata_cancelled
            await super().close()

    transport = SplitFailure()

    async def scenario():
        with pytest.raises(LookupError):
            async with JRingClient(transport, timeout=0.1) as client:
                await client.heart_rate_sample()

    run(scenario())
    assert transport.metadata_cancelled is True
    assert transport.close_while_metadata_active is False
    assert transport.close_count == 1
    assert transport.connected is False
    assert transport.heart_rate_subscription_count == 0
    assert transport.write_count == 0
