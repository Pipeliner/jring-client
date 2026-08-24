# JRing human UX specification

Status: accepted for v0.4

## Human goal

A Linux user who owns a JRing should be able to understand what the client can safely
do, try it without hardware, and recover from ordinary setup errors without reading a
Python traceback. Safety and privacy must remain visible without turning routine use
into guesswork.

## Product principles

1. Lead with the task: commands read as `jring status --simulate` and
   `jring history --simulate --output history.jsonl`.
2. Default to human-readable output. Structured JSON is explicit with `--json`.
3. Errors name the remedy and do not expose internals unless a developer runs tests.
4. Discovery never selects a device and never prints a Bluetooth address.
5. A hardware write requires an explicit confirmation on the same command.
6. Output never includes an address, raw health payload, or hidden telemetry.
7. Readiness checks are passive and distinguish optional hardware setup from the
   always-available simulator path.
8. General-purpose input mappings preview by default, use a closed action vocabulary,
   and require explicit authorization before emitting operating-system input.

## Acceptance scenarios

### First safe success

Given no ring and no optional Bluetooth dependency, when a person runs
`jring status --simulate`, then they see battery, identity, capability, and safety
information in readable text and the command exits successfully.

### Automation

Given the simulator, when a person runs `jring status --simulate --json`, then stdout
is valid JSON with stable field names and contains no device address.

### Flexible option placement

Given an existing script using `jring --simulate status`, when it upgrades, then the
old placement still works; the more natural `jring status --simulate` works too.

### Recoverable setup error

Given missing hardware support or an unavailable characteristic, when a command
fails, then stderr begins with `jring: error:`, explains the issue, contains no
traceback, and the process exits non-zero.

### Deliberate write

Given a selected device, when a person requests `time-sync` without `--yes` or
`--allow-write`, then argument parsing refuses the operation before connecting.

### Predictable export

Given history records, when the output ends in `.jsonl` or `.csv`, then the client
atomically writes that exact format. Any other suffix is rejected with a clear error.

### Passive setup diagnosis

Given any supported installation, when a person runs `jring doctor`, then the client
checks Python, Linux, Bleak, BlueZ, evdev, and `/dev/uinput` readiness without
scanning, connecting, writing, or using the network. It reports simulator, BLE
hardware, and desktop-input readiness independently with concrete remedies.

### Readiness automation

Given missing optional hardware prerequisites, when automation runs
`jring doctor --json`, then it receives stable structured checks and a successful exit
because diagnosis completed. With `--require-hardware`, the same report exits nonzero.
Automation can independently use `--require-input` for Linux desktop-input readiness.

### Standard HID visibility

Given a selected device advertising Bluetooth service `1812`, when a person requests
status, then the human and JSON outputs report standard HID availability. The client
does not reinterpret or log raw HID reports.

### Safe step-to-input preview

Given no ring, when a person runs
`jring input --simulate --map step=click:left`, then the client exercises a simulated
step, describes the mouse click it would emit, and produces no operating-system input.

### Deliberate input injection

Given a valid simulated mapping, when a person adds `--allow-input`, then exactly one
allowlisted keyboard or mouse action is emitted through Linux `uinput`. Shell commands,
paths, arbitrary key codes, and unsupported sensor event names are rejected before a
sink is opened. Hardware motion input remains unavailable until verified.

## Test map

| Scenario | Executable evidence |
|---|---|
| First safe success | `test_human_status_is_readable` |
| Automation | `test_json_status_is_stable_and_private` |
| Flexible option placement | `test_global_option_placement_remains_compatible` |
| Recoverable setup error | `test_expected_error_is_actionable_without_traceback` |
| Deliberate write | `test_time_sync_requires_explicit_confirmation` |
| Predictable export | `test_history_export_rejects_ambiguous_suffix` |
| Passive setup diagnosis | `test_doctor_explains_hardware_setup_without_failing` |
| Readiness automation | `test_doctor_json_can_strictly_require_hardware` |
| Standard HID visibility | `test_standard_hid_service_is_reported` |
| Safe step-to-input preview | `test_step_mapping_previews_without_emitting_input` |
| Deliberate input injection | `test_input_injection_requires_opt_in`, `test_shell_mapping_is_rejected` |

## Deliberate non-goals

The CLI will not auto-connect from scan results, persist addresses, automate pairing,
guess vendor packets, execute mapped shell commands, upload data, or label measurements as medical conclusions.
Interactive device selection may be designed later only if it can preserve explicit
identity confirmation and avoid persistent identifiers in logs.
