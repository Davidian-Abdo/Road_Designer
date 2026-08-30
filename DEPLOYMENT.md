# Deployment Guide

A step-by-step, no-assumed-experience guide to getting all three Road Designer surfaces live:
the FastAPI backend on Hugging Face Spaces, the React frontend on Cloudflare Pages, and the
existing Streamlit app back on its feet at its new file path. Written for someone doing this
for the first time — every click is spelled out.

If you get stuck partway through, that's normal; jump to [Troubleshooting](#troubleshooting)
near the end, or just ask for help with whatever screen you're stuck on.

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [Before you start](#2-before-you-start)
3. [Part A — Deploy the backend to Hugging Face Spaces](#3-part-a--deploy-the-backend-to-hugging-face-spaces)
4. [Part B — Deploy the frontend to Cloudflare Pages](#4-part-b--deploy-the-frontend-to-cloudflare-pages)
5. [Part C — Close the loop: lock down CORS](#5-part-c--close-the-loop-lock-down-cors)
6. [Part D — Fix the Streamlit Cloud app](#6-part-d--fix-the-streamlit-cloud-app)
7. [Part E — Keep the backend from falling asleep](#7-part-e--keep-the-backend-from-falling-asleep)
8. [Part F — Final end-to-end check](#8-part-f--final-end-to-end-check)
9. [Updating later](#9-updating-later)
10. [Troubleshooting](#10-troubleshooting)
11. [What this costs](#11-what-this-costs)

---

## 1. The big picture

You're deploying **three separate things**, in this order:

```
  Part A                Part B                  Part D
┌───────────┐         ┌───────────┐         ┌─────────────┐
│  Backend  │ ◄────── │ Frontend  │         │  Streamlit  │
│(FastAPI,  │  calls   │  (React,  │         │  (unchanged,│
│Hugging    │  its API │ Cloudflare│         │ own account,│
│Face Space)│         │  Pages)   │         │  own URL)   │
└───────────┘         └───────────┘         └─────────────┘
```

- **Backend first** — it works standalone (you can test it in a browser before the frontend
  exists), and the frontend needs its URL to be configured.
- **Frontend second** — needs the backend's URL as a build-time setting.
- **Part C loops back** to the backend once, to lock its CORS setting down to the frontend's
  real URL (until then it's wide open, which is fine for getting things working first).
- **Streamlit is independent** of the other two — it's the existing app, just needs its
  Streamlit Cloud dashboard setting updated to match where its file moved to in this repo.

Each of these can be redone independently later — none of them depend on each other at
runtime, only the CORS setting and the frontend's build-time API URL link them together.

**One licence thing before you start.** Road Designer is published under the Beamstack
Community License 1.0 (`LICENSE` at the repo root; plain-language summary in `LICENSING.md`).
Deploying it publicly is fine and expected, but the licence asks two small things of every
public deployment, yours included:

1. The `LICENSE`, `NOTICE`, and `THIRD-PARTY-NOTICES.md` files must travel with the code you
   push to Hugging Face — the assembly step in Part A now copies them, and `backend/Dockerfile`
   now `COPY`s them into the image.
2. The user-facing surfaces — the React SPA (Part B) and the Streamlit app (Part D) — must show
   a "Powered by Beamstack" credit linked to <https://beam-stack.com>, somewhere a user would
   look for credits (a footer, an About panel, a splash screen). It need not be on every screen.
   The FastAPI backend has no UI, so it only needs point 1.

---

## 2. Before you start

You'll need three accounts, all free:

- [ ] A **GitHub** account, with this repository pushed to it (if it's only local right now,
      say so and that needs sorting out first — everything below assumes the code is already
      on GitHub, since both Hugging Face and Cloudflare pull from there).
- [ ] A **Hugging Face** account — sign up at [huggingface.co](https://huggingface.co/join).
- [ ] A **Cloudflare** account — sign up at [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up).

You'll also want **Git installed locally** (you already have it, since this is a git repo) and
a terminal to run a handful of copy-paste commands.

---

## 3. Part A — Deploy the backend to Hugging Face Spaces

### A.1 — Create the Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space) (log in first).
2. Fill in the form:
   - **Owner**: your username.
   - **Space name**: something like `road-designer-api`.
   - **License**: choose **Other**. Road Designer is under the Beamstack Community
     License 1.0, which is not in Hugging Face's licence list; you'll declare it
     properly in the Space README in step A.4b. (The dropdown doesn't affect how
     the Space runs, but it shouldn't misreport the licence as MIT/Apache/etc.)
   - **Select the Space SDK**: choose **Docker**.
   - **Docker template**: choose the **Blank** template (we'll replace its placeholder files).
   - **Space hardware**: the free tier (usually labeled **CPU basic** and marked **Free**).
   - **Visibility**: **Public** is simplest and free either way; **Private** also works if you'd
     rather the code not be visible on huggingface.co.
3. Click **Create Space**.

You now have an empty Space at `https://huggingface.co/spaces/<your-username>/<space-name>`,
with an auto-generated `README.md` (it already contains the metadata Hugging Face needs —
don't touch it) and a placeholder `Dockerfile`.

### A.2 — Get a write access token

Hugging Face Spaces are just git repositories — you push code to them like any other git
remote. To push over HTTPS you need a token (not your account password):

1. Click your profile picture (top-right) → **Settings** → **Access Tokens**.
2. Click **New token** (or **Create new token**).
3. Name it something like `road-designer-deploy`, set **Type** to **Write**.
4. Click **Create**, then **copy the token somewhere safe** — it's shown only once.

### A.3 — Why this needs a small assembly step

Hugging Face's Docker SDK requires the `Dockerfile` to sit at the **root** of the Space's own
git repository. Ours lives at `backend/Dockerfile` in this project, and it expects
`road_designer/`, `samples/`, and `backend/` to be *siblings* (it does `COPY road_designer ...`,
`COPY samples ...`, `COPY backend ...` from the build context root — see `backend/Dockerfile`
and `CLAUDE.md` § 15 if you want the full reasoning).

So instead of pushing this whole monorepo as-is, you'll push a **separate clone of the Space**,
containing just those three folders plus one copy of the Dockerfile at its root. This is a
one-time setup; updating later (§ 9) is the same handful of commands run again.

### A.4 — Assemble and push

Run this from a terminal, **outside** your `Road_designe` project folder (anywhere is fine —
this creates a new folder next to it):

```bash
git clone https://huggingface.co/spaces/<your-username>/<space-name> road-designer-space
cd road-designer-space

# adjust this path to wherever your Road_designe project actually lives
PROJECT=/path/to/Road_designe

cp -r "$PROJECT/road_designer" ./road_designer
cp -r "$PROJECT/samples" ./samples
cp -r "$PROJECT/backend" ./backend
cp -r "$PROJECT/brand" ./brand
cp "$PROJECT/LICENSE" "$PROJECT/NOTICE" "$PROJECT/THIRD-PARTY-NOTICES.md" ./  # Notice Files — required by LICENSE § 3.4
cp ./backend/Dockerfile ./Dockerfile   # Hugging Face needs it at the repo root
rm ./backend/Dockerfile                 # avoid keeping two copies lying around

git add -A
git commit -m "Deploy Road Designer API"
git push
```

When `git push` asks for credentials:
- **Username**: your Hugging Face username.
- **Password**: paste the **access token** from A.2 (not your account password).

### A.4b — Declare the licence on the Space

The Space came with an auto-generated `README.md` whose top block (between two `---` lines) is
Hugging Face front-matter. Open it and add these three lines inside that block (leave everything
else as-is):

```yaml
license: other
license_name: beamstack-community-license-1.0
license_link: LICENSE
```

`license_link: LICENSE` resolves to the `LICENSE` file you just copied into the Space repo, so
the Space page links to the real text. Below the `---` block you can also add a body line:

```
Powered by Beamstack — source and licence: https://github.com/<your-username>/<repo>
```

Then commit and push:

```bash
git add README.md && git commit -m "Declare licence" && git push
```

The backend is an API with no user interface, so the "Powered by Beamstack" *badge* requirement
(`LICENSE` § 3.7(b)) does not apply to it — shipping the `LICENSE` / `NOTICE` /
`THIRD-PARTY-NOTICES.md` files (done in A.4) plus this README line is what it needs. The badge
requirement *does* apply to the React SPA and the Streamlit app — see B.5 and Part D.

### A.5 — Watch it build

Go back to the Space's page in your browser. It'll show a **Building** status with a live log
— this takes a couple of minutes (installing numpy/scipy/matplotlib/etc. isn't instant). If it
fails, the **Logs** tab tells you why (see [Troubleshooting](#10-troubleshooting) if it's not
obvious). Once it says **Running**, you're live.

### A.6 — Find your URL and test it

Your backend's URL follows the pattern:

```
https://<your-username>-<space-name>.hf.space
```

(dashes replace spaces/underscores — the exact URL is also shown at the top of the Space page
once it's running). Open these in a browser to confirm it's alive:

- `https://<your-space-url>/health` → should show `{"status":"ok"}`
- `https://<your-space-url>/docs` → interactive API documentation (FastAPI's built-in Swagger UI)

**Write this URL down** — you need it in the next part.

---

## 4. Part B — Deploy the frontend to Cloudflare Pages

### B.1 — Create the Pages project

1. Log in to the [Cloudflare dashboard](https://dash.cloudflare.com).
2. In the left sidebar, click **Workers & Pages**.
3. Click **Create** → the **Pages** tab → **Connect to Git**.
4. Authorize Cloudflare to access your GitHub account if prompted, then pick this repository.

### B.2 — Configure the build

This is the step that matters most — Cloudflare needs to know your React app lives in a
subfolder of this repo, not at its root:

| Field | Value |
|---|---|
| Project name | anything, e.g. `road-designer` (becomes part of your `*.pages.dev` URL) |
| Production branch | `main` |
| Framework preset | **Vite** (or **None** — either works, since the build command is explicit) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| **Root directory** | **`frontends/react`** ← this is the monorepo setting, don't skip it |

### B.3 — Set the backend URL (before the first real deploy, or redeploy after)

Cloudflare will try to build immediately after you save the above — let it, but the app won't
be able to reach the backend yet because the API URL isn't set. Fix that:

1. Go to the Pages project → **Settings** → **Environment variables**.
2. Add a variable for **both Production and Preview**:
   - **Name**: `VITE_API_BASE_URL`
   - **Value**: your Hugging Face Space URL from A.6, e.g. `https://you-road-designer-api.hf.space`
     (no trailing slash).
3. Save, then go to the **Deployments** tab and **Retry deployment** (or just push any commit —
   either triggers a fresh build).

This is important: **`VITE_API_BASE_URL` is baked into the JavaScript at build time**, not read
at runtime. Setting it *after* a build has already happened does nothing until the next build.

### B.4 — Get your URL

Once the deploy finishes, Cloudflare gives you a URL like `https://road-designer.pages.dev`.
Open it — you should see the app's UI, though submitting a design will fail with a CORS error
until Part C is done (that's expected, not a bug).

### B.5 — Check the "Powered by Beamstack" credit is visible

`LICENSE` § 3.7 requires any deployed UI built on Road Designer to show "Powered by Beamstack"
(the text, or the logo in `brand/`), linked to <https://beam-stack.com>, somewhere a user would
look for credits — the app footer, an About panel, or a splash screen. It need not be on every
screen. Confirm it renders on your deployed Pages URL; if it's missing, add it to the SPA before
treating the deploy as done. This applies to any fork or third-party deployment too, not just
yours.

---

## 5. Part C — Close the loop: lock down CORS

Right now the backend accepts requests from any origin (`ALLOWED_ORIGIN` defaults to `"*"`) —
fine for getting things working, not something to leave in place. Point it at your real
Cloudflare Pages URL from B.4:

1. Go back to your Hugging Face Space → **Settings** tab.
2. Find **Variables and secrets** → **New variable** (not "secret" — this isn't sensitive).
3. **Name**: `ALLOWED_ORIGIN`
   **Value**: your Pages URL from B.4, e.g. `https://road-designer.pages.dev` (no trailing
   slash; comma-separate multiple origins if you ever add a custom domain later).
4. Save — the Space restarts automatically to pick it up (takes under a minute).

Now the React app at your Pages URL should be able to submit designs successfully.

---

## 6. Part D — Fix the Streamlit Cloud app

The Streamlit app's code moved from `app.py` to `frontends/streamlit/app.py` in this repo's
restructure. If you already have this app deployed on Streamlit Community Cloud, its dashboard
still points at the old path and needs updating:

1. Go to [share.streamlit.io](https://share.streamlit.io) and log in.
2. Find your app in the list, click the **⋮** menu next to it → **Settings**.
3. Under **General**, change **Main file path** to:
   ```
   frontends/streamlit/app.py
   ```
4. Save. The app reboots automatically with the new path.

If you haven't deployed the Streamlit app yet, just point a new Streamlit Cloud app at this
path from the start when you create it — same field, same value.

As with the React SPA (B.5), the Streamlit app must show the "Powered by Beamstack" credit
(`LICENSE` § 3.7) — in the sidebar, the page footer, or an "À propos" expander — linked to
<https://beam-stack.com>. Confirm it's there after the reboot.

---

## 7. Part E — Keep the backend from falling asleep

Hugging Face's free-tier Spaces can go to sleep after a period of inactivity, causing a slow
"cold start" on the next request. This repo already ships a GitHub Actions workflow
(`.github/workflows/keep-alive-hf-space.yml`) that pings the backend's `/health` endpoint every
~12 minutes to keep it warm — it just needs one secret set:

1. In this repo on GitHub, go to **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
3. **Name**: `HF_SPACE_HEALTH_URL`
   **Value**: `https://<your-space-url>/health` (from A.6).
4. Save.

The workflow will start running on its own schedule — no further action needed. If the secret
isn't set, the workflow just logs a message and does nothing (it won't fail your repo's checks).

---

## 8. Part F — Final end-to-end check

With all of the above done, do one full pass as a real user would:

1. Open your Cloudflare Pages URL.
2. Fill in the form — an axe file, a terrain CSV (or the synthetic-terrain option), a REFT
   category, and a **company name** (required — the submit button stays disabled without it,
   same rule as the Streamlit app).
3. Submit, watch the job status go `queued → running → done`.
4. Download all 4 files (DXF, XLSX, both PDFs) and confirm they open correctly.
5. Check the preview tabs (profil en long / Bruckner / tracé en plan) render.
6. Separately, open your Streamlit Cloud URL and confirm it still works exactly as before.

If everything above works, you're fully deployed.

---

## 9. Updating later

Each surface updates independently:

- **Streamlit** and **Cloudflare Pages** both auto-redeploy on every push to `main` (that's
  what the Git integration in Part B and Streamlit Cloud's own GitHub integration do — no
  extra steps needed).
- **The Hugging Face Space does not auto-sync from GitHub** — it's a separate git remote (see
  § 3.4's reasoning). To push new backend/engine code to it, repeat the copy step from A.4 in
  your existing `road-designer-space` clone (no need to re-clone or redo A.1–A.3):

  ```bash
  cd road-designer-space
  PROJECT=/path/to/Road_designe

  rsync -a --delete "$PROJECT/road_designer/" ./road_designer/
  rsync -a --delete "$PROJECT/samples/" ./samples/
  rsync -a --delete "$PROJECT/backend/" ./backend/
  rsync -a --delete "$PROJECT/brand/" ./brand/
  cp "$PROJECT/LICENSE" "$PROJECT/NOTICE" "$PROJECT/THIRD-PARTY-NOTICES.md" ./
  rm -f ./backend/Dockerfile   # the copy at repo root (below) is the one that counts

  cp "$PROJECT/backend/Dockerfile" ./Dockerfile   # only needed if the Dockerfile itself changed

  git add -A
  git commit -m "Update Road Designer API"
  git push
  ```

  (`rsync --delete` makes sure files removed from the source also disappear from the Space —
  plain `cp -r` would leave stale files behind.)

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser console shows a CORS error when submitting a design | `ALLOWED_ORIGIN` on the HF Space doesn't match your Pages URL exactly | Recheck Part C — no trailing slash, exact scheme (`https://`), exact hostname |
| Every API call from the React app 404s or hits `localhost` | `VITE_API_BASE_URL` wasn't set before the last build, or has a typo | Recheck B.3, then trigger a fresh Cloudflare Pages deploy — this variable is baked in at build time, changing it alone does nothing |
| HF Space stuck on "Building" or fails outright | Check the **Logs** tab on the Space page for the actual error | Common culprits: forgot to delete the extra `backend/Dockerfile` copy (harmless but confusing), or a typo in a copied path |
| `git push` to the Space keeps asking for a password / rejects it | Used your Hugging Face account password instead of the access token | Use the **token** from A.2 as the password, username is still your HF username |
| First request after a while is slow | Free-tier Space cold start | Set up Part E; a very long idle stretch can still cause one cold request even with the keep-alive ping |
| Design job seems to hang on "running" for a long time | Normal for larger inputs — cross-section PDFs with 100+ pages take real time to render | Give it a minute or two before assuming something's wrong; check the Space's **Logs** tab for progress lines |
| Streamlit app shows a blank page or import error after the path change | Main file path wasn't actually saved, or a leftover cached deploy | Recheck Part D's exact path string, save again, and use "Reboot app" from the Streamlit Cloud dashboard if needed |

---

## 11. What this costs

All three surfaces run on free tiers as configured here:

- **Hugging Face Spaces** — CPU-basic hardware is free; no time limit, subject to the
  sleep/cold-start behavior noted in Part E.
- **Cloudflare Pages** — free tier includes unlimited requests and bandwidth for static sites;
  builds are rate-limited per month on the free plan, which is generous for a project updated a
  few times a week.
- **Streamlit Community Cloud** — free for public apps.

Nothing here requires a paid plan on any platform.
