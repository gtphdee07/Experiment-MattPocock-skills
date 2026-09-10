# Android — design is done, implementation is Phase 3

The mobile design exists: **`../mobile/prototype.html`** — a 440px, fully
self-contained interactive prototype of the whole flow (5 wizard steps +
colour-coded results grid, working light/dark toggle, WTWT fonts embedded).
Open it in a browser to see the intended layout and interactions.

When Phase 3 starts, port from:

- `../mobile/prototype.html` — layout, flow, spacing, the light/dark treatment.
- `../design-tokens.md` — the WTWT palette, type scale, radius, and the
  colourblind-safe status-box spec (fill + border style + icon), to be rebuilt
  as native components.
- `../brand-assets/` — logo + favicon.
- `../web/` — the Phase 2 backend the Android app calls.

Phase 3 still gets its own `grill-with-docs` session first (native Kotlin/Compose
vs cross-platform; online-only vs an on-device port of `towing_core`'s six
comparisons; token storage; legal-review status of `LEGAL_DISCLAIMER`). See
`~/.claude/plans/nifty-crafting-pond.md`.
