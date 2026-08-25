import asyncio
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from jring.bleak_transport import BleakTransport
from jring.transport import GattCharacteristicTarget, TargetedBleTransport
from jring.uuids import (
    CURRENT_TIME,
    CURRENT_TIME_SERVICE,
    HID_REPORT,
    HUMAN_INTERFACE_DEVICE_SERVICE,
    REPORT_REFERENCE_DESCRIPTOR,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_SERVICE_56FF,
)


CURRENT_TIME_VALUE = b"\xe8\x07\x01\x02\x03\x04\x05\x02\x00\x01"
TEST_ADDRESS = "synthetic-device"


def current_time_service(*, properties=("write",)):
    characteristic = SimpleNamespace(
        uuid=CURRENT_TIME,
        properties=list(properties),
        descriptors=[],
    )
    service = SimpleNamespace(
        uuid=CURRENT_TIME_SERVICE,
        characteristics=[characteristic],
    )
    return service, characteristic


def test_bleak_one_x_none_return_is_a_successful_connection(monkeypatch):
    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.timeout = timeout
            self.disconnected_callback = disconnected_callback
            self.is_connected = False

        async def connect(self):
            self.is_connected = True
            return None

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    asyncio.run(transport.connect())


def test_bleak_gatt_inventory_enumerates_metadata_without_reading_values(monkeypatch):
    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE.upper(),
                    characteristics=[
                        SimpleNamespace(
                            uuid=HID_REPORT.upper(),
                            properties=["notify"],
                            descriptors=[SimpleNamespace(uuid=REPORT_REFERENCE_DESCRIPTOR.upper())],
                        )
                    ],
                )
            ]

        async def read_gatt_char(self, _uuid):
            raise AssertionError("metadata inventory must not read a value")

        async def connect(self):
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        return await transport.gatt_characteristics()

    result = asyncio.run(scenario())

    assert result[0].service_uuid == HUMAN_INTERFACE_DEVICE_SERVICE
    assert result[0].uuid == HID_REPORT
    assert result[0].properties == ("notify",)
    assert result[0].descriptor_uuids == (REPORT_REFERENCE_DESCRIPTOR,)
    assert result[0].instance_id == "service-1-characteristic-1"
    assert result[0].descriptor_instance_ids == (
        "service-1-characteristic-1-descriptor-1",
    )


def test_bleak_write_with_response_requests_and_awaits_gatt_response(monkeypatch):
    completed = False
    service, target = current_time_service()

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [service]

        async def connect(self):
            self.is_connected = True

        async def write_gatt_char(self, characteristic, data, *, response):
            nonlocal completed
            assert characteristic is target
            assert data == CURRENT_TIME_VALUE
            assert response is True
            await asyncio.sleep(0)
            completed = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        await transport.write_with_response(CURRENT_TIME, CURRENT_TIME_VALUE)

    asyncio.run(scenario())

    assert completed is True


def test_bleak_write_with_response_propagates_response_failure(monkeypatch):
    class ExpectedFailure(Exception):
        pass

    service, _target = current_time_service()

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [service]

        async def connect(self):
            self.is_connected = True

        async def write_gatt_char(self, _characteristic, _data, *, response):
            assert response is True
            raise ExpectedFailure("write response failed")

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        await transport.write_with_response(CURRENT_TIME, CURRENT_TIME_VALUE)

    try:
        asyncio.run(scenario())
    except ExpectedFailure as exc:
        assert str(exc) == "write response failed"
    else:
        raise AssertionError("response failures must propagate")


def test_connection_scoped_targets_map_exact_characteristic_objects_without_io(monkeypatch):
    first = SimpleNamespace(uuid=HID_REPORT, properties=["notify"], descriptors=[])
    second = SimpleNamespace(uuid=HID_REPORT, properties=["notify"], descriptors=[])

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
                    characteristics=[first, second],
                )
            ]

        async def connect(self):
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        metadata = await transport.gatt_characteristics()
        assert metadata[0].target is not None
        assert metadata[1].target is not None
        assert metadata[0].target != metadata[1].target
        refreshed = await transport.gatt_characteristics()
        assert refreshed[0].target is metadata[0].target
        assert refreshed[1].target is metadata[1].target
        return metadata

    metadata = asyncio.run(scenario())

    assert transport.owns_target(metadata[0].target) is True
    assert transport.owns_target(metadata[1].target) is True
    assert transport._targets[id(metadata[0].target)][1] is first
    assert transport._targets[id(metadata[1].target)][1] is second
    assert metadata[0].target.instance_id != metadata[1].target.instance_id


def test_forged_and_disconnected_targets_are_not_owned(monkeypatch):
    characteristic = SimpleNamespace(
        uuid=HID_REPORT, properties=["notify"], descriptors=[]
    )

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
                    characteristics=[characteristic],
                )
            ]
            self.write_count = 0

        async def connect(self):
            self.is_connected = True

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.write_count += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        target = (await transport.gatt_characteristics())[0].target
        assert target is not None
        forged = GattCharacteristicTarget(
            target.connection_generation,
            target.service_uuid,
            target.uuid,
            target.instance_id,
        )
        assert transport.owns_target(forged) is False
        assert transport.owns_target(target) is True
        transport._client.is_connected = False
        transport._client.disconnected_callback(transport._client)
        assert transport.owns_target(target) is False

    asyncio.run(scenario())
    assert transport._client.write_count == 0


def test_disconnect_listeners_are_isolated_removable_and_fire_once(monkeypatch):
    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False

        async def connect(self):
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)
    observed = []
    transport.add_disconnect_listener(
        lambda _error: (_ for _ in ()).throw(RuntimeError("listener failure"))
    )
    remove = transport.add_disconnect_listener(lambda error: observed.append(error))

    async def scenario():
        await transport.connect()
        transport._client.is_connected = False
        transport._client.disconnected_callback(transport._client)
        transport._client.disconnected_callback(transport._client)
        remove()
        await transport.connect()
        transport._client.is_connected = False
        transport._client.disconnected_callback(transport._client)

    asyncio.run(scenario())
    assert observed == [None]


def test_failed_metadata_refresh_revokes_previous_snapshot_target(monkeypatch):
    characteristic = SimpleNamespace(
        uuid=HID_REPORT, properties=["notify"], descriptors=[]
    )

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.fail_inventory = False
            self.write_count = 0

        @property
        def services(self):
            if self.fail_inventory:
                raise OSError("inventory failed")
            return [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
                    characteristics=[characteristic],
                )
            ]

        async def connect(self):
            self.is_connected = True

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.write_count += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        target = (await transport.gatt_characteristics())[0].target
        assert target is not None
        transport._client.fail_inventory = True
        with pytest.raises(OSError, match="inventory failed"):
            await transport.gatt_characteristics()
        assert transport.owns_target(target) is False

    asyncio.run(scenario())
    assert transport._client.write_count == 0


def test_successful_bleak_snapshot_omission_revokes_removed_target_without_growth(
    monkeypatch,
):
    first = SimpleNamespace(uuid=HID_REPORT, properties=["notify"], descriptors=[])
    second = SimpleNamespace(uuid=HID_REPORT, properties=["notify"], descriptors=[])
    service = SimpleNamespace(
        uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
        characteristics=[first, second],
    )

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [service]

        async def connect(self):
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        original = await transport.gatt_characteristics()
        first_target = original[0].target
        removed_target = original[1].target
        assert first_target is not None
        assert removed_target is not None
        assert len(transport._targets) == 2
        assert len(transport._targets_by_backend_id) == 2

        service.characteristics = [first]
        for _attempt in range(3):
            reduced = await transport.gatt_characteristics()
            assert len(reduced) == 1
            assert reduced[0].target is first_target
            assert transport.owns_target(first_target) is True
            assert transport.owns_target(removed_target) is False
            assert len(transport._targets) == 1
            assert len(transport._targets_by_backend_id) == 1

        service.characteristics = [first, second]
        restored = await transport.gatt_characteristics()
        assert restored[0].target is first_target
        assert restored[1].target is not removed_target
        assert transport.owns_target(removed_target) is False
        assert len(transport._targets) == 2
        assert len(transport._targets_by_backend_id) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "specifier",
    [
        VENDOR_CHARACTERISTIC_33F3,
        "33f3",
        UUID(VENDOR_CHARACTERISTIC_33F3),
        7,
        SimpleNamespace(uuid=VENDOR_CHARACTERISTIC_33F3),
    ],
)
def test_live_write_allowlist_rejects_every_vendor_or_nonstandard_specifier(
    monkeypatch, specifier
):
    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = True
            self.write_count = 0

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.write_count += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    with pytest.raises(PermissionError, match="Current Time"):
        asyncio.run(transport.write_with_response(specifier, b"payload"))
    assert transport._client.write_count == 0


@pytest.mark.parametrize(
    ("services", "payload"),
    [
        (
            [
                SimpleNamespace(
                    uuid=VENDOR_SERVICE_56FF,
                    characteristics=[
                        SimpleNamespace(
                            uuid=CURRENT_TIME,
                            properties=["write"],
                            descriptors=[],
                        )
                    ],
                )
            ],
            CURRENT_TIME_VALUE,
        ),
        (
            [current_time_service()[0], current_time_service()[0]],
            CURRENT_TIME_VALUE,
        ),
        ([current_time_service(properties=("read",))[0]], CURRENT_TIME_VALUE),
        ([current_time_service()[0]], b"payload"),
    ],
)
def test_current_time_write_rejects_wrong_ambiguous_nonwritable_or_malformed_route(
    monkeypatch, services, payload
):
    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = services
            self.write_count = 0

        async def connect(self):
            self.is_connected = True

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.write_count += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        with pytest.raises(PermissionError, match="Current Time"):
            await transport.write_with_response(CURRENT_TIME, payload)

    asyncio.run(scenario())
    assert transport._client.write_count == 0


def test_bleak_exposes_target_ownership_but_no_live_target_io():
    target_io = (
        "read_target",
        "write_target_with_response",
        "subscribe_target",
        "unsubscribe_target",
    )
    for name in target_io:
        assert not hasattr(BleakTransport, name)
        assert not hasattr(TargetedBleTransport, name)
    assert hasattr(TargetedBleTransport, "add_disconnect_listener")
    assert hasattr(TargetedBleTransport, "owns_target")


def test_late_old_client_disconnect_cannot_invalidate_new_generation(monkeypatch):
    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
                    characteristics=[
                        SimpleNamespace(
                            uuid=HID_REPORT, properties=["notify"], descriptors=[]
                        )
                    ],
                )
            ]
            self.instances.append(self)

        async def connect(self):
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)
    observed = []
    transport.add_disconnect_listener(observed.append)

    async def scenario():
        await transport.connect()
        first_client = transport._client
        first_client.is_connected = False
        first_client.disconnected_callback(first_client)
        await transport.connect()
        second_client = transport._client
        target = (await transport.gatt_characteristics())[0].target
        assert target is not None
        first_client.disconnected_callback(first_client)
        assert transport.owns_target(target) is True
        second_client.is_connected = False
        second_client.disconnected_callback(second_client)
        assert transport.owns_target(target) is False

    asyncio.run(scenario())
    assert observed == [None, None]


def test_bleak_connect_and_close_lifecycle_is_single_flight(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()

    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.instances.append(self)

        async def connect(self):
            entered.set()
            await release.wait()
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        first = asyncio.create_task(transport.connect())
        await entered.wait()
        with pytest.raises(ConnectionError, match="connecting or connected"):
            await transport.connect()
        with pytest.raises(ConnectionError, match="lifecycle operation"):
            await transport.close()
        release.set()
        await first
        with pytest.raises(ConnectionError, match="connecting or connected"):
            await transport.connect()

    asyncio.run(scenario())
    assert transport._connection_generation == 1
    assert len(Client.instances) == 2  # inert constructor client plus one attempt


def test_failed_bleak_connect_retry_uses_fresh_candidate(monkeypatch):
    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.instances.append(self)

        async def connect(self):
            if self is self.instances[1]:
                raise OSError("first candidate failed")
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        with pytest.raises(OSError, match="first candidate failed"):
            await transport.connect()
        await transport.connect()

    asyncio.run(scenario())
    assert transport._connection_generation == 1
    assert len(Client.instances) == 3


def test_failed_candidate_disconnect_cannot_alias_successful_retry(monkeypatch):
    characteristic = SimpleNamespace(
        uuid=HID_REPORT, properties=["notify"], descriptors=[]
    )

    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE,
                    characteristics=[characteristic],
                )
            ]
            self.instances.append(self)

        async def connect(self):
            if self is self.instances[1]:
                raise OSError("candidate failed")
            self.is_connected = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)
    observed = []
    transport.add_disconnect_listener(observed.append)

    async def scenario():
        with pytest.raises(OSError, match="candidate failed"):
            await transport.connect()
        failed_client = Client.instances[1]
        await transport.connect()
        current_client = transport._client
        target = (await transport.gatt_characteristics())[0].target
        assert target is not None

        failed_client.disconnected_callback(failed_client)
        assert transport.owns_target(target) is True
        assert observed == []

        current_client.is_connected = False
        current_client.disconnected_callback(current_client)
        assert transport.owns_target(target) is False
        assert observed == [None]

    asyncio.run(scenario())


def test_failed_connected_candidate_is_never_promoted_to_live_io(monkeypatch):
    service, _target = current_time_service()

    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.services = [service]
            self.backend_calls = 0
            self.instances.append(self)

        async def connect(self):
            self.is_connected = True
            if len(self.instances) >= 3 and self is self.instances[2]:
                raise OSError("connected candidate failed promotion")

        async def disconnect(self):
            self.is_connected = False

        async def read_gatt_char(self, _characteristic):
            self.backend_calls += 1

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.backend_calls += 1

        async def start_notify(self, _characteristic, _callback):
            self.backend_calls += 1

        async def stop_notify(self, _characteristic):
            self.backend_calls += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        await transport.close()
        with pytest.raises(OSError, match="failed promotion"):
            await transport.connect()

        actions = (
            transport.read(HID_REPORT),
            transport.write_with_response(CURRENT_TIME, CURRENT_TIME_VALUE),
            transport.subscribe(HID_REPORT, lambda _data: None),
            transport.unsubscribe(HID_REPORT),
            transport.service_uuids(),
            transport.gatt_characteristics(),
        )
        for action in actions:
            with pytest.raises(ConnectionError, match="connected and idle"):
                await action

    asyncio.run(scenario())
    assert transport._client.backend_calls == 0


def test_hardware_io_is_rejected_while_connecting_closing_or_disconnected(monkeypatch):
    connect_entered = asyncio.Event()
    connect_release = asyncio.Event()
    close_entered = asyncio.Event()
    close_release = asyncio.Event()
    service, _target = current_time_service()

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self._services = [service]
            self.backend_calls = 0
            self.service_reads = 0

        @property
        def services(self):
            self.service_reads += 1
            return self._services

        async def connect(self):
            connect_entered.set()
            await connect_release.wait()
            self.is_connected = True

        async def disconnect(self):
            close_entered.set()
            await close_release.wait()
            self.is_connected = False

        async def read_gatt_char(self, _characteristic):
            self.backend_calls += 1

        async def write_gatt_char(self, _characteristic, _data, *, response):
            self.backend_calls += 1

        async def start_notify(self, _characteristic, _callback):
            self.backend_calls += 1

        async def stop_notify(self, _characteristic):
            self.backend_calls += 1

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    def actions():
        return (
            transport.read(HID_REPORT),
            transport.write_with_response(CURRENT_TIME, CURRENT_TIME_VALUE),
            transport.subscribe(HID_REPORT, lambda _data: None),
            transport.unsubscribe(HID_REPORT),
            transport.service_uuids(),
            transport.gatt_characteristics(),
        )

    async def assert_rejected():
        for action in actions():
            with pytest.raises(ConnectionError, match="connected and idle"):
                await action

    async def scenario():
        candidate = asyncio.create_task(transport.connect())
        await connect_entered.wait()
        await assert_rejected()
        assert transport._client.backend_calls == 0
        assert transport._client.service_reads == 0
        connect_release.set()
        await candidate

        close = asyncio.create_task(transport.close())
        await close_entered.wait()
        await assert_rejected()
        assert transport._client.backend_calls == 0
        assert transport._client.service_reads == 0
        close_release.set()
        await close

        await assert_rejected()
        assert transport._client.backend_calls == 0
        assert transport._client.service_reads == 0

    asyncio.run(scenario())


def test_close_is_rejected_while_backend_io_is_in_flight(monkeypatch):
    read_entered = asyncio.Event()
    read_release = asyncio.Event()

    class Client:
        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False

        async def connect(self):
            self.is_connected = True

        async def read_gatt_char(self, _characteristic):
            read_entered.set()
            await read_release.wait()
            return b"value"

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport(TEST_ADDRESS, timeout=2)

    async def scenario():
        await transport.connect()
        read = asyncio.create_task(transport.read(HID_REPORT))
        await read_entered.wait()
        with pytest.raises(ConnectionError, match="lifecycle operation"):
            await transport.close()
        read_release.set()
        assert await read == b"value"

    asyncio.run(scenario())
