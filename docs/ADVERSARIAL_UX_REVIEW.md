# Adversarial UX review

Date: 2026-08-25

## Personas challenged

- A first-time Linux user with no Python packaging or Bluetooth vocabulary.
- A privacy-sensitive wearable owner at risk from proximity or identifier leakage.
- A screen-reader or motor-accessibility user evaluating the ring as an input device.
- A sysadmin or automation author relying on JSON, exit codes, and bounded execution.
- An owner of partially compatible JRing firmware with missing standard services.
- A hardware reverse engineer or contributor handling sensitive protocol evidence.
- A distro packager who needs reproducible metadata without mutating system Python.
- A Bash or man-page user discovering a safety-sensitive command from the terminal.

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
| Vendor UUID presence looked like a usable command route | Capabilities now reports fixed main/raw structural and transport-ownership states from metadata only, with live, owner, hardware, and I/O denials adjacent |
| A cumulative counter adapter returned a dispatchable input event | Experimental output is now a closed non-input-eligible candidate; only a no-argument synthetic baseline/+1 fixture can create the simulator preview event |
| HID service presence was called usable | Output says `service advertised` and keeps usability unknown |
| Interface count was inflated by helper and call-site methods | Whole-artifact output reconciles exact AIDL rows and labels 903 classified methods as supplemental |
| Embedded-SDK classic socket references were omitted | The artifact inventory includes socket creation and close in one OTA helper, labels them as lifecycle references rather than a transport, and notes that actual transfer uses GATT |
| An input-first inventory hid classic and host integration surfaces | Five task-first rows expose classic attachment, an RFCOMM socket lifecycle reference, two metadata callbacks, and the host volume request without promoting them to HID/input support |
| Decoded Classic/App-ID notifications looked like profile attachment, pairing, or setter acknowledgement | The zero-write fake accepts only exact `45/00`, `45/01`, and `45/02`, redacts private text, keeps App-ID uncorrelated, counts selectorless/unknown traffic as unrelated, and grants no setter causation, identifier equality, acknowledgement, terminal, bonding, RFCOMM, HID, live, hardware, or input state |
| A passive touch-mode value looked like touch enablement, device state, a gesture, tap, button, sensor sample, or input event, while ordinary serialization leaked the value and omitted safety fields | The zero-write fake routes only exact `78/09` to a private neutral touch-setting projection; `00`/`01` remain separate unknown-motion projections and every other selector is unrelated. Decoded storage is excluded from dataclass/JSON output, fixed negative-authority fields remain visible, the setter has zero observed app invokes, and the result grants no setter causation, acknowledgement, terminal, live, hardware, or input meaning |
| Inbound motion-candidate selectors `00`/`01` looked like off/on state, setter acknowledgement, activation, gestures, steps, buttons, or live input, while channel patterns could leak through serialization | The zero-write scripted fake accepts exact `78/00` and `78/01` only as private nine-channel callback projections. Values stay outside repr/dataclass/JSON output, all meanings remain unknown or unproven, `InputMapper` rejects the event, and fixed fields deny setter causation, acknowledgement, sensor-event promotion, terminal, live, hardware, and input authority |
| A MAIN `4E` action code looked like ChatGPT execution, a content request, acknowledgement, terminal, or mappable AI button | The zero-write fake retains it only as a private, neutral, passive per-frame candidate. It owns no request while the protocol relationship stays unknown; trailing content canaries are neither stored nor serialized. Duplicate arrival is not completion, `4F` content and shared `54` state traffic remain unrelated, and fixed fields deny chat/content execution, acknowledgement, terminal, live, hardware, and input authority |
| A matched `54/12` fake query response looked like current device state, readiness, connection, battery, firmware health, binding, or live support, while generic result serialization leaked its code | Inventory separates decoder from write-performing fake-transaction coverage; canonical `54/11` is revalidated, response ownership begins only at actual write entry, parsed storage is excluded from dataclass/JSON output, and fake success grants none of those live or hardware meanings |
| Wi-Fi fake coverage was hidden, while dataclass serialization exposed private network names and fragment metadata | The inventory now labels only library-test response assembly; the result hides names, signal values, and fragment IDs from representations and ordinary serialization, and explicitly denies host/ring scan, protocol delivery, acknowledgement, terminal, live, owner, hardware, and input claims |
| Wi-Fi callbacks before request dispatch and uncertain fake writes could be treated as owned, reusable observations | A write-entry ownership gate discards early notifications; one immutable deadline covers all stages, invoked calls without a return become uncertain, and uncertain dispatch or cleanup taints reuse |
| Disabled source scan filtering was reported as a callback-silence cause | Scan evidence lists null or malformed advertisements, callback exceptions, and a dead callback Binder instead |
| A client name match looked like device identity evidence | Human and JSON discovery output explicitly label `likely_jring` as a client-side name heuristic |
| SDK callbacks implied app consumption | Unknown-motion and both raw callback rows say that the reviewed app bodies discard their arguments |
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
| Shared parsers/factories looked one-to-one | Pipeline, stateful, and branching relationships remain distinct; exact sensor selectors and typed raw callback wrappers leave zero unresolved family bindings |
| A broad raw parser could project the wrong callback family | Five callback-specific wrappers accept only `0001`, `0002`/`0003`, `0006`, `0009`, or `000a` respectively and fail closed on every other known raw type |
| Exact mutation bytes implied exact source behavior | Dial queue clearing, retained sequential alarm state, and host-derived language defaults are explicit non-reproduced divergences |
| Alarm frame callbacks looked like per-alarm or whole-batch success | The dedicated fake preserves ordered base/content calls but labels `0d`/`8d` as uncorrelated per-frame observations with uninterpreted bodies; privacy-safe multiplicity, quiet, and limits cannot prove completion, failures stop only future synthetic writes, and results retain no private alarm material |
| Alarm callback/write/disconnect races lost observations or invented stop causality | Owned callbacks are classified even when writes fail or time out, simultaneous successful returns stay returned when disconnect also fires, observation/disconnect races retain the removed callback, and only the dispatch loop can claim that a failure stopped future writes |
| Forged frozen alarm objects bypassed pre-connect validation | The simulator reconstructs the batch, alarms, clock values, and weekdays on the accepted Python domain before acquiring the fake lease or connecting |
| A notification marker looked like display, delivery, or whole-batch acknowledgement | The fake correlates `12` only to an already-invoked frame marker and keeps every marker, returned call, quiet, and limit insufficient for batch success, terminal state, or planner-state commit; future markers remain unowned and are never buffered or retroactively matched |
| An unmarked `92` callback looked like a known failed frame or batch | Its body and frame identity remain uninterpreted; stopping only future fake writes and tainting reuse is labeled conservative simulator policy, not proof of source failure semantics or queue behavior |
| Fake notification execution looked like source atomic enqueue or overlap safety | Sequential scripted calls explicitly do not reproduce source queue acceptance, atomic enqueue/delivery, caller throttling, planner serialization, or the source's global callback-overlap race |
| A privacy-safe notification result implied that no private copy existed | Results retain no request, ID, text, UID, digest, marker identity, frame, or frame count, while documentation separately discloses that the exact scripted-test transport deliberately retains private write calls for focused inspection |
| Every AIDL request looked like one fixed GATT command | A 112-row route partition separates 85 deterministic codecs from shared state, dynamic writes, descriptor control, DFU, and 23 no-packet operations |
| SDK exposure was presented as APK use | A separate exact ledger distinguishes 51 app-invoked request targets from 61 bundled-but-uninvoked targets and keeps runtime reachability unclaimed |
| All callback invokes were flattened into “directly dispatched” | Every callback row now preserves main-response, raw-response, and outside-dispatcher invoke counts; repeated sites and four cross-origin overlaps remain visible |
| Non-codec callback booleans and integers looked self-explanatory | Structured result semantics distinguish queue acceptance, mixed auth status, SDK connection state, discarded RSSI status, OTA phase/detail, and retry state |
| Scan privacy implied raw advertisement forwarding | The row records only selected identity/RSSI plus six derived identifier fragments, alongside auto-connect/OTA side effects |
| A reset/stale step sample became the next click's baseline | Equal or decreasing counters quarantine the adapter until explicit rebaseline, so the following `+1` remains silent |
| Same-spelled request and callback methods could collapse | Interface roles preserve both `setAutoHeartMode` rows without name-only joining |
| A shared opcode made Phone-MAC look acknowledged by a host-volume request | The Phone-MAC row has no eligible callback; opcode `49` is an explicit unrelated-pipeline collision |
| A returned fake host-volume write looked like a completed request-response transaction | A separate request-to-projection coordinator reports protocol completeness unknown, application acknowledgement false, one write maximum, and taints post-invocation uncertainty |
| A host-volume simulator could silently inspect desktop audio or turn into a volume button | It accepts only explicit caller-supplied offline values, labels that provenance, discards the inbound body, never touches host audio, and stays distinct from volume-up/down input candidates |
| A contact fingerprint notification looked like acknowledgement of outbound contact content | Contact-content is only a conditional app-local reverse-sync candidate; the no-batch equality branch and independently initiated local-change path remain visible, and records stay redacted |
| Private Wi-Fi and FTP names implied connection or completion | Credential selectors remain disjoint from an unowned state event, while the FTP terminal-shaped signal is shared by source-local success and exhausted failure |
| Complete-looking interface counts appeared before the live and hardware gaps | Protocol coverage now begins with an explicit negative parity verdict and separates scoped AIDL accounting from semantic, live-vendor, and hardware dimensions |
| Zero generic topology rows looked like complete response semantics | The immediately adjacent warning says every row merely has a more-specific static classification; 58 caveated rows, live zero, and hardware zero remain separate |
| A typed value/event callback was promoted to singleton transaction success | An 85-row fake-singleton ledger admits only 36 statically matched terminals; every row remains explicitly live-, owner-, and hardware-ineligible |
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
| Build pins omitted transitive frontend requirements | The release wheelhouse closes over exact build, packaging, pyproject-hooks, setuptools, and tomli pins; CI proves an isolated no-index backend build, and the same wheelhouse covers every claimed Python minor |
| Version-specific wheel examples became stale every release | Packager and install examples use a `VERSION` placeholder and name the authoritative project metadata |
| Shell and manual help could drift from argparse or expose suppressed compatibility flags | One stdlib-only generator derives all visible parser contexts, aliases, choices, and file values; byte-golden tests reject drift |
| A schema-valid public protocol candidate could sound like owner approval or live support | Schema 2 calls itself a candidate, exposes the future notification/write effects, strips private evidence references, and fixes every runtime-authority flag false |
| A historical owner observation could become a reusable consent token | Private validation authenticates neither consent nor truth, refuses derivation, and fixes repeat, publication, runtime, generic-I/O, and hardware authority false |
| A successful write callback could be presented as successful device-info | The private state matrix separates ATT dispatch, matched terminal, CRC, and cleanup; only all required states can form a historical success |
| Failed or uncertain evidence could be discarded as “unsupported” | Negative preflight and uncertain dispatch/cleanup remain valid observations without broad model or firmware claims |
| A connect timeout could be recorded as a definite failure with no cleanup | Connection has an outcome-unknown state that requires a disconnect attempt and keeps the overall attempt uncertain |
| A self-authored file could claim it came from a nonexistent exporter | Provenance says self-declared historical record; evidence ID and device context are fixed to withheld states |
| No terminal could hide timeout, cancellation, disconnect, overflow, or unrelated traffic | Closed absence reasons preserve attempt-local uncertainty and never become incompatibility |
| Renaming a private ledger or using Python/Markdown/extensionless text could bypass extension-based checks | The scanner recognizes evidence-shaped JSON by content, reserves case-normalized evidence suffixes globally, and checks identifier patterns in every regular file without echoing its name or value |
| Generated help could absorb an address, secret environment, host path, or capture name | Hostile-environment generation is byte-identical and privacy-scanned; the generator never probes runtime state |
| Completion installation could silently mutate a shell | Bash and man files ship only as inert package resources; no shell configuration or host help directory is changed |
| Manual readers could encounter active commands before safety boundaries | The offline/no-scan/no-connect/no-write/no-uinput contract precedes every generated command and option listing |

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
