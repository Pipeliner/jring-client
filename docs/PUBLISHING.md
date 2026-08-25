# PyPI publishing runbook

The `publish-pypi.yml` workflow separates package validation from publication. A
manual run is validation-only by default (`publish: false`): it builds twice with
pinned tools, compares the builds byte for byte, inspects their contents, installs the
exact wheel without an index, runs offline simulator smoke checks, and retains the
wheel and source archive for two days. It has no OIDC permission and cannot publish.

Publication is deliberately unavailable until the repository owner completes the
remaining PyPI trust binding below. Do not add a PyPI API token or a GitHub Actions
secret. Trusted Publishing exchanges GitHub's short-lived OIDC identity directly with
PyPI.

## Jobs to be done

- When a maintainer is preparing a package, they can exercise the complete build,
  inspection, and install path without possessing publication authority or risking an
  upload.
- When an owner approves a release, the bytes they reviewed are the bytes sent to
  PyPI, and publication still requires an independently configured repository and
  package-index trust boundary.
- When a contributor reviews automation, they can see that untrusted events, mutable
  action references, long-lived credentials, rebuilds in the privileged job, and
  silent duplicate handling are absent.

## Acceptance contract

- Manual dispatch is the only trigger and `publish: false` is the default.
- Validation has read-only repository access and no OIDC permission.
- Publication is possible only for a matching protected version tag when
  `publish: true`; the `pypi` environment must approve the deployment.
- The publication job downloads the validation job's immutable artifact ID and runs
  the PyPA publisher once. It does not check out or execute repository code.
- Every external action is pinned to a full commit SHA. No password, API token,
  repository write permission, PR path, or automatic tag path exists.

## Configured GitHub controls

The repository has a `pypi` environment with `Pipeliner` as its required reviewer and
a custom deployment policy that accepts only `v*` tags. An active repository ruleset
restricts creation, update, and deletion of matching tags to `Pipeliner`; this also
makes `github.ref_protected` true for an authorized version tag.

Self-review remains permitted because the repository currently has one maintainer.
Enable **prevent self-review** when a second release maintainer is available so the
initiator cannot approve the same deployment.

## Remaining PyPI configuration

In the `jring-client` project on PyPI, add a GitHub Trusted Publisher with exactly:

- Owner: `Pipeliner`
- Repository: `jring-client`
- Workflow: `publish-pypi.yml`
- Environment: `pypi`

If the PyPI project does not exist yet, create a pending publisher with the same
identity. Do not configure a password or API token. This account-level trust change
cannot be performed by the repository workflow and must be reviewed in PyPI.

The official setup references are the
[PyPI Trusted Publisher guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/),
the [PyPI security model](https://docs.pypi.org/trusted-publishers/security-model/),
and [GitHub environment protection](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments).

## Validate without publishing

1. Open **Actions → publish-pypi → Run workflow**.
2. Select the branch or candidate version tag to validate.
3. Leave `publish: false` and run it.
4. Review the reproducibility, package inspection, clean-install smoke results, and
   the `pypi-distributions-<commit>` artifact. No environment approval is requested,
   no OIDC token can be minted, and nothing is uploaded to PyPI.

This path is appropriate while configuring PyPI or reviewing a candidate. It never
runs for a pull request, fork, push, release, or tag automatically.

Offline source-tree tests always validate the declared project keywords and URLs. The
fresh wheel-and-sdist metadata test additionally requires the exact setuptools version
pinned in `pyproject.toml`. On a distribution Python with an older build backend, only
that artifact-building test is skipped; it must not silently use the older backend to
judge current metadata behavior. Use the isolated development environment or the
pinned validation workflow for artifact assertions. Files already present in local
`dist/` are disposable build outputs and are never evidence for the current source;
the release workflow builds twice from the selected commit and compares fresh outputs.

## Publish an approved version

1. Confirm the clean commit has passed normal tests and validation-only publishing.
2. Create the matching protected tag, for example `v0.5.0` for project version
   `0.5.0`. Tag creation and release notes remain manual owner actions outside this
   workflow.
3. Dispatch `publish-pypi` at that exact tag with `publish: true`.
4. Wait for `build-and-validate` to finish. Inspect that job and its immutable
   artifact before approving the pending `pypi` environment deployment.
5. The publishing job downloads that artifact by GitHub artifact ID. It does not
   check out source, rebuild, run project code, accept `skip-existing`, or receive a
   repository token with write access. Its only elevated permission is
   `id-token: write`, used by the pinned PyPA action for OIDC and package attestations.

Reject the deployment if the selected ref, artifact names, version, commit, or review
results are unexpected. A duplicate PyPI version fails loudly and must be investigated;
published files are immutable and must never be silently skipped or replaced.

## Remaining owner-side gate

The GitHub controls are configured. Publishing remains disabled until the PyPI Trusted
Publisher identity matches `Pipeliner/jring-client`, `publish-pypi.yml`, and `pypi`.
Only the PyPI owner can create and audit that final trust binding.
