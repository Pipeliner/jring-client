from pathlib import Path


ROOT = Path(__file__).parents[1]
INSTALL = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
COMPATIBILITY = (ROOT / "docs" / "COMPATIBILITY.md").read_text(encoding="utf-8")
DISTRO_SMOKE_PATH = ROOT / ".github" / "workflows" / "distro-smoke.yml"


def test_install_guide_covers_each_promised_linux_family():
    for family in (
        "Ubuntu and Debian",
        "Fedora",
        "RHEL, Rocky Linux, and AlmaLinux 9",
        "Arch Linux",
        "openSUSE and SLES 15",
        "NixOS",
    ):
        assert family in INSTALL

    for package_manager in ("apt", "dnf", "pacman", "zypper", "nix-shell"):
        assert package_manager in INSTALL


def test_interpreter_and_virtual_environment_contract_is_explicit():
    assert "Python 3.10 or newer" in INSTALL
    assert "Python 3.10 and 3.13" in INSTALL
    assert "Python 3.9" in INSTALL
    assert "python3 -m venv" in INSTALL
    assert "python3.11 -m venv" in INSTALL
    assert ". .venv/bin/activate" in INSTALL
    assert "Do not install into the distribution-managed Python environment" in INSTALL


def test_each_hardware_layer_has_dependencies_and_a_passive_check():
    for term in (
        "BlueZ",
        "bluetoothctl",
        "python3-dev",
        "python3-devel",
        "linux-api-headers",
        "linux-glibc-devel",
        "jring doctor",
        "jring status --simulate",
    ):
        assert term in INSTALL

    assert "evdev may need a compiler, Python headers, and Linux input headers" in INSTALL
    assert "does not establish that a real ring connects" in INSTALL


def test_uinput_setup_is_narrow_and_names_its_security_boundary():
    assert 'KERNEL=="uinput"' in INSTALL
    assert 'MODE="0660"' in INSTALL
    assert 'TAG+="uaccess"' in INSTALL
    assert "boot.kernelModules = [ \"uinput\" ];" in INSTALL
    assert "input injection into the whole desktop session" in INSTALL
    assert "Do not run `jring` as root" in INSTALL
    assert "chmod 666" not in INSTALL
    assert 'MODE="0666"' not in INSTALL


def test_compatibility_claims_separate_documentation_ci_and_hardware_evidence():
    for term in (
        "Documented installation path",
        "CI exercised",
        "Owner hardware verified",
        "Ubuntu",
        "Debian",
        "Fedora",
        "RHEL / Rocky / Alma 9",
        "Arch",
        "openSUSE Leap 15.6",
        "SLES 15",
        "NixOS",
    ):
        assert term in COMPATIBILITY

    assert "GitHub-hosted Ubuntu runner" in COMPATIBILITY
    assert "Python 3.10 and 3.13" in COMPATIBILITY
    assert "No distro row is a real-ring compatibility claim" in COMPATIBILITY
    assert "No owner hardware observations" in COMPATIBILITY


def test_compatibility_guide_does_not_promote_documented_distros_to_verified():
    assert "Documentation is not execution evidence" in COMPATIBILITY
    assert "not CI-exercised" in COMPATIBILITY
    assert "untested" in COMPATIBILITY
    assert "tested on all supported distributions" not in COMPATIBILITY.lower()


def test_native_distro_smoke_matrix_is_bounded_and_pinned():
    workflow = DISTRO_SMOKE_PATH.read_text(encoding="utf-8")

    for family, image in (
        ("debian", "debian:13-slim"),
        ("fedora", "fedora:44"),
        ("enterprise-linux-9", "rockylinux/rockylinux:9"),
        ("arch", "archlinux:base"),
        ("opensuse", "opensuse/leap:15.6"),
    ):
        assert f"family: {family}" in workflow
        assert f"image: {image}" in workflow

    assert "timeout-minutes:" in workflow
    assert "fail-fast: false" in workflow
    assert "max-parallel:" in workflow
    assert "ubuntu-latest" not in workflow
    assert ":latest" not in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow


def test_native_distro_smoke_is_simulator_only_and_checks_every_layer():
    workflow = DISTRO_SMOKE_PATH.read_text(encoding="utf-8")

    for command in (
        "python -m pip install -e '.[dev]'",
        "python -m pytest -q",
        "jring doctor --json",
        "jring status --simulate --json",
        "jring capabilities --simulate --json",
        "jring input --simulate --map step=key:space",
    ):
        assert command in workflow

    for unsafe in ("--active-scan", "--allow-input", "--address", "--select"):
        assert unsafe not in workflow
    assert "privileged:" not in workflow
    assert "/dev/" not in workflow


def test_native_distro_claims_keep_sles_and_nixos_documentation_only():
    assert "Native container smoke" in COMPATIBILITY
    assert "SLES 15" in COMPATIBILITY and "documentation-only" in COMPATIBILITY
    assert "NixOS" in COMPATIBILITY and "documentation-only" in COMPATIBILITY
