# Exact scope attestation

Status: design contract for Symphony issue #57. No attestation command is implemented
by this document.

## Job

An owner needs to record the exact model, firmware point-build, and transport/backend
scope of one selected ring for later review, without disclosing those values publicly or
turning a successful read into runtime permission.

## Proposed flow

The future command requires a mode-0600 selected-address file, a new mode-0600 private
output, and explicit consent for one connection and the standard Device Information
reads required for the scope. It must say before connecting that it records private
scope values only; it performs no vendor write, notification subscription, decoder,
input action, upload, browser launch, retry, or runtime change.

All required fields must be present, parse as a strict sanitized symbol, and identify an
exact point build. Firmware majors, ranges, dates, opaque identifiers, paths, UUIDs,
addresses, timestamps, ambiguous values, and contradictory repeated reads are rejected.
The backend scope is a closed local symbol, not an inferred library version. The private
record is exclusively created in a restrictive owner-only directory and includes no
claim of compatibility, authorization, or repeat permission.

## Review and promotion boundary

An offline review may disclose only that an exact private scope record is structurally
valid and remains unreviewed. A separate source-controlled decision must bind operation,
public sanitized scope symbols, backend, and decision version before #49 may consider
eligibility. Neither an attestation, review, public candidate, nor issue draft changes
the empty runtime eligibility ledger.

## RED-first acceptance

1. Missing consent, unsafe paths, missing/major-only/malformed/ambiguous values,
   disconnect, cancellation, or an output failure close without promotion or retry.
2. Tests prove values never appear in stdout, stderr, JSON, repr, GitHub drafts,
   generated artifacts, or repository scans.
3. Tests prove no vendor write, notification subscription, input, network, browser, or
   eligibility-registry mutation occurs.
4. A public decision must reject a differing model, point build, backend, operation, or
   decision version exactly; no prefix, range, family, or nearest-match fallback exists.
