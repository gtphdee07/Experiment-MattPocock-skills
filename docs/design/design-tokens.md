# WTWT design tokens

**"Wandering Trails, Wagging Tails" (WTWT)** — the shared design system for every
Towing Limit Checker surface (Streamlit, Web, Mobile). Extracted from
`mobile/prototype.html` (the authoritative source — a fully self-contained
render with the tokens, fonts, and interaction runtime bundled in). The
Streamlit and Web deliverables restate subsets of this for their platforms.

## Brand colours

| Token | Hex | Variants | Role |
|---|---|---|---|
| `sunset-orange` | `#f0942f` | light `#ffb050`, dark `#c9701a` | primary accent / CTA / `state-warning` |
| `trail-green` | `#4d7a3a` | light `#6f9a56`, dark `#33552b` | secondary accent / `state-success` / links |
| `dusk-mauve` | `#8d7fa0` | light `#a99cc0`, dark `#5f5578` | tertiary accent / `state-info` |
| `sunset-rose` | `#c17f8f` | light `#daa5b0`, dark `#8f5866` | quaternary accent |
| `charcoal` | `#2a2a28` | soft `#4a4844` | primary text / strong borders |
| `cream` | `#f6efe4` | dark `#ece1cf` | page background / inverse text |
| `mist` | `#d9d2d6` | — | neutral |
| `white` | `#ffffff` | — | surfaces / cards |

## Semantic roles (light)

| Role | Value |
|---|---|
| `fg-1` / `fg-2` / `fg-inverse` | charcoal / charcoal-soft / cream |
| `bg-page` / `bg-surface` / `bg-surface-sunken` | cream / white / cream-dark |
| `border-subtle` / `border-strong` | charcoal @ 14% / charcoal |
| `accent-primary` (hover/active) | sunset-orange (→ sunset-orange-dark) |
| `accent-secondary` (hover) | trail-green (→ trail-green-dark) |
| `state-success` / `state-warning` / `state-info` / `state-danger` | trail-green / sunset-orange / dusk-mauve / `#b5473a` |

Dark-mode role values: see the light/dark table in `streamlit/DELIVERABLE.md §1`
(the Streamlit deliverable ships light-only but documents the full dark fork).

## Result-box status colours (from `streamlit/DELIVERABLE.md §3`)

Solid fills, white text, **same hex in light and dark** (they sit on their own
fill, not the page). Hue never carries the meaning alone — border style + icon do:

| Status | Fill | Border style | Icon |
|---|---|---|---|
| Pass | `#335a2b` | 1px solid | ✓ |
| Near Limit | `#8a4d12` | 2px dashed | ⚠ triangle |
| Fail | `#a8402f` | 2px solid (thick) | ✕ |
| Not Evaluated | `#4f4d48` | 2px dotted | – dash |

## Typography

- **Display / headings:** `Quicksand` (700) — `--font-display`
- **Body:** `Karla` (400 / 500 / 700) — `--font-body`
- **Script (decorative, brand only):** `Alex Brush` — `--font-script`
- Both primary fonts are Google Fonts; Streamlit Community Cloud + a web build
  fetch them by name (no self-hosting needed). `mobile/prototype.html` embeds them.

| Token | Size |
|---|---|
| `text-display-1` / `-2` | `clamp(2.6rem,4vw+1rem,4.5rem)` / `clamp(2rem,3vw+1rem,3.2rem)` |
| `text-h1` / `h2` / `h3` | `clamp(1.7rem,1.5vw+1rem,2.4rem)` / `1.6rem` / `1.25rem` |
| `text-body-lg` / `body` / `small` / `caption` | `1.15rem` / `1rem` / `0.875rem` / `0.75rem` |

Leading: tight `1.1`, snug `1.3`, normal `1.55`, loose `1.7`.
Weights: regular `400`, medium `500`, bold `700`.

## Spacing

`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128` px (`--space-1` … `--space-10`).

## Radius

`sm 8px · md 14px · lg 22px · pill 999px`. (The Streamlit `[theme]` block sets
`baseRadius = "1rem"` ≈ 16px as its single global value.)

## Shadows

`--shadow-color: 220 10% 20%` (HSL). `sm` = `0 1px 2px …/.08, 0 1px 1px …/.06`;
`md` = `0 6px 16px …/.12, 0 2px 4px …/.08`; `lg` = `0 16px 40px …/.18, 0 4px 10px …/.1`.

## Per-surface deliverables

| Surface | Where | Notes |
|---|---|---|
| Mobile | `mobile/prototype.html` | 440px interactive prototype, light/dark toggle, full wizard + results. The authoritative render. |
| Streamlit | `streamlit/` | `config.toml` + `results.py` + `main()` patch + `DELIVERABLE.md`. Ships light-only. |
| Web | `web/` | FastAPI `api/` + React `frontend/` (`src/theme.ts` mirrors these tokens). |
