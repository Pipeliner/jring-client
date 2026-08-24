# JRing jobs to be done

Status: reprioritized after adversarial review for v0.5

## Core jobs

### Establish trust before touching hardware

When I am considering a community client for a wearable with sensitive data, I want
to try its safe path and understand its boundaries before selecting my ring, so I can
decide whether I trust it.

Desired outcomes:

- Reach a useful simulated result without Bluetooth or an account.
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

### Reuse the ring as a general-purpose input

When a ring gesture or motion event is available, I want to map it to a small,
predictable keyboard or mouse action, so I can control presentations, accessibility
tools, or desktop workflows without installing an opaque automation stack.

Desired outcomes:

- Detect when a ring exposes the standard Bluetooth HID service.
- Preview a mapping before it can generate operating-system input.
- Require explicit authorization for each input-injection run.
- Allow only named keyboard and mouse actions; never execute shell commands.
- Exercise the full mapping path with simulated `step` events while hardware motion
  packets remain unverified.

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
