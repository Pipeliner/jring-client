# Adversarial UX review

Date: 2026-08-24

## Personas challenged

- A first-time Linux user with no Python packaging or Bluetooth vocabulary.
- A privacy-sensitive wearable owner at risk from proximity or identifier leakage.
- A screen-reader or motor-accessibility user evaluating the ring as an input device.
- A sysadmin or automation author relying on JSON, exit codes, and bounded execution.
- An owner of partially compatible JRing firmware with missing standard services.
- A hardware reverse engineer or contributor handling sensitive protocol evidence.

## v0.5 findings addressed

| Adversarial failure | Resolution |
|---|---|
| `discover --simulate` could activate a real scan | Simulation is rejected before discovery; scanning requires `--active-scan` |
| Discovery was called passive while Bleak scanned actively | Copy and design now truthfully describe radio-active scan requests |
| Bleak 1.x successful `connect()` returned `None` and was treated as failure | Transport success follows completion plus `is_connected` |
| Simulation and address selection could be combined silently | Source modes are mutually exclusive at parsing |
| Status and capabilities silently used contradictory simulator rings | Named `basic` and `hid` profiles now select one consistent fixture and appear in human and JSON provenance |
| Accepted flags could be ignored | Non-applicable global flags are rejected; input JSON is implemented |
| Simulated results looked like real health data | Human banners and structured/export provenance identify the simulator |
| Missing optional battery data hid all capabilities | Status returns partial optional fields and still inventories services |
| HID service presence was called usable | Output says `service advertised` and keeps usability unknown |
| Backend errors could leak addresses or BlueZ paths | The final error boundary redacts identifiers, paths, and long payload hex |
| Address selection required a sensitive argv value | Mode-0600 `--address-file` is the documented path; argv is marked legacy |
| History silently replaced an existing file | Existing exports require `--force` |
| `nan`, infinity, and excessive timeouts were accepted | CLI parsing enforces a finite 0–30 second range |
| Unsupported hardware history could connect before refusing | Parser rejects it before transport construction |

## Release gates before live sensor-to-input bridging

The current `step` path remains a one-event simulator. Real motion input must not be
enabled until all of these have specifications and executable tests. Protocol and
neutral-event work is tracked in [#1](https://github.com/Pipeliner/jring-client/issues/1)
and [#3](https://github.com/Pipeliner/jring-client/issues/3); emission safety is tracked
in [#4](https://github.com/Pipeliner/jring-client/issues/4), with accessible alternatives
in [#5](https://github.com/Pipeliner/jring-client/issues/5).

1. Define the evidence-backed event meaning and establish an initial baseline without
   emitting input.
2. Reject stale, duplicated, replayed, and out-of-order events; never replay a queue
   after reconnect.
3. Debounce and rate-limit events, with a maximum count and run duration.
4. Keep preview as the default and require visible arming with source and mapping.
5. Provide an emergency stop; disarm on disconnect, timeout, cancellation, protocol
   failure, or sink failure.
6. Guarantee key-up, notification unsubscribe, transport close, and `uinput` close at
   every cancellation point.
7. Expose only the input codes needed by the selected mapping.
8. Design alternative gestures for users who cannot generate a step and use
   primary/secondary terminology alongside left/right mouse labels.

## Remaining product work

Every remaining item is now owned by the public [roadmap](ROADMAP.md): guided selection
[#6](https://github.com/Pipeliner/jring-client/issues/6), deeper passive diagnostics
[#7](https://github.com/Pipeliner/jring-client/issues/7), partial field states
[#8](https://github.com/Pipeliner/jring-client/issues/8), the automation contract
[#9](https://github.com/Pipeliner/jring-client/issues/9), end-user distribution
[#10](https://github.com/Pipeliner/jring-client/issues/10), evidence and contributor
safety [#1](https://github.com/Pipeliner/jring-client/issues/1), the compatibility matrix
[#11](https://github.com/Pipeliner/jring-client/issues/11), and an explicit owner license
decision [#12](https://github.com/Pipeliner/jring-client/issues/12).
