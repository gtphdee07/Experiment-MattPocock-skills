# Towing Limit Checker - Web (React + FastAPI)

Design + reference implementation for the desktop web version, styled per
the WTWT design system and consistent with `Towing Limit Checker - Web.dc.html`
(the visual mockup) and the mobile prototype.

## Layout in this repo

Drop these two folders in at the repo root as new apps, alongside the
existing `apps/streamlit` and `apps/cli`:

- `webapp/api/`      -> `apps/web-api/`   (FastAPI - imports `towing_core` directly, no duplicated math)
- `webapp/frontend/` -> `apps/web/`       (Vite + React + TypeScript)

## Run locally

```
# terminal 1 - API
cd apps/web-api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# terminal 2 - frontend
cd apps/web
npm install
npm run dev
```

The frontend calls `VITE_API_BASE` (defaults to `http://localhost:8000`) -
set it as an env var for your deployed API origin, and tighten the API's
CORS `allow_origins` to match before shipping.

## What's real vs. placeholder

- The evaluation math is real: the API calls `towing_core.evaluate_weigh_event`
  directly, so results match the CLI and Streamlit app exactly.
- Colors/type/status-box spec match `streamlit-theme/DELIVERABLE.md` and the
  mobile prototype - same fills, same colorblind-safe icon+border treatment.
- Header nav links (Home/About) and footer links are placeholders pending
  real destinations.
