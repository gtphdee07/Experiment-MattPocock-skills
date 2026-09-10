# Design brief — Towing Limit Checker (Streamlit calculator)

Hand this to Claude Design. The output comes back here and gets applied to
`apps/streamlit/`.

## What this is

A free, no-login web calculator for RV owners. You enter your tow vehicle's
weight ratings, your trailer's ratings, and the numbers off a CAT Scale weigh
ticket; it tells you whether the loaded rig is within every legal weight
limit, as a grid of colour-coded result boxes (green / amber / red / grey).

- **Audience:** ordinary RV / travel-trailer owners, not engineers. Often
  checking on a phone in a truck-stop parking lot.
- **Tone:** trustworthy, plain, calm. A safety tool, not a marketing site.
  Fast to read, no decorative clutter. Think "well-made government form" more
  than "SaaS landing page".
- **Live app:** `apps/streamlit/streamlit_app.py`, deployed on Streamlit
  Community Cloud. Single page, a 5-step wizard then a results screen.

## Screen inventory (the full surface to style)

1. **App header** — title "Towing Limit Checker", one-line caption, an emoji
   favicon (currently ⚖️).
2. **Sidebar** — "Step N of 5" text + a "Start over" button.
3. **Wizard steps 1–4** — each: a section heading, a sentence of helper text,
   a form of numeric inputs, "Next"/"Back" buttons. Step 4 has a checkbox
   that reveals more inputs.
4. **Results screen (step 5):**
   - a **status banner** at the top (currently Streamlit's built-in
     `st.error` / `st.warning` / `st.success` / `st.info` — red / amber /
     green / blue) reflecting the worst result.
   - a **3-column grid of 6 result boxes** (custom HTML, fully restyleable —
     see below).
   - an optional advisory "Time-Gap Warning" line.
   - a small-print legal disclaimer caption.
   - "Back" / "Start over" buttons.

## The 6 result boxes — the core visual

Each box shows: a check name (e.g. "Drive Axle"), a status word, an
`actual lb vs rating lb` line, and — only for a grey box — a short reason.

Four possible statuses, with fixed traffic-light meaning:

| Status | Meaning | Current colour |
|---|---|---|
| **Pass** | within its limit | `#1a7f37` green |
| **Near Limit** | under the limit but close (only ever appears on the "Trailer GVWR" box) | `#9a6700` amber |
| **Fail** | over a legal limit | `#cf222e` red |
| **Not Evaluated** | not enough data to check this one | `#6e7781` grey |

Current box style: solid colour fill, white text, `8px` radius, ~`0.7rem`
padding, `7rem` min-height, small type (0.8–0.95rem). Column-interleaved so
row 1 is Steer / Drive / Trailer axles, row 2 is Hitched GVWR / GCWR /
Trailer GVWR.

## Where the design gets applied (technical surface — please target these exactly)

1. **`.streamlit/config.toml` `[theme]` table** (Streamlit **1.63**, so the
   full modern theming surface is available). Fill in real values for the
   keys you want to set:
   `base` (`"light"` or `"dark"`), `primaryColor`, `backgroundColor`,
   `secondaryBackgroundColor`, `textColor`, `linkColor`, `borderColor`,
   `showWidgetBorder` (bool), `baseRadius` (e.g. `"0.5rem"` or `"full"`),
   `baseFontSize` (int px), `font` / `headingFont` / `codeFont` (a family
   string, or `[[theme.fontFaces]]` blocks pointing at a **repo-committed**
   font file), and an optional `[theme.sidebar]` sub-table with the same
   keys for sidebar-specific overrides.
   Streamlit renders in the **viewer's** light/dark mode; `base` sets the
   default. If you want one committed look, say so and pick `base`.
2. **The 6 result boxes** — give me: fill colour, text colour, border, radius,
   and any leading icon/emoji, **for each of the 4 statuses, in both light
   and dark** if the theme allows both.
3. **The status banner** — either keep Streamlit's built-ins (just pick which
   of error/warning/success/info maps to each overall status) or specify a
   custom HTML banner (fill, text, icon).
4. **`st.set_page_config`** — page title, and favicon: an emoji, **or** a
   small square image committed to the repo (PNG/SVG).
5. **Header** — optional `st.logo(...)` with a logo image (again: a file that
   lives in the repo — Community Cloud serves nothing external). If you want
   a logo, provide the actual asset (SVG preferred, or PNG at 2x), plus a
   monochrome favicon version.
6. **Optional CSS polish** — a single `st.markdown("<style>…</style>",
   unsafe_allow_html=True)` block is possible but brittle across Streamlit
   releases; keep it minimal and mark each rule optional.

## Hard constraints

- **Legible in both light and dark.** No colour may be defined only for one
  mode.
- **Status must not rely on hue alone.** The four statuses have to be
  distinguishable for red-green colour blindness (use lightness/shape/icon
  differences too). The status word stays in every box regardless.
- **Traffic-light semantics are fixed:** green = good, amber = caution, red =
  over the limit, grey = not checked. Don't reassign these.
- **No external assets.** Fonts, logos, icons must be repo-committed files or
  system/Google fonts Streamlit can fetch itself. No image CDNs.
- **Phone-first.** The results grid and forms must read well at ~375px wide.
- It's a **calculator**. Keep chrome light; the result boxes are the hero.

## Deliverable — please return exactly this

1. **Palette table:** every colour role → hex for light → hex for dark, with
   a one-word note on intent.
2. **A filled-in `[theme]` block** ready to drop into `.streamlit/config.toml`
   (plus `[theme.sidebar]` if used, plus any `[[theme.fontFaces]]`).
3. **Result-box spec:** the 4 statuses × {fill, text, border, radius, icon},
   for light and dark.
4. **Banner spec:** the mapping to keep, or a custom banner spec.
5. **Typography:** heading font, body font, and the type scale for the box
   elements (name / status word / figures / reason line).
6. **Favicon + logo:** the direction, and — if a custom image — the asset
   files themselves (SVG/PNG), including a favicon-sized version.
7. **Optional CSS:** any extra rules, each clearly marked optional, as a
   single `<style>` block.

Keep rationale short. Concrete values beat paragraphs — I translate this
straight into config + code.
