# License decision brief

Status: **selected and implemented**. JRing Client uses the MIT License.

## Job to be done

Users and contributors need an unambiguous grant before they can confidently use,
redistribute, or modify the project. The repository owner needs a small, explicit
choice rather than an inferred decision based on public visibility or dependency
licenses.

## Observed project facts

- The repository was public without a license grant before this decision. It now has
  canonical MIT text in `LICENSE` and `pyproject.toml` declares the `MIT` SPDX
  expression.
- The base package declares no runtime dependencies. Optional direct dependencies in
  the current lock are Bleak 1.1.1 (MIT), evdev 1.9.3 (BSD-3-Clause), and pytest 9.1.1
  (MIT). Release tooling pins build 1.5.0 and setuptools 84.0.0, both MIT.
- The completed metadata inspection covers every package in `uv.lock`, plus the pinned
  release tools. It does not establish the ownership of repository history, copied
  snippets, trademarks, patents, or every contributor's authority to license work.

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

- SPDX identifier: **MIT**
- Copyright notice: **Copyright (c) 2026 JRing Client contributors**
- Decision made by: **repository owner**
- Decision date: **2026-08-24**

## Compatibility inspection

The exact locked dependency and release-tool metadata was inspected on 2026-08-24:

- MIT: Bleak, dbus-fast, iniconfig, pluggy, the locked PyObjC packages, pytest,
  tomli, all locked WinRT packages, build, and setuptools.
- BSD-family: evdev (`BSD-3-Clause`), Pygments (`BSD-2-Clause`), and colorama
  (PyPI's BSD classifier; no SPDX expression in its metadata).
- Apache/BSD: async-timeout (Apache 2 metadata) and packaging
  (`Apache-2.0 OR BSD-2-Clause`).
- Other permissive metadata: typing-extensions (`PSF-2.0`) and exceptiongroup
  (PyPI's MIT classifier; no SPDX expression in its metadata).

The base installation has no runtime dependencies. Optional packages are referenced as
dependencies rather than copied into JRing distributions, and release tools are not
shipped. No reciprocal/copyleft license was found in the inspected metadata. On that
scope, no conflict with distributing JRing itself under MIT was identified. This is a
metadata and packaging review, not a legal opinion or a substitute for reviewing the
dependencies' full license texts when redistributing them.

## Implementation verification

1. `LICENSE`, package metadata, README, and contribution guidance all identify MIT.
2. Repository tests fail when those declarations disagree or when artifact metadata or
   source contents omit the license.
3. Both wheel and source distribution are built and inspected before the change is
   committed and pushed.
