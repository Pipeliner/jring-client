# Repository guidance

This repository is exclusively for the JRing Linux client. Keep it independent:
do not add dependencies on sibling application repositories or workspace-relative
paths.

Treat Bluetooth addresses, advertisement payloads, packet captures, and health
measurements as sensitive. Never commit them. Discovery must stay redacted and require
explicit consent before activating the radio, hardware selection must be explicit, and
vendor writes must remain disabled until the protocol is supported by repeatable
owner-authorized evidence and tests.

Use `docs/JTBD.md` for product prioritization and `docs/UX_SPEC.md` as the human-facing
behavior specification. Update the relevant jobs, acceptance scenarios, and tests
together when CLI behavior changes.

Track future product work in GitHub issues. Each implementation issue must state its
JTBD outcome, SDD behavior and safety contract, RED-first TDD evidence, allowed
artifacts, and blockers. Apply the `symphony` label only when the issue is sufficiently
bounded for the fail-closed workflow; a label is eligibility, not permission to bypass
hardware, privacy, publication, or human-decision gates.
