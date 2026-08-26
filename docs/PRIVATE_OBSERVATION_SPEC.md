# Private owner observation workflow

Status: implementation contract for Symphony issue #55. No observation command is
implemented by this document.

## Job to be done

An owner investigating a selected ring needs to retain a bounded unknown-notification
observation locally, then prepare a safe public handoff without placing an address,
raw frame, health value, credential, or private path into GitHub.

## Proposed terminal flow

The future `jring observe` command must require a mode-0600 `--address-file`, a new
mode-0600 `--private-output`, `--allow-connect`, `--allow-notifications`, and a
same-command `--allow-observation` acknowledgement. Guided selection may be added only
after it retains the existing active-scan/default-no flow. The command must show its
exact bounded duration and record limit before transport construction.

It connects once, validates one connection-generation-owned target, subscribes once,
retains at most the requested bounded number of observations, unsubscribes, closes,
and exclusively writes one private record. It never sends a vendor write, reads a
characteristic value, retries, uploads, opens a browser, or enables runtime behavior.
Timeout, cancellation, disconnect, overflow, malformed traffic, uncertain cleanup, or
private-file failure must produce a closed result that does not invite automatic retry.

## Private record and review

Raw observations, if any, exist only in the new private mode-0600 file outside the
repository. Human/JSON command output never names its path or echoes raw data. The
file lifecycle must reuse the owner-evidence restrictive-parent, no-link, exclusive
creation, atomic-write, and verification guarantees.

An offline review command must first display a value-free summary: capture outcome,
count, local cleanup state, declared model/build scope, and explicit authority denials.
Only a separate review receipt can permit an optional sanitized public candidate. The
candidate can state that an observation exists and whether it was bounded/complete; it
cannot disclose identifiers, timestamps, frames, values, target IDs, paths, or a claim
of compatibility, event meaning, terminal behavior, input eligibility, or runtime
authorization.

## External comparative evidence

Public implementations may nominate a candidate route or decoder for a future
observation plan, but the command must label that basis `external_unverified`. It is
never sufficient to choose a target, infer an event meaning, or authorize a write.
Each candidate needs clean-room reconciliation, exact scope, and owner-hardware review
before any runtime behavior can be considered verified.

## RED-first acceptance

1. Missing consent, invalid/ambiguous/stale selection, unsafe output, a pre-existing
   output, and an unsupported target fail before Bluetooth I/O.
2. Tests cover deadline, count cap, overflow, early/late notification, malformed
   traffic, disconnect, cancellation, subscribe/unsubscribe/close failure, and one
   generation only.
3. Standard output, errors, JSON, repr, issue-draft URL, repository scan, and public
   derivation never contain private observations or identifying metadata.
4. A review or public candidate cannot mutate the runtime registry, authorize a repeat,
   or make an external implementation verified.
