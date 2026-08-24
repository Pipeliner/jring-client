# JRing human UX specification

Status: accepted for v0.5 after adversarial review

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
9. Simulation and hardware selection are mutually exclusive, and every simulated
   result carries visible, machine-readable provenance.
10. Accepted options are never ignored. Radio-active scanning and replacement of an
    existing export each require an explicit flag.
11. JSON automation receives an additive versioned envelope on every accepted JSON
    path, including failures; stderr stays empty in JSON mode.

## Acceptance scenarios

### First safe success

Given no ring and no optional Bluetooth dependency, when a person runs
`jring status --simulate`, then they see battery, identity, capability, and safety
information in readable text and the command exits successfully.

### Automation

Given the simulator, when a person runs `jring status --simulate --json`, then stdout
is valid JSON with stable field names, includes `schema_version`, `operation`, `source`,
and `ok`, and contains no device address.

### Automation failures

Given `--json`, when parsing, prerequisites, permissions, timeouts, protocol
compatibility, or internal execution fail, stdout contains exactly one JSON object and
stderr is empty. The object includes `schema_version`, `operation`, `source`, `ok:
false`, and an `error` object with stable `code`, `retryable`, and a sanitized human
`message`. It never includes a traceback, Bluetooth address, BlueZ path, or raw payload.

Exit meanings are stable within the current CLI major version:

| Exit | Error code | Meaning | Retryable default |
|---:|---|---|---|
| 0 | none | Operation completed | no |
| 2 | `usage` | Arguments or requested mapping are invalid | no |
| 3 | `unavailable` | A required local dependency, device, or connection is unavailable | yes |
| 4 | `timeout` | The bounded operation expired | yes |
| 5 | `protocol_incompatible` | A required service/value is absent, malformed, or unsupported | no |
| 6 | `permission_denied` | Explicit authorization or local permission is missing | no |
| 70 | `internal` | An unexpected client failure occurred | no |
| 130 | `interrupted` | The user interrupted the operation | yes |

Schema 1 additions are backward-compatible: existing success fields remain at their
current paths. Removing or renaming a field requires a new `schema_version`; English
messages are explanatory and are not compatibility keys.

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

The BLE section separates installed prerequisites from passive operational evidence
for the system D-Bus, BlueZ daemon, adapter presence, adapter power, and session query
permission. Each check is `available`, `unavailable`, `denied`, or `uninspected` with a
reason and remedy. Failure to inspect is never presented as absence or health. Ring
compatibility remains `not_checked`; `doctor` never proves a ring will connect.

### Readiness automation

Given missing optional hardware prerequisites, when automation runs
`jring doctor --json`, then it receives stable structured checks and a successful exit
because diagnosis completed. With `--require-hardware`, the same report exits nonzero.
Automation can independently use `--require-input` for Linux desktop-input readiness.

### Standard HID visibility

Given a selected device advertising Bluetooth service `1812`, when a person requests
status, then the human and JSON outputs report that the standard HID service was
observed while usability remains unknown. The client does not reinterpret or log raw
HID reports.

### Safe step-to-input preview

Given no ring, when a person runs
`jring input --simulate --map step=click:left`, then the client exercises a simulated
step, describes the mouse click it would emit, and produces no operating-system input.

### Deliberate input injection

Given a valid simulated mapping, when a person adds `--allow-input`, then exactly one
allowlisted keyboard or mouse action is emitted through Linux `uinput`. Shell commands,
paths, arbitrary key codes, and unsupported sensor event names are rejected before a
sink is opened. Hardware motion input remains unavailable until verified.

### Radio intent is explicit

Given any command marked simulated, it performs no Bluetooth scan or connection.
`discover` rejects `--simulate`, and a real discovery requires `--active-scan` with
copy explaining that the radio sends scan requests but never connects.

### Source intent and provenance

`--simulate` and hardware selection are mutually exclusive. Human simulated results
lead with `SIMULATION — no ring contacted`; JSON includes `schema_version` and
`source`, and exported rows include `source` plus `synthetic`.

### Honest partial status

Given a ring without the optional Battery characteristic, status still reports device
information and advertised services. Human wording says a service was advertised and
not tested; JSON marks battery availability independently.

Given optional Device Information reads that are mixed valid, unavailable, malformed,
and slow, status finishes within one field-collection deadline and preserves every
completed independent result. Each field reports exactly one of `available`,
`unavailable`, `malformed`, `timed_out`, or `not_advertised`. Service-inventory failure
is also explicit and never turns an unknown HID/heart-rate state into `not advertised`.

Schema 1 retains the existing `device_info`, `battery_percent`, `battery_available`,
and capability booleans. It additively exposes `device_info_states`, `battery_state`,
and capability `inventory_state`; automation may adopt these without losing the old
value paths.

### Supported Bleak connection contract

Given a supported Bleak 1.x client whose successful `connect()` completes with no
return value, the transport treats completion plus `is_connected` as success. A
successful adapter connection is never converted into a client error.

### Option meaning is enforced

Options that do not apply to a subcommand fail during parsing. Timeouts are finite and
between zero and 30 seconds. Any accepted `--json` success writes only valid JSON to
stdout; commands without a JSON contract reject the option.

### Private and sanitized selection

A person may put an exact address in a mode-0600 file and pass `--address-file` so the
identifier is absent from argv. Conflicting source selectors fail before transport
construction. Expected and unexpected CLI errors redact MAC-like identifiers, long
payload hex, and BlueZ D-Bus paths and never show a traceback.

### Non-destructive export

History refuses to replace an existing destination unless `--force` is explicit.
Both paths remain atomic and restrictive, and simulated rows keep provenance.

## Test map

| Scenario | Executable evidence |
|---|---|
| First safe success | `test_human_status_is_readable` |
| Automation | `test_json_status_is_stable_and_private` |
| Automation failures | `test_json_failures_have_stable_envelopes_and_exit_codes`, `test_json_usage_error_has_no_stderr`, `test_json_error_redaction` |
| Flexible option placement | `test_global_option_placement_remains_compatible` |
| Recoverable setup error | `test_expected_error_is_actionable_without_traceback` |
| Deliberate write | `test_time_sync_requires_explicit_confirmation` |
| Predictable export | `test_history_export_rejects_ambiguous_suffix` |
| Passive setup diagnosis | `test_doctor_explains_hardware_setup_without_failing`, `test_bluez_layers_remain_distinct`, `test_passive_bluez_probe_uses_only_read_queries` |
| Readiness automation | `test_doctor_json_can_strictly_require_hardware` |
| Standard HID visibility | `test_standard_hid_service_is_reported` |
| Safe step-to-input preview | `test_step_mapping_previews_without_emitting_input` |
| Deliberate input injection | `test_input_injection_requires_opt_in`, `test_shell_mapping_is_rejected` |
| Radio intent is explicit | `test_discovery_requires_explicit_active_scan`, `test_simulated_discovery_never_scans` |
| Source intent and provenance | `test_source_modes_are_exclusive`, `test_simulated_status_has_provenance` |
| Honest partial status | `test_missing_battery_still_reports_hid`, `test_status_reports_each_optional_field_state`, `test_status_uses_one_deadline_for_all_optional_fields`, `test_cli_exposes_partial_status_states` |
| Supported Bleak connection contract | `test_bleak_one_x_none_return_is_a_successful_connection` |
| Option meaning is enforced | `test_non_applicable_global_options_are_rejected`, `test_timeout_must_be_finite_and_bounded` |
| Private and sanitized selection | `test_address_file_must_be_private`, `test_cli_errors_redact_identifiers` |
| Non-destructive export | `test_history_export_requires_force_to_replace` |

## Deliberate non-goals

The CLI will not auto-connect from scan results, persist addresses, automate pairing,
guess vendor packets, execute mapped shell commands, upload data, or label measurements as medical conclusions.
Interactive device selection may be designed later only if it can preserve explicit
identity confirmation and avoid persistent identifiers in logs.
