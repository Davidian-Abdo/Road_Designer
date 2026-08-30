# Third-party notices

Road-Designer (Beamstack Community License 1.1) is built on the third-party
packages listed below. Each is distributed by its own authors under its own
license; none is owned by Beamstack. All are **permissive** licenses
(MIT, BSD-3-Clause, Apache-2.0, or the BSD-style Matplotlib License), which is
what allows the combined work to be offered under the Beamstack Community
License. The full license text of each package ships inside that package's
distribution (e.g. its `*.dist-info/` or `node_modules/<pkg>/LICENSE`).

This file is one of the **Notice Files** referenced by Section 1.18 of the
`LICENSE`. Keep it, `LICENSE`, and `NOTICE` together in every redistribution.

Versions below are the lower bounds pinned in the project's requirement files;
the license of each project applies to whatever compatible version is installed.

## Engine + CLI + Streamlit frontend (`requirements.txt`)

| Package | Pin | License | SPDX |
|---|---|---|---|
| streamlit | `>=1.39,<2.0` | Apache License 2.0 | `Apache-2.0` |
| ezdxf | `>=1.3.4,<2.0` | MIT License | `MIT` |
| numpy | `>=1.26,<3.0` | BSD 3-Clause | `BSD-3-Clause` |
| scipy | `>=1.13,<2.0` | BSD 3-Clause | `BSD-3-Clause` |
| pandas | `>=2.2,<3.0` | BSD 3-Clause | `BSD-3-Clause` |
| openpyxl | `>=3.1,<4.0` | MIT License | `MIT` |
| matplotlib | `>=3.9,<4.0` | Matplotlib License (BSD-style, PSF-derived) | `matplotlib` / `PSF-2.0` |
| pytest | `>=8.0` | MIT License (test only) | `MIT` |

## FastAPI backend (`backend/requirements.txt`) — adds

| Package | Pin | License | SPDX |
|---|---|---|---|
| fastapi | `>=0.115,<1.0` | MIT License | `MIT` |
| uvicorn | `>=0.30,<1.0` | BSD 3-Clause | `BSD-3-Clause` |
| python-multipart | `>=0.0.9,<1.0` | Apache License 2.0 | `Apache-2.0` |
| pydantic | `>=2.7,<3.0` | MIT License | `MIT` |
| httpx | `>=0.27,<1.0` | BSD 3-Clause (test only) | `BSD-3-Clause` |

(uvicorn's `[standard]` extra pulls in, among others, `uvloop` — MIT/Apache-2.0,
`httptools` — MIT, `websockets` — BSD-3-Clause, `watchfiles` — MIT,
`python-dotenv` — BSD-3-Clause. All permissive.)

## React frontend (`frontends/react/package.json`)

| Package | Range | License | SPDX |
|---|---|---|---|
| react | `^18.3.1` | MIT License | `MIT` |
| react-dom | `^18.3.1` | MIT License | `MIT` |
| clsx | `^2.1.1` | MIT License | `MIT` |
| tailwind-merge | `^2.5.4` | MIT License | `MIT` |
| vite | `^5.4.10` | MIT License | `MIT` |
| @vitejs/plugin-react | `^4.3.3` | MIT License | `MIT` |
| tailwindcss | `^3.4.14` | MIT License | `MIT` |
| postcss | `^8.4.47` | MIT License | `MIT` |
| autoprefixer | `^10.4.20` | MIT License | `MIT` |
| typescript | `^5.6.3` | Apache License 2.0 | `Apache-2.0` |
| @types/node, @types/react, @types/react-dom | `^22 / ^18` | MIT License (DefinitelyTyped) | `MIT` |

## Notes on compatibility

- **No copyleft dependency** (no GPL / LGPL / AGPL / MPL) is present in any of
  the three surfaces. Relicensing the larger work under the Beamstack Community
  License is therefore unobstructed.
- **Apache-2.0 components** (streamlit, python-multipart, typescript) require
  their `NOTICE` (if any) and license to be preserved on redistribution — this
  file plus the packages' bundled license texts satisfy that.
- The **Matplotlib License** is a BSD-style permissive license; matplotlib must
  keep its copyright notice, which travels inside the installed package.
- If you add a dependency under a copyleft or source-available license, record
  it here and check it against Section 3 of the `LICENSE` before shipping.
