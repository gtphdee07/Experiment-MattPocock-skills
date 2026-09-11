# Phase 2 backend stack: synchronous FastAPI, SQLAlchemy Core, Alembic, fastapi-users with session cookies

`apps/backend` needs to talk to Postgres (SQLite locally; "SQLite now, Postgres later" was settled during the original architecture grilling), track schema changes over time, authenticate real Accounts, and map `towing_core`'s frozen dataclasses to JSON at the HTTP boundary. Grilled during the Phase 2 session (2026-09-11) against the alternatives below.

**Decisions:**
- Persistence via **SQLAlchemy Core** (not the full ORM) — a typed query builder + engine abstraction, without an ORM's object-identity/session machinery duplicating the domain's existing frozen-dataclass model.
- **Synchronous** endpoints — FastAPI runs sync handlers in a threadpool automatically; matches every other layer in the codebase (`towing_app.services`, the `Sqlite*Store` classes, the Claude-vision calls), all sync per ADR 0009's single-shot design.
- **Alembic** for migrations.
- **fastapi-users** for registration/login, using its **session-cookie** auth backend (not JWT).
- **No email verification** at registration for v1.
- Pydantic boundary classes **hand-written per endpoint** (one small input/output class per route, matching the `docs/design/web/api/main.py` reference's `TruckIn`/`CheckOut` style), not generated through a shared mapping helper.

## Why

- Consistency with the existing codebase mattered more than "the modern FastAPI default." Every other tier is sync and returns plain dataclasses (ADR 0009); going async here would mean either wrapping every sync call in a threadpool by hand (no real gain over FastAPI's own threadpool-by-default for sync handlers) or rewriting `services.py` and the `Sqlite*Store` classes to async, for a traffic level this app doesn't have.
- SQLAlchemy Core keeps the persistence layer closer to the hand-written-SQL style already used in `towing_app/sqlite.py` than a full ORM would, while still buying Alembic and real Postgres portability — the two things raw `sqlite3` + `CREATE TABLE IF NOT EXISTS` genuinely lacked.
- fastapi-users avoids hand-rolling password hashing and session handling — a security-sensitive area not worth reinventing — without adding a paid third-party account the way a hosted auth provider would.
- Session cookies fit a single backend server; JWT's cross-server statelessness solves a problem this app doesn't have, in exchange for refresh-token rotation and careful frontend token storage.

## Considered options

- **Full SQLAlchemy ORM.** Rejected: introduces a second representation of each entity (ORM model vs. the frozen domain dataclass) that has to be kept in sync, for a domain model that's already small and stable.
- **Async FastAPI + an async driver.** Rejected for v1: would force an async rewrite of `services.py`/storage that nothing else in the codebase needs yet. The storage-Protocol seam (ADR 0008) makes swapping the backend's persistence layer possible later without touching `towing_core`, if real load ever demands it.
- **JWT (access + refresh tokens).** Rejected: solves a multi-server scaling problem this single-backend app doesn't have, at the cost of refresh-token rotation and frontend token-storage risk (XSS if mishandled).
- **A hosted auth provider** (Clerk / Auth0 / Supabase Auth). Rejected: fastest to ship, but adds a paid third-party dependency and an external account for what fastapi-users already handles safely in-process.
- **Hand-written versioned SQL migration scripts.** Rejected: works, but means building and maintaining a small migration runner that Alembic already provides as the standard tool for this stack.
- **A shared Pydantic conversion helper** (auto-mapping domain dataclasses to schemas). Rejected for v1: more indirection than the current endpoint count justifies; the reference implementation's one-class-per-endpoint style is easier to read. Revisit if the endpoint count grows enough that the duplication becomes the bigger cost.

## Consequences

- Email verification is deferred, not rejected outright — registering with any email works for v1. Adding verification later means wiring in a transactional email provider (Postmark/SendGrid/SES) and enabling fastapi-users' existing verification flow; it doesn't require a schema change.
- The backend's specific PaaS host (Railway/Fly.io/Render) and the frontend's specific static host (Vercel/Netlify/Cloudflare Pages) are implementation-time picks, not architectural commitments — any of the shortlisted options fits this stack equally.
- Photo/OCR endpoint upload-size and timeout limits are left to implementation time as a sane default, not a grilled decision.
- "Graphing of historical weights," named in the original epic, is out of scope for this ADR — it is a feature-design question for its own `to-spec` pass once the CRUD+auth backend exists, not an architecture decision.
