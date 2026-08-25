# Strict vendor GATT transaction specification

Status: accepted fake-only SDD for tracker issue #21

## Job to be done

When a future reviewed adapter attempts one owner-approved vendor operation, the owner
and automation must be able to tell whether notification setup completed, whether the
command might have been sent, whether an exact application response matched, and what
recovery is safe. A transport callback must never be promoted to device success, and
late callbacks must never complete another attempt.

This slice is deliberately inert. `StrictVendorGattTransactionEngine` returns actions
for synthetic tests, performs no I/O, accepts no arbitrary UUID or payload, and keeps
all hardware/runtime-eligibility flags false.

## Connection state contract

The mandatory MAIN route is exactly `33f3` request, `33f4` response, and the one
enumerated `2902` descriptor belonging to that response instance. The only optional
route is RAW `33f5`/`33f6` with its own exact descriptor. Preflight supplies
connection-scoped characteristic and descriptor identities; reconstructed equal
objects do not satisfy callback identity.

| Phase | Required evidence | Safe next action |
|---|---|---|
| `primary_subscription_required` | primary descriptor action dispatched and its exact platform callback succeeds | enable optional RAW, or become ready |
| `optional_subscription_required` | primary is complete; RAW descriptor callback pending | ready or explicitly degraded |
| `ready` | all requested descriptor callbacks succeeded | one MAIN operation |
| `ready_degraded` | primary succeeded; optional RAW definitely failed before an uncertain lane state | one MAIN operation; RAW unavailable |
| `operation_in_progress` | one closed operation owns the serialized lane | wait for exact write callback/response |
| `reconnect_required` | lane may contain late traffic or the one operation completed | disconnect; never replay |
| `disconnected` | exact current connection was torn down | a higher-generation preflight may begin |

Dispatch return and platform completion are separate. A successful descriptor
completion proves only local GATT completion; it is not a peripheral application
acknowledgement. A primary failure is durable even if no operation was waiting.
Optional definite failure names the unavailable `raw_notifications` capability and
may degrade; optional dispatch uncertainty or a post-dispatch timeout requires
reconnection and cannot degrade to ready.

An adapter must record `DISPATCHED` atomically at I/O invocation entry, before yielding
to the backend. `DEFINITELY_NOT_DISPATCHED` is valid only when the backend was never
entered; if invocation entry itself cannot be established, the outcome is unknown and
the connection is quarantined. Merely receiving an inert action is not dispatch.

## Operation contract

Admission repeats the operation's process-local integrity check, fake-singleton
terminal ledger check, and closed registry lookup. The row must be ring-facing,
`offline_only`, `main_command`/`main_tx_rx`, and have one exact matched-response rule.
Generic `setUuid` and `writeCharacteristic` routes cannot enter this engine.

An operation has one immutable deadline from action creation through application
response. Every dispatch, completion, notification, and poll checks expiry first;
at `now == deadline`, timeout wins. The exact current connection token, exact current
target object, current action token, and operation matcher must all agree. Unrelated
notifications are inert and do not extend the deadline. Pre-write notifications are
not buffered.

After any write might have escaped, all terminal paths consume the connection. A
matched success, matched device failure, timeout, disconnect, malformed response,
failed write callback, or unknown dispatch ends in `reconnect_required`. No operation
is queued or automatically repeated after reconnect. This one-operation-per-connection
quarantine prevents a delayed duplicate response from closing a later operation with
the same signature.

## Human and automation semantics

Connection readiness and operation outcome are separate. Stable statuses state the
stage (`primary_subscription_*`, `optional_raw_subscription_*`, `operation_*`) and
closures expose `completeness`, `replay_allowed=false`, and
`automatic_retry=prohibited`.

Every accepted write callback and terminal operation update includes the normalized
`OperationResult` contract, with synthetic provenance, static-candidate confidence,
ordering, stage, dispatch/effect derivation, terminal basis, deadline state, and
recovery. Exact response matches keep device effect `unknown`.

- Before a command write is dispatched: `aborted`; no command was sent.
- After possible dispatch without an exact terminal: `uncertain`; reconnect and do
  not replay. Verify device state before deciding on a new explicit attempt.
- Exact success response: `matched_success` with completeness `response_matched` and
  response outcome `exact_success`; this proves correlation, not physical effect.
- Exact failure response: `matched_failure`; never call it success.
- Stale callback or old disconnect: `stale_callback_ignored`; it consumes no current
  state or deadline.

Representations and explicit `public_payload()` methods omit frames, values, UUIDs,
operation IDs, descriptor and
characteristic instance identifiers, device identifiers, and addresses. Parsed values
are held outside serializable object state and available only through an explicitly
test-named synthetic accessor. Update and closure models reject `dataclasses.asdict`.

For assistive-input consumers, anything other than the exact required readiness state
must mean `input_armed=false`. A degraded connection is not input-ready when its named
missing capability is the selected event source, and reconnect never emits catch-up
events.

## Test-driven acceptance

Executable tests cover exact descriptor identity, descriptor dispatch versus callback
completion, primary failure visibility, optional RAW degradation, dispatch uncertainty,
exact-deadline precedence, old-generation callbacks and disconnects, disconnect
clearing, mutated operation rejection, redacted actions, late duplicate quarantine,
and prohibition of automatic replay.

A live adapter remains blocked on operation-specific owner consent, target ownership
validation inside the transport, reviewed BlueZ callback semantics, model/firmware
evidence, and the hardware-verified registry promotion process.
