"""Keep test traffic out of the presentation database, including legacy suites."""
import pytest

from gateway.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_runtime_database(tmp_path, monkeypatch):
    monkeypatch.setenv("IML_MODE", "demo")
    monkeypatch.setenv("IML_DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
