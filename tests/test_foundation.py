import pytest
from pydantic import ValidationError
from sqlalchemy import text


def test_settings_reject_missing_or_short_secret(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short", _env_file=None)


def test_foreign_keys_enabled_on_each_connection(tmp_path):
    from app.db.session import build_engine

    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.connect() as one, engine.connect() as two:
            assert one.scalar(text("PRAGMA foreign_keys")) == 1
            assert two.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()


def test_app_does_not_create_database_on_startup(tmp_path):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    db_path = tmp_path / "untouched.db"
    settings = Settings(jwt_secret="a" * 32, database_url=f"sqlite:///{db_path}")
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
    assert not db_path.exists()
