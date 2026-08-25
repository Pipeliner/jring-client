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
- Inspect statically proven request and response layouts offline with synthetic data,
  without making those codecs callable from a live client.
- Gain useful passive and read-only support while uncertain or destructive
  operations remain visibly gated.
- Never confuse a UUID string, advertised property, static opcode, or simulated
  vector with proven behavior on my ring.
- Preserve raw device timestamps and opaque field names where the app's timezone
  handling or user-facing labels are not independently proven.
- Use only legitimate owner pairing/session flows; extracted secrets, token replay,
  authorization bypasses, and device impersonation are out of scope.
- Keep the APK, decompiled code, captures, identifiers, and real measurements private.

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
- Atomic exports with an unambiguous format.
- Versioned machine-readable successes and failures with stable exit meanings, so
  automation never needs to scrape English diagnostics.
- Useful partial results from firmware with missing, malformed, or slow optional
  fields, without multiplying the command deadline by the number of fields.

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
- Reject tag/version drift, secrets, unsafe paths, and undeclared archive members.
- Install the wheel in a clean environment and run only passive/simulated smoke paths.
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
- Discover the complete local action vocabulary without Bluetooth, optional packages,
  or an input device.
- Preview a mapping before it can generate operating-system input.
- Require explicit authorization for each input-injection run.
- Allow only named keyboard and mouse actions; never execute shell commands.
- Describe mouse buttons as primary/secondary alongside left/right labels, and make
  aliases resolve to exactly the same action.
- Expose only the kernel input capability selected by the mapping.
- Exercise the full mapping path with simulated `step` events while hardware motion
  packets remain unverified.
- Distinguish discrete app-action events from cumulative step counters and raw motion;
  only the former may become direct input candidates without gesture inference.
- Keep phone-call, location, camera-lifecycle, time-write, raw audio/image, Wi-Fi,
  file, and OTA side effects outside the default input action path.
- Inspect raw AI/action/audio/image framing offline without subscribing, writing,
  persisting private content, or repeating the APK's unsafe length and CCCD behavior.

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

The v0.5 slice repairs adversarially identified trust failures: simulated operations
cannot touch radios, active scans require explicit authorization, outputs retain
provenance, optional data cannot hide capabilities, errors redact identifiers, and
destructive export replacement is explicit. Actual JRing motion events stay blocked
until owner-authorized evidence establishes their protocol and the live-input safety
state machine is specified.
