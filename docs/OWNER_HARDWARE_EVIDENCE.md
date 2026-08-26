# Owner-hardware evidence runner specification

Status: implementation contract for Symphony issue #34.

## Job to be done

When an owner and maintainer need to decide whether one recovered operation works on
one coarse model/firmware scope, they can run one bounded attempt against an explicitly
selected ring and obtain a private record plus a separately reviewable public row. The
attempt must not turn an address, response value, packet, successful callback, or past
consent into reusable runtime authority.

## Initial supported attempt

The first and only executable evidence operation is the closed `getDeviceInfo` MAIN
canary already present in the operation registry. Its recovered request/terminal pair
is useful for transport verification, but the parsed device information is private and
is never returned, logged, serialized, or copied into either evidence object.

This allowlist is intentionally narrower than the 112-row recovered registry. A row's
presence, offline codec, or `read_only` idempotence does not make it evidence-runnable.
Additional operations require their own issue, consent set, threat review, production
transport test, and firmware-scoped evidence.

## Authority and consent

A run plan is process-local, identity-sealed, single-use, and bound to:

- one exact address source loaded into a sealed selection in the same process, with
  guided scan-and-confirm selection available for a fresh human choice;
- `getDeviceInfo`;
- independent `connect`, `subscribe`, and `write` consent;
- an enabled local negative control;
- one finite overall deadline; and
- one new private output path.

No consent implies another. Extra consent, copied/reconstructed plans, reused plans,
unknown operations, simulation, interactive ambiguity, stale generations, and unsafe
output paths fail before transport construction or Bluetooth I/O. The plan and result
represent no input, binding, network, firmware, file-transfer, or OTA authority.

## Exact production sequence

The production path uses `BleakTransport` and exact connection-owned objects:

1. connect once to the explicitly selected ring;
2. enumerate services and characteristic/descriptor metadata under the overall
   deadline;
3. resolve exactly one MAIN `56ff` route with request `33f3`, response `33f4`, and one
   response-owned `2902` descriptor;
4. prove characteristic and descriptor object ownership for the current generation;
5. activate notifications on the exact `33f4` backend object;
6. hold a bounded pre-write negative-control window; a terminal-shaped notification
   in this window makes the attempt ambiguous and prevents the write;
7. invoke exactly one response-requesting write on the exact `33f3` backend object;
8. accept exactly one current-generation matched `getDeviceInfo` terminal;
9. deactivate the exact `33f4` notification once; and
10. disconnect once.

No retry or reconnect occurs inside an attempt. A callback, ATT write completion, or
disconnect is never sufficient by itself to establish application success, firmware
incompatibility, or vendor authorization.

## Deadline, cancellation, and uncertainty

One monotonic Bluetooth deadline reserves time for unsubscribe and disconnect while
bounding every transport await; the CLI default is 8 seconds and includes setup,
response, and cleanup. Equality is expired. A deadline that ends before cleanup
completes is uncertain and non-retryable. The fixed-size atomic evidence
commit begins only after cleanup; filesystem `fsync` is not falsely described as
cancellable by Python. Cancellation records the stage, performs bounded cleanup,
commits the private attempt when possible, and is then re-raised to preserve exit 130.
For this command, interruption is non-retryable: the write may have escaped even when
the process reports exit 130. Human and JSON recovery therefore direct the owner to
inspect the requested private record, when it exists, before considering another
separately authorized manual attempt.

Failure before the vendor write invocation is `aborted`. Once the invocation may have
escaped, timeout, cancellation, disconnect, write failure, missing response, or failed
cleanup is `uncertain`. An uncertain attempt is never replayed. Malformed and unrelated
notifications remain distinct from a matched failure terminal. Cleanup is attempted
exactly once; failed or unknown cleanup prevents an accepted result. Attempt status,
write dispatch, response terminal, cleanup outcome, and evidence-commit outcome remain
independent fields: cleanup uncertainty or output failure must not erase the event that
caused the attempt to stop.

## Evidence objects

The private record is created exclusively with mode `0600`, committed atomically, and
never accepted from a symlink or existing destination. It contains closed control-plane
states needed to audit one attempt, but no address, Bluetooth object path, target ID,
UUID, frame, response value, parsed device data, precise wall time, filesystem path, or
exception text. It remains private because its attempt/evidence identity can link an
owner's observation.

A public compatibility row is derived only after a separate maintainer decision. It
contains exactly:

- a schema version and closed public-record type;
- coarse, explicitly owner-declared model family and firmware major;
- Linux family, Python minor, BlueZ major, and Bleak major;
- registered operation ID;
- one closed operation status;
- one approved, non-sensitive evidence reference;
- the explicit decision (`promote` or `reject`); and
- explicit false live-runtime and repeat authority.

The public row contains no consent administration or private attempt identity.
Promotion records review; it does not mutate the runtime registry, grant repeat
authority, or establish support for any other operation or firmware scope.

## Result and recovery order

Human output uses the same screen-reader-friendly order for every outcome:

1. primary attempt status;
2. write dispatch (`not_started`, `started`, or `completed`);
3. response terminal (`not_observed`, matched success/failure, invalid, or premature);
4. unsubscribe and disconnect cleanup outcomes;
5. private evidence commit outcome; and
6. a status-specific recovery instruction.

An exact response is a response-terminal observation, never a property of the write.
If the private commit fails, output says that no reviewable record was created and does
not direct the owner to review a nonexistent file. Uncertain, interrupted, or
post-dispatch outcomes prohibit automatic replay. Pre-dispatch failures may explain a
fresh manual setup attempt, but never perform it.

## Status vocabulary

- `candidate_success`: public-row vocabulary for an exact terminal plus confirmed cleanup.
- `device_rejected`: an exact registered failure terminal was observed.
- `aborted`: no vendor write may have escaped.
- `uncertain`: a write may have escaped or cleanup is not confirmed.
- `protocol_incompatible`: the exact route or response shape was contradicted.
- `environment_unavailable`: local prerequisites or connection failed without a
  device-protocol conclusion.

`blocked_vendor_authorization` is deliberately absent. A matched failure, disconnect,
timeout, route absence, or review rejection is not proof of an authorization gate.
Issue #23 may add the verdict only after
approved owner evidence establishes an explicit local firmware-gate signature or a
controlled paired observation. Disconnect alone can never select that status.

## Task-first workflow

Create a private directory and choose a destination that does not yet exist:

```sh
install -d -m 700 .private/jring
jring verify-device-info --select --active-scan \
  --private-output .private/jring/device-info-attempt.json \
  --model-family reviewed-family --firmware-major reviewed-major \
  --allow-connect --allow-notifications --allow-write --negative-control
```

The human command discloses its one connection, subscription, negative-control window,
and vendor write before constructing the transport. Automation may use one exact
mode-0600 `--address-file`; direct address arguments remain rejected. A private output
must be new. Existing files, links, unsafe parents, ambiguous selection, and missing
independent authority fail before Bluetooth I/O.

Review the completed record without loading Bleak or touching a radio:

```sh
jring review-owner-evidence \
  --private-input .private/jring/device-info-attempt.json \
  --decision promote \
  --evidence-reference reviewed-device-info-canary-v1
```

This no-write preview shows the attempt, dispatch, terminal, cleanup, commit, declared
scope, and every Linux/Python/BlueZ/Bleak field eligible for the public row. After
inspecting it, seal the decision in a new private review receipt:

```sh
jring review-owner-evidence \
  --private-input .private/jring/device-info-attempt.json \
  --decision promote \
  --evidence-reference reviewed-device-info-canary-v1 \
  --review-output .private/jring/device-info-review.json \
  --allow-review-decision
```

The receipt creates no public file and grants no runtime authority. Derivation accepts
only a receipt cryptographically bound to the exact private record.

After that review receipt and a separate maintainer decision, exclusively create one
sanitized row:

```sh
jring derive-owner-evidence \
  --private-input .private/jring/device-info-attempt.json \
  --review-receipt .private/jring/device-info-review.json \
  --public-output reviewed-device-info-row.json \
  --allow-public-evidence
```

`promote` records acceptance of evidence only. It neither changes the operation
registry nor grants live eligibility; that separate boundary belongs to issue #49.
The created row remains self-describing outside this repository: it carries its schema
and record type, labels scope as owner-declared, and states that live and repeat
authority are false.
Promotion is refused while a required coarse environment dimension is `unknown` or
`withheld`; a reject row may retain those unknowns as useful negative evidence.
Retain private records only as long as the review needs them, keep them outside Git and
backups where practical, and delete them through the owner's normal secure retention
process. Unlinking a file does not promise physical erasure from SSD media, snapshots,
or backups. Crash-created temporary files use unpredictable names and a run cleans only
an inode it created; inspect an orphan before removing it and first confirm that no
evidence process is active.

## Test evidence

The primary test substitutes only the Bleak backend while exercising production
`BleakTransport`, exact backend-object ownership, and the full ordered sequence. Other
tests cover each await boundary, stale/reconstructed targets, independent consent,
single use, negative-control contamination, exact-deadline precedence, malformed and
unrelated traffic, disconnect, uncertain cleanup, atomic restrictive files, public
redaction, and lack of replay. Synthetic policy tests must neither construct Bleak nor
import `/dev/uinput`.
