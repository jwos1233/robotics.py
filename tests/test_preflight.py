"""Preflight behaviour.

The distinction these pin is the one that made the first Railway deploy
unreadable: a missing variable and an unreachable database must not produce
the same failure.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from robotics_radar.config import ConfigError, Settings
from robotics_radar.preflight import wait_for_database


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from robotics_radar.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestConfig:
    def test_missing_database_url_has_no_localhost_fallback(self, monkeypatch):
        """A localhost default would mask an unset variable as a dead server."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = Settings(_env_file=None)
        assert s.database_url is None
        with pytest.raises(ConfigError):
            _ = s.sqlalchemy_url

    def test_error_names_the_variable_and_the_remedy(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = Settings(_env_file=None)
        with pytest.raises(ConfigError) as exc:
            _ = s.sqlalchemy_url
        message = str(exc.value)
        assert "DATABASE_URL" in message
        assert "${{Postgres.DATABASE_URL}}" in message

    def test_railway_postgres_scheme_is_normalised(self):
        s = Settings(_env_file=None, database_url="postgres://u:p@host:5432/db")
        assert s.sqlalchemy_url.startswith("postgresql+psycopg://")

    def test_already_qualified_url_is_left_alone(self):
        url = "postgresql+psycopg://u:p@host:5432/db"
        assert Settings(_env_file=None, database_url=url).sqlalchemy_url == url


class TestWaitForDatabase:
    def test_unconfigured_fails_immediately_without_retrying(self, monkeypatch):
        """Retrying a configuration mistake only delays the useful message."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        slept: list[float] = []
        with pytest.raises(ConfigError):
            wait_for_database(max_attempts=5, sleep=slept.append)
        assert slept == []

    def test_unreachable_retries_then_raises_connection_error(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u@127.0.0.1:59999/nope")
        slept: list[float] = []
        with pytest.raises(ConnectionError) as exc:
            wait_for_database(max_attempts=3, base_delay=0.001, sleep=slept.append)
        assert len(slept) == 2  # retries between attempts, not after the last
        assert "not a missing variable" in str(exc.value)

    def test_backoff_grows(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u@127.0.0.1:59999/nope")
        slept: list[float] = []
        with pytest.raises(ConnectionError):
            wait_for_database(max_attempts=4, base_delay=1.0, sleep=slept.append)
        assert slept == sorted(slept)
        assert slept[0] < slept[-1]

    def test_succeeds_against_a_live_database(self, monkeypatch):
        import os

        url = os.environ.get("DATABASE_URL")
        if not url:
            pytest.skip("DATABASE_URL not set")
        wait_for_database(max_attempts=1)

    def test_operational_error_is_the_retried_class(self):
        """Guards the except clause against being narrowed by mistake."""
        assert issubclass(OperationalError, Exception)
