# Towing Limit Checker

Helps an RV owner work out whether a specific **Tow Vehicle + Trailer** pairing
is within its legal weight limits — using **actual certified scale weights**
(CAT Scale tickets) and the ratings off each vehicle's certification label,
rather than guessing from brochure capacity numbers.

## Live demo

**→ https://bhw6ybrhzszjnsuyvf2mg4.streamlit.app/**

A no-login web calculator: enter your truck's ratings, your trailer's ratings,
and the numbers from a CAT Scale weigh ticket, and it shows every weight check
as a colour-coded box — green (within limit), amber (close), red (over), grey
(not enough data to check). Nothing is stored.

## What it checks

For one weigh event it runs six overload comparisons and one advisory:

| Check | Compares |
|---|---|
| Steer / Drive / Trailer **Axle** overload | each axle-group scale weight vs its GAWR |
| **Hitched GVWR** overload | the tow vehicle's axles (while hitched) vs the truck's GVWR |
| **GCWR** overload | combined scale weight vs the truck's GCWR |
| **Trailer GVWR** overload | derived trailer weight (combined − solo ticket) vs the trailer's GVWR |
| **Time-Gap Warning** (advisory) | how far apart the combined and solo weighings were |

Each check comes back as **Pass**, **Near Limit**, **Fail**, or **Not Evaluated**.
See [`CONTEXT.md`](CONTEXT.md) for the full vocabulary and [`docs/adr/`](docs/adr/)
for the decisions behind the rules.

## Repository layout

A [`uv`](https://docs.astral.sh/uv/) workspace with a dependency-free compute
core reused across every surface:

```
packages/towing-core/   pure compute — models, the overload calculations, rig
                        evaluation, and storage / field-source ports (stdlib only)
packages/towing-app/     application services — SQLite persistence, the Claude-vision
                        tag/ticket OCR adapters, weigh-event orchestration
apps/cli/                interactive command-line client (towing_cli)
apps/streamlit/          the standalone web calculator (compute tier only)
docs/design/             the WTWT design system + per-surface deliverables
```

The layering is enforced by a static import check
(`packages/towing-core/tests/test_layering.py`). Details in
[`docs/adr/0008-two-tier-core-and-uv-monorepo-workspace.md`](docs/adr/0008-two-tier-core-and-uv-monorepo-workspace.md)
and [`CODING_STANDARDS.md`](CODING_STANDARDS.md).

## Running locally

Prerequisites: [`uv`](https://docs.astral.sh/uv/) and Python 3.12. Then
`uv sync` once.

**The web calculator:**

```bash
uv run streamlit run apps/streamlit/streamlit_app.py
```

**The CLI** (SQLite-backed garage, weigh-event history, optional photo OCR):

```bash
uv run towing-app --help
uv run towing-app truck add
uv run towing-app weigh-event run
```

The CLI stores its garage at `~/.towing_app/garage.db` by default. For
development, point it somewhere disposable first:

```bash
export TOWING_APP_DB_PATH="$PWD/.dev-data/garage.db"   # bash
$env:TOWING_APP_DB_PATH = "$PWD\.dev-data\garage.db"   # PowerShell
```

Photo OCR (reading a DOT tag or CAT Scale ticket from a picture) uses the
Anthropic API and needs `ANTHROPIC_API_KEY` set; everything else works offline.

## Tests

```bash
uv run pytest -k "not real"     # 314 tests, all offline
uv run pytest                   # + 6 smoke tests that call the real Anthropic API
```

The 6 `test_real_*` tests need `ANTHROPIC_API_KEY` and API credit; skip them with
`-k "not real"` for a fully offline run.

Also run in CI-style: `uv run mypy .`, `uv run ruff check .`,
`uv run ruff format --check .`.

## Status

- **Compute core + services + CLI + Streamlit calculator** — done.
- **FastAPI backend + full web app** (accounts, garage, history) — planned.
- **Android app** — planned.

## Disclaimer

This is a personal reference tool for recreational RV towing. The in-app legal
disclaimer is placeholder text pending review. Results are estimates from
user-entered data and are not a substitute for certified scale readings or
professional advice.

## License

MIT — see [`LICENSE`](LICENSE).
