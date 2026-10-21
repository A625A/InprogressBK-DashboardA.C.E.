from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.main import create_app
from app.services import dashboard

URLS = {
    "totals": "/dashboard/kpis/totals",
    "top_five": "/dashboard/kpis/top-5",
    "monthly_values": "/dashboard/kpis/valor-por-mes?year=2025",
}


@pytest.fixture
def loaders(monkeypatch):
    result = {}
    for name in URLS:
        result[name] = Mock(wraps=getattr(dashboard, name))
        monkeypatch.setattr(dashboard, name, result[name])
    return result


@pytest.fixture
def cache_clock(app, monkeypatch):
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(app.state.dashboard_cache, "_clock", clock)
    return clock


def warm(client, auth_headers):
    responses = [client.get(url, headers=auth_headers) for url in URLS.values()]
    assert all(response.status_code == 200 for response in responses)
    return [response.json() for response in responses]


@pytest.mark.parametrize("endpoint", URLS)
def test_endpoint_miss_hit_and_expiry(
    client, app, auth_headers, kpi_data, loaders, cache_clock, endpoint
):
    url = URLS[endpoint]
    first = client.get(url, headers=auth_headers)
    assert first.status_code == 200
    cache_clock.return_value += app.state.settings.dashboard_cache_ttl_seconds - 0.01
    assert client.get(url, headers=auth_headers).json() == first.json()
    assert loaders[endpoint].call_count == 1
    cache_clock.return_value = 100 + app.state.settings.dashboard_cache_ttl_seconds
    assert client.get(url, headers=auth_headers).json() == first.json()
    assert loaders[endpoint].call_count == 2


def test_endpoint_and_year_keys_are_independent_and_ignore_sensitive_query_data(
    client, app, auth_headers, kpi_data, loaders, cache_clock
):
    before = warm(client, auth_headers)
    other = "/dashboard/kpis/valor-por-mes?year=2024"
    response = client.get(other, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["year"] == 2024
    assert response.json()["meses"][11]["valor_importado"] == 20
    assert warm(client, auth_headers) == before
    assert client.get(other, headers=auth_headers).json() == response.json()
    # Only the parsed year participates, regardless of query order or extra inputs.
    assert (
        client.get(
            "/dashboard/kpis/valor-por-mes?token=private-marker&year=02025", headers=auth_headers
        ).json()
        == before[2]
    )
    assert [load.call_count for load in loaders.values()] == [1, 1, 2]
    contents = repr(app.state.dashboard_cache._entries)
    assert "private-marker" not in contents
    assert auth_headers["Authorization"].split()[1] not in contents
    assert "tester" not in contents
    assert "password" not in contents


def test_commit_invalidates_only_affected_kpis_after_data_is_durable(
    client, app, auth_headers, policy_payload, loaders, cache_clock, monkeypatch
):
    warm(client, auth_headers)
    other = "/dashboard/kpis/valor-por-mes?year=2024"
    other_result = client.get(other, headers=auth_headers).json()
    original = app.state.dashboard_cache.invalidate_policy

    def assert_committed(year):
        # A separate connection must see both header and items before invalidation.
        with app.state.engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM polizas")) == 1
            assert conn.scalar(text("SELECT count(*) FROM poliza_items")) == 2
        original(year)

    invalidation = Mock(side_effect=assert_committed)
    monkeypatch.setattr(app.state.dashboard_cache, "invalidate_policy", invalidation)
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 201
    invalidation.assert_called_once_with(2025)
    after = warm(client, auth_headers)
    assert after[0] == {"total_polizas": 1, "valor_importado_total": 230.0}
    assert sum(row["valor_importado"] for row in after[1]["paises"]) == 230
    assert after[2]["meses"][4]["valor_importado"] == 230
    assert client.get(other, headers=auth_headers).json() == other_result
    assert [load.call_count for load in loaders.values()] == [2, 2, 3]


def test_null_date_invalidates_global_kpis_only(
    client, auth_headers, policy_payload, loaders, cache_clock
):
    warm(client, auth_headers)
    policy_payload["fecha_declaracion"] = None
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 201
    after = warm(client, auth_headers)
    assert after[0]["total_polizas"] == 1
    assert all(row["valor_importado"] == 0 for row in after[2]["meses"])
    assert [load.call_count for load in loaders.values()] == [2, 2, 1]


@pytest.mark.parametrize("failure", ["duplicate", "foreign_key", "late_item", "commit", "invalid"])
def test_failures_and_rollbacks_preserve_warm_cache(
    client, app, auth_headers, policy_payload, loaders, cache_clock, monkeypatch, failure
):
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 201
    before = warm(client, auth_headers)
    invalidate = Mock(wraps=app.state.dashboard_cache.invalidate_policy)
    monkeypatch.setattr(app.state.dashboard_cache, "invalidate_policy", invalidate)
    if failure != "duplicate":
        policy_payload["correlativo"] += 1
    if failure == "foreign_key":
        policy_payload["items"][1]["pais_id"] = 999
    if failure == "invalid":
        policy_payload["items"] = []
    if failure == "late_item":
        with app.state.engine.begin() as conn:
            conn.execute(
                text("""CREATE TRIGGER reject_second_item BEFORE INSERT ON poliza_items
                WHEN NEW.cantidad_fraccion = 999
                BEGIN SELECT RAISE(ABORT, 'late failure'); END""")
            )
        policy_payload["items"][1]["cantidad_fraccion"] = 999

    def fail_commit(session):
        raise IntegrityError("COMMIT", {}, Exception("simulated commit failure"))

    session_class = app.state.session_factory.class_
    if failure == "commit":
        event.listen(session_class, "before_commit", fail_commit)
    try:
        response = client.post("/polizas", json=policy_payload, headers=auth_headers)
    finally:
        if failure == "commit":
            event.remove(session_class, "before_commit", fail_commit)
    assert response.status_code == (422 if failure in {"foreign_key", "invalid"} else 409)
    invalidate.assert_not_called()
    assert warm(client, auth_headers) == before
    assert all(load.call_count == 1 for load in loaders.values())
    with app.state.engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM polizas")) == 1
        assert conn.scalar(text("SELECT count(*) FROM poliza_items")) == 2


@pytest.mark.parametrize("endpoint", URLS)
def test_warm_cache_still_checks_missing_invalid_expired_and_deleted_user_jwt(
    client, app, auth_headers, loaders, cache_clock, endpoint
):
    url = URLS[endpoint]
    assert client.get(url, headers=auth_headers).status_code == 200
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": "1", "iat": now - timedelta(minutes=5), "exp": now - timedelta(minutes=1)},
        app.state.settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    for headers in [
        {},
        {"Authorization": "Bearer invalid"},
        {"Authorization": f"Bearer {expired}"},
    ]:
        assert client.get(url, headers=headers).status_code == 401
    with app.state.engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    assert client.get(url, headers=auth_headers).status_code == 401
    assert loaders[endpoint].call_count == 1


@pytest.mark.parametrize("endpoint", URLS)
def test_endpoint_errors_are_not_cached(client, auth_headers, monkeypatch, endpoint):
    original = getattr(dashboard, endpoint)
    loader = Mock(side_effect=HTTPException(503, "temporary failure"))
    monkeypatch.setattr(dashboard, endpoint, loader)
    assert client.get(URLS[endpoint], headers=auth_headers).status_code == 503
    assert client.get(URLS[endpoint], headers=auth_headers).status_code == 503
    loader.side_effect = original
    assert client.get(URLS[endpoint], headers=auth_headers).status_code == 200
    assert client.get(URLS[endpoint], headers=auth_headers).status_code == 200
    assert loader.call_count == 3


def test_invalid_year_is_not_cached(client, app, auth_headers, loaders):
    assert (
        client.get("/dashboard/kpis/valor-por-mes?year=secret", headers=auth_headers).status_code
        == 422
    )
    loaders["monthly_values"].assert_not_called()
    assert not app.state.dashboard_cache._entries


def test_ttl_environment_configuration_and_app_isolation(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHBOARD_CACHE_TTL_SECONDS", raising=False)
    assert Settings(jwt_secret="x" * 32, _env_file=None).dashboard_cache_ttl_seconds == 60
    monkeypatch.setenv("DASHBOARD_CACHE_TTL_SECONDS", "2.5")
    settings = Settings(
        jwt_secret="x" * 32, database_url=f"sqlite:///{tmp_path / 'unused.db'}", _env_file=None
    )
    first, second = create_app(settings), create_app(settings)
    try:
        assert first.state.dashboard_cache is not second.state.dashboard_cache
        assert first.state.dashboard_cache._ttl_seconds == 2.5
    finally:
        first.state.engine.dispose()
        second.state.engine.dispose()


@pytest.mark.parametrize("ttl", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_ttl_rejected(ttl):
    with pytest.raises(ValidationError):
        Settings(jwt_secret="x" * 32, dashboard_cache_ttl_seconds=ttl, _env_file=None)
