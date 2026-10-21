from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import text

CREDS = {"username": "evaluador", "password": "a-secure-password"}


def test_registration_hashes_password_and_rejects_duplicate(client, app):
    response = client.post("/register", json=CREDS)
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "evaluador"}
    with app.state.engine.connect() as conn:
        stored = conn.scalar(text("SELECT password_hash FROM users"))
    assert stored.startswith("$argon2id$")
    assert CREDS["password"] not in stored
    assert client.post("/register", json=CREDS).status_code == 409


def test_login_returns_expiring_token_and_rejects_bad_credentials(client, app):
    client.post("/register", json=CREDS)
    result = client.post("/login", json=CREDS)
    assert result.status_code == 200
    body = result.json()
    assert body["token_type"] == "bearer"
    claims = jwt.decode(
        body["access_token"], app.state.settings.jwt_secret.get_secret_value(), algorithms=["HS256"]
    )
    assert claims["sub"] == "1"
    assert claims["exp"] - claims["iat"] == 1800
    for creds in [dict(CREDS, password="wrong-password"), dict(CREDS, username="missing")]:
        response = client.post("/login", json=creds)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_registration_does_not_echo_password(client):
    response = client.post("/register", json={"username": "x", "password": "secret"})
    assert response.status_code == 422
    assert "secret" not in response.text


@pytest.mark.parametrize(
    "kind",
    [
        "expired",
        "signature",
        "missing_exp",
        "missing_sub",
        "missing_iat",
        "bad_sub",
        "unknown_user",
        "malformed",
    ],
)
def test_rejects_invalid_tokens(client, app, kind):
    client.post("/register", json=CREDS)
    now = datetime.now(UTC)
    claims = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=1)}
    key = app.state.settings.jwt_secret.get_secret_value()
    if kind == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif kind == "signature":
        key = "different-key-with-at-least-32-characters"
    elif kind.startswith("missing_"):
        del claims[kind.removeprefix("missing_")]
    elif kind == "bad_sub":
        claims["sub"] = "not-a-user-id"
    elif kind == "unknown_user":
        claims["sub"] = "9999"
    token = "bad.token" if kind == "malformed" else jwt.encode(claims, key, algorithm="HS256")
    response = client.get("/protected-test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_protected_route_requires_existing_authenticated_user(client, app):
    assert client.get("/protected-test").status_code == 401
    client.post("/register", json=CREDS)
    token = client.post("/login", json=CREDS).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/protected-test", headers=headers).status_code == 200
    with app.state.engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    assert client.get("/protected-test", headers=headers).status_code == 401


def test_deleted_user_token_cannot_authenticate_replacement_account(client, app):
    assert client.post("/register", json=CREDS).status_code == 201
    old_token = client.post("/login", json=CREDS).json()["access_token"]
    with app.state.engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    replacement = client.post("/register", json=dict(CREDS, username="replacement"))
    assert replacement.status_code == 201
    assert (
        client.get("/protected-test", headers={"Authorization": f"Bearer {old_token}"}).status_code
        == 401
    )
