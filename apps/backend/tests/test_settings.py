"""Unit tests (solitary) for `towing_backend.settings.load_settings` (#33).

`load_settings` falls back to a hardcoded, publicly-known `DEFAULT_SECRET`
when `TOWING_BACKEND_SECRET` is unset - fine for local dev, a real footgun
for a misconfigured production deploy if nothing surfaces it. These tests
assert the fallback logs an unmissable warning, and that a real, explicitly
configured secret never does.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from towing_backend.migrate import run_migrations
from towing_backend.settings import DEFAULT_SECRET, load_settings


def test_fallback_secret_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="towing_backend.settings"):
        settings = load_settings(env={})

    assert settings.secret == DEFAULT_SECRET
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "TOWING_BACKEND_SECRET" in caplog.records[0].message
    assert "not set" in caplog.records[0].message.lower()


def test_configured_secret_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="towing_backend.settings"):
        settings = load_settings(
            env={"TOWING_BACKEND_SECRET": "a-real-production-secret"}
        )

    assert settings.secret == "a-real-production-secret"
    assert caplog.records == []


def test_blank_secret_env_var_also_falls_back_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # `env.get(...) or DEFAULT_SECRET` already treats an empty string the
    # same as unset (existing behavior) - the warning must fire for that
    # case too, not just a fully absent key.
    with caplog.at_level(logging.WARNING, logger="towing_backend.settings"):
        settings = load_settings(env={"TOWING_BACKEND_SECRET": ""})

    assert settings.secret == DEFAULT_SECRET
    assert len(caplog.records) == 1


def test_running_migrations_does_not_disable_pre_existing_loggers(
    tmp_path: Path,
) -> None:
    """Regression test: `alembic/env.py` calls `logging.config.fileConfig`,
    whose `disable_existing_loggers` defaults to `True` - left at that
    default, the *first* `run_migrations()` call in a process would
    permanently disable every logger already created (including this
    module's own `logger`, from `settings.py`'s #33 startup warning),
    silently defeating that fix for the rest of the process's lifetime.
    `create_app()` calls `run_migrations()` on every app construction, not
    just once via the `alembic` CLI, so this really does happen in
    practice (and does happen across this test session, run test-file by
    test-file, once anything else has already called `create_app()`)."""
    sentinel_logger = logging.getLogger("towing_backend.settings")
    assert not sentinel_logger.disabled, "logger was already disabled before this test"

    db_path = tmp_path / "migration-logging-check.db"
    run_migrations(f"sqlite+aiosqlite:///{db_path}")

    assert not sentinel_logger.disabled
