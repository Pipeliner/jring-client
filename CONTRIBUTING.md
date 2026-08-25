# Contributing to JRing client

Start with a public issue describing the user job, intended behavior, executable tests,
artifacts, and blockers. Keep each change independently reviewable. Update JTBD and UX
specification text before implementation, add a failing test, then make it pass.

## Evidence safety

Never attach or commit raw Bluetooth captures, Android application archives, addresses,
BlueZ object paths, device or account identifiers, precise personal timestamps, health
measurements, report maps, or vendor payload dumps. Do not paste them into an issue,
pull request, CI log, commit message, or chat transcript.

Work with synthetic evidence unless the owner separately authorizes a local hardware
observation. Keep originals outside the repository. Create a minimal manifest from the
synthetic example, then validate and derive locally:

```sh
python3 scripts/evidence_tool.py validate path/to/manifest.json
python3 scripts/evidence_tool.py derive path/to/manifest.json > /tmp/jring-fixture.json
```

The validator refuses unsafe content; it does not promise to anonymize it. Review the
derived fixture yourself before adding it. Run `python3 scripts/evidence_tool.py scan .`
and the full tests before committing. If a finding or reproduction needs sensitive
material, stop and follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

Schema-2 `*-claim.json` files are public review candidates and must have an exact
`*-fixture.json` derivation. The current allowlist contains only the sealed vendor-main
device-info canary shape. Do not turn a private owner manifest into a tracked claim:
construct and review the minimal public candidate separately. Schema validation grants no
permission to connect, activate notifications, write, publish private evidence, or
claim hardware support.

A schema-2 private device-info observation is a self-declared record of one historical
attempt only. It withholds identifiers and model/firmware context. Keep it
outside the repository, owned by the current user, and mode 0600 (or read-only 0400),
then run only `python3 scripts/evidence_tool.py validate path/to/observation.json`.
Validation performs no Bluetooth operation and authenticates neither the owner nor the
observation. `derive` deliberately refuses this artifact; do not commit, attach, paste,
or publish it. A future pre-run plan, its one attempt, this post-run observation, and
any separately consented public candidate are four different artifacts and decisions.

The `-manifest.json`, `-claim.json`, and `-fixture.json` suffixes are reserved across
the repository; moving an unpaired artifact outside `tests/fixtures/evidence` does not
bypass validation.

Vendor writes remain disabled. Evidence contribution never authorizes scanning,
connecting, subscribing, input injection, or packet emission.

## License

Project source, including accepted contributions, is distributed under the
[MIT License](LICENSE). This repository does not add a separate contributor license
agreement.
