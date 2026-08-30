# Road Designer — React frontend

A Vite + React + TypeScript + Tailwind single-page app for Road-Designer V 1.0. This is a
**separate product** from `frontends/streamlit/` — same `road_designer` engine underneath,
different UI, different deployment target. It talks to the FastAPI service in `backend/`
over HTTP; it has no server-side code of its own.

See the repo root `CLAUDE.md` § 15 ("Deployment architecture — three surfaces") for the full
picture of how this fits with the Streamlit app and the FastAPI backend.

## Local development

```bash
cd frontends/react
cp .env.example .env.local     # edit VITE_API_BASE_URL if your backend isn't on :8000
npm install
npm run dev
```

This expects a FastAPI backend already running (see `backend/README.md` — usually
`uvicorn backend.app.main:app --reload` from the repo root, on `http://localhost:8000`).

## Building

```bash
npm run build      # tsc -b && vite build → dist/
npm run preview    # serve the production build locally, for a final check before deploy
```

## Deploying to Cloudflare Pages

1. **Build command**: `npm run build`
2. **Build output directory**: `dist`
3. **Root directory** (if deploying from this monorepo via the dashboard's Git integration):
   `frontends/react`
4. **Environment variable** (Settings → Environment variables, both Production and Preview):
   `VITE_API_BASE_URL` = the deployed FastAPI backend's URL, no trailing slash (e.g. a Google
   Cloud Run URL `https://road-designer-api-xxxxxxxxxx-ew.a.run.app`, or a Hugging Face Space
   URL `https://<user>-<space>.hf.space`). See `DEPLOYMENT.md` Part A.

   **This is a Vite *build-time* variable** — it gets baked into the JS bundle when
   `npm run build` runs. Setting it in `wrangler.toml`'s `[vars]` section does **not** affect
   the build; it must be set in the Pages dashboard (or exported in your shell before a
   `wrangler pages deploy` from the CLI).

`wrangler.toml` is included for the CLI-deploy path (`wrangler pages deploy dist`) as an
alternative to the dashboard's Git-integration path — most users will want the dashboard path
and can otherwise ignore this file.

## UI primitives — no shadcn CLI dependency

`src/components/ui/` (Button, Field, Select, Card, Section) are hand-written in a
shadcn-like style rather than generated via the shadcn CLI, so the app has zero extra
network dependency at build time. If you'd rather use shadcn's actual generated components
later, running `npx shadcn@latest add <component>` and swapping the import paths should be a
drop-in replacement — the hand-written primitives use the same prop shapes and Tailwind
conventions shadcn's generator produces.

## Project structure

```
src/
├── lib/
│   ├── types.ts       ← TS mirror of backend/app/schemas.py's DesignConfigIn (form prefill only —
│   │                     the backend is the source of truth; it re-validates everything server-side)
│   └── api.ts          ← typed fetch client (createDesign, getDesignStatus, getPreview, fileDownloadUrl)
├── hooks/
│   └── useDesignJob.ts ← 2s polling loop against GET /designs/{id}, stops on done/error
├── components/
│   ├── DesignForm.tsx       ← full config form (mirrors the Streamlit sidebar's sections)
│   ├── JobStatusPanel.tsx   ← status badge + 4 download buttons + REFT warnings
│   ├── PreviewPanel.tsx     ← tabbed profil-en-long / Bruckner / tracé-en-plan preview
│   ├── chart/
│   │   └── InteractiveLineChart.tsx  ← from-scratch SVG chart (wheel-zoom, drag-pan, hover) — no
│   │                                    charting library dependency
│   ├── Header.tsx, MissionBand.tsx, ContactFooter.tsx  ← BeamStack-toned chrome
│   └── ui/                  ← hand-written Button/Field/Select/Card/Section primitives
└── App.tsx
```

## Known gaps

- Not yet verified in an actual browser in a sandboxed dev session — `npm install`, `tsc -b`,
  and `npm run build` all pass clean, and the dev server serves the expected HTML shell, but no
  one has looked at the rendered UI yet. Run `npm run dev` locally and open
  `http://localhost:5173` (or whatever port Vite picks) to do that check before a first deploy.
