# Anthropic-only OCR; Axle-Count Lookup free but per-Account capped

Now that ADR 0013's OCR Credit model directly bounds per-Account Anthropic cost exposure for the three image-based field sources (Truck Tag, Trailer Tag, Scale Ticket), a Tesseract fallback is no longer needed purely for cost containment — Claude-vision stays the sole OCR provider, with the `FieldSource` Protocol still leaving the seam open if this is ever revisited. The Axle-Count Lookup (also a Claude call, via web search, but not image-based and not covered by OCR Credit's definition) stays free to use, but is capped by a per-Account lifetime counter (ceiling to be set later) rather than being drawn from OCR Credit or left fully uncapped; once an Account exhausts its lookup allowance, the field source is skipped entirely — it never calls Claude again for that Account — and Axle Count falls back to manual entry, the same fallback pattern OCR Credit exhaustion already uses.

## Considered Options

- **Keeping Tesseract as a cheap fallback OCR provider for the three image-based sources.** Rejected — the OCR Credit purchase-and-cap model already bounds exposure directly (ADR 0013), so a lower-accuracy fallback provider buys no additional protection, only extra adapter code and the support burden of explaining degraded-accuracy results.
- **Extending OCR Credit to cover the Axle-Count Lookup too, treating every Claude call uniformly.** Rejected — the lookup is structurally rare (once per Trailer Profile, not once per Weigh Event) and isn't literally OCR (no image involved), so folding it into paid credits would charge for something users don't perceive as the feature they bought; a separate free-but-capped allowance keeps the mental model honest.
- **Leaving the Axle-Count Lookup fully unmetered.** Rejected — it's still a real Claude API cost with no revenue behind it; an unbounded free feature is exactly the cost-exposure risk the paywall exists to avoid, just relocated to a different endpoint.

## Consequences

- The lookup cap needs its own per-Account lifetime-counter field, separate from OCR Credit's balance, plus its own configurable ceiling constant — added alongside OCR Credit's fields when #32 is implemented.
- #20 (Photo OCR + axle-count lookup endpoints) now enforces two independent limits: OCR Credit balance for the three image sources, and the lookup counter for the Axle-Count Lookup. Its spec should be revisited alongside the #18 payment-first revisit already noted in ADR 0013.
