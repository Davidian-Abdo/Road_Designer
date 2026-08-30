# Contributing to Road-Designer

Thanks for your interest. This project is published by **Beamstack** under the
**Beamstack Community License 1.0** ([`LICENSE`](LICENSE)); please read
[`LICENSING.md`](LICENSING.md) first so the terms below make sense.

## Getting set up

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest tests/ -v                                    # engine suite

# backend work as well:
pip install -r backend/requirements.txt
pytest backend/tests/ -v
```

The engineering reference for how the code is organised, the invariants it must
keep (PK as the independent variable, French on-drawing labels, `DesignConfig`
as the only configuration contract, no module-level constants, …) and the bug
history is [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md). Match the style
and conventions of the surrounding code.

## Pull requests

- Keep changes focused; one topic per PR.
- Add or update tests for anything behavioural. `pytest tests/` and
  `pytest backend/tests/` must pass.
- Don't add a dependency under a copyleft or source-available licence without
  raising it first — see `THIRD-PARTY-NOTICES.md`.
- New source files should carry the standard header (see below).

## Legal terms for contributions

By submitting a contribution (a pull request, patch, or any other change) you
agree to **all** of the following.

### 1. Licence of your contribution (inbound = outbound, plus a commercial grant)

You license your contribution to Beamstack and to all recipients of the software
under the **Beamstack Community License 1.0**, the same licence as the project.

**In addition**, you grant to Beamstack (as defined in `LICENSE` — currently
Abdellah Daoudi, trading as Beamstack, and any entity later incorporated to hold
the Beamstack projects) a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable licence to use, reproduce, modify, prepare derivative works of,
publicly display, sublicense, and distribute your contribution, **and to
re-license your contribution under other terms, including proprietary or
commercial terms**.

You keep the copyright in your contribution. This extra grant exists for one
reason: `LICENSE` reserves Beamstack's right to sell commercial licences and to
waive the attribution requirement, and that is only workable if every
contribution can be included in those commercial licences without tracking down
each contributor.

### 2. Patents

You grant Beamstack and downstream recipients a licence to any patent claims you
own or control that are necessarily infringed by your contribution, on the same
terms as Section 2.1(b) of `LICENSE`.

### 3. You have the right to contribute — Developer Certificate of Origin

Every commit must be signed off (`git commit -s`), adding a line:

```
Signed-off-by: Your Name <your.email@example.com>
```

which certifies the Developer Certificate of Origin, version 1.1:

> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I have the
>     right to submit it under the open source license indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best of my
>     knowledge, is covered under an appropriate open source license and I have
>     the right under that license to submit that work with modifications,
>     whether created in whole or in part by me, under the same open source
>     license (unless I am permitted to submit under a different license), as
>     indicated in the file; or
>
> (c) The contribution was provided directly to me by some other person who
>     certified (a), (b) or (c) and I have not modified it.
>
> (d) I understand and agree that this project and the contribution are public
>     and that a record of the contribution (including all personal information
>     I submit with it, including my sign-off) is maintained indefinitely and
>     may be redistributed consistent with this project or the open source
>     license(s) involved.

If you contribute on behalf of your employer, make sure you have their
permission, or that the work is outside the scope of your employment.

### 4. No trademark rights

These terms grant you no right to use the "Beamstack" name or logo beyond the
attribution use that `LICENSE` Section 3.7 requires of everyone.

## Standard source-file header

Python:

```python
# SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com>
# SPDX-License-Identifier: LicenseRef-BCL-1.0
```

TypeScript / JavaScript:

```ts
// SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com>
// SPDX-License-Identifier: LicenseRef-BCL-1.0
```

## Questions

Licensing or commercial questions: **askdaoudi@gmail.com**.
