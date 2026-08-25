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
| Interface count was inflated by helper and call-site methods | Whole-artifact output reconciles exact AIDL rows and labels 903 classified methods as supplemental |
| Embedded-SDK classic socket references were omitted | The artifact inventory includes two RFCOMM API methods in one OTA helper without promoting them to BLE capabilities |
| Process-local filters implied Android broadcast delivery | Receiver mismatches are blockers and no unseen bridge is invented |
| Native substring matches implied Bluetooth behavior | Boundary-aware rescanning records zero recognized identifiers while native absence remains unproven |
| No direct dial constructor was called runtime dormancy | Reflection, Binder, resources, and opaque native behavior keep activation inconclusive |
| Five reflection files were treated as five unknown calls | The model distinguishes 11 calls in 10 methods and resolves only their constant Android helper targets |
| Packaged Binder methods or resource labels implied a live dial-transfer route | The model traces relevant static routes and reports zero app activation edges while keeping runtime reachability inconclusive |
| A native library implied hidden Bluetooth transport | All packaged JNI roots are bounded to image/wallpaper work; whole-ELF and external binding limits remain explicit |
| Non-opcode callbacks disappeared behind one `not_reproduced` label | Every row now has behavior or declaration evidence, with side effects and payload semantics still unclaimed |
| Callback inventory exposed sensitive transport and platform values | Coverage emits privacy categories only, never the values themselves |
| An eight-channel parser silently discarded the final motion value | The fixed-frame decoder consumes nine signed pairs while keeping every axis meaning unknown |
| Input-focused inventory hid blocked device actions | All 13 mapped actions are discoverable; seven side-effecting actions remain visibly blocked and input-ineligible |
| HID Report UUID deduplication hid multiple report instances | Each observed report record keeps a numbered property/descriptor state and an explicit `not_read` value state |
| Repeated HID aggregation was still UUID-last-wins | Aggregate state is order-independent `multiple_consistent`/`multiple_mixed`, with all malformed descriptor peers retained |
| Metadata IDs implied a usable duplicate selector | Opaque IDs are connection/inventory-scoped metadata only and remain explicitly non-targetable without a private generation-bound object registry |
| `readable` sounded like a successful read | The state is `read_property_advertised`; human output says the value was not read |
| Callback targets, invoke sites, and opcode branches were treated as one count | The dispatcher crosswalk separates 85 targets, 125 syntactic/124 reachable invokes, and 104 distinct opcodes |
| A duplicated case-insensitive opcode made every invoke look reachable | The shadowed ECG failure invoke is retained as syntax evidence but excluded from reachable routes |
| One opcode dispatching two callback families was flattened into a single meaning | Opcode `25` exposes one generic-mode success followed by six sport samples without inflating the family count |
| Python accepted unsigned values for callbacks the SDK suppresses | Integer-parsed four-byte fields enforce the APK signed ceiling while wider ECG paths remain unsigned |
| A failed sensor command looked like observed device state | Requested direction is separate and actual `active` state is unknown on failure |
| A recognized failure opcode implied callback delivery | Failure metadata identifies callback-silent `83`/`8b`/`8c` branches and both `a5` byte predicates |
| Fixed-width callback strings lost leading zeroes as integers | Device revisions and dial codes preserve uppercase hexadecimal text and add numeric convenience properties |
| Codec counts were disconnected from their implementations | Immutable registries resolve all 171 designated rows to code without invoking it |
| Shared parsers/factories looked one-to-one | Pipeline, stateful, branching, and five unresolved raw-family bindings are separate locator kinds; four sensor selectors are now exact |
| Exact mutation bytes implied exact source behavior | Dial queue clearing, retained sequential alarm state, and host-derived language defaults are explicit non-reproduced divergences |
| Every AIDL request looked like one fixed GATT command | A 112-row route partition separates 85 deterministic codecs from shared state, dynamic writes, descriptor control, DFU, and 23 no-packet operations |
| SDK exposure was presented as APK use | A separate exact ledger distinguishes 51 app-invoked request targets from 61 bundled-but-uninvoked targets and keeps runtime reachability unclaimed |
| Same-spelled request and callback methods could collapse | Interface roles preserve both `setAutoHeartMode` rows without name-only joining |
| Declaration parity hid transaction and marshalling drift | A 217-row Binder crosswalk verifies contiguous IDs, all four surfaces, ordered Parcel kinds, reply handshakes, and synchronous mode |
| Parcel `int32` erased boolean meaning | Each row exposes semantic kinds separately from its Parcel representation |
| Local notification state was mislabeled as a CCCD action | Raw control evidence separates local toggles, always-enable descriptor bytes, queue-result callback, and asynchronous completion |
| Strict payload length was called callback-equivalent | Typed raw payloads now model bounded per-frame zero-fill/truncation and label the whole-frame cap as hardening |
| Typed raw parsing hid the generic callback | Projection evidence shows generic delivery separately, including typed-silent short and unknown frames |
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
