# JRing jobs to be done

Status: reprioritized after adversarial review for v0.5

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
- Preview a mapping before it can generate operating-system input.
- Require explicit authorization for each input-injection run.
- Allow only named keyboard and mouse actions; never execute shell commands.
- Describe mouse buttons as primary/secondary alongside left/right labels, and make
  aliases resolve to exactly the same action.
- Expose only the kernel input capability selected by the mapping.
- Exercise the full mapping path from two closed synthetic cumulative-counter frames,
  through exact decoding, baseline and isolated-increment policy, into a simulated
  `step` preview while hardware motion packets remain unverified.
- Exercise device-action, cumulative-step, Classic info/name, and host-volume-request
  decoding through an exact subscribe-only fake that performs zero writes, redacts
  private values, and grants no live subscription, Classic attachment, or input
  authority.
- Exercise the proven host-volume reverse pipeline separately: one exact fake request
  may trigger one closed projection of explicitly caller-supplied offline values on
  the same connection generation. Never read or change host audio, retry an uncertain
  write, or mistake a local transport return for an application acknowledgement or
  protocol terminal.
- Distinguish discrete app-action events from cumulative step counters and raw motion;
  only the former may become direct input candidates without gesture inference.
- Keep phone-call, location, camera-lifecycle, time-write, raw audio/image, Wi-Fi,
  file, and OTA side effects outside the default input action path.
- Inspect raw AI/action/audio/image framing offline without subscribing, writing,
  persisting private content, or repeating the APK's unsafe length and CCCD behavior.
- Account for raw-notification enable and disable orchestration as non-runnable static
  evidence, so a broken disable branch cannot be mistaken for a usable subscription.

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
is safe to retry later without claiming that a device family is incompatible.

The historical observation remains distinct from a future pre-run plan, the transport
attempt itself, a separately consented public candidate, and runtime eligibility.
Negative and uncertain outcomes are useful evidence. A hand-edited success is not
authenticated hardware proof, and validation must never connect, subscribe, write,
derive a public artifact, or broaden support to a model or firmware family.

The v0.5 slice repairs adversarially identified trust failures: simulated operations
cannot touch radios, active scans require explicit authorization, outputs retain
provenance, optional data cannot hide capabilities, errors redact identifiers, and
destructive export replacement is explicit. Actual JRing motion events stay blocked
until owner-authorized evidence establishes their protocol and the live-input safety
state machine is specified.
