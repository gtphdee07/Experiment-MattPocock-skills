# Account stays out of `towing-core`; a Garage is owned by exactly one Account

Phase 2 introduces real user Accounts for the web app. `towing_core`'s storage Protocols (`TruckStore`, `TrailerStore`, `WeighEventStore`) are imported unchanged by the CLI and the Streamlit calculator, neither of which has a login. We decided Account is a **backend-only** concept: it does not enter `towing_core`'s Protocols at all. The backend's own persistence layer (SQLAlchemy Core, see ADR 0011) scopes rows by an `account_id` column that `towing_core` knows nothing about. Every Garage belongs to exactly one Account (1:1).

## Why

- ADR 0008 committed `towing_core` to being the dependency-free compute tier imported unchanged by every surface — including two, CLI and Streamlit, that will never have accounts. Threading an `account_id` through `TruckStore.list()` / `.save()` / etc. would force those two surfaces to pass a dummy value forever, pulling a web-specific concept into the tier ADR 0008 deliberately kept framework-agnostic.
- 1:1 Garage:Account is the simplest model and matches CONTEXT.md's pre-existing Garage definition ("the user's saved collection...") almost exactly — there was never an implied multi-garage or shared-garage design to preserve.
- It stays additive: the backend's schema carries an `account_id` column from day one regardless, so adding Garage sharing or multiple garages per Account later is a new join table or a relaxed uniqueness constraint, not a breaking migration or a change to `towing_core`.

## Considered options

- **Extend `towing_core`'s storage Protocols with an `account_id` parameter, shared across every surface.** Rejected: forces the CLI and Streamlit calculator, which have no login, to pass `None`/a dummy value everywhere, and pulls a web-specific concept into the tier ADR 0008 deliberately kept pure.
- **Multiple Garages per Account.** Rejected for v1: no product need surfaced for it, and it adds a garage-switcher step nothing in the design asked for. Revisit if real usage shows a need (e.g. someone managing two households' rigs).
- **A Garage shared across multiple Accounts** (e.g. a couple). Rejected for v1: matches some real usage, but needs a membership/permissions model this early — same "revisit later, additively" reasoning as above.

## Consequences

- `packages/towing-core/towing_core/storage.py`'s Protocols do not change for Phase 2. `test_layering.py` still enforces `towing_core` importing nothing web-specific.
- `apps/backend` (not yet built) defines its own account-scoped persistence — SQLAlchemy Core tables with an `account_id` column — storing the same domain dataclasses (`TruckProfile`, `TrailerProfile`, `WeighEventRecord`, etc.) without being required to implement `towing_core`'s Protocols verbatim.
- CONTEXT.md gained **Account** (backend-only, added 2026-09-11) and a tightened **Garage** definition: owned 1:1 by an Account in the web app; still one implicit, unowned Garage in the CLI and the Streamlit calculator.
