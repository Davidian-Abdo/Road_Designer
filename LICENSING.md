# Licensing — plain-language guide

> This page explains the licence in everyday terms. It is **not** part of the
> licence and it is **not** legal advice. The [`LICENSE`](LICENSE) file is what
> actually governs; where this page and `LICENSE` differ, `LICENSE` wins.

## What licence is this?

**Beamstack Community License 1.1** (`LicenseRef-BCL-1.1`). It is a
**source-available** licence — the code is public and you may read, use, and
modify it, but it is **not** "open source" in the [OSI](https://opensource.org/osd)
sense, because it (a) forbids selling the software and (b) requires visible
"Powered by Beamstack" credit.

Technically it is a **renamed, modified version of the Mozilla Public License
2.0**, which the MPL explicitly allows (its Section 10.3). Conditions were added
and the MPL's GPL-compatibility machinery was removed. Everything else behaves
like the MPL: **file-level copyleft** — if you change one of the project's files
and share it, that file stays under this licence, but files you add yourself can
be under terms of your choice.

### Two modes

BCL-1.1 has an optional third condition, **Section 3.8 "Network Use"** — an
AGPL-style rule: if you deploy a *modified* version so others use it over a
network (including in a browser, or via an API/agent), you must offer them your
source. It is **off by default** and only switches on when a project attaches
the **Exhibit C** notice.

| | Base BCL-1.1 (`LicenseRef-BCL-1.1`) | With Exhibit C (`LicenseRef-BCL-1.1-Network`) |
|---|---|---|
| Modified files, on distribution | must be published | must be published |
| Modified version hosted as a network service | owes only attribution | must also offer users the source |
| Used by | **Road-Designer** | e.g. Bunyan |

**Road-Designer uses the base mode** — no Exhibit C. Everything below describes
that mode; the network rule does not apply to Road-Designer.

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
| Host a *modified* version of Road-Designer as a free service | **Yes** — you owe only attribution (Road-Designer has no Exhibit C). For a project that *does* carry Exhibit C, you'd also have to offer users your source. |
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
4. Set your package metadata's licence to **`LicenseRef-BCL-1.1`**.
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

By contributing you agree your contribution is licensed under BCL-1.1 **and**
you grant Beamstack the right to also license it commercially — this is what
keeps the paid-licence option workable. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Where this fits — the Beamstack License Framework

Road-Designer is on the **Community tier** of the
[Beamstack License Framework (BLF)](https://github.com/TheBeamstack/beamstack-licensing),
which assigns every Beamstack project one of five tiers — **Open** (real
open source, AGPL/MPL/Apache; e.g. Bunyan), **Community** (BCL-1.1; Road-Designer),
**Community-Network** (BCL-1.1 + Exhibit C), **Commercial**, and **Dedicated**
(a client-hosted private instance). The framework repo holds the canonical
licence texts, the Beamstack CLA, templates, and the decision log.

## Using BCL-1.1 for another Beamstack project

The `beamstack-licensing` repo holds the canonical BCL text
([`licenses/BCL-1.1.txt`](https://github.com/TheBeamstack/beamstack-licensing/blob/main/licenses/BCL-1.1.txt));
`scripts/apply-tier.sh` scaffolds it into a project. To adopt it manually:

1. Copy `LICENSE`, `NOTICE`, `THIRD-PARTY-NOTICES` into the project. Adjust
   `NOTICE`'s product name and the third-party list.
2. Add the SPDX header to source files:
   `SPDX-License-Identifier: LicenseRef-BCL-1.1` (or `-Network`, see step 3).
3. **Decide on network copyleft.** If the project is a hosted service or a
   client-side web app and its moat is the running deployment (not the shipped
   code), attach the **Exhibit C** notice from `LICENSE` — paste it into the
   project's `NOTICE` (and, ideally, the top of `LICENSE`), and use
   `LicenseRef-BCL-1.1-Network` in metadata. If the project is a tool, library,
   or CLI where copyleft-on-distribution is enough, do **not** attach Exhibit C.
4. Put a `CONTRIBUTING.md` (or CLA) in place **before the first outside PR** if
   you want to keep the commercial-relicensing option — inbound contributions
   must be licensed to allow it.
5. The copyright holder and steward stay **Beamstack** — do not rename the
   licence per project.

**What Exhibit C's Section 3.8 does and does not reach.** It obligates you, when
you deploy a *modified* version so others use it over a network, to offer those
users the **Corresponding Source** of your version — the modified Covered
Software plus the scripts/config/build definitions needed to build and run it.
It is triggered only by modification (an unmodified deployment satisfies it by
pointing at the public source). It expressly does **not** sweep in separately
authored plugins, extension modules, data-defined definitions, format codecs, or
user scripts that talk to the software through a documented extension interface —
MPL's per-file boundary is preserved, so a plugin/content ecosystem is not
chilled. "Over a network" is defined to include in-browser / client-side
execution and access by an API or an automated agent, closing the gap a literal
AGPL §13 leaves for single-page apps.

## A note on enforceability

Custom licences carry more uncertainty than off-the-shelf ones. The core (a
modified MPL) is well-trodden; the `No Sale` wording follows the widely-used
"Commons Clause"; the attribution wording follows common "badgeware" practice;
Section 3.8 follows AGPL §13 with SPA-specific clarifications. Even so, before
you rely on this licence in a dispute, have a lawyer in the relevant
jurisdiction review it — Section 3.8's "client-side execution is network use"
language in particular is deliberately ahead of settled case law.
