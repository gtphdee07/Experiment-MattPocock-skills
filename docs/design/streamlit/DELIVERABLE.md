# Towing Limit Checker — Streamlit theme deliverable

Ships as **base = "light"**, one committed look (your pick — not OS-responsive).
Dark-mode column below documents the fixed-fill result boxes and banner tints, which
must hold up regardless of viewer mode per the brief's hard constraint, and gives you
a ready fork to `base = "dark"` later if you want a true toggle.

## 1. Palette table

| Role | Light | Dark | Intent |
|---|---|---|---|
| Background | `#f6efe4` | `#201f1c` | page |
| Secondary background | `#ece1cf` | `#242320` | sidebar / sunken widgets |
| Surface (cards) | `#ffffff` | `#2c2b28` | forms |
| Text | `#2a2a28` | `#f6efe4` | primary ink |
| Text muted | `#4a4844` | `#cbc3b6` | helper copy |
| Border | `#ddd3c0` | `rgba(246,239,228,.16)` | hairlines |
| Primary accent | `#f0942f` | `#f0942f` | Next / primary CTA |
| Link | `#33552b` | `#8bbf72` | links, secondary button text |
| Status — Pass | `#335a2b` | `#335a2b` | fixed fill, white text |
| Status — Near Limit | `#8a4d12` | `#8a4d12` | fixed fill, white text |
| Status — Fail | `#a8402f` | `#a8402f` | fixed fill, white text |
| Status — Not Evaluated | `#4f4d48` | `#4f4d48` | fixed fill, white text |
| Banner — error tint | `#fbe9e6` / text `#8a2f24` | `#3a201c` / text `#f2a99c` | Fail |
| Banner — warning tint | `#fdf0e0` / text `#7a3d0d` | `#3a2a14` / text `#f0b878` | Near Limit |
| Banner — success tint | `#e9f1e3` / text `#2a4322` | `#223a1c` / text `#a8cf99` | Pass |
| Banner — info tint | `#f1eef5` / text `#4a3f60` | `#2c283a` / text `#c4b8dd` | Not Evaluated |

Status fills are the same hex in both modes (they're solid, independent of page background) —
only the box **border** changes weight/opacity by mode so it doesn't disappear against a dark page
(see §3). Banner tints are the only role with distinct light/dark values, since those sit directly
on the page background.

## 2. `.streamlit/config.toml` — drop-in `[theme]` block

See `streamlit-theme/config.toml` in this folder — copy its `[theme]` and `[theme.sidebar]`
tables verbatim into `apps/streamlit/.streamlit/config.toml`. `font`/`headingFont` name
Google Fonts (Karla / Quicksand) directly — no `[[theme.fontFaces]]` needed, Streamlit
Community Cloud fetches them itself.

## 3. Result-box spec (4 statuses × light/dark)

All boxes: white text, `8px`→`16px` (`baseRadius`-matching) corner radius, `0.7rem 0.85rem`
padding, `7rem` min-height, name `0.95rem/700`, status word `0.85rem/600`, figures line
`0.85rem/500`, reason note `0.8rem/400` at 90% opacity — same scale as today, just heavier
weights so status reads at a glance.

| Status | Fill (both modes) | Border — light | Border — dark | Icon (colorblind aid) |
|---|---|---|---|---|
| Pass | `#335a2b` | `1px solid rgba(0,0,0,.12)` | `1px solid rgba(255,255,255,.28)` | check ✓ |
| Near Limit | `#8a4d12` | `2px dashed rgba(0,0,0,.2)` | `2px dashed rgba(255,255,255,.6)` | triangle-exclamation |
| Fail | `#a8402f` | `2px solid rgba(0,0,0,.25)` | `2px solid rgba(255,255,255,.7)` | X |
| Not Evaluated | `#4f4d48` | `2px dotted rgba(0,0,0,.2)` | `2px dotted rgba(255,255,255,.4)` | dash — |

Border **style** (solid/dashed/dotted) plus the icon are the colorblind-safe signal — hue
alone never carries the meaning. Icons are small (14px) inline SVG strokes, no icon font.

## 4. Banner spec

Keep Streamlit's built-ins — no custom HTML banner needed:

| Overall status | Streamlit call |
|---|---|
| Fail | `st.error(...)` |
| Near Limit | `st.warning(...)` |
| Pass | `st.success(...)` |
| Not Evaluated | `st.info(...)` |

Copy unchanged from the current `_render_banner`. If you'd rather match the exact tint
hexes in §1 instead of Streamlit's defaults, swap to the custom-HTML banner using those values.

## 5. Typography

- **Heading font:** Quicksand (700) — `st.title`, `st.header`, sidebar step label, box name/status.
- **Body font:** Karla (400/500) — helper text, inputs, captions, figures line, disclaimer.
- **Scale:** title ~1.75rem, step header ~1.25rem, body ~1rem, helper/caption ~0.85rem,
  box name 0.95rem/700, box status 0.85rem/600, box figures 0.85rem/500, box note 0.8rem/400.

## 6. Favicon + logo

- **Favicon:** `assets/wtwt-favicon-mono.png` (64×64, monochrome charcoal mark auto-derived
  from the full logo for this deliverable — a placeholder; swap in a hand-cleaned mono mark
  when you have one). Pass as `st.set_page_config(page_icon="assets/wtwt-favicon-mono.png")`.
- **Header logo:** `assets/wtwt-logo.png` (500×500, full color) via
  `st.logo("assets/wtwt-logo.png")` at the top of `main()`. Both files must be committed
  under `apps/streamlit/` for Community Cloud to serve them.

## 7. Optional CSS polish (`st.markdown(..., unsafe_allow_html=True)`)

Both rules below are optional — each is flagged and can be dropped independently without
breaking the theme.

```html
<style>
/* OPTIONAL: sticky Back / Start-over footer on the results screen so the reset
   action is always reachable without scrolling back up on a phone. */
div[data-testid="stHorizontalBlock"]:has(button:contains("Start over")) {
  position: sticky;
  bottom: 0;
  background: var(--background-color, #f6efe4);
  padding: 0.75rem 0 0.5rem;
  border-top: 1px solid #ddd3c0;
}

/* OPTIONAL: subtle staggered entrance for the 6 result boxes. */
@keyframes twlc-rise {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
div[data-testid="column"] > div:has(> div[style*="border-radius:8px"]) {
  animation: twlc-rise 260ms ease-out both;
}
div[data-testid="column"]:nth-child(2) > div { animation-delay: 40ms; }
div[data-testid="column"]:nth-child(3) > div { animation-delay: 80ms; }
</style>
```

The `:has()`/`:contains()` selectors depend on Streamlit's current DOM test-ids and are the
brittle part the brief warns about — re-check them after any Streamlit version bump.
