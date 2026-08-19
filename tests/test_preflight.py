"""Preflight behaviour.

The distinction these pin is the one that made the first Railway deploy
unreadable: a missing variable and an unreachable database must not produce
the same failure.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from robotics_radar.config import ConfigError, Settings, visible_database_env_vars
from robotics_radar.preflight import wait_for_database


@pytest.fixture
def no_db_env(monkeypatch):
    """Strip every database-ish variable, as an unlinked service would see."""
    import os

    for name in list(os.environ):
        if name.upper().startswith(("DATABASE", "PG", "POSTGRES")):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from robotics_radar.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestConfig:
    def test_missing_database_url_has_no_localhost_fallback(self, no_db_env):
        """A localhost default would mask an unset variable as a dead server."""
        s = Settings(_env_file=None)
        assert s.database_url is None
        with pytest.raises(ConfigError):
            _ = s.sqlalchemy_url

    def test_error_names_the_variable_and_the_remedy(self, no_db_env):
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


class TestFallbackResolution:
    """Railway supplies a connection in more than one shape. Accept all of them."""

    def test_database_url_wins(self, no_db_env, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@primary:5432/db")
        monkeypatch.setenv("PGHOST", "parts")
        monkeypatch.setenv("PGUSER", "u")
        monkeypatch.setenv("PGDATABASE", "db")
        s = Settings(_env_file=None)
        assert s.database_url_source == "DATABASE_URL"
        assert "primary" in s.sqlalchemy_url

    def test_composes_from_libpq_parts(self, no_db_env, monkeypatch):
        monkeypatch.setenv("PGHOST", "db.internal")
        monkeypatch.setenv("PGPORT", "5433")
        monkeypatch.setenv("PGUSER", "radar")
        monkeypatch.setenv("PGPASSWORD", "s3cr3t")
        monkeypatch.setenv("PGDATABASE", "radar")
        s = Settings(_env_file=None)
        assert s.database_url_source == "PGHOST/PGUSER/PGDATABASE"
        assert s.sqlalchemy_url == "postgresql+psycopg://radar:s3cr3t@db.internal:5433/radar"

    def test_password_special_characters_are_encoded(self, no_db_env, monkeypatch):
        """An unencoded @ or / in a password silently corrupts the host."""
        monkeypatch.setenv("PGHOST", "db.internal")
        monkeypatch.setenv("PGUSER", "radar")
        monkeypatch.setenv("PGPASSWORD", "p@ss/word")
        monkeypatch.setenv("PGDATABASE", "radar")
        url = Settings(_env_file=None).sqlalchemy_url
        assert "p%40ss%2Fword" in url
        assert url.count("@") == 1

    def test_public_url_is_last_resort(self, no_db_env, monkeypatch):
        monkeypatch.setenv("DATABASE_PUBLIC_URL", "postgresql://u:p@public:5432/db")
        s = Settings(_env_file=None)
        assert s.database_url_source == "DATABASE_PUBLIC_URL"

    def test_incomplete_parts_do_not_compose_a_broken_url(self, no_db_env, monkeypatch):
        monkeypatch.setenv("PGHOST", "db.internal")  # no user, no database
        with pytest.raises(ConfigError):
            _ = Settings(_env_file=None).sqlalchemy_url


class TestDiagnostics:
    def test_reports_when_nothing_is_linked(self, no_db_env):
        assert visible_database_env_vars() == []
        with pytest.raises(ConfigError) as exc:
            _ = Settings(_env_file=None).sqlalchemy_url
        assert "NO database-related variables" in str(exc.value)

    def test_lists_partially_linked_variables_by_name(self, no_db_env, monkeypatch):
        monkeypatch.setenv("PGHOST", "db.internal")
        assert "PGHOST" in visible_database_env_vars()
        with pytest.raises(ConfigError) as exc:
            _ = Settings(_env_file=None).sqlalchemy_url
        assert "PGHOST" in str(exc.value)

    def test_never_prints_credential_values(self, no_db_env, monkeypatch):
        """The message goes to deploy logs; values must never appear."""
        monkeypatch.setenv("PGHOST", "db.internal")
        monkeypatch.setenv("PGPASSWORD", "hunter2-do-not-log")
        with pytest.raises(ConfigError) as exc:
            _ = Settings(_env_file=None).sqlalchemy_url
        message = str(exc.value)
        assert "PGPASSWORD" in message
        assert "hunter2-do-not-log" not in message
