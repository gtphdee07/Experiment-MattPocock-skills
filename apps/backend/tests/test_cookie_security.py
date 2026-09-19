"""HTTP-level regression tests for issue #39's real root cause.

Confirmed directly against the live deployed backend before this fix:
login succeeded and set a session cookie, but every subsequent
authenticated request silently lost it, because fastapi-users defaults
the cookie's `SameSite` attribute to `Lax` - which browsers refuse to
send on a cross-site `fetch()` (only on a top-level navigation). ADR 0016
deploys `apps/web` and `apps/backend` to different registrable domains, a
genuinely cross-site relationship, so this wasn't a local-dev-only gap.

`SameSite=None` is required for a cross-site cookie to be sent at all, but
every modern browser rejects it outright unless `Secure` is also set -
these two attributes are coupled, not independent, which is why
`towing_backend.settings.Settings.cookie_secure` alone now drives both
(see `towing_backend.app.create_app`'s `CookieTransport` construction).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from towing_backend.app import create_app
from towing_backend.settings import Settings

EMAIL = "addie@example.com"
PASSWORD = "correct-horse-battery-staple"


def _settings(db_path: Path, *, cookie_secure: bool) -> Settings:
    # A local settings-builder, not conftest.py's `make_settings` - matches
    # this test directory's existing convention (test_photo_ocr_endpoints.py
    # does the same) of each file owning the settings shape it needs.
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        cors_origin="http://localhost:5173",
        secret="test-secret",
        cookie_secure=cookie_secure,
    )


def _login_set_cookie_header(tmp_path: Path, *, cookie_secure: bool) -> str:
    settings = _settings(tmp_path / "backend.db", cookie_secure=cookie_secure)
    app: FastAPI = create_app(settings)
    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register", json={"email": EMAIL, "password": PASSWORD}
        )
        assert register_response.status_code == 201, register_response.text

        login_response = client.post(
            "/auth/login", data={"username": EMAIL, "password": PASSWORD}
        )
        assert login_response.status_code == 204, login_response.text

        set_cookie = login_response.headers.get("set-cookie")
        assert set_cookie is not None, "login did not set a session cookie"
        return set_cookie


def test_cookie_secure_true_sets_samesite_none_and_secure(tmp_path: Path) -> None:
    set_cookie = _login_set_cookie_header(tmp_path, cookie_secure=True)

    assert "secure" in set_cookie.lower()
    assert "samesite=none" in set_cookie.lower()


def test_cookie_secure_false_sets_samesite_lax_and_not_secure(tmp_path: Path) -> None:
    set_cookie = _login_set_cookie_header(tmp_path, cookie_secure=False)

    assert "secure" not in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
