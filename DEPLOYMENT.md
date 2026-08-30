<!-- SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com> -->
<!-- SPDX-License-Identifier: LicenseRef-BCL-1.1 -->

# Deployment Guide

A step-by-step, no-assumed-experience guide to getting all three Road Designer surfaces live:

| Surface | Host | Role |
|---|---|---|
| **Streamlit app** | Streamlit Community Cloud (free) | Always-on, standalone. The fallback that never needs a backend. |
| **FastAPI backend** | **Google Cloud Run** (free tier) | The API the React SPA calls. Portable — can be moved to Hugging Face later ([Part G](#12-part-g--switching-the-backend-to-hugging-face-spaces-later)). |
| **React SPA** | Cloudflare Pages (free), served at **`road-designer.beam-stack.com`** | The "product" frontend. Talks to the backend over HTTPS. |

Written for someone doing this for the first time — every click is spelled out. If you get
stuck partway through, jump to [Troubleshooting](#10-troubleshooting), or ask for help with
whatever screen you're on.

> **Why Cloud Run and not Hugging Face?** Hugging Face changed its pricing: Docker Spaces now
> need a **PRO** plan ($9/mo) for any CPU hardware. Cloud Run's always-free monthly allotment
> covers light-to-moderate use of this backend at $0. If sustained traffic ever pushes past
> that allotment, HF PRO's flat $9 becomes the cheaper option — and the Dockerfile is
> host-neutral, so switching is ~20 minutes (Part G).

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [Before you start](#2-before-you-start)
3. [Part A — Deploy the backend to Google Cloud Run](#3-part-a--deploy-the-backend-to-google-cloud-run)
4. [Part B — Deploy the frontend to Cloudflare Pages](#4-part-b--deploy-the-frontend-to-cloudflare-pages)
5. [Part C — Close the loop: lock down CORS](#5-part-c--close-the-loop-lock-down-cors)
6. [Part D — Fix the Streamlit Cloud app](#6-part-d--fix-the-streamlit-cloud-app)
7. [Part E — Cold starts](#7-part-e--cold-starts)
8. [Part F — Final end-to-end check](#8-part-f--final-end-to-end-check)
9. [Updating later](#9-updating-later)
10. [Troubleshooting](#10-troubleshooting)
11. [What this costs](#11-what-this-costs)
12. [Part G — Switching the backend to Hugging Face Spaces later](#12-part-g--switching-the-backend-to-hugging-face-spaces-later)

---

## 1. The big picture

```
  Part A                    Part B                  Part D
┌─────────────┐           ┌───────────┐         ┌─────────────┐
│  Backend    │ ◄──────── │ Frontend  │         │  Streamlit  │
│ (FastAPI,   │  calls    │  (React,  │         │ (standalone,│
│  Google     │  its API  │ Cloudflare│         │  own account│
│  Cloud Run) │           │  Pages)   │         │  and URL)   │
└─────────────┘           └───────────┘         └─────────────┘
```

- **Backend first** — it works standalone (test it in a browser before the frontend exists),
  and the frontend needs its URL as a build-time setting.
- **Frontend second** — needs the backend's URL.
- **Part C loops back** to the backend once, to lock its CORS setting down to the frontend's
  real URL (until then it's wide open, which is fine for getting things working).
- **Streamlit is independent** of the other two — it needs no backend and no other service. If
  the Cloud Run backend is ever down, the Streamlit app still does everything.

Each surface can be redeployed independently later — only the CORS setting and the frontend's
build-time API URL link the backend and the SPA together.

**One licence thing before you start.** Road Designer is published under the Beamstack
Community License 1.1 (`LICENSE` at the repo root; plain-language summary in `LICENSING.md`).
Deploying it publicly is fine and expected, but the licence asks two small things of every
public deployment, yours included:

1. The `LICENSE`, `NOTICE`, and `THIRD-PARTY-NOTICES.md` files must travel with the code. The
   repo-root `Dockerfile` already `COPY`s them into the backend image, so Cloud Run is covered
   automatically; keep them in any fork.
2. The user-facing surfaces — the React SPA (Part B) and the Streamlit app (Part D) — must show
   a "Powered by Beamstack" credit linked to <https://beam-stack.com>, somewhere a user would
   look for credits (a footer, an About panel, a splash screen). It need not be on every screen.
   The FastAPI backend has no UI, so it only needs point 1.

---

## 2. Before you start

Accounts (all have a free tier):

- [ ] **GitHub** — this repository must already be pushed to it (Cloudflare pulls from there).
- [ ] **Google Cloud** — sign up at [cloud.google.com](https://cloud.google.com). Cloud Run's
      free monthly allotment is real, but Google **requires a billing account with a card**
      before you can deploy anything. You will not be charged at the usage this backend
      generates; [Part E](#7-part-e--cold-starts) and [§ 11](#11-what-this-costs) explain the
      numbers, and you can set a $1 budget alert for peace of mind.
- [ ] **Cloudflare** — sign up at [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up).
- [ ] A **Hugging Face** account is **not** needed unless/until you do Part G.

Tools:

- **Git** (you have it — this is a git repo).
- **The `gcloud` CLI** — either install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
  locally, **or** use [Cloud Shell](https://shell.cloud.google.com) in your browser (gcloud is
  pre-installed there; you'll `git clone` your repo into it). The steps below work the same in
  both.

---

## 3. Part A — Deploy the backend to Google Cloud Run

### A.1 — Create a project and enable billing

1. Go to the [Google Cloud console](https://console.cloud.google.com).
2. Top bar → the project dropdown → **New Project**. Name it e.g. `road-designer`; note the
   **Project ID** it generates (like `road-designer-472912`) — you'll use it below.
3. Left menu → **Billing** → link a billing account (add a card if you don't have one). Cloud
   Run will refuse to deploy without this even for free-tier usage.
4. *(Optional but recommended)* **Billing → Budgets & alerts → Create budget**: amount `$1`,
   alert at 100 %. You'll get an email long before any real charge.

### A.2 — Point gcloud at your project and enable the APIs

In your terminal (or Cloud Shell):

```bash
gcloud auth login                       # opens a browser; skip in Cloud Shell (already authed)
gcloud config set project YOUR_PROJECT_ID

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

If you're using Cloud Shell, also get the code there:

```bash
git clone https://github.com/YOUR_GH_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

If you're local, just `cd` into your `Road_designe` folder.

### A.3 — Deploy

From the **repo root** (the folder containing `Dockerfile`, `road_designer/`, `backend/`):

```bash
gcloud run deploy road-designer-api \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --no-cpu-throttling \
  --max-instances 3 \
  --timeout 600
```

What each flag does:

| Flag | Why |
|---|---|
| `--source .` | Build the image from the repo-root `Dockerfile` (Cloud Build does it; the first run offers to create an Artifact Registry repo — answer **Y**). |
| `--region europe-west1` | Belgium — close to Morocco with full Cloud Run support. `europe-southwest1` (Madrid) is closer still; any region works, free-tier compute is region-independent. |
| `--allow-unauthenticated` | It's a public API. |
| `--memory 1Gi` | scipy + matplotlib rendering a 100-page cross-section PDF needs headroom. `512Mi` works for modest inputs and stretches the free tier further, at some OOM risk. |
| `--no-cpu-throttling` | **Important.** This backend finishes design jobs in a background thread *after* the HTTP response is sent. Without this flag Cloud Run throttles CPU to ~zero once the response is sent and the job stalls. |
| `--max-instances 3` | Caps a runaway bill from a bug or abuse. Plenty for this workload. |
| `--timeout 600` | 10-minute request ceiling. Requests are actually short (submit / poll / download), but big first builds can be slow. |

The build takes a few minutes (installing numpy/scipy/matplotlib). When it finishes, gcloud
prints a **Service URL** like `https://road-designer-api-abcdefghij-ew.a.run.app`.

### A.4 — Test it

Open in a browser:

- `https://YOUR-SERVICE-URL/health` → `{"status":"ok"}`
- `https://YOUR-SERVICE-URL/docs` → FastAPI's Swagger UI

**Write the Service URL down** — Part B needs it. You can also fetch it any time with:

```bash
gcloud run services describe road-designer-api --region europe-west1 --format 'value(status.url)'
```

### A.5 — About the free tier and cold starts

With `--no-cpu-throttling`, Cloud Run bills for the whole time an instance is alive — during
requests, plus ~15 minutes idle before it scales to zero. At 1 vCPU + 1 GiB, the free monthly
allotment (180,000 vCPU-seconds) is about **50 instance-hours per month**. Occasional use stays
well under that. See [§ 11](#11-what-this-costs).

The trade-off: after it scales to zero, the next request pays a **cold start** (~10–30 s for
this image). That's normal. Do **not** wire up the keep-alive workflow against Cloud Run (see
[Part E](#7-part-e--cold-starts)) — keeping it warm 24/7 would blow the free allotment.

---

## 4. Part B — Deploy the frontend to Cloudflare Pages

### B.1 — Create the Pages project

1. Log in to the [Cloudflare dashboard](https://dash.cloudflare.com).
2. Left sidebar → **Workers & Pages**.
3. **Create** → the **Pages** tab → **Connect to Git**.
4. Authorise Cloudflare for your GitHub account if prompted, then pick this repository.

### B.2 — Configure the build

Cloudflare needs to know the React app lives in a subfolder:

| Field | Value |
|---|---|
| Project name | anything, e.g. `road-designer` (becomes part of your `*.pages.dev` URL) |
| Production branch | `main` |
| Framework preset | **Vite** (or **None** — the build command is explicit either way) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| **Root directory** | **`frontends/react`** ← the monorepo setting, don't skip it |

### B.3 — Set the backend URL

Cloudflare builds immediately after you save — let it, but the app can't reach the backend
until you set the URL:

1. Pages project → **Settings** → **Environment variables**.
2. Add, for **both Production and Preview**:
   - **Name**: `VITE_API_BASE_URL`
   - **Value**: your Cloud Run Service URL from A.4, e.g.
     `https://road-designer-api-abcefghij-ew.a.run.app` (no trailing slash).
3. **Deployments** tab → **Retry deployment** (or push any commit) to rebuild.

**`VITE_API_BASE_URL` is baked into the JavaScript at build time**, not read at runtime.
Changing it does nothing until the next build.

### B.4 — Get your URL

The finished deploy gives you `https://road-designer.pages.dev`. Open it — the UI loads, but
submitting a design fails with a CORS error until Part C. That's expected.

### B.5 — Add the custom domain

You'll serve the SPA from **`road-designer.beam-stack.com`**, not the `*.pages.dev` URL.

1. Pages project → **Custom domains** → **Set up a domain** → enter `road-designer.beam-stack.com`
   → **Continue**.
2. If `beam-stack.com` is already managed in this same Cloudflare account, Cloudflare adds the
   DNS record for you — click **Activate domain**. If the domain's DNS lives elsewhere,
   Cloudflare shows a `CNAME` (`road-designer` → `your-project.pages.dev`) to add at your DNS
   provider.
3. Wait for the status to read **Active** (a minute or two; TLS certificate is automatic).

`road-designer.beam-stack.com` is now the SPA's canonical URL. The `*.pages.dev` URL keeps
working — decide in Part C whether to allow it in CORS too.

### B.6 — Check the "Powered by Beamstack" credit is visible

`LICENSE` § 3.7 requires any deployed UI built on Road Designer to show "Powered by Beamstack"
(the text, or the logo in `brand/`), linked to <https://beam-stack.com>, somewhere a user would
look for credits — a footer, an About panel, a splash screen. Not required on every screen.
Confirm it renders; if it's missing, add it to the SPA before treating the deploy as done. This
applies to any fork or third-party deployment too, not just yours.

---

## 5. Part C — Close the loop: lock down CORS

Right now the backend accepts any origin (`ALLOWED_ORIGIN` defaults to `"*"`). Point it at your
SPA's real origin — the custom domain from B.5:

```bash
gcloud run services update road-designer-api \
  --region europe-west1 \
  --update-env-vars ALLOWED_ORIGIN=https://road-designer.beam-stack.com
```

To also allow the `*.pages.dev` fallback (and Cloudflare preview builds), comma-separate the
origins — no spaces, no trailing slashes:

```
--update-env-vars ALLOWED_ORIGIN=https://road-designer.beam-stack.com,https://road-designer.pages.dev
```

Or in the console: **Cloud Run → road-designer-api → Edit & deploy new revision → Variables &
Secrets → add `ALLOWED_ORIGIN`**.

The new revision rolls out in under a minute. The React app at `road-designer.beam-stack.com`
can now submit designs.

---

## 6. Part D — Fix the Streamlit Cloud app

The Streamlit app's code moved from `app.py` to `frontends/streamlit/app.py` in the repo
restructure. If it's already deployed on Streamlit Community Cloud, its dashboard still points
at the old path:

1. Go to [share.streamlit.io](https://share.streamlit.io) and log in.
2. Find your app → the **⋮** menu → **Settings**.
3. Under **General**, set **Main file path** to:
   ```
   frontends/streamlit/app.py
   ```
4. Save. The app reboots with the new path.

If you haven't deployed the Streamlit app yet, point a new Streamlit Cloud app at that same
path from the start.

As with the React SPA (B.6), the Streamlit app must show the "Powered by Beamstack" credit
(`LICENSE` § 3.7) — in the sidebar, the page footer, or an "À propos" expander — linked to
<https://beam-stack.com>. Confirm it's there after the reboot.

---

## 7. Part E — Cold starts

Cloud Run scales the backend to zero when idle, so the first request after a quiet spell pays a
**cold start** of ~10–30 s (container start + Python imports). Subsequent requests are fast
until it goes idle again.

This repo ships `.github/workflows/keep-alive-backend.yml`, a cron ping that keeps a sleeping
backend warm. **Do not use it with this Cloud Run setup.** Because you deployed with
`--no-cpu-throttling`, a kept-warm instance is billed continuously and would blow the free
monthly allotment. Leave the secret unset; the workflow no-ops.

The keep-alive workflow *is* useful if you later move to Hugging Face (Part G), Render, or
Koyeb — hosts where an idle instance is free. Set the `BACKEND_HEALTH_URL` repo secret then.

If cold starts genuinely bother you before you have that much traffic, the options are: accept
them (simplest); pay Cloud Run for a warm `--min-instances 1` (leaves the free tier, ~$70/mo at
1 vCPU/1 GiB — not worth it); or move to HF PRO (Part G, flat $9/mo, and then keep-alive is
fine).

---

## 8. Part F — Final end-to-end check

1. Open `https://road-designer.beam-stack.com`.
2. Fill the form — an axe file, a terrain CSV (or the synthetic-terrain option), a REFT
   category, and a **company name** (required — submit stays disabled without it).
3. Submit; watch the job go `queued → running → done` (the first submit of the day eats a cold
   start — give it up to a minute).
4. Download all 4 files (DXF, XLSX, both PDFs); confirm they open.
5. Check the preview tabs (profil en long / Bruckner / tracé en plan) render.
6. Separately, open your Streamlit Cloud URL and confirm it still works.
7. Confirm "Powered by Beamstack" is visible on both the SPA and the Streamlit app.

---

## 9. Updating later

Each surface updates independently:

- **Streamlit** and **Cloudflare Pages** auto-redeploy on every push to `main` — nothing to do.
- **Cloud Run does not auto-deploy from GitHub.** After pushing backend or engine changes,
  re-run the deploy from the repo root:

  ```bash
  gcloud run deploy road-designer-api --source . --region europe-west1 \
    --allow-unauthenticated --memory 1Gi --cpu 1 --no-cpu-throttling \
    --max-instances 3 --timeout 600
  ```

  Environment variables (`ALLOWED_ORIGIN`) persist across deploys — you don't need to re-set
  them. Cloud Run keeps old container images in Artifact Registry; every few months, delete old
  ones (**Artifact Registry → cloud-run-source-deploy → delete old tags**) or the storage can
  creep past the 0.5 GB free limit (~$0.05/GB/month after that).

*(Want push-to-deploy? Cloud Run → your service → **Set up Continuous Deployment** wires it to
your GitHub repo via Cloud Build. Optional; the one command above is enough.)*

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `gcloud run deploy` fails: billing not enabled | No billing account linked | A.1 step 3 — link a billing account to the project |
| Deploy fails on `--allow-unauthenticated` (`Setting IAM policy failed`) | An org policy blocks public services (rare on personal projects) | Deploy without the flag, then **Cloud Run → service → Security → Allow unauthenticated**, or ask your org admin |
| Browser console shows a CORS error when submitting | `ALLOWED_ORIGIN` doesn't match the Pages URL exactly | Recheck Part C — no trailing slash, exact `https://`, exact hostname; confirm a new revision deployed |
| Every API call from the SPA hits `localhost` or 404s | `VITE_API_BASE_URL` wasn't set before the last build, or has a typo | Recheck B.3, then trigger a fresh Cloudflare Pages build — it's baked in at build time |
| Job sticks on `running` and never finishes | You deployed **without** `--no-cpu-throttling`, so the background thread is starved | Re-run the deploy command from § 9 (it includes the flag) |
| First request after a while takes ~20 s | Cold start after scale-to-zero | Expected. Part E. Don't "fix" it with keep-alive on this setup. |
| Job seems slow on big inputs | 100+ page cross-section PDFs take real time to render | Give it a minute; check logs (**Cloud Run → service → Logs**) for progress |
| Build fails pulling a huge context / times out | A stray `Road_venv/` or `node_modules/` got uploaded | `.gcloudignore` should prevent this — confirm it's present at the repo root and not gitignored |
| Streamlit app blank / import error after the path change | Main file path not saved, or a stale deploy | Recheck Part D's path string, save again, "Reboot app" from the dashboard |

---

## 11. What this costs

- **Streamlit Community Cloud** — free for public apps.
- **Cloudflare Pages** — free: unlimited requests and bandwidth for static sites; monthly build
  quota is generous for a project updated a few times a week.
- **Google Cloud Run** — always-free monthly allotment: **2M requests, 180,000 vCPU-seconds,
  360,000 GiB-seconds, 1 GiB North-America egress**. With `--no-cpu-throttling` at 1 vCPU /
  1 GiB, the binding limit is ~**50 instance-hours/month**. A few designs a day, each keeping an
  instance alive ~15–20 min, is far under that → **$0**. Cloud Build (image builds) is free up
  to 120 minutes/day; a build here is ~3–5 minutes. Artifact Registry storage past 0.5 GB is
  ~$0.05/GB/month — trim old images occasionally (§ 9).
- **Hugging Face** — only if you do Part G: **PRO is $9/month**, flat, and then the backend
  doesn't sleep and the keep-alive ping is free to run.

**The crossover.** Cloud Run is free while traffic is light. If it grows enough that an
instance is alive most of the day, Cloud Run's usage billing (~$0.10/instance-hour ⇒ tens of
dollars/month for near-always-on) exceeds HF PRO's flat $9. That's the point to run Part G.

---

## 12. Part G — Switching the backend to Hugging Face Spaces later

Do this only when [§ 11](#11-what-this-costs)'s crossover is reached (or if you just prefer HF).
It needs a **PRO** subscription ($9/mo) for CPU hardware. The `Dockerfile` is unchanged — it
already listens on `$PORT` and falls back to `7860`, which is exactly what HF expects.

### G.1 — Create the Space

1. Subscribe to [Hugging Face PRO](https://huggingface.co/pricing).
2. [huggingface.co/new-space](https://huggingface.co/new-space):
   - **Space name**: `road-designer-api`.
   - **License**: **Other** (declared properly in G.3).
   - **SDK**: **Docker** → **Blank** template.
   - **Hardware**: **CPU basic** (now available because you're PRO).
   - **Visibility**: Public or Private, your call.
3. **Create Space**.

### G.2 — Get a write token

Profile picture → **Settings** → **Access Tokens** → **New token**, type **Write**, copy it.

### G.3 — Assemble and push

HF's Docker SDK wants the `Dockerfile` at the Space repo's own root, with `road_designer/`,
`samples/`, `backend/` and the Notice Files as siblings. Push a separate clone of the Space
containing exactly that:

```bash
git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/road-designer-api road-designer-space
cd road-designer-space

PROJECT=/path/to/Road_designe    # adjust

cp -r "$PROJECT/road_designer" ./road_designer
cp -r "$PROJECT/samples"       ./samples
cp -r "$PROJECT/backend"       ./backend
cp -r "$PROJECT/brand"         ./brand
cp "$PROJECT/Dockerfile" "$PROJECT/LICENSE" "$PROJECT/NOTICE" "$PROJECT/THIRD-PARTY-NOTICES.md" ./

git add -A
git commit -m "Deploy Road Designer API"
git push        # username = your HF username, password = the WRITE token from G.2
```

For later updates, re-run the `cp`/`rsync` and `git push` (no need to re-create the Space):

```bash
cd road-designer-space
PROJECT=/path/to/Road_designe
rsync -a --delete "$PROJECT/road_designer/" ./road_designer/
rsync -a --delete "$PROJECT/samples/"       ./samples/
rsync -a --delete "$PROJECT/backend/"       ./backend/
rsync -a --delete "$PROJECT/brand/"         ./brand/
cp "$PROJECT/Dockerfile" "$PROJECT/LICENSE" "$PROJECT/NOTICE" "$PROJECT/THIRD-PARTY-NOTICES.md" ./
git add -A && git commit -m "Update Road Designer API" && git push
```

### G.4 — Declare the licence on the Space

The Space's auto-generated `README.md` has a front-matter block between two `---` lines. Add:

```yaml
license: other
license_name: beamstack-community-license-1.0
license_link: LICENSE
```

and optionally a body line: `Powered by Beamstack — source: https://github.com/<you>/<repo>`.
Commit and push. (No UI badge needed — the backend has none.)

### G.5 — Cut over

1. Wait for the Space to show **Running**; its URL is `https://YOUR_HF_USERNAME-road-designer-api.hf.space`.
   Check `/health` and `/docs`.
2. **Space → Settings → Variables and secrets → New variable**: `ALLOWED_ORIGIN` =
   `https://road-designer.beam-stack.com` (same value as Part C — comma-add the `*.pages.dev`
   fallback if you kept it).
3. **Cloudflare Pages → Settings → Environment variables**: change `VITE_API_BASE_URL` to the
   Space URL, then **Retry deployment**.
4. *(Optional)* Set the `BACKEND_HEALTH_URL` repo secret to `https://<space-url>/health` so
   `.github/workflows/keep-alive-backend.yml` keeps it warm — now safe, because HF doesn't bill
   per idle-second.
5. Once the SPA is confirmed working against HF, delete the Cloud Run service to stop any
   billing: `gcloud run services delete road-designer-api --region europe-west1`.
