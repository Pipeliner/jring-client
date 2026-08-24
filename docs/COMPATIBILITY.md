# Compatibility evidence

Compatibility reports are review artifacts, not telemetry. The tool never scans,
connects, reads a ring, or publishes output. A report has no timestamp, address, account,
health measurement, raw payload, serial, distro patch version, or exact personal data.

The coarse dimensions are model family, firmware major, Linux family, Python minor,
BlueZ major, and Bleak major. Hardware evidence states are:

- `untested`: no evidence for this dimension.
- `verified`: prerequisites, connection, or standard reads were directly established.
- `advertised` / `not_advertised`: HID service metadata was observed, without a
  usability claim.
- `incompatible`: the named dimension was attempted and failed its contract.

The row summary is one of `untested`, `prerequisites_only`, `connected`,
`standard_reads_verified`, `hid_advertised`, `motion_verified`, or `incompatible`.
Synthetic CI rows are restricted to the first two and keep connection, standard reads,
HID, and motion `untested`.

## Current matrix

This matrix contains no owner hardware observations and makes no compatibility claim.

| Source | Environment | Prerequisites | Connection | Standard reads | HID | Motion |
|---|---|---|---|---|---|---|
| Synthetic CI | Python 3.10 | untested | untested | untested | untested | untested |
| Synthetic CI | Python 3.13 | untested | untested | untested | untested | untested |

Owner hardware rows require an accepted privacy-safe evidence ID and a mode-0600 report
file. Generate/validate locally, inspect the complete JSON, then decide separately
whether to contribute it. Matrix merge is deterministic and rejects duplicate report
IDs; zero errors never changes an untested state into a compatibility claim.
