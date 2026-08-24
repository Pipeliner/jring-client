# Repository guidance

This repository is exclusively for the JRing Linux client. Keep it independent:
do not add dependencies on sibling application repositories or workspace-relative
paths.

Treat Bluetooth addresses, advertisement payloads, packet captures, and health
measurements as sensitive. Never commit them. Discovery must stay passive and
redacted, hardware selection must be explicit, and vendor writes must remain disabled
until the protocol is supported by repeatable owner-authorized evidence and tests.

Use `docs/JTBD.md` for product prioritization and `docs/UX_SPEC.md` as the human-facing
behavior specification. Update the relevant jobs, acceptance scenarios, and tests
together when CLI behavior changes.
