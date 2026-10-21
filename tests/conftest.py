import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.init import initialize_database
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        jwt_secret="test-only-secret-with-at-least-32-characters",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    application = create_app(settings)
    initialize_database(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    from app.core.security import current_user

    @app.get("/protected-test", dependencies=[Depends(current_user)])
    def protected_test():
        return {"ok": True}

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    credentials = {"username": "tester", "password": "test-password-123"}
    assert client.post("/register", json=credentials).status_code == 201
    response = client.post("/login", json=credentials)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}
