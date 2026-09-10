# The shared tiers are single-shot; each frontend owns its own review/confirm/retry UX

When the flat CLI was split (ADR 0008), a lot of the interactive collection code — the re-prompt-until-valid loops, the per-field "OCR returned `None`, fall back to a typed value" flow, the batch confirm-or-discard gate before anything is saved — looked like domain-adjacent logic that belonged in the shared tier. We deliberately did **not** move it there. The shared tiers (`towing-core`, `towing-app`) expose single-shot use-case functions that take complete inputs and return either a domain result or a structured `list[Problem]`; they never call `input()`, never `print()`, and never drive a prompt loop. All of the conversational logic stays in `apps/cli` (`prompt.py` / `collect.py` / the `run_*` flows). Each future frontend (Streamlit, web, Android) builds its own review/confirm/retry experience on top of the same use cases.

`towing_app.services.record_weigh_event(...)` is the concrete embodiment: it takes fully-formed `TruckProfile` / `TrailerProfile` / `CombinedTicket` / optional `SoloTicket` plus the linking and time-gap parameters, and returns `tuple[RigEvaluation, WeighEventRecord]` on success or `list[Problem]` (a structured value, **not** a raised exception) for conditions like "no Truck Profiles saved" or "profile has no id". The CLI decides how to present a `Problem`; a web backend would map the same list to a `422` body; Streamlit would render it inline. None of them inherit a prompt.

## Why

- **Framework-agnostic core with no I/O leak.** A use case that takes an `emit` callback or a `read` function has already picked a UX shape. Returning data and letting the caller render keeps the core testable without `capsys` and keeps web/Android from having to stub terminal I/O.
- **Review UX is genuinely per-surface.** A CLI re-prompts inline; a web form shows all fields with inline validation and a single submit; a phone shows the OCR'd values over the photo for tap-to-correct. There is no single "confirm-or-retry" flow that serves all three — trying to share one would force the lowest common denominator on every frontend.
- **`Problem` as data, not an exception.** Exceptions force the caller into `try/except` control flow and lose the "here are all the things wrong at once" shape. A `list[Problem]` is directly renderable and directly serializable.

## Considered options

- **Move the interactive collectors into `towing-app` behind an injected `emit`/`read` sink.** Rejected: the sink is still a UX commitment, the `capsys`-based tests would have to move with it, and the backend would carry terminal-interaction code it never runs. The `emit=print` default was kept *within `apps/cli`* only, so the ~280 existing flow tests pass unchanged.
- **A shared "wizard engine" describing steps declaratively.** Rejected as speculative — three frontends with three genuinely different interaction models is not enough evidence to design a cross-framework abstraction, and it would be hard to reverse once each frontend depended on it.

## Consequences

- Each frontend re-implements its own confirm/retry/manual-fallback flow. This is accepted duplication — the alternative (a shared abstraction over three dissimilar UIs) is worse.
- The single-shot boundary is what lets `apps/cli` keep the "evaluate → render → persist" ordering and the exact printed output it always had, verified by the pre-existing CLI-flow test suite (now in `apps/cli/tests/`) and a baseline transcript diff.
- Adding a frontend means writing a new client over `towing_app.services` (or `towing_core` directly for a stateless surface), not extending the shared tier with new interaction hooks.
