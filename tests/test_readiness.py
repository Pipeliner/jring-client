from jring.readiness import diagnose


def test_missing_hardware_prerequisites_have_specific_remedies():
    report = diagnose(
        platform="linux",
        python_version=(3, 10),
        module_available=lambda _name: False,
        executable_available=lambda _name: False,
        path_writable=lambda _path: False,
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
    )

    assert report.simulator_ready
    assert report.hardware_ready
    assert report.input_ready
    assert report.next_step == "jring discover"
    assert all(check.ok for check in report.checks)


def test_simulated_desktop_input_readiness_is_independent_from_bleak():
    report = diagnose(
        platform="linux",
        python_version=(3, 12),
        module_available=lambda name: name == "evdev",
        executable_available=lambda _name: False,
        path_writable=lambda path: path == "/dev/uinput",
    )

    assert not report.hardware_ready
    assert report.input_ready
