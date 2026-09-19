# Hosting cost options — backend+Postgres and static frontend

**Status:** research only — no decision has been made. ADR 0011 explicitly leaves "the backend's specific PaaS host (Railway/Fly.io/Render) and the frontend's specific static host (Vercel/Netlify/Cloudflare Pages)" as "implementation-time picks, not architectural commitments." This document exists so a human can make that pick, informed by primary-source facts as of **2026-09-18**.

**Usage profile costed against:** 10 active users in month 1, +10/month, ~120 by month 12. Light CRUD (create/edit a few DB rows per session), no heavy compute, no file/video storage, Postgres stays well under 1GB. A few hundred HTTP requests per user per month, at most — so at month 12, roughly 120 × a few hundred ≈ tens of thousands of requests/month, not millions.

---

## Summary / lean

**Backend + Postgres:** **Fly.io is the clear outlier on cost** for this workload — its supported path (Managed Postgres, "MPG") has **no free tier and starts at $38/month** regardless of database size or traffic, because MPG is sold in fixed compute-plan tiers, not billed by usage. Railway and Render both land far cheaper in practice (roughly $5–25/month across the whole year), so Fly.io is not cost-competitive here unless you're willing to run Fly's **deprecated, unsupported** self-hosted ("unmanaged") Postgres instead of MPG. Between **Railway** and **Render**, the numbers are genuinely close and come down to preference: Render's compute/DB pricing is flat and predictable per instance but its *free* Postgres tier auto-deletes data 30 days after creation (a trap for a real app, not a viable "free forever" option); Railway has no separate free Postgres tier at all — a database is metered like any other service against the $5/month Hobby plan's included usage credit, which a small always-on Postgres instance will likely exceed on its own, making the effective floor closer to $10–15/month rather than $5.

**Frontend static hosting:** **Cloudflare Pages is the clear winner** — genuinely free, unmetered static bandwidth, a 100,000-requests/day free allowance for any dynamic Functions (thousands of times this app's real month-12 volume), and no commercial-use restriction. This matters specifically because Vercel's free Hobby tier is contractually restricted to **non-commercial personal use** — and this repo's own ADR 0013 makes this a paid product (Website Access, Android Access, OCR Credits are real purchases), which would put a Vercel deployment out of Hobby-tier compliance from day one and require Pro at $20/month per seat regardless of how little traffic it gets. Netlify's free tier is also genuinely usable ($0 through month 12 is plausible) but its 300-credit pool is shared across bandwidth, requests, *and* deploys, so active development (frequent redeploys) eats into the same budget that serves real users — a subtler trap than Vercel's ToS restriction, but still a real one. Cloudflare Pages also fits this repo's own multi-surface-architecture design best: its $5/month paid tier (only needed if Functions usage ever exceeds the free daily cap) is billed **once per Cloudflare account**, not per project, so future apps in this `uv`/npm monorepo share the same ceiling instead of each requiring a new $20/month Pro seat.

---

## Backend + Postgres hosting

### 1. Railway

**Plans (primary source: [docs.railway.com/pricing/plans](https://docs.railway.com/pricing/plans), confirmed at [railway.com/pricing](https://railway.com/pricing)):**

- **Free Plan**: $0/month, includes **$1 of usage credit per month**. Resource ceiling: 1 vCPU / 0.5 GB RAM per service, 1 replica, 3-day log history. Too small to run a real backend+DB pair — effectively a "kick the tires" tier, not a hosting option.
- **Trial**: new accounts get a one-time **$5 credit valid for 30 days** (2 vCPU / 1 GB per service while on trial).
- **Hobby**: **$5/month flat**, includes **$5 of monthly usage credit**. Resource ceiling: up to 48 vCPU / 48 GB per service, 6 replicas, 7-day log history, 5 GB volume storage.
- **Pro**: **$20/month flat** (per workspace, not per seat), includes $20 of usage credit. Ceiling: up to 1,000 vCPU / 1 TB per service, 42 replicas, 30-day logs, self-serve volume expansion to 1 TB.

**Usage-based rates that consume the plan credit** ([docs.railway.com/pricing/plans](https://docs.railway.com/pricing/plans)):
- RAM: **$10/GB/month**
- CPU: **$20/vCPU/month** (billed per-second while actively used)
- Network egress: **$0.05/GB**
- Volume storage: **$0.15/GB/month**

**Postgres — no separate free tier.** Railway's own PostgreSQL guide ([docs.railway.com/databases/postgresql](https://docs.railway.com/databases/postgresql), [docs.railway.com/guides/postgresql](https://docs.railway.com/guides/postgresql)) deploys Postgres as an ordinary Railway service — it is metered under the exact same RAM/CPU/volume-storage rates above, drawing from the same plan credit as the backend container itself. There is no Railway-specific "free managed Postgres" allowance the way Render has one. Volume storage for Postgres data is billed at the same **$0.15/GB/month** rate as any volume ([search confirms via docs.railway.com/reference/pricing and docs.railway.com/volumes/reference](https://docs.railway.com/pricing/plans)). Backups are available via Railway's native Point-in-Time Recovery / backup feature (no separate primary-source price found for retention beyond the standard volume/bucket storage rates — bucket storage for backup retention is billed at **$0.015/GB/month**, per [docs.railway.com](https://docs.railway.com/storage-buckets/billing)).

**Sleep/cold-start behavior:** none documented for paid (Hobby+) services — containers run continuously and are billed per-second while running; "stopped services cost nothing," but nothing in Railway's own docs describes automatic idle-based sleeping the way Render's free tier does.

**Cost estimate for this profile:**
- A minimal always-on FastAPI container (say 512 MB RAM, light CPU) plus a minimal always-on Postgres instance (512 MB RAM, <1 GB storage) will, by Railway's own per-GB/per-vCPU rates, run roughly **$8–15/month in raw usage** even at near-zero traffic, because the meter is driven by RAM/CPU *uptime*, not requests. The $5 Hobby plan credit covers only part of that, so the realistic floor is the **$5/month plan fee plus a few dollars of overage** — call it **~$8–15/month** — essentially flat across month 1, 6, and 12, since this workload's actual request volume never comes close to moving the needle (RAM/CPU-hours dominate, not egress or request count).
- Month 1 (10 users): ~$8–12/mo. Month 6 (~60 users): ~$10–15/mo. Month 12 (~120 users): ~$12–18/mo (allowing a small egress/CPU creep, still dominated by base compute, not traffic).

**Gotcha:** the $5/Hobby and $20/Pro fees are **per workspace**, not per project or per seat — a real advantage if this monorepo eventually deploys more than one small app under the same Railway account, since the base fee doesn't multiply per app (only the usage credit gets consumed faster). But because Postgres has no dedicated free/cheap allowance, the "free compute, pay only for DB" story other providers can tell doesn't apply here — everything draws from one shared, usage-metered pool.

### 2. Fly.io

**Free tier / trial (primary source: [fly.io/docs/about/free-trial/](https://fly.io/docs/about/free-trial/)):** New accounts get a trial that lasts **2 VM-hours of machine runtime or 7 days, whichever comes first** (up to 10 machines, 2 vCPU/4 GB per machine, 20 GB volume storage; trial machines auto-stop after 5 minutes running). Adding a payment method ends the trial immediately and starts real billing. Fly's general pricing page ([fly.io/docs/about/pricing/](https://fly.io/docs/about/pricing/)) confirms the old standing free allowance (3 shared-cpu-1x 256 MB machines + 3 GB volume storage) is **legacy/grandfathered only** — new accounts do not get it.

**Compute (pay-as-you-go, [fly.io/docs/about/pricing/](https://fly.io/docs/about/pricing/)):** billed per second. Example: `shared-cpu-1x` with 256 MB RAM ≈ **$2.02/month** if run continuously in Amsterdam; a `performance-1x` 2 GB machine ≈ $32.19/month. Reserved-capacity discounts (~40% off) are available if pre-committing to a usage block. Network egress: **$0.02/GB** for North America/Europe, up to $0.12/GB for Africa/India. Volume storage: **$0.15/GB/month**; snapshots $0.08/GB/month with the first 10 GB/month free.

**Managed Postgres (MPG) — no free tier at all ([fly.io/docs/mpg/](https://fly.io/docs/mpg/)):**
| Plan | CPU | Memory | Price |
|---|---|---|---|
| Basic | Shared-2x | 1 GB | **$38.00/month** |
| Starter | Shared-2x | 2 GB | $72.00/month |
| Launch | Performance-2x | 8 GB | $282.00/month |

Storage beyond the plan's included amount is **$0.28/GB-month** (max 1 TB/cluster). All MPG plans include HA, backups, and connection pooling — but there is no smaller/cheaper tier below the **$38/month Basic plan**, regardless of how small the actual database is (this app's Postgres stays well under 1 GB for a very long time at this scale, but MPG's pricing is not usage-based — it's a fixed monthly compute-plan fee).

**Unmanaged Postgres — deprecated, unsupported, but cheaper:** Fly still documents ([fly.io/docs/postgres/](https://fly.io/docs/postgres/)) a self-run option where "a Fly app with flyctl sugar on top" runs Postgres as an ordinary Machine + volume, billed at the same per-second compute/volume rates as any app (i.e., a few dollars/month for a tiny instance). Fly's own docs are explicit that this is **not supported**: "We are not able to provide support or guidance for unmanaged Postgres," it carries real risk (single-node failure loses data since the last snapshot), and Fly is steering all new usage toward MPG or its newer Supabase-partnered "Fly Postgres" offering instead.

**Cost estimate for this profile:**
- **If using the supported MPG path:** ~$38/month for the database alone (Basic plan) plus a small always-on compute machine (~$2–10/month depending on size) — **≈$40–48/month, essentially flat across month 1, 6, and 12**, since 120 users of light CRUD never justifies moving off the $38 Basic MPG tier, and the fixed monthly fee doesn't scale down for low traffic.
- **If using the deprecated/unsupported self-run Postgres path:** compute + volume only, likely **~$5–12/month total**, comparable to Railway/Render — but explicitly unsupported by Fly, a real risk for anything beyond a toy deployment.

**Gotcha:** Fly.io's real "free tier" for new accounts is essentially gone (7-day/2-VM-hour trial only) — don't plan around a standing free allowance the way older Fly.io writeups describe. The **$38/month MPG floor, independent of database size or traffic**, is the single biggest cost gotcha of all six services evaluated here: it doesn't matter that this app's data stays under 1 GB for years — Fly's supported managed-Postgres pricing doesn't reward that.

### 3. Render

**Free web service ([render.com/docs/free](https://render.com/docs/free)):** **750 free instance-hours per workspace per month.** A free web service **spins down after 15 minutes of no inbound traffic** and takes about a minute to spin back up on the next request (cold start). No persistent disk (ephemeral filesystem — fine here, since all real state lives in Postgres). Single instance only, no scaling. Services suspend for the rest of the month if the 750-hour budget is exhausted.

**Free Postgres ([render.com/docs/free](https://render.com/docs/free)):** **fixed 1 GB storage cap**, and critically: **free Render Postgres databases expire 30 days after creation**, with a 14-day grace period to upgrade before the data is deleted. No backups on the free tier. Only one free database per workspace. This is a real trap for this project — a database that auto-deletes itself after ~44 days is not a "free forever" tier the way Postgres-bundling matters for the research question; it's closer to a 6-week trial.

**Compute plan names/specs (primary source: [render.com/docs/compute-plans](https://render.com/docs/compute-plans)) — dollar prices confirmed via multiple independent secondary sources since render.com/pricing itself is a JavaScript-rendered page that did not yield raw price text to a plain fetch, flagged explicitly here per this project's citation convention:**

| Web service plan | CPU/RAM | Price (secondary-confirmed) |
|---|---|---|
| Free | 0.1 CPU / 512 MB | $0 |
| Starter | 0.5 CPU / 512 MB | **~$7/month** |
| Standard | 1 CPU / 2 GB | **~$25/month** |

| Postgres plan | CPU/RAM/connections | Price (secondary-confirmed) |
|---|---|---|
| Free | 0.1 CPU / 256 MB, 100 conn | $0 (30-day expiry, see above) |
| Basic-256mb | 256 MB | **~$6/month** + storage at ~$0.30/GB-month |
| Basic-1gb | 1 GB | **~$19/month** |

(Render's own docs confirm the *plan structure and specs* — [render.com/docs/compute-plans](https://render.com/docs/compute-plans), [render.com/docs/postgresql-creating-connecting](https://render.com/docs/postgresql-creating-connecting) — including that "the compute plan does not affect storage capacity; it only determines RAM, CPU, and connection limit." The exact dollar figures above come from cross-checking three independent aggregator/comparison sources that agreed on the same numbers, since Render's pricing page would not render its price table content to a plain-text fetch.)

**Cost estimate for this profile:**
- **Staying entirely on free tiers**: $0/month, but the Postgres 30-day auto-delete makes this a non-starter for real user data beyond the first ~6 weeks, and the 15-minute sleep/cold-start on the free web service is a real UX problem for a login-based app (first request after any idle gap takes ~1 minute).
- **Realistic "actually keep the data" setup**: Starter web service (~$7/mo) + Basic-256mb Postgres (~$6/mo + negligible storage, since the DB stays well under 1 GB) ≈ **$13–15/month**, flat across month 1, 6, and 12 — this workload's traffic never approaches any of Render's per-plan ceilings, so the cost doesn't grow with the user count.
- If willing to accept the free web service's sleep/cold-start behavior (tolerable at 10–20 users, increasingly noticeable by 120), compute could stay on the free 750-hour allotment (a single 24/7 service uses ~720 of the 750 hours) — but the Postgres expiry issue still forces at least the ~$6–7/month DB spend to avoid data loss. **Realistic floor: ~$6–15/month depending on how much cold-start latency is tolerated.**

**Gotcha:** the free Postgres tier's **30-day hard expiry** is the sharpest gotcha of the three backend options — it looks like a "bundled free managed Postgres" tier in marketing terms, but it functionally is not one for an app meant to run for a year. Render's compute/DB pricing is otherwise flat and predictable per instance (no usage-metering surprises like Railway), but every additional future app in the monorepo needs its own paid web-service + Postgres instance — there's no shared/flat account-level fee the way Railway's workspace fee or Cloudflare's account-level $5/month works.

---

## Frontend static hosting

### 4. Vercel

**Hobby (free) plan ([vercel.com/docs/plans/hobby](https://vercel.com/docs/plans/hobby), [vercel.com/docs/pricing](https://vercel.com/docs/pricing)):**
- **Fast Data Transfer**: first 100 GB/month included.
- **Fast Origin Transfer**: first 10 GB/month included (this is the tighter of the two caps, since it applies to uncached/dynamic origin traffic).
- **Edge Requests**: first 1,000,000/month.
- **Vercel Function Invocations**: first 1,000,000/month; **Active CPU**: 4 CPU-hours included; **Provisioned Memory**: 360 GB-hours included.
- 200 projects, 100 deployments/day, 1-hour runtime log retention.
- **Exceeding limits**: no overage billing on Hobby — "Hobby costs nothing and stops rather than bills." Most limit breaches pause the affected feature until the **next 30-day cycle** ([vercel.com/docs/plans/hobby](https://vercel.com/docs/plans/hobby)).

**Hard restriction — commercial use is explicitly disallowed on Hobby:** "the Hobby plan restricts users to non-commercial, personal use only" ([vercel.com/docs/plans/hobby](https://vercel.com/docs/plans/hobby), citing Vercel's Fair Use Guidelines). This project is a paid product per ADR 0013 (Website Access / Android Access / OCR Credits are real Stripe purchases) — meaning a Vercel deployment of this frontend would not actually qualify for the free Hobby tier's terms of use from day one, independent of how little traffic it gets.

**Pro plan:** **$20/month per developer seat** (Viewer seats free), unlimited projects, usage-based on-demand pricing beyond a monthly credit once seat(s) are purchased ([vercel.com/docs/pricing](https://vercel.com/docs/pricing)).

**Cost estimate for this profile:** Traffic-wise, this app would stay comfortably inside Hobby's 100 GB/10 GB/1M-request caps through month 12 — tens of thousands of monthly requests and a small static bundle's bandwidth are nowhere near those ceilings. But because this is a commercial product, the realistic cost is **$20/month starting month 1** (one Pro seat), not $0, once Vercel's own usage terms are taken at face value.

**Gotcha:** the commercial-use restriction, not traffic volume, is what actually drives Vercel's cost for this specific project — a rare case where the free tier's *technical* limits are irrelevant because its *terms of use* disqualify the app first.

### 5. Netlify

**Free plan ([netlify.com/pricing](https://www.netlify.com/pricing/)):** **300 credits/month, hard limit** — no overage, no buying more; when credits run out, sites pause until the next cycle. Credits are a single shared pool spent by every kind of usage:
- Bandwidth: **20 credits/GB**
- Production deploys: **15 credits each**
- Web requests: **2 credits per 10,000**
- Compute (Functions): **10 credits/GB-hour**

At $10/1,500 credits (Pro-tier rate), 300 credits ≈ **$2/month of notional value**, or roughly **15 GB of bandwidth if spent on nothing else** — but deploys and requests draw from the same pool, so real headroom for traffic is less than 15 GB once normal development/redeploy activity is factored in.

**Paid plans:** **Personal $9/month** (1,000 credits), **Pro $20/month** with **unlimited members** (3,000 credits) ([netlify.com/pricing](https://www.netlify.com/pricing/)). No commercial-use restriction found in Netlify's own pricing docs (unlike Vercel's Hobby clause).

**Cost estimate for this profile:** This app's actual light-CRUD traffic (tens of thousands of requests/month, modest bandwidth given caching) should fit inside 300 credits/month through month 12 in production — **$0/month is plausible at every checkpoint** — but active development with frequent redeploys (15 credits each) measurably eats into the same budget that also has to cover real user bandwidth and requests, unlike Vercel/Cloudflare where deploys aren't metered against the same cap that serves traffic.

**Gotcha:** the shared-pool credit model means "how much of my free tier is left" depends on *both* deployment cadence and traffic together — a subtler trap than Vercel's flat ToS restriction, but real for a project still under active development. If deploys are frequent, Personal ($9/month) may be needed sooner than traffic alone would suggest.

### 6. Cloudflare Pages

**Free tier:**
- **Builds**: 500/month, 1 concurrent build ([developers.cloudflare.com/pages/platform/limits/](https://developers.cloudflare.com/pages/platform/limits/)).
- **Static asset requests**: "free and unlimited" — "a request is considered static when it does not invoke Functions" ([developers.cloudflare.com/pages/functions/pricing/](https://developers.cloudflare.com/pages/functions/pricing/)). No bandwidth cap found for static assets in Cloudflare's own docs — this is Cloudflare's standard "no bandwidth fees" model carried over from Workers/CDN.
- **Pages Functions** (any dynamic glue code, e.g. calling the FastAPI backend): billed against the **Workers free plan's shared daily cap of 100,000 requests/day** ([developers.cloudflare.com/pages/functions/pricing/](https://developers.cloudflare.com/pages/functions/pricing/), [developers.cloudflare.com/workers/platform/pricing/](https://developers.cloudflare.com/workers/platform/pricing/)) — resets at midnight UTC.
- Custom domains: 100 on the free plan. Max file size: 25 MiB/asset. 20,000 files max on free.

**Paid — Workers Paid plan, $5/month flat, billed per Cloudflare account (not per project):** 10,000,000 requests/month included (+$0.30/additional million), 30,000,000 CPU-ms/month included (+$0.02/additional million ms) ([developers.cloudflare.com/workers/platform/pricing/](https://developers.cloudflare.com/workers/platform/pricing/)). No charges for data egress/bandwidth from Workers/Pages.

**No commercial-use restriction found** in Cloudflare's own Pages/Workers pricing docs (contrast with Vercel's explicit Hobby-tier ban).

**Cost estimate for this profile:** **$0/month at month 1, 6, and 12.** 100,000 requests/day (≈3,000,000/month) free for any dynamic Functions is thousands of times this app's realistic month-12 volume (tens of thousands of requests/month total), and static asset bandwidth is unmetered regardless of volume.

**Gotcha (favorable for this repo specifically):** the $5/month Paid plan — only needed if Functions usage ever exceeds the free daily request cap — is billed **once per Cloudflare account, not per project**. Per this repo's own `CONTEXT.md` (a `uv`/npm monorepo with `apps/cli`, the future `apps/streamlit`, and the already-built `apps/web`), if more small apps are deployed under the same Cloudflare account later, they'd all share that single $5/month ceiling rather than each requiring a new per-project or per-seat paid plan the way Vercel Pro ($20/month/seat) or Render's per-instance pricing would.

---

## Comparison table

| Service | Free tier viability at this scale | Month 1 / 6 / 12 estimated cost | Key gotcha |
|---|---|---|---|
| **Railway** (backend+DB) | No real free DB tier; $5/mo Hobby plan is the practical floor | ~$8–12 / ~$10–15 / ~$12–18 | Postgres is usage-metered like any other service, no bundled free allowance — RAM/CPU uptime, not traffic, drives cost |
| **Fly.io** (backend+DB) | Free trial is 7 days/2 VM-hrs only; Managed Postgres has zero free tier | ~$40–48 / ~$40–48 / ~$40–48 (MPG path) | **$38/mo Managed Postgres floor regardless of DB size/traffic** — cheaper only via the deprecated, unsupported self-run Postgres path |
| **Render** (backend+DB) | Free web + free Postgres exist but free DB **expires 30 days after creation** | ~$6–15 / ~$13–15 / ~$13–15 | Free Postgres tier is a ~6-week trial in disguise, not a real free-forever bundled DB |
| **Vercel** (frontend) | Traffic fits Hobby's caps easily, but Hobby **bans commercial use** | ~$20 / ~$20 / ~$20 (Pro required day one, per ToS) | Free tier's terms of use, not its technical limits, disqualify this paid product |
| **Netlify** (frontend) | Plausibly free through month 12 if deploy cadence stays modest | ~$0 / ~$0 / ~$0 (or $9 if deploys are frequent) | 300-credit pool is shared across bandwidth, requests, *and* deploys |
| **Cloudflare Pages** (frontend) | Comfortably free at every checkpoint | ~$0 / ~$0 / ~$0 | None found at this scale; $5/mo paid tier (if ever needed) is flat per account, not per project |

## Recommendation

- **Frontend: Cloudflare Pages**, plainly. It's free at every stage of this growth curve, carries no commercial-use restriction (unlike Vercel), doesn't share its usage cap between deploys and real traffic (unlike Netlify), and its eventual $5/month paid tier is account-wide — the best fit for this repo's own multi-surface-monorepo trajectory (CONTEXT.md; `apps/cli`, `apps/web`, future `apps/streamlit`).
- **Backend + Postgres:** **Fly.io can be ruled out on cost** for this specific workload — its supported Managed Postgres has a **$38/month floor with no free tier**, an order of magnitude more than the other two options, and unrelated to how small this app's actual database stays. Between **Railway and Render, the numbers are genuinely close (roughly $8–18/month either way) and come down to preference, not cost**: pick **Render** for flat, predictable per-instance pricing (accepting that its free Postgres tier is really a 30-day trial, not a bundled free DB) and its workspace-level free Hobby seat; pick **Railway** if a single flat account/workspace fee that doesn't multiply per future monorepo app matters more than predictable line-item pricing, and usage-metered billing (rather than fixed instance tiers) is acceptable.

---

## Sources

- Railway: [Pricing plans](https://docs.railway.com/pricing/plans), [railway.com/pricing](https://railway.com/pricing), [PostgreSQL guide](https://docs.railway.com/databases/postgresql), [PostgreSQL deployment guide](https://docs.railway.com/guides/postgresql), [Storage buckets billing](https://docs.railway.com/storage-buckets/billing) (fetched 2026-09-18)
- Fly.io: [Pricing](https://fly.io/docs/about/pricing/), [Free trial](https://fly.io/docs/about/free-trial/), [Managed Postgres (MPG)](https://fly.io/docs/mpg/), [Postgres (unmanaged)](https://fly.io/docs/postgres/) (fetched 2026-09-18)
- Render: [Free tier](https://render.com/docs/free), [Compute plans](https://render.com/docs/compute-plans), [PostgreSQL creating/connecting](https://render.com/docs/postgresql-creating-connecting); render.com/pricing itself is JavaScript-rendered and did not yield raw price text to a plain fetch — dollar figures for paid compute/Postgres instance tiers are corroborated across multiple independent secondary sources and flagged as such above (fetched 2026-09-18)
- Vercel: [Hobby plan](https://vercel.com/docs/plans/hobby), [Pricing](https://vercel.com/docs/pricing) (fetched 2026-09-18)
- Netlify: [Pricing](https://www.netlify.com/pricing/) (fetched 2026-09-18)
- Cloudflare Pages/Workers: [Pages Functions pricing](https://developers.cloudflare.com/pages/functions/pricing/), [Pages platform limits](https://developers.cloudflare.com/pages/platform/limits/), [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) (fetched 2026-09-18)

Where a claim above relies on secondary-source corroboration rather than a directly fetchable primary-source price table (Render's exact dollar figures for paid compute/Postgres plans, since render.com/pricing renders its tables client-side), that is called out explicitly in the relevant section rather than presented as primary-confirmed, matching this repo's existing research-notes convention (`docs/research/transactional-email-providers.md`).
