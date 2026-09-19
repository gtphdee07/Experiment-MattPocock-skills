"""FastAPI app factory for the Towing Limit Checker's Account/Garage backend.

Wires fastapi-users' session-cookie auth (registration, login, logout,
`GET/PATCH /users/me`) onto the `Account`/`AccountSession` tables, adds the
one custom route fastapi-users doesn't ship by default - a self-service
`DELETE /users/me` (its own built-in `DELETE /users/{id}` is
superuser-on-other-accounts only) - registers issue #20's session-
authenticated photo-OCR/axle-count-lookup proposal endpoints (see
`towing_backend.photo_ocr`), and exposes an unauthenticated
`GET /api/health`, carrying forward the CORS/health conventions from
`docs/design/web/api/main.py`.

Everything wired here is `async def`: fastapi-users' routers and its
`SQLAlchemyUserDatabase`/`SQLAlchemyAccessTokenDatabase` adapters (>=6)
only accept an `AsyncSession` - there is no sync adapter to fall back to
in the currently-installed version - so the Account/session boundary runs
async even though ADR 0011 otherwise calls for sync endpoints. `GET
/api/health`, which touches no database, stays a plain sync `def` to match
the reference implementation's style where nothing forces otherwise.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.calculator import build_calculator_router, rate_limit_key
from towing_backend.db import make_engine, make_session_factory
from towing_backend.migrate import run_migrations
from towing_backend.models import Account, AccountSession
from towing_backend.photo_ocr import PhotoOCRDependencies, build_photo_ocr_router
from towing_backend.profiles_routes import build_profile_router
from towing_backend.schemas import AccountCreate, AccountRead, AccountUpdate
from towing_backend.settings import Settings, load_settings
from towing_backend.sync_db import make_sync_engine, make_sync_session_factory
from towing_backend.users import AccountManager
from towing_backend.weigh_events_routes import build_weigh_events_router

COOKIE_NAME = "towing_backend_session"
# Two weeks - a reasonable v1 default; not a value the issue grilled.
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 14


def create_app(
    settings: Settings | None = None,
    photo_ocr_dependencies: PhotoOCRDependencies | None = None,
) -> FastAPI:
    settings = settings if settings is not None else load_settings()

    run_migrations(settings.database_url)

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    # Issue #21: a second, synchronous engine/session factory pointed at the
    # same database, for `towing_app.services.record_weigh_event` (reused
    # unmodified, fully synchronous) - never the async engine above. See
    # `towing_backend.sync_db`'s module docstring.
    sync_engine = make_sync_engine(settings.database_url)
    sync_session_factory = make_sync_session_factory(sync_engine)

    async def get_async_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def get_account_db(
        session: AsyncSession = Depends(get_async_session),
    ) -> AsyncIterator[SQLAlchemyUserDatabase[Account, int]]:
        yield SQLAlchemyUserDatabase(session, Account)

    async def get_session_db(
        session: AsyncSession = Depends(get_async_session),
    ) -> AsyncIterator[SQLAlchemyAccessTokenDatabase[AccountSession]]:
        yield SQLAlchemyAccessTokenDatabase(session, AccountSession)

    async def get_account_manager(
        account_db: SQLAlchemyUserDatabase[Account, int] = Depends(get_account_db),
        session: AsyncSession = Depends(get_async_session),
    ) -> AsyncIterator[AccountManager]:
        yield AccountManager(account_db, session, settings.secret)

    cookie_transport = CookieTransport(
        cookie_name=COOKIE_NAME,
        cookie_max_age=SESSION_LIFETIME_SECONDS,
        # Local dev/test runs over plain HTTP; tighten to True once this is
        # actually served over HTTPS (deploy-time config, not a spec
        # decision - see ADR 0011's "specific PaaS host" consequence).
        cookie_secure=False,
    )

    def get_database_strategy(
        session_db: SQLAlchemyAccessTokenDatabase[AccountSession] = Depends(
            get_session_db
        ),
    ) -> DatabaseStrategy[Account, int, AccountSession]:
        return DatabaseStrategy(session_db, lifetime_seconds=SESSION_LIFETIME_SECONDS)

    auth_backend: AuthenticationBackend[Account, int] = AuthenticationBackend(
        name="session",
        transport=cookie_transport,
        get_strategy=get_database_strategy,
    )

    fastapi_users = FastAPIUsers[Account, int](get_account_manager, [auth_backend])
    current_active_account = fastapi_users.current_user(active=True)

    app = FastAPI(title="Towing Limit Checker Backend")

    # Issue #38: `/api/evaluate` is the one unauthenticated route (the free
    # calculator has to stay anonymous, ADR 0013), so it gets a per-IP rate
    # limit instead of the session-auth gate every other route relies on -
    # see `towing_backend.calculator.rate_limit_key`'s own docstring for why
    # that's a hand-written key function, not one of slowapi's built-ins.
    limiter = Limiter(key_func=rate_limit_key)
    app.state.limiter = limiter
    # slowapi's own handler is typed against a plain `Exception`, narrower
    # than Starlette's `add_exception_handler` signature expects - a stub
    # gap in the library itself, not a real type error here.
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
    app.add_middleware(SlowAPIMiddleware)

    # Narrowed to the deployed frontend origin via env-driven settings
    # (issue #18 Story 17) - never "*", unlike the stateless reference
    # implementation this extends, since credentialed (cookie-bearing)
    # cross-origin requests need a specific origin, not a wildcard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_register_router(AccountRead, AccountCreate),
        prefix="/auth",
        tags=["auth"],
    )

    # Registered *before* `get_users_router` below: Starlette matches
    # routes in registration order, and that router's own built-in
    # `DELETE /users/{id}` (superuser-only) would otherwise match
    # `/users/me` first - "me" satisfies the `{id}` path parameter just
    # fine - and shadow this route with a spurious 403.
    @app.delete(
        "/users/me",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        tags=["users"],
    )
    async def delete_me(
        account: Account = Depends(current_active_account),
        account_manager: AccountManager = Depends(get_account_manager),
    ) -> None:
        await account_manager.delete(account)

    app.include_router(
        fastapi_users.get_users_router(AccountRead, AccountUpdate),
        prefix="/users",
        tags=["users"],
    )

    # Issue #19: Truck/Trailer Profile CRUD, scoped to the caller's own
    # Garage via the same `current_active_account`/`get_async_session`
    # dependencies the Account routes above already use.
    app.include_router(
        build_profile_router(
            current_active_account=current_active_account,
            get_async_session=get_async_session,
        ),
        tags=["profiles"],
    )

    # Issue #20: photo-OCR / axle-count-lookup proposal endpoints. Session-
    # authenticated via the same `current_active_account` dependency as
    # every other protected route above, despite writing nothing to any
    # Account's data - required to keep the real-Anthropic-API spend behind
    # a signed-in Account.
    app.include_router(
        build_photo_ocr_router(current_active_account, photo_ocr_dependencies)
    )

    # Issue #21: Weigh Event creation and history, scoped to the caller's
    # own Garage via the same dependencies every other protected route above
    # uses.
    app.include_router(
        build_weigh_events_router(
            current_active_account=current_active_account,
            get_async_session=get_async_session,
            sync_session_factory=sync_session_factory,
        ),
        tags=["weigh-events"],
    )

    # Issue #38: the free calculator's own endpoint - unauthenticated by
    # design, registered last since it needs no dependency on any of the
    # Account-scoped machinery above.
    app.include_router(build_calculator_router(limiter), tags=["calculator"])

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app
