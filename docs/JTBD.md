# JRing jobs to be done

Status: complete implementation portfolio tracked in milestones M0–M6

## Product completion target

JRing is a local-first Linux companion for every ring-facing Bluetooth capability in
the clean-room specification. Completion means a capability is runnable and verified
on a named model/firmware scope or repeatably proven unavailable, vendor-gated, or
unsafe there. Static codecs and simulated behavior do not count as live completion.

The core Linux integrations are a stable Python event API, JSON Lines, MPRIS, and
allowlisted `uinput`, with permission-checked XDG TOML profiles. Vendor accounts,
advertising/social integrations, and Android-only plumbing are excluded. MQTT, D-Bus,
OSC, MIDI, arbitrary shell execution, Fish completions, and simulator expansion are
not first-party completion requirements.

The decision-complete dependency graph lives in [ROADMAP.md](ROADMAP.md) and public
[completion epic #16](https://github.com/Pipeliner/jring-client/issues/16).

## Core jobs

### Replace the owner app without losing ring capabilities

When I own a JRing and choose Linux, I want every Bluetooth capability exposed by
the authorized Android package accounted for in the Python client, so I can stop
depending on the vendor app or cloud without accepting guessed writes or hidden
privacy risks.

Desired outcomes:

- See one complete matrix of app operations, GATT endpoints, protocol evidence,
  Python support, firmware scope, and owner-hardware verification.
- Count every interface request exactly once by its primary route, including local,
  cloud, filesystem, conversion, DFU, dynamic-GATT, and no-op surfaces that are not
  ordinary vendor Bluetooth commands.
- Give every request either a closed offline codec or a non-runnable behavior/control
  model, so “accounted for” never means “callable” and no residual method is silently
  left as unknown implementation state.
- Inspect statically proven request and response layouts offline with synthetic data,
  without making those codecs callable from a live client.
- Exercise an ordered multi-frame alarm batch against a scripted fake while clearly
  seeing that frame callbacks cannot prove an alarm, content chunk, or whole-batch
  terminal and that no private schedule survives in the result.
- Exercise a planned multi-frame notification against the exact scripted fake while
  distinguishing a callback for an already-invoked marker from ring display, delivery,
  whole-batch acknowledgement, terminal state, or planner-state commit. Future markers
  must remain unowned and unbuffered; an unmarked failure may stop only future fake
  writes without becoming proof of which frame or batch failed. Keep notification text,
  IDs, UIDs, digests, markers, and frame shape out of the result while disclosing that
  the scripted-test transport deliberately retains private calls for focused tests.
- Gain useful passive and read-only support while uncertain or destructive
  operations remain visibly gated.
- Never confuse a UUID string, advertised property, static opcode, or simulated
  vector with proven behavior on my ring.
- Preserve raw device timestamps and opaque field names where the app's timezone
  handling or user-facing labels are not independently proven.
- Keep developer-cloud validation, device-cloud policy, application binding, Android
  bonding, and command-transaction state distinct. Use only legitimate owner flows;
  extracted secrets, token replay, authorization bypasses, and device impersonation
  are out of scope.
- Keep the APK, decompiled code, captures, identifiers, and real measurements private.
- Treat firmware update as a destructive multi-boundary workflow—main GATT, cloud,
  files, and SUOTA—not as a normal vendor request that static bytes can authorize.

### Establish trust before touching hardware

When I am considering a community client for a wearable with sensitive data, I want
to try its safe path and understand its boundaries before selecting my ring, so I can
decide whether I trust it.

Desired outcomes:

- Reach a useful simulated result without Bluetooth or an account.
- Choose a named `basic` or `hid` simulator profile, see that profile in every
  result, and receive the same advertised-capability state across commands.
- See which operations are offline, which activate the radio, how identifiers are
  redacted, and that vendor writes are off.
- Never need to reveal a device address merely to check whether the software runs.

### Make this computer ready

When hardware access does not work yet, I want one passive check that distinguishes an
unsupported platform, missing Python support, missing Bleak, and missing BlueZ tools,
so I can fix the right layer without trial-and-error or a traceback.

Desired outcomes:

- Diagnose prerequisites without scanning, connecting, writing, or using the network.
- Give one concrete remedy for each failed check.
- Keep a successful simulator path visible even when hardware is not ready.
- Let automation require hardware readiness explicitly.
- Distinguish installed prerequisites from the system D-Bus, BlueZ daemon, adapter,
  adapter power, and session permission states; ring compatibility remains untested
  until an explicitly selected connection is attempted.
- Distinguish a missing passive diagnostic tool from a system D-Bus failure, using a
  stable check name and a package-manager-neutral remedy instead of guessing that the
  bus needs repair.

### Read and export my data safely

When my selected ring exposes a verified capability, I want bounded reads and local,
predictable exports, so I can use my data without a cloud dependency or silent side
effects.

Desired outcomes:

- Human-readable status by default and stable JSON on request.
- Explicit device selection and bounded timeouts.
- Collect exactly one standard Heart Rate Measurement only after explicit hardware
  notification consent, then confirm cleanup before revealing it. Keep simulation
  synthetic and Bluetooth-free; send no vendor command, persist no measurement, and
  describe the result as fitness information rather than medical advice or general
  model/firmware compatibility.
- Atomic exports with an unambiguous format.
- Versioned machine-readable successes and failures with stable exit meanings, so
  automation never needs to scrape English diagnostics.
- Useful partial results from firmware with missing, malformed, or slow optional
  fields, without multiplying the command deadline by the number of fields.

### Understand connection progress and uncertainty

When a connection is slow, denied, interrupted, or racing a late callback, I want the
client to name the exact stage and safest next action, so I do not retry a command that
the ring may already have received or mistake cloud policy for ownership.

Desired outcomes:

- Distinguish link connection, endpoint validation, notification activation, write
  outcome, and matched application response.
- Never describe high-level notification activation as a confirmed CCCD write or
  peripheral acknowledgement.
- Report developer-cloud policy, device-cloud policy, application binding, and Android
  bonding independently; no state silently promotes another.
- Ignore callbacks from an earlier connection generation.
- Buffer a valid early response only within its operation and generation, without
  extending the original deadline.
- After an accepted write loses confirmation, report `uncertain`, do not replay, and
  require a fresh connection before another vendor operation.
- Make cancellation and cleanup bounded; explain whether work stopped before or after
  possible dispatch without printing frame bytes or identifiers.
- Give every normalized attempt a generation-scoped operation sequence, a primary
  outcome, a stable reason, and a recovery directive. Announce the outcome first;
  `accepted` means local dispatch only, while device effect remains unknown even after
  a matched response.

### Understand static recovery gaps without false completeness

When I review the recovered protocol evidence, I want decompiler run failures, emitted
hard-failure markers, warning-bearing scopes, and fallback output reported as distinct
facts, so I can decide what still needs instruction-level review without mistaking a
clean count for semantic or hardware proof.

Desired outcomes:

- Pair every zero scoped-marker count with a nonzero output denominator.
- Keep run-reported failures, failed-method stubs, marker occurrences, and affected-file
  counts separate; never manufacture a difference or success percentage.
- Lead screen-reader-friendly output with `source recovery completeness: not established`.
- State that warning-bearing application and embedded-SDK files still exist.
- Describe fallback-mode completion as output availability, not complete source
  validation, complete smali review, complete DEX coverage, protocol parity, or ring
  compatibility.
- Publish aggregates only; keep rendered source, locators, logs, and bytecode private.
- Treat structured/fallback agreement only as same-tool surface corroboration, and keep
  divergences, omitted bodies, and warning-bearing dependencies visibly unresolved.
- Require bounded instruction review before a warning-site result can support a named
  branch, selector, signedness, byte-order, or retry claim.
- Bind each private instruction review to the exact artifact, DEX unit, complete method
  prototype, reproducible span fingerprint, and every relevant control-flow edge.
- Publish only the sanitized bounded result, fact scope, span count, and limitations;
  never publish private descriptors, offsets, fingerprints, disassembly, or paths.
- Distinguish `not performed`, `confirmed`, `contradicted`, and `inconclusive` reviews;
  a scoped negative direct-call search remains inconclusive about reflection or native
  activation.
- Keep local cursor movement, dispatch booleans, terminal flags, and app broadcasts
  separate from peripheral delivery or acknowledgement.

### Select my ring without exposing its address

When I want to inspect a nearby ring, I want to select it by a temporary identity cue
and confirm the connection in the same command, so its stable Bluetooth address does
not enter shell history, process listings, logs, or configuration.

Desired outcomes:

- Authorize an active scan separately from the subsequent connection.
- Compare coarse, privacy-preserving cues under aliases that change every process.
- Never auto-connect, even when exactly one candidate appears.
- Cancel or reject an unclear selection without connecting.
- Keep a mode-0600 address file as the non-interactive automation path.

### Understand the whole artifact without mistaking plumbing for capabilities

When I assess protocol parity, I want interface declarations, implementations,
call/dispatch sites, Android Bluetooth helpers, manifest activation, resources, JNI,
Binder, and reflection reported as separate surfaces, so a large code count or absent
direct constructor never becomes a fake capability or completeness claim.

Desired outcomes:

- Reconcile the exact request and callback declaration sets against the public ledgers;
  implementation and call-site methods never create additional interface rows.
- Treat Android GATT, scanning, bonding, classic-profile, and OTA helpers as platform or
  internal transport evidence until a public interface relationship is established.
- Separate the complete owned-scope Android Bluetooth instruction-reference inventory
  from semantic, dependency/transitive, runtime, and hardware review, which may remain
  incomplete even when every direct reference is classified.
- Give every non-opcode callback either closed behavior evidence or an explicit
  declaration-without-dispatch state; never leave platform callbacks silently
  unclassified.
- Link every codec-designated ledger row to importable Python code, while distinguishing
  direct, bound, branching, pipeline, stateful, and unresolved-family relationships.
- Exercise generic history through an exact fake request, with source callback counts
  preserved and local quiet visibly distinct from a device-confirmed terminal.
- Show generic topology rows, all rows retaining caveats, and every
  terminal-rule category as separate denominators so a smaller gap count cannot imply
  parity.
- When the generic topology bucket reaches zero, immediately explain that only static
  classification improved; caveats, response semantics, live availability, and hardware
  verification remain separate gates.
- Answer whether complete Bluetooth capability parity is established before presenting
  closure-looking counts, and keep successful report generation separate from scoped
  interface accounting, source semantics, live vendor availability, and hardware
  verification.
- Distinguish cross-opcode events, unrelated same-opcode collisions, disjoint private
  state events, and source-local terminal-shaped projections from acknowledgements so
  names, shared opcodes, or workflow proximity never manufacture transaction success.
- Let a privacy-sensitive protocol reviewer see that contact-content has only a
  conditional, app-local reverse-sync topology, with private records redacted and no
  acknowledgement, terminal, local-store implementation, or runnable path implied.
- See deterministic main/raw packet routes separately from shared preflight, dynamic
  writes, descriptor control, DFU, and operations that produce no fixed packet.
- On an explicitly selected ring, see whether the current metadata snapshot can
  structurally identify each main/raw endpoint pair and whether both opaque targets
  still belong to the transport, without reading, subscribing, writing, or treating
  structural readiness as live, owner-authorized, or hardware-verified support.
- Expose process-local/system broadcast mismatches, unhandled registered actions,
  sender-permission gaps, and teardown-domain mismatches as app defects, not features.
- Treat resource keyword counts as UI/localization surface, never capability counts.
- Correct substring false positives in native symbols; distinguish reviewed JNI roots
  and statically traced Binder/resource routes from unmatched declarations, unreviewed
  instructions, and runtime-generated activation that remain unresolved.
- Publish only sanitized counts and conclusions; keep artifact identities, component and
  action names, code locators, fingerprints, resources, and binaries private.

### Contribute protocol evidence without exposing private data

When I have owner-authorized or synthetic protocol evidence, I want a fail-closed local
review workflow that produces the smallest test fixture, so I can help compatibility
without publishing identifiers, health values, proprietary archives, or raw captures.

Desired outcomes:

- Declare provenance, publication consent, context, redactions, coverage, and confidence.
- Reject unsafe or incomplete input without repeating the sensitive value.
- Keep originals local and derive deterministic reviewable output without uploading it.
- Route sensitive security reports to a verified private channel.
- Prevent capture files, app archives, and unsafe evidence data from entering Git.
- Resolve vendor routes by exact connection-scoped service/characteristic instance and
  reject duplicate UUIDs, stale identities, or missing response/notification metadata
  before any future operation can subscribe or write.
- Let a protocol maintainer distinguish a typed callback projection from a proven
  transaction terminal, so value/event callbacks and ambiguous batched routes can never
  be reported as singleton success.
- Let a maintainer publish a schema-2 candidate for one sealed vendor device-info
  canary without copying its private owner ledger, raw vectors, or evidence reference;
  validation must keep live eligibility, owner authorization, and hardware support
  false until separate runtime and owner gates exist.

### Understand what environments are actually supported

When I evaluate JRing on my model and Linux setup, I want a versioned compatibility
matrix that separates synthetic prerequisites from owner-run hardware observations, so
I can see exactly what is verified, incompatible, and still untested.

Desired outcomes:

- Compare only coarse model, firmware-major, Linux-family, Python-minor, BlueZ-major,
  and Bleak-major dimensions.
- Never publish addresses, accounts, timestamps, health data, or raw payloads.
- Treat untested as untested rather than compatible or successful.
- Generate and merge reports deterministically for review before publication.

### Install a verified end-user artifact

When I install JRing without a source checkout, I want a reproducible wheel with a
checksum and provenance tied to its commit, so I can verify, smoke-test, upgrade, and
remove it without trusting an editable working tree.

Desired outcomes:

- Build byte-identical wheel and normalized source archives with pinned tooling.
- Rebuild in a fresh isolated environment using only an explicitly prepared,
  fully pinned local wheelhouse and no package-index access.
- Advertise only Linux and fixed Python-minor classifiers backed by committed CI.
- Reject tag/version drift, secrets, unsafe paths, and undeclared archive members.
- Install the wheel in a clean environment and run only passive/simulated smoke paths.
- Give Bash and man-page users deterministic help generated from the same
  parser as the CLI, without probing the host or configuring their shell.
- Keep artifact preparation separate from package-index publication and release creation.

### Reuse the ring as a general-purpose input

When a ring gesture or motion event is available, I want to map it to a small,
predictable keyboard or mouse action, so I can control presentations, accessibility
tools, or desktop workflows without installing an opaque automation stack.

Desired outcomes:

- Detect when a ring exposes the standard Bluetooth HID service.
- Inspect a task-first local inventory of HID metadata, static device actions, step and
  motion candidates, and raw non-health framing before selecting or contacting a ring.
- See evidence, maturity, hardware verification, live availability, and input
  eligibility separately so a static candidate cannot look usable.
- Inspect standard HID characteristic and descriptor metadata without reading report
  maps, subscribing to reports, or claiming operating-system usability.
- Preserve repeated HID Report characteristics as separate numbered metadata instances
  with their own descriptor state.
- Discover the complete local action vocabulary without Bluetooth, optional packages,
  or an input device.
- Describe each action by the APK's actual host effect—find-phone sound/volume reset,
  camera, call, location/weather, media, time synchronization, or volume—while making
  clear that vendor callbacks are not Android HID reports and none of those effects run.
- Preview a mapping before it can generate operating-system input.
- Require explicit authorization for each input-injection run.
- Allow only named keyboard and mouse actions; never execute shell commands.
- Describe mouse buttons as primary/secondary alongside left/right labels, and make
  aliases resolve to exactly the same action.
- Expose only the kernel input capability selected by the mapping.
- Exercise the full mapping path from two closed synthetic cumulative-counter frames,
  through exact decoding, baseline and isolated-increment policy, into a simulated
  `step` preview while hardware motion packets remain unverified.
- Exercise device-action, cumulative-step, Classic info/name, redacted App-ID,
  host-volume-request, exact `78/00` and `78/01` private unknown-motion callback
  projections, exact `4E` private passive chat-action candidates, exact `54/04`
  private Wi-Fi callback state-code candidates, and exact `78/09`
  touch-mode setting projections through an
  exact subscribe-only fake that performs zero writes and redacts private values.
  Keep every other `78` selector unrelated. Never reinterpret motion channels as
  axes, units, cadence, gestures, steps, buttons, or input, nor reinterpret the
  neutral touch value as enabled/state, a gesture, tap, button, sensor sample, or
  input event. The unused setters and passive callbacks grant no setter causation,
  acknowledgement, terminal, live subscription, hardware support, Classic
  attachment, or input authority.
  The fake run owns no request; the protocol request relationship stays unknown. The
  chat-action code grants no ChatGPT/content execution, content retention,
  acknowledgement, terminal, or input meaning.
  Discard Wi-Fi address material and grant no credential processing, host/ring
  networking, or radio change. Do not report whether Wi-Fi is enabled, connected,
  joined, current, or internet-reachable, and grant no acknowledgement, terminal,
  live, hardware, or input meaning.
- Exercise the proven host-volume reverse pipeline separately: one exact fake request
  may trigger one closed projection of explicitly caller-supplied offline values on
  the same connection generation. Never read or change host audio, retry an uncertain
  write, or mistake a local transport return for an application acknowledgement or
  protocol terminal.
- Exercise the exact operation-bound device-system fake query as one synthetic
  `54/11` write followed by one matching `54/12` response. Keep its private callback
  code redacted and never call fake completion current device state, Bluetooth
  readiness/connection, battery/power, firmware health, owner binding, live support,
  or hardware verification.
- Preserve the originally validated bytes of every request admitted to the singleton
  fake runtime. Reject changed fields, stored frames, or instance-shadowed accessors
  before operation creation; copies must preserve the same sealed identity. Correlate
  endpoint/opcode/selector before declaring malformed ownership, keep EQ SET traffic
  outside EQ GET, and keep heart-session start and stop branches distinct.
- Exercise the existing Wi-Fi network-name count/fragment response assembler with one
  exact scripted-fake request while hiding names, signal values, and fragment IDs from
  ordinary serialization. Never contact host networking or a live ring, and never
  interpret a returned fake call, count equality, quiet, or a caller limit as protocol
  completion.
- Distinguish discrete app-action events from cumulative step counters and raw motion;
  only the former may become direct input candidates without gesture inference.
- Keep phone-call, location, camera-lifecycle, time-write, raw audio/image, Wi-Fi,
  file, and OTA side effects outside the default input action path.
- Inspect raw AI/action/audio/image framing offline without subscribing, writing,
  persisting private content, or repeating the APK's unsafe length and CCCD behavior.
- Account for raw-notification enable and disable orchestration as non-runnable static
  evidence, so a broken disable branch cannot be mistaken for a usable subscription.

### Recover safely from one vendor command attempt

When I authorize one future vendor operation, I want setup, possible dispatch, and an
exact application response reported separately, so I know whether anything may have
changed and whether repeating the command is safe.

Desired outcomes:

- Never call a connection ready until the exact primary notification descriptor has a
  successful platform completion callback.
- See primary setup failure even when no command was waiting, and continue without RAW
  only when the failure is definitely confined to that optional capability.
- Know “no command was sent” versus “the command may have been sent.”
- Ignore old-generation descriptor, write, notification, and disconnect callbacks.
- Never automatically repeat a read, setter, control, or unknown-idempotence operation.
- Reconnect after any possibly dispatched attempt and quarantine delayed duplicates so
  they cannot close another operation.
- Keep target identities, frames, values, device identifiers, and addresses out of
  ordinary output.
- Disarm assistive input immediately when its exact source capability is not ready,
  with no catch-up events after reconnect.

## Opportunity ordering

1. Trust repair: radio-active operations, simulation, provenance, and accepted options
   must always match what the client actually does.
2. Real-hardware baseline: supported Bleak connections and partial status across ring
   variants must work before adding protocol surface.
3. Safe sensor-to-input mapping: retain a simulator-first path and design live input
   around debounce, rate limits, disarming, and guaranteed cleanup.
4. Guided private device selection: replace sensitive argv identifiers with ephemeral
   aliases while keeping identity confirmation explicit.
5. Vendor history/live metrics: blocked on owner-authorized evidence.

### Review one private device-info attempt without rerunning it

When I have a sanitized record of one previously authorized device-info attempt, I want
to validate its route, dispatch, response, and cleanup states locally, so I can find
inconsistencies without exposing identifiers or accidentally granting another run.

I need connect timeouts, possible write dispatch without a terminal, and cleanup
uncertainty to remain distinct from definite failure, so the record tells me whether it
certainly stopped before dispatch or instead prohibits replay, without claiming that a
device family is incompatible.

The historical observation remains distinct from a future pre-run plan, the transport
attempt itself, a separately consented public candidate, and runtime eligibility.
Negative and uncertain outcomes are useful evidence. A hand-edited success is not
authenticated hardware proof, and validation must never connect, subscribe, write,
derive a public artifact, or broaden support to a model or firmware family.

Desired outcomes:

- See the complete traffic disclosure before a connection starts.
- Use fresh guided selection as a human or an exact private address source in automation.
- After every completed or interrupted attempt, hear the result in the same order:
  attempt, write dispatch, response terminal, cleanup, evidence commit, then recovery.
- Treat interruption after possible dispatch as non-retryable and inspect the requested
  private record before deciding whether a new manually authorized attempt is safe.
- Preserve attempt, response-terminal, cleanup, and evidence-commit outcomes separately
  rather than allowing a cleanup or file failure to replace the original outcome.
- Preview every prospective public field privately, retain a separate review receipt,
  and only then derive a sanitized accept/reject row without loading Bluetooth.
- Make the detached public artifact self-describing: versioned, owner-declared in
  scope, and explicitly without runtime or repeat authority.
- Never overwrite an earlier private or public record, and never convert review into
  runtime authority.

The v0.5 slice repairs adversarially identified trust failures: simulated operations
cannot touch radios, active scans require explicit authorization, outputs retain
provenance, optional data cannot hide capabilities, errors redact identifiers, and
destructive export replacement is explicit. Actual JRing motion events stay blocked
until owner-authorized evidence establishes their protocol and the live-input safety
state machine is specified.

### Understand a possible vendor-authorization gate without contacting it

When a reviewed local operation succeeds or fails, I want an offline, operation-bound
explanation that distinguishes a proven local gate from ordinary transport uncertainty,
so I do not mistake a timeout for account trouble or send identifiers to a vendor.

Desired outcomes:

- Require exact model, firmware point build, backend, operation, and decision-version
  scope; never fall back to a firmware major or operation family.
- Say a successful observation did not encounter a gate, not that the firmware is
  globally ungated or that another live run is authorized.
- Preserve generic failure, malformed traffic, route absence, disconnect, failed
  control, cleanup uncertainty, offline state, and timeout without inventing a gate.
- Recognize a blocked gate only from a separately approved exact denial contract or a
  reviewed ordered denial/success differential after legitimate owner authorization.
- Never contact a vendor service, reproduce application state, suggest a bypass, bind,
  retry, or turn the classification into runtime authority.

The complete state, privacy, and accessibility contract is in
[VENDOR_AUTHORIZATION_GATES.md](VENDOR_AUTHORIZATION_GATES.md). Production terminal
verdicts remain unavailable until #49 and real reviewed owner evidence close the named
scope and receipt blockers.

### Know whether one exact runtime scope was reviewed

When I consider a recovered operation on a selected ring, I need an exact reviewed
scope decision rather than an operation-name allowlist, so an observation on a nearby
firmware or another backend cannot silently enable a run.

Desired outcomes:

- Compare operation, model, exact point-build symbol, backend, and decision version
  exactly; unknown, major-only, range, wildcard, stale-version, and fallback matches
  fail closed.
- Treat a checked-in decision as eligibility metadata only: selection, current
  connection ownership, fresh consent, dispatch, repeat, and runtime authority remain
  separate.
- Keep canary results, publication review, synthetic gate examples, and private
  evidence references out of runtime lookup and public inspection output.
- Make the complete reviewed source change validate atomically, rejecting duplicate
  scope keys, contradictory records, and replayed reviewed-evidence references.

The current ledger deliberately has no rows. Issue #57 must first provide a
privacy-safe exact build-scope attestation; therefore this boundary cannot claim that
any ring or operation is supported today.
