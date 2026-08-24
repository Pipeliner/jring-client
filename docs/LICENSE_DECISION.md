# License decision brief

Status: **owner decision required**. This document does not license JRing Client.

## Job to be done

Users and contributors need an unambiguous grant before they can confidently use,
redistribute, or modify the project. The repository owner needs a small, explicit
choice rather than an inferred decision based on public visibility or dependency
licenses.

## Observed project facts

- The repository is public, but it has no `LICENSE` file and `pyproject.toml` has no
  project license expression. Public visibility alone is not a license grant.
- The base package declares no runtime dependencies. Optional direct dependencies in
  the current lock are Bleak 1.1.1 (MIT), evdev 1.9.3 (BSD-3-Clause), and pytest 9.1.1
  (MIT). Release tooling pins build 1.5.0 and setuptools 84.0.0, both MIT.
- That inventory covers declared direct and release-tool metadata only. It does not
  audit transitive packages, repository history, copied snippets, generated artifacts,
  trademarks, patents, or the identity and consent of every copyright holder.
- No compatibility conclusion is made here. Complete the broader inspection after the
  owner chooses a candidate and before publishing licensed artifacts.

Metadata sources inspected on 2026-08-24:

- [Bleak on PyPI](https://pypi.org/project/bleak/)
- [evdev on PyPI](https://pypi.org/project/evdev/)
- [pytest on PyPI](https://pypi.org/project/pytest/)
- [build on PyPI](https://pypi.org/project/build/)
- [setuptools on PyPI](https://pypi.org/project/setuptools/)

## Practical options

| Choice | Practical effect | Best fit when |
| --- | --- | --- |
| `MIT` | Short, permissive terms requiring preservation of the copyright and permission notice; the canonical text does not contain an express patent-license section. | Simplicity and minimal downstream obligations matter most. |
| `Apache-2.0` | Permissive terms with an express patent grant and patent-termination provisions; distributions must preserve required notices, including qualifying `NOTICE` content when present. | Explicit patent terms and detailed contribution/distribution rules are valuable. |
| `MPL-2.0` | File-level copyleft: recipients of distributed modified covered files must be able to obtain their source under MPL, while separate files may remain under other terms in a larger work. | Improvements to JRing files should remain shareable without applying copyleft to an entire combined application. |

Canonical references:

- [MIT License, Open Source Initiative](https://opensource.org/license/mit)
- [Apache License 2.0 and application guidance](https://www.apache.org/licenses/LICENSE-2.0)
- [Mozilla Public License 2.0 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)

These summaries are operational guidance, not legal advice. Read the selected license
and obtain professional advice for legal certainty, especially for ownership, patent,
employment, or prior-contribution questions.

## Owner decision record

Choose exactly one option, or name another license explicitly:

- SPDX identifier: **UNDECIDED**
- Copyright holder/name for notices, if applicable: **UNDECIDED**
- Decision made by: **UNDECIDED**
- Decision date: **UNDECIDED**

Useful decision rule: choose MIT for the shortest permissive grant, Apache-2.0 for a
permissive grant with explicit patent terms, or MPL-2.0 for file-level reciprocity.
No option is selected by this brief.

## Implementation contract after the decision

1. Add the unmodified canonical license text and any required notice material.
2. Add the exact SPDX expression to `pyproject.toml`; make the README and contribution
   guidance agree without inventing extra contributor terms.
3. Audit direct and transitive dependencies, copied material, and built distributions
   against the selected terms; document the inspection scope and unresolved questions.
4. Add tests that fail when the license file, package metadata, README notice, or built
   artifact metadata disagree.
5. Build and inspect both wheel and source distribution before committing and pushing.

Until the owner fills in the decision record, issue #12 remains blocked and no license
text or package license metadata should be added.
