# Install a reviewed JRing artifact

No package index or GitHub release is published yet. Download the wheel and
`SHA256SUMS` from an owner-reviewed `release-artifacts` workflow run, keep them in one
directory, and verify before installation:

```sh
sha256sum --check SHA256SUMS
pipx install ./jring_client-0.5.0-py3-none-any.whl
# or: uv tool install ./jring_client-0.5.0-py3-none-any.whl
jring doctor
jring status --simulate
```

The base wheel has no Bluetooth or desktop-input dependency. For hardware support,
inject the optional Bleak dependency into the isolated tool environment with your
installer's documented package-injection command. Desktop input additionally needs
`evdev` and local `/dev/uinput` permission; do not run JRing as root.

Upgrade only after verifying the new artifact, using `pipx install --force PATH` or
`uv tool upgrade jring-client` when the selected installer supports the artifact
source. Remove it with `pipx uninstall jring-client` or
`uv tool uninstall jring-client`. User-created address files and exports are not
removed automatically.

Artifact provenance is a GitHub build attestation tied to the workflow and commit.
Checksums detect changed downloads; neither mechanism is a project license or a claim
that real JRing hardware has been verified. Publishing to an index, creating a GitHub
release, signing with owner credentials, and choosing a license remain separate owner
decisions.
