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


@pytest.fixture
def dimensions(app):
    from sqlalchemy import text

    with app.state.engine.begin() as conn:
        for table in ["aduanas", "tipo_regimen", "pais", "tipo_unidad_medida"]:
            conn.execute(text(f"INSERT INTO {table} (id, name) VALUES (1, 'Uno'), (2, 'Dos')"))
        conn.execute(
            text("INSERT INTO sac (id, fraccion, descripcion) VALUES (1, 101, 'A'), (2, 202, 'B')")
        )


@pytest.fixture
def policy_payload(dimensions):
    return {
        "correlativo": 12345,
        "fecha_declaracion": "2025-05-01",
        "tipo_cambio_dolar": 7.65,
        "aduana_id": 1,
        "tipo_regimen_id": 1,
        "items": [
            {
                "sac_id": 1,
                "pais_id": 1,
                "tipo_unidad_medida_id": 1,
                "cantidad_fraccion": 2,
                "tasa_dai": 5,
                "valor_dai": 10,
                "valor_cif_uds": 200,
                "tasa_cif_cantidad_fraccion": 100,
            },
            {
                "sac_id": 2,
                "pais_id": 2,
                "tipo_unidad_medida_id": 2,
                "cantidad_fraccion": 1,
                "tasa_dai": 0,
                "valor_dai": 0,
                "valor_cif_uds": 30,
                "tasa_cif_cantidad_fraccion": 30,
            },
        ],
    }
