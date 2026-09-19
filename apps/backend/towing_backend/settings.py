"""Environment-driven configuration for the backend service.

Mirrors `apps/cli/towing_cli/cli.py`'s `resolve_db_path` pattern (an env-var
override, a project-local default) rather than reaching for a settings
framework this small service doesn't need.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DB_URL_ENV_VAR = "TOWING_BACKEND_DB_URL"
CORS_ORIGIN_ENV_VAR = "TOWING_BACKEND_CORS_ORIGIN"
SECRET_ENV_VAR = "TOWING_BACKEND_SECRET"
COOKIE_SECURE_ENV_VAR = "TOWING_BACKEND_COOKIE_SECURE"

# Development-only default DB path. `.dev-data/` is gitignored (see root
# CLAUDE.md: "Keep development activity off the app's real default data
# path") - there is no real shipped default here yet the way the CLI's
# `~/.towing_app/garage.db` is real user data, since this backend has no
# production deployment target chosen yet (ADR 0011), so a project-local
# path is the only sane default rather than inventing a fake "real" one.
DEFAULT_DB_PATH = Path(".dev-data") / "backend.db"
DEFAULT_CORS_ORIGIN = "http://localhost:5173"
# Dev-only fallback secret for fastapi-users' reset-password/verification
# token signing (both flows are deferred per ADR 0011, but BaseUserManager
# requires the attributes to be set regardless). Real deployments must set
# TOWING_BACKEND_SECRET explicitly.
DEFAULT_SECRET = "dev-only-insecure-secret-change-before-any-real-deploy"


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origin: str
    secret: str
    # #39: coupled to the session cookie's SameSite attribute in app.py, not
    # an independent flag - a cross-site deploy (frontend and backend on
    # different registrable domains, the actual shape ADR 0016 produces)
    # needs SameSite=None, which every modern browser rejects outright
    # unless Secure is also set. False (SameSite=Lax) is the right default
    # for local HTTP dev, where there's no cross-site relationship to begin
    # with.
    cookie_secure: bool = False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = env if env is not None else os.environ
    database_url = env.get(DB_URL_ENV_VAR) or f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"
    cors_origin = env.get(CORS_ORIGIN_ENV_VAR) or DEFAULT_CORS_ORIGIN
    secret = env.get(SECRET_ENV_VAR) or DEFAULT_SECRET
    cookie_secure = (env.get(COOKIE_SECURE_ENV_VAR) or "").strip().lower() == "true"
    if secret == DEFAULT_SECRET:
        # #33: a silent fallback here means every reset-password/
        # verification token gets signed with a value that's public (it's
        # in the repo) - fine for local dev, a real footgun for a deploy
        # that simply forgot to set the real one. Loud on purpose.
        logger.warning(
            "%s is not set - falling back to the insecure development "
            "secret. Do not run this in production without setting a real "
            "secret.",
            SECRET_ENV_VAR,
        )
    return Settings(
        database_url=database_url,
        cors_origin=cors_origin,
        secret=secret,
        cookie_secure=cookie_secure,
    )
