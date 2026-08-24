# JRing jobs to be done

Status: prioritized for v0.3

## Core jobs

### Establish trust before touching hardware

When I am considering a community client for a wearable with sensitive data, I want
to try its safe path and understand its boundaries before selecting my ring, so I can
decide whether I trust it.

Desired outcomes:

- Reach a useful simulated result without Bluetooth or an account.
- See that discovery is passive, identifiers are redacted, and vendor writes are off.
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

1. Setup readiness: delivered in v0.3 without expanding protocol scope.
2. Safe sensor-to-input mapping: high general-use value with a simulator-first path.
3. Partial status when optional characteristics are absent: useful across ring models.
4. Guided explicit device selection: valuable, but requires careful privacy design.
5. Vendor history/live metrics: valuable but blocked on owner-authorized evidence.

The v0.4 slice adds standard HID detection and a simulator-first `jring input` path.
Actual JRing motion events stay blocked until owner-authorized evidence establishes
their protocol.
