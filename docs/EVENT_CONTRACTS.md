# Neutral event and operation-result contract

Status: schema 1, offline contract only; no live transport integration

This contract gives later runtime, JSON Lines, desktop-control, and input work one
stable vocabulary without asking consumers to parse vendor callback objects. It is a
control-plane envelope, not a value container or an authority token.

## Ring events

`RingEvent` is immutable and factory-created. Its serialized fields, in canonical
order, are:

| Field | Meaning |
|---|---|
| `record_type`, `schema_version` | Fixed `ring_event`, schema `1` discriminant |
| `semantic_kind` | Closed neutral kind; no axis, gesture, medical, or button inference |
| `relationship`, `source_operation` | `unknown`, `unowned`, or exact operation correlation |
| `sequence`, `connection_generation` | Connection-wide ordering, not a persistent device identity |
| `provenance`, `confidence` | Synthetic/static/live origin and proof strength |
| `wall_time_state`, `device_time_state` | Presence/withholding states only; no clock values |
| `deadline_state` | Process-monotonic operation-deadline state; no absolute deadline |
| `automation_eligible` | Derived hardware-evidence gate, never sink consent |

Unknown events are opaque, unattributed, deadline-free, and ineligible for automation.
Passive actions and sensor candidates are `unowned`: they cannot name a request merely
because an opcode or method name looks related. Schema 1 permits an operation source
only for a transaction-callback event whose closed registry row has a matchable
terminal. A live event additionally requires that exact operation to be owner-hardware
verified. No current registry row satisfies that gate, so every current event is
non-automatable.

The ordering domain is one complete normalized stream per connection generation.
Sequences and generations start at 1, are contiguous, and do not exceed the largest
integer exactly interoperable through common JSON number implementations. Unknown
events consume sequence positions. A reconnect advances exactly one generation and
resets the sequence. Duplicate, stale, future-generation, skipped, or reordered
events are rejected atomically; a consumer must explicitly advance before accepting a
new generation. Generation 1 may recur after a process restart, so the pair is not a
global identifier.

## Operation results

`OperationResult` carries a connection-wide result `sequence` and a generation-scoped
`operation_sequence`. The latter correlates multiple stages from one attempt and
distinguishes repeated or concurrent calls without retaining a device or request
identifier. `OperationResultOrderGuard` rejects gaps, stage regression, changes to an
attempt's operation, evidence regression, duplicate states, and updates after a
terminal result. An uncertain write may be the first emitted result when invocation
did not return, because manufacturing an earlier `accepted` row would be false.
Once local acceptance has been emitted, later uncertainty must advance to response or
cleanup and keeps `dispatch_state=locally_accepted`; it can never regress to
`possibly_sent` or `not_sent`.

The first machine field to interpret is `outcome`:

| Outcome | Exact user meaning | Recovery |
|---|---|---|
| `aborted` | Work definitely stopped before possible dispatch | Fix the named local cause, then retry deliberately |
| `accepted` | A local write/dispatch call returned; peripheral receipt is unknown | Continue waiting; do not call this success |
| `response_matched` | An exact current-attempt response was observed | Device effect remains unknown; cleanup can still become uncertain |
| `uncertain` | Dispatch may have happened but no safe terminal conclusion exists | Reconnect and never replay automatically |
| `unsupported` | This runtime or policy cannot perform the operation | Do not infer ring or firmware absence |
| `proven_unavailable` | Closed evidence says the named scoped target lacks it | Valid only with registry firmware scope and evidence |

`dispatch_state` and `device_effect` are derived rather than caller-controlled.
`locally_accepted` never means the ring received anything. Even a matched success
terminal leaves `device_effect=unknown`; completion means the bounded client workflow
completed, not that a setting persisted or a physical action occurred. An exact
response match is allowed only for registry rows with a matchable terminal rule.
`terminal_basis` distinguishes an exact success response, exact failure response,
explicit terminal marker, or terminal metadata. A matched failure remains
`terminal_without_success`; a conditional history route can complete only from its
marker or metadata basis, never from quiet or a generic response label.
Failure bases are also operation-specific: an operation without a recovered failure
predicate cannot manufacture a matched failure.
Generic transport routes marked unsafe cannot produce dispatched outcomes.

`uncertain` is derived from `completion=unknown`. A stable `reason` and `recovery`
directive prevent scripts from guessing from prose. The closed state matrix enforces:

- accepted work is at write/in-progress with an active deadline;
- a matched response has a satisfied deadline and may be response/in-progress,
  complete/succeeded, or response-preserving cleanup/unknown;
- uncertain dispatch is unknown, expired or cancelled, and always reconnect/no-replay;
- definite pre-dispatch aborts are terminal without success and retry only after a fix;
- unsupported and proven-unavailable results are preflight, not-sent, deadline-free;
- proven-unavailable and live/hardware claims require exact scoped registry evidence.

Wall observation, device time, and process-monotonic deadline state are independent.
Only their state labels serialize. An expired deadline proves neither device failure
nor absence of mutation.

## Privacy, construction, and compatibility

The exact schema allowlists are metadata-only. They contain no generic typed value,
raw packet, stable address, device identifier, private content, measurement, or exact
wall/device/monotonic time. Operation names can still reveal the category of a user's
activity, so applications should keep these records local unless a later export policy
explicitly redacts or authorizes them.

Factories validate registry membership and every state relationship. Direct dataclass
construction is closed, fields are frozen and slotted, and a process-local weak seal
makes serializers reject changes to declared fields even through low-level mutation.
Immutable copies preserve object identity. Returned mappings are independent, and
errors expose only stable codes without echoing rejected values. Operation-specific
typed values must use a separately reviewed closed wrapper;
adding an arbitrary `value`, `content`, or similarly named field is invalid.

Serializers emit canonical compact schema-1 JSON. Parsers accept schema-1 fields in
any object-key order but reject missing or additional fields, invalid derived fields,
unknown enum values, and unknown schema versions. Any field addition or meaning change
requires a new schema version. Future readers must retain an explicit schema-1 parser;
schema-1 readers fail closed on newer versions.

Existing simulator result dataclasses and `input.SensorEvent` are legacy local models,
not normalized-contract consumers. This issue intentionally does not integrate them.
The runtime, JSON Lines, MPRIS, and input tracker slices must adapt through these
contracts before claiming completion.
