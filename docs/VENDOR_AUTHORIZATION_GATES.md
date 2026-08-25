# Vendor-authorization gate classifier specification

Status: preparatory implementation contract for Symphony issue #23. Production gate
decisions remain blocked on #49 and reviewed owner-hardware evidence.

## Job to be done

When a ring operation appears to fail locally, an owner needs a precise offline
explanation of what the reviewed evidence does and does not establish. The explanation
must never contact a vendor service, impersonate the Android application, suggest a
bypass, or turn a historical observation into permission to run the operation again.

## Boundary and dependency order

The classifier is a synchronous pure function. It imports no Bluetooth or networking
backend and performs no scan, connection, subscription, write, retry, binding, DNS,
HTTP, socket, subprocess, or filesystem operation. Evidence collection and restrictive
private-file handling belong to the owner-hardware workflow; exact runtime scope and
atomic promotion belong to #49.

The production approved-evidence ledger is initially empty. Consequently, this slice
cannot emit a reviewed production `blocked_vendor_authorization` or
`ungated_for_operation` verdict. Synthetic evidence may exercise safe uncertainty
paths, but can never enter the approved ledger, mutate the operation registry, or grant
runtime, repeat, binding, network, or bypass authority.

This is intentional. The current #34 record contains an owner-declared model family and
firmware major, while production decisions require an exact model scope, firmware point
build, transport/backend scope, and evidence-decision version. Its matched failure is a
generic device rejection, not a proven authorization signature. A #34 review rejection
is also not an affirmative gate review. No inference fills any of those gaps.

## Exact scope

Every observation and classification request is bound to all of:

- one registered operation ID;
- one sanitized exact model scope;
- one sanitized exact firmware point-build scope;
- one closed transport/backend scope; and
- one positive evidence-decision version.

Unknown, withheld, wildcard, range, firmware-major-only, backend-fallback, downgrade,
family-wide, stale-version, or mismatched values fail with a stable value-free error.
They do not become an ambiguous verdict. Scope matching will consume the single exact
relation implemented by #49; it must not grow an independent fallback matcher.

## Closed verdict state machine

The future reviewed classifier has five successful verdicts:

| Verdict | Required reviewed evidence | Meaning |
| --- | --- | --- |
| `ungated_for_operation` | Exact current-generation matched success, passed control, completed dispatch, confirmed cleanup and evidence commit | A gate was not observed for this operation and exact reviewed scope; absence is not proven |
| `blocked_vendor_authorization` | A gate-specific approved exact denial contract, or an ordered reviewed same-scope exact-denial then exact-success differential after legitimate out-of-process owner authorization | A local gate was observed only for this operation and exact reviewed scope |
| `ambiguous` | Valid applicable but non-specific evidence: generic failure, either disconnect phase, malformed or premature traffic, route absence, failed control, write uncertainty, cleanup uncertainty, or conflicting observations | No authorization conclusion |
| `offline` | Local availability/connection was not established and dispatch is proven not sent | No gate observation and no incompatibility conclusion |
| `timed_out` | The bounded collection attempt expired | No gate conclusion; dispatch and cleanup uncertainty remain private |

A generic matched failure—including the current #34 `device_rejected` state—is
ambiguous. Disconnect, silence, timeout, route absence, cached application state, static
APK cloud behavior, and owner assertion are never authorization proof.

An approved exact denial requires a separate restrictive gate-review receipt bound to
the canonical owner record, its owner-review receipt, the exact scope, a closed symbolic
denial-contract ID, and an accept/reject decision. A controlled differential additionally
requires two independently reviewed records bound in order, unique evidence references,
and explicit review that the intervening authorization was legitimate, owner-controlled,
and out of process. The classifier never records the action, application status,
credentials, endpoints, binding labels, response values, or denial bytes.

## Public result contract

Every successful result uses the same closed fields: schema and record type, operation
ID, exact sanitized scope, verdict, evidence basis, coarse dispatch and cleanup states,
interpretation, exact-scope-only conclusion, closed recovery directive,
`automatic_retry: prohibited`, classifier Bluetooth/network access states, and an
authority object whose runtime, registry, repeat, binding, network, and bypass values
are all false.

It contains no evidence reference or digest, address, path, UUID target, frame, value,
precise time, device or phone identifier, app/cloud status, endpoint, credential,
secret, or binding label. Invalid input produces a stable value-free, non-retryable
error and no partial verdict.

## Human result contract

Human rendering is non-interactive, non-color, and uses this fixed screen-reader order:

1. conclusion-first authorization-gate heading;
2. stable verdict token;
3. operation;
4. sanitized exact classification scope;
5. evidence provenance, stated before any observation wording;
6. evidence basis;
7. dispatch state;
8. cleanup state;
9. statement that runtime eligibility is unchanged;
10. statement that network, binding, and bypass were not attempted; and
11. one status-specific next action.

Synthetic rendering labels itself as an example in the conclusion, reports
`scope_reviewed: false`, and never calls its scope reviewed. The offline token means
only that local availability was unconfirmed; human text does not attribute that state
to the ring rather than the adapter, permissions, power, or proximity.

`ungated_for_operation` says that absence was not proven. A blocked result says JRing
offers no bypass and does not instruct the owner to log in, open the official app, copy
credentials, or retry. Ambiguous and timed-out results prohibit replay. Offline directs
the owner only to local adapter, power, and proximity checks; a later test needs fresh
selection and consent.

## RED-first acceptance

1. Exact scope, provenance, schema, decision-version, replay, conflict, and ordered-pair
   validation fail closed before classification.
2. Approved exact denial and legitimate controlled differential are the only future
   blocked paths; exact reviewed success is the only future ungated path.
3. Every non-specific outcome maps only to ambiguous, offline, or timed out.
4. Static, unreviewed, owner-asserted, cached, and synthetic evidence cannot enter a
   production terminal verdict or approved ledger.
5. Every result leaves the operation registry byte-for-byte unchanged and all authority
   false. No automatic replay exists.
6. Tests fail on any socket, DNS, HTTP, Bleak, subprocess, vendor endpoint, credential,
   signing, or cached-decision capability.
7. Golden JSON keeps one identical key/type schema; golden human output keeps the fixed
   order and conclusion-first wording for each reachable verdict.

## Named blockers

- #49 must supply the exact scope relation, decision version, replay/conflict checks,
  and deterministic source-controlled rebuild.
- A gate-specific private review receipt and restrictive ordered-pair review boundary
  do not yet exist.
- No reviewed real-ring denial signature or controlled differential exists.
- #34 currently covers only `getDeviceInfo` and intentionally stores no point build or
  denial semantics.

Until those blockers close, this module is an uncertainty-preserving classifier
foundation, not an authorization detector and not a runtime eligibility source.
