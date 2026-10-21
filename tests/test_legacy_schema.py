"""Compatibility against the supplied DDL, without importing or running the ETL."""

import ast
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.init import initialize_database
from app.main import create_app


def test_initialization_preserves_legacy_tables_and_nullable_data(tmp_path):
    database = tmp_path / "legacy.db"
    tree = ast.parse((Path(__file__).parents[1] / "setup.py").read_text())
    schema = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_schema"
    )
    with sqlite3.connect(database) as conn:
        for node in ast.walk(schema):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
            ):
                sql = ast.literal_eval(node.args[0])
                assert sql.lstrip().upper().startswith("CREATE ")
                conn.execute(sql)
        conn.execute("INSERT INTO pais (name) VALUES ('País de prueba')")
        conn.execute(
            "INSERT INTO polizas (correlativo, fecha_declaracion) VALUES (100, '2025-01-01')"
        )
        conn.execute("INSERT INTO poliza_items (poliza_id) VALUES (1)")
        before = dict(conn.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL"))
    settings = Settings(
        database_url=f"sqlite:///{database}",
        jwt_secret="test-only-secret-with-at-least-32-characters",
    )
    app = create_app(settings)
    try:
        initialize_database(app.state.engine)
        initialize_database(app.state.engine)
        with app.state.engine.connect() as conn:
            after = dict(
                conn.execute(text("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL"))
                .tuples()
                .all()
            )
            assert all(after[name] == sql for name, sql in before.items())
            assert "users" in after
            assert conn.scalar(text("SELECT count(*) FROM polizas")) == 1
            assert conn.scalar(text("SELECT count(*) FROM poliza_items")) == 1
        with TestClient(app) as client:
            credentials = {"username": "legacy_reader", "password": "test-password-123"}
            assert client.post("/register", json=credentials).status_code == 201
            token = client.post("/login", json=credentials).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            assert client.get("/dimensions/paises", headers=headers).json() == [
                {"id": 1, "name": "País de prueba"}
            ]
            body = client.get("/polizas/1", headers=headers).json()
            assert body["correlativo"] == 100
            assert body["aduana_id"] is None
            assert body["items"][0]["valor_cif_uds"] is None
            assert client.get("/polizas", headers=headers).json()["total"] == 1
    finally:
        app.state.engine.dispose()


def test_database_rejects_invalid_fk_without_service_validation(app):
    with pytest.raises(IntegrityError), app.state.engine.begin() as conn:
        conn.execute(text("INSERT INTO polizas (correlativo, aduana_id) VALUES (100, 999)"))
    with app.state.engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM polizas")) == 0
