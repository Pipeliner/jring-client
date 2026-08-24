import json
import subprocess

from jring.readiness import BluezProbe, ProbeValue, diagnose, probe_bluez


def available_bluez():
    ready = ProbeValue("available", "synthetic available evidence")
    return BluezProbe(ready, ready, ready, ready, ready)


def test_missing_hardware_prerequisites_have_specific_remedies():
    report = diagnose(
        platform="linux",
        python_version=(3, 10),
        module_available=lambda _name: False,
        executable_available=lambda _name: False,
        path_writable=lambda _path: False,
        bluez_probe=available_bluez,
    )

    assert report.simulator_ready
    assert not report.hardware_ready
    assert not report.input_ready
    failed = {check.name: check for check in report.checks if not check.ok}
    assert "pip install" in failed["bleak"].remedy
    assert "BlueZ" in failed["bluetoothctl"].remedy
    assert report.next_step == "jring status --simulate"


def test_complete_linux_setup_is_hardware_ready():
    report = diagnose(
        platform="linux",
        python_version=(3, 14),
        module_available=lambda name: name in {"bleak", "evdev"},
        executable_available=lambda name: name == "bluetoothctl",
        path_writable=lambda path: path == "/dev/uinput",
        bluez_probe=available_bluez,
    )

    assert report.simulator_ready
    assert report.hardware_ready
    assert report.input_ready
    assert report.next_step == "jring discover --active-scan"
    assert all(check.ok for check in report.checks)


def test_simulated_desktop_input_readiness_is_independent_from_bleak():
    report = diagnose(
        platform="linux",
        python_version=(3, 12),
        module_available=lambda name: name == "evdev",
        executable_available=lambda _name: False,
        path_writable=lambda path: path == "/dev/uinput",
        bluez_probe=available_bluez,
    )

    assert not report.hardware_ready
    assert report.input_ready


def test_bluez_layers_remain_distinct():
    probe = BluezProbe(
        dbus=ProbeValue("unavailable", "system bus socket is absent"),
        daemon=ProbeValue("uninspected", "D-Bus unavailable"),
        adapter=ProbeValue("unavailable", "no adapter is managed"),
        power=ProbeValue("uninspected", "adapter unavailable"),
        permission=ProbeValue("denied", "session query was denied"),
    )
    report = diagnose(
        platform="linux",
        python_version=(3, 12),
        module_available=lambda name: name == "bleak",
        executable_available=lambda name: name == "bluetoothctl",
        path_writable=lambda _path: False,
        bluez_probe=lambda: probe,
    )

    checks = {check.name: check for check in report.checks}
    assert checks["system_dbus"].state == "unavailable"
    assert checks["bluez_daemon"].state == "uninspected"
    assert checks["bluetooth_adapter"].state == "unavailable"
    assert checks["adapter_power"].state == "uninspected"
    assert checks["bluez_permission"].state == "denied"
    assert all(checks[name].remedy for name in (
        "system_dbus", "bluez_daemon", "bluetooth_adapter",
        "adapter_power", "bluez_permission",
    ))
    assert report.adapter_operational is False
    assert report.ring_compatibility == "not_checked"


def test_passive_bluez_probe_uses_only_read_queries():
    calls = []
    responses = iter((
        {"type": "b", "data": [True]},
        {
            "type": "b",
            "data": [True],
        },
    ))

    def runner(arguments, **kwargs):
        calls.append((tuple(arguments), kwargs))
        return subprocess.CompletedProcess(arguments, 0, json.dumps(next(responses)), "")

    result = probe_bluez(
        system_bus_exists=lambda: True,
        find_executable=lambda _name: "/usr/bin/busctl",
        adapter_names=lambda: ("hci0",),
        runner=runner,
    )

    assert result.dbus.state == "available"
    assert result.daemon.state == "available"
    assert result.adapter.state == "available"
    assert result.power.state == "available"
    assert result.permission.state == "available"
    assert len(calls) == 2
    rendered = " ".join(word for call, _kwargs in calls for word in call).lower()
    assert "namehasowner" in rendered
    assert "get-property" in rendered
    assert "powered" in rendered
    assert not any(word in rendered for word in ("scan", "discovery", "connect", "set-property"))
    assert all(kwargs["timeout"] <= 1 for _call, kwargs in calls)


def test_missing_system_bus_is_unavailable_without_running_commands():
    def forbidden(*_args, **_kwargs):
        raise AssertionError("no command may run without the system bus socket")

    result = probe_bluez(
        system_bus_exists=lambda: False,
        find_executable=lambda _name: "/usr/bin/busctl",
        adapter_names=lambda: (),
        runner=forbidden,
    )

    assert result.dbus.state == "unavailable"
    assert result.daemon.state == "uninspected"
    assert result.permission.state == "uninspected"
