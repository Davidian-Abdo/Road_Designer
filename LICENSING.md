# Licensing — plain-language guide

> This page explains the licence in everyday terms. It is **not** part of the
> licence and it is **not** legal advice. The [`LICENSE`](LICENSE) file is what
> actually governs; where this page and `LICENSE` differ, `LICENSE` wins.

## What licence is this?

**Beamstack Community License 1.0** (`LicenseRef-BCL-1.0`). It is a
**source-available** licence — the code is public and you may read, use, and
modify it, but it is **not** "open source" in the [OSI](https://opensource.org/osd)
sense, because it (a) forbids selling the software and (b) requires visible
"Powered by Beamstack" credit.

Technically it is a **renamed, modified version of the Mozilla Public License
2.0**, which the MPL explicitly allows (its Section 10.3). Two conditions were
added and the MPL's GPL-compatibility machinery was removed. Everything else
behaves like the MPL: **file-level copyleft** — if you change one of the
project's files and share it, that file stays under this licence, but files you
add yourself can be under terms of your choice.

## Why this licence

| Goal | How the licence delivers it |
|---|---|
| Engineers can freely use, learn from, and build on the code | Full use, modify, and redistribute rights (Section 2.1) |
| It can't be taken and sold as someone else's product | `No Sale` condition (Section 3.6) |
| The Beamstack brand travels with anything built on it | `Attribution` condition (Section 3.7) |
| Improvements come back to the community | File-level copyleft, inherited from MPL 2.0 (Section 3.1) |
| Beamstack can still offer paid commercial terms later | Reserved-rights note + Section 3.7(f) waiver; contributions are licensed to allow it (see `CONTRIBUTING.md`) |

## Can I…?

| Scenario | Allowed? |
|---|---|
| Use it inside my company / BET | **Yes** |
| Use it to produce drawings, studies, or models I bill to a client | **Yes** — the deliverable is what's sold, not the software |
| Give a copy to a colleague or publish a free fork | **Yes**, if you keep the Notice Files and the attribution |
| Modify the engine | **Yes** — publish your changed files under this same licence |
| Build a free web app on it | **Yes** — show "Powered by Beamstack" on an About/footer/splash screen, linked to beam-stack.com |
| Sell a product or subscription whose value is mostly this software | **No** — needs a commercial licence |
| Charge people for access to a hosted instance of it | **No** — needs a commercial licence |
| Offer paid support/hosting of *the software itself* as my business | **No** — needs a commercial licence |
| Remove the "Powered by Beamstack" credit | **No** — needs a written waiver |
| Keep my modified fork closed-source | **No** for changes to the project's own files; your *added* files can be closed |
| Re-license the code as MIT / MPL / GPL / AGPL | **No** |
| Call my product "Beamstack Road Tools" or use the logo as my brand | **No** — trademark is reserved (Section 3.7(e)) |

## How to comply — checklist

1. Keep `LICENSE`, `NOTICE`, and `THIRD-PARTY-NOTICES.md` in every copy you
   distribute; keep the source-file headers.
2. Has a UI? Put **"Powered by Beamstack"** (text or logo) on a credits-type
   screen or a footer or splash, linked to <https://beam-stack.com>. Not needed
   on every screen. No UI (library/CLI)? Skip this step.
3. Say **"based on Beamstack software"** with a link in your README / docs /
   about page.
4. Set your package metadata's licence to **`LicenseRef-BCL-1.0`**.
5. Don't sell it, don't charge for access, don't strip the credit, don't use the
   Beamstack name/logo as your own.

## Commercial licence

Anything in the "No" rows above is available under a paid commercial licence,
and Beamstack can also grant a written waiver of the attribution requirement.

**Contact:** askdaoudi@gmail.com

## Ownership

Copyright © 2026 **Beamstack**. "Beamstack" is a trademark registered with
OMPIC (Morocco). Beamstack is not yet an incorporated company; pending
incorporation the rights holder of record is **Abdellah Daoudi** (sole
proprietor). The licence is written so the brand "Beamstack" is what appears
everywhere, with the individual named only where a real person is legally
required.

## For contributors

By contributing you agree your contribution is licensed under BCL-1.0 **and**
you grant Beamstack the right to also license it commercially — this is what
keeps the paid-licence option workable. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## A note on enforceability

Custom licences carry more uncertainty than off-the-shelf ones. The core (a
modified MPL) is well-trodden; the `No Sale` wording follows the widely-used
"Commons Clause"; the attribution wording follows common "badgeware" practice.
Even so, before you rely on this licence in a dispute, have a lawyer in the
relevant jurisdiction review it.
