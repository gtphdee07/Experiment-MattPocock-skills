# Design assets

Visual design + branding for the Towing Limit Checker surfaces. The shared
identity is **"Wandering Trails, Wagging Tails" (WTWT)** — one palette, one type
system (Quicksand / Karla), one colourblind-safe status treatment across every
surface.

**Start here:** `design-tokens.md` — the WTWT palette, type, spacing, radius,
and the result-box status spec, as text. Every surface implements a subset.

| Path | What | Used by |
|---|---|---|
| `design-tokens.md` | The WTWT system in text — single source of truth | every surface |
| `streamlit-branding-brief.md` | The brief handed to Claude Design | — (history) |
| `brand-assets/` | Canonical WTWT logo + mono favicon (PNG) | every surface |
| `mobile/prototype.html` | **Mobile design** — a 440px, fully self-contained interactive prototype (all 5 wizard steps + results grid, working light/dark toggle, embedded fonts). Open it in a browser. The authoritative visual render | Phase 3; reference for all |
| `streamlit/` | **Phase 1 deliverable** — `config.toml` theme block, restyled `results.py`, `streamlit_app.py.patch.py`, `DELIVERABLE.md`. Ready to apply to `apps/streamlit/` | Phase 1 (active) |
| `web/` | **Phase 2 reference implementation** — FastAPI `api/` + Vite/React/TS `frontend/` (`src/theme.ts` mirrors the tokens). Staged reference only, not wired into the build; Phase 2's grilling picks the real stack | Phase 2 |
| `android/` | Notes only — the mobile prototype above is the design; this covers what to port | Phase 3 |
| `_original-deliverables/` | The raw bundles as delivered (zips, `.dc.html`s, duplicates). Gitignored. Everything in them is extracted above — delete anytime | — |

Only `streamlit/` is consumed by the current build. `mobile/`, `web/`, and
`android/` are staged for their phases (see `~/.claude/plans/nifty-crafting-pond.md`).

## What was delivered (Sept 2026)

Three designs — Mobile, Web, Streamlit — plus the shared brand. Packaging was
messy: the Streamlit bundle arrived twice (once mislabeled "mobile app design"),
the mobile mockup arrived first as a partial `.dc.html` (missing its token CSS +
runtime) and then complete as `mobile/prototype.html`. A `Towing Limit Checker -
Web.dc.html` referenced by `web/README.md` was never received — the `web/` code
bundle covers web regardless.
