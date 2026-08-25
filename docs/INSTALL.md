# Install JRing on Linux

## What this guide promises

The job is to reach a safe simulated result in an isolated Python environment, then
add Bluetooth or desktop-input support only when that job needs it. The behavior
contract is:

- use Python 3.10 or newer without changing the distribution-managed interpreter;
- install the smallest dependency set for simulation, Bluetooth, or input;
- keep all checks passive until the user separately authorizes a scan or connection;
- never solve an input permission problem by running JRing as root or making
  `/dev/uinput` world-writable.

The package metadata accepts CPython 3.10 and newer. The repository's regular CI
currently exercises Python 3.10 and 3.13 on a GitHub-hosted Ubuntu runner. Other
versions and the distro recipes below are documented installation paths, not claims
that CI or a real ring has verified them. In particular, Python 3.9 is too old.
Choose a distro-provided 3.10-or-newer interpreter; Python 3.11 is the conservative
choice on Enterprise Linux 9.

No package index or GitHub release is published yet. A wheel from an owner-reviewed
`release-artifacts` workflow run is a short-lived review artifact, not a release. Keep
the wheel and `SHA256SUMS` together and verify them before installation:

```sh
sha256sum --check SHA256SUMS
```

Checksums detect a changed download and workflow provenance ties an artifact to a
commit. Neither establishes that a real ring connects, nor substitutes for reviewing
the source and workflow.

## Create an isolated environment

After installing the distro prerequisites below, create a virtual environment. On
distros whose interpreter command is `python3`:

```sh
python3 --version
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
```

The first command must report 3.10 or newer. Inside the activated environment,
`python` and `pip` refer to `.venv`, even on systems that have no system-wide `python`
alias. Do not install into the distribution-managed Python environment and do not use
pip's `--break-system-packages` escape hatch.

Install a verified local wheel for the simulator:

```sh
python -m pip install ./jring_client-0.5.0-py3-none-any.whl
jring doctor
jring status --simulate
jring capabilities --simulate
```

Those two simulated commands use the same `basic` profile and therefore both report
that standard HID is not advertised. A metadata-only HID fixture is opt-in with
`--simulate-profile hid`; output always names the selected profile, and neither
profile contacts a ring or emits HID reports.

If `pipx` or `uv` is already managed by the distribution, either can create the
isolated tool environment instead:

```sh
pipx install ./jring_client-0.5.0-py3-none-any.whl
# or
uv tool install ./jring_client-0.5.0-py3-none-any.whl
```

For a source checkout, the equivalent developer install is:

```sh
python -m pip install -e '.[dev]'
jring status --simulate
```

The base install has no Bluetooth or desktop-input dependency. Add only the extra for
the job at hand:

```sh
# Source checkout: Bluetooth reads and explicitly authorized discovery
python -m pip install -e '.[ble]'

# Source checkout: simulated desktop-input emission
python -m pip install -e '.[input]'
```

For an installed wheel, install the matching optional dependencies into the same
virtual environment with `python -m pip`, or use `pipx inject`/`uv tool` package
injection. Keep the dependency bounds recorded in `pyproject.toml`; do not use `sudo
pip`. The `evdev` package may have a wheel for the selected interpreter. If it builds
from source, evdev may need a compiler, Python headers, and Linux input headers; the
distro recipes install those prerequisites.

## Distribution prerequisites

These commands install prerequisites; they do not scan, pair, or connect a ring.
Package availability can differ in older point releases and enabled enterprise
modules. Stop if the interpreter version check is below 3.10 rather than adding an
unreviewed third-party repository.

### Ubuntu and Debian

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-dev build-essential linux-libc-dev bluez
python3 --version
python3 -m venv .venv
```

`bluez` provides the daemon and `bluetoothctl`. The Python development package,
compiler toolchain, and `linux-libc-dev` provide the common evdev build prerequisites.

### Fedora

```sh
sudo dnf install python3 python3-pip python3-devel gcc kernel-headers bluez
python3 --version
python3 -m venv .venv
```

Use the Fedora interpreter only when it reports 3.10 or newer.

### RHEL, Rocky Linux, and AlmaLinux 9

The platform's default Python 3.9 does not meet JRing's requirement. Use the
AppStream Python 3.11 packages instead; repository/module availability depends on the
exact Enterprise Linux 9 minor release.

```sh
sudo dnf install python3.11 python3.11-pip python3.11-devel gcc kernel-headers bluez
python3.11 --version
python3.11 -m venv .venv
. .venv/bin/activate
```

Do not replace or relink `/usr/bin/python3`; system tools may depend on Python 3.9.

### Arch Linux

```sh
sudo pacman -Syu --needed python python-pip base-devel linux-api-headers bluez bluez-utils
python --version
python -m venv .venv
```

Arch calls its current Python 3 interpreter `python`. `bluez-utils` provides
`bluetoothctl`.

### openSUSE and SLES 15

For openSUSE Leap or SLES 15, select the official Python 3.11 module/packages available
for the installed service pack. On releases exposing the `python311` package names:

```sh
sudo zypper install python311 python311-pip python311-devel gcc make linux-glibc-devel bluez
python3.11 --version
python3.11 -m venv .venv
```

SLES may require enabling its official Python module through the site's normal
SUSEConnect/subscription process first. Do not substitute a community repository on a
managed SLES host without administrator review. Tumbleweed users may use its current
`python3`, `python3-pip`, and `python3-devel` packages if `python3 --version` is new
enough. `linux-glibc-devel` supplies the user-space Linux input headers used to build
evdev; `kernel-devel` is intended for building kernel modules and is not needed here.

### NixOS

Use a temporary development shell rather than installing with the mutable system
Python:

```sh
nix-shell -p python313 python313Packages.pip python313Packages.virtualenv \
  gcc pkg-config linuxHeaders bluez
python --version
python -m venv .venv
. .venv/bin/activate
```

For a persistent host configuration, enable BlueZ declaratively and rebuild using the
normal reviewed NixOS configuration workflow:

```nix
hardware.bluetooth.enable = true;
```

The Nix package attribute can move between nixpkgs revisions. Pin the nixpkgs revision
used by the machine and choose any available CPython 3.10-or-newer attribute if
`python313` is absent.

## BlueZ: installed is not operational

After installing packages, these read-only commands distinguish a missing service or
adapter from a JRing protocol problem:

```sh
command -v busctl
systemctl status bluetooth --no-pager
bluetoothctl show
jring doctor
```

`jring doctor` is passive: it does not scan, connect, write, or use the network. A
successful prerequisite check does not establish that a real ring connects. Starting
or enabling the Bluetooth service is an administrator decision; pairing and active
scanning require separate, explicit user action.

`busctl` is used only for bounded read-only operational checks. Some minimal Linux
installations provide `bluetoothctl` without providing `busctl`. In that case doctor
reports `diagnostic_tool: unavailable` and leaves `system_dbus` and dependent checks
`uninspected`; it does not tell you to repair D-Bus merely because its diagnostic tool
is absent. Install the package for your distribution that provides `busctl`, then rerun
doctor. The remedy deliberately names the executable rather than assuming `apt`, `dnf`,
`pacman`, or `zypper`.

If `diagnostic_tool` is available but `system_dbus` is unavailable, the bounded query
actually failed and D-Bus/service investigation is appropriate. Resolve checks in the
order shown: a remedy may refer to another stable check name when downstream state was
not inspectable.

## Least-privilege `/dev/uinput` access

Previewing a mapping does not need evdev or `/dev/uinput`. Stop after preview unless
desktop control is intended:

```sh
jring input --simulate --map step=key:space
```

Linux uinput permission authorizes input injection into the whole desktop session,
not just one application. Do not run `jring` as root, do not use an unrestricted chmod,
and do not set a world-writable mode. First load the module through the distro's normal
module configuration and inspect the device:

```sh
sudo modprobe uinput
ls -l /dev/uinput
```

For a single-user graphical workstation managed by systemd-logind, an administrator
can review a udev rule that grants the active local seat a revocable ACL:

```udev
KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", MODE="0660", OPTIONS+="static_node=uinput"
```

Place reviewed local rules under `/etc/udev/rules.d/`; reload them with the distro's
normal udev procedure and start a fresh login session. For a headless or shared host,
prefer a dedicated `jring-input` group containing only the account that runs JRing:

```udev
KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="jring-input", MODE="0660", OPTIONS+="static_node=uinput"
```

Group membership still grants that account desktop-wide injection. Remove the account
from the group when input mapping is no longer needed. On NixOS, express the same
active-seat policy declaratively:

```nix
boot.kernelModules = [ "uinput" ];
services.udev.extraRules = ''
  KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", MODE="0660", OPTIONS+="static_node=uinput"
'';
```

Then run `jring doctor --require-input` as the unprivileged user. Do not proceed if the
reported permission differs from the policy you intended.

## Upgrade and remove

Verify every replacement artifact before upgrading. In a virtual environment, install
the verified wheel again with `python -m pip install --upgrade PATH_TO_WHEEL`. A pipx
installation can use `pipx install --force PATH_TO_WHEEL`; a uv tool installation can
use the installer's documented local-artifact upgrade operation.

Remove an isolated tool with `pipx uninstall jring-client` or `uv tool uninstall
jring-client`; remove a project virtual environment only after checking that it
contains no user exports. Uninstalling never removes address files or exported data.
