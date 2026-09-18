# Backend auth boundary is async, not sync (amends ADR 0011)

`fastapi-users`' currently-installed SQLAlchemy adapter (`fastapi-users-db-sqlalchemy`, pinned via `fastapi-users[sqlalchemy]>=14.0`) only ships an async `SQLAlchemyUserDatabase`/`SQLAlchemyAccessTokenDatabase` — verified directly against the installed package: `SQLAlchemyUserDatabase.__init__` takes `session: AsyncSession`, with no sync variant exported. So `apps/backend`'s Account/session boundary (registration, login, logout, `GET/PATCH /users/me`, the custom `DELETE /users/me`) runs fully `async def`, amending ADR 0011's general "synchronous endpoints" decision for this one boundary. `GET /api/health`, which touches no database, stays sync since nothing forces otherwise. Discovered and verified while implementing issue #18 (2026-09-18).

## Consequences

Every backend feature built after this one (#19 Garage CRUD, #20 OCR/lookup, #21 Weigh Event, #32 purchases) mixes async auth-boundary route handlers with the rest of the codebase's synchronous business logic (`towing_app.services`, the `Sqlite*Store` classes, the Claude-vision adapters — all sync per ADR 0009). Any async route handler that calls into that sync code must explicitly offload it (FastAPI's `run_in_threadpool`, or `anyio.to_thread.run_sync`) rather than calling it directly — a blocking call made straight from an `async def` route (synchronous SQLite I/O, a synchronous Anthropic API call) blocks the whole event loop and degrades every other in-flight request, the opposite of what async is for. This is a real constraint on every future backend build, not just a note.

## Considered Options

- **Hand-rolling the Account/session persistence layer to keep it sync.** Rejected — defeats ADR 0011's own stated reason for choosing `fastapi-users`: not hand-rolling a security-sensitive primitive (password hashing, session tokens) the library already solves.
- **Pinning an older `fastapi-users-db-sqlalchemy` version with sync support, if one exists.** Not pursued — trades a current, maintained dependency for a likely-unmaintained older one, purely to match a style preference against a real security-sensitive library. Not worth it.
