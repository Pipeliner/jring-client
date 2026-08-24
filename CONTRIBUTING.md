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

Vendor writes remain disabled. Evidence contribution never authorizes scanning,
connecting, subscribing, input injection, or packet emission.
