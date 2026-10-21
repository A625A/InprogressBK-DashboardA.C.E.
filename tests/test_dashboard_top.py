import pytest
from sqlalchemy import event, text


@pytest.fixture
def ranked_data(app, kpi_data):
    with app.state.engine.begin() as conn:
        for identifier, amount in [(3, 300), (4, 300), (5, 150), (6, 100), (7, None)]:
            conn.execute(
                text("INSERT INTO pais (id, name) VALUES (:id, :name)"),
                {"id": identifier, "name": f"País {identifier}"},
            )
            conn.execute(
                text("INSERT INTO sac (id, fraccion, descripcion) VALUES (:id, :fraccion, :name)"),
                {"id": identifier, "fraccion": identifier * 100, "name": f"Producto {identifier}"},
            )
            conn.execute(
                text(
                    "INSERT INTO poliza_items (poliza_id, pais_id, sac_id, valor_cif_uds) VALUES (1, :id, :id, :amount)"
                ),
                {"id": identifier, "amount": amount},
            )
        # Unassigned dimensions contribute to totals, not to an invented ranking bucket.
        conn.execute(text("INSERT INTO poliza_items (poliza_id, valor_cif_uds) VALUES (1, 5000)"))


def test_top_five_requires_authentication(client):
    assert client.get("/dashboard/kpis/top-5").status_code == 401
    assert (
        client.get("/dashboard/kpis/top-5", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )


def test_top_five_uses_sql_grouping_limits_and_stable_ties(client, app, auth_headers, ranked_data):
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.upper())

    event.listen(app.state.engine, "before_cursor_execute", capture)
    try:
        response = client.get("/dashboard/kpis/top-5", headers=auth_headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    data = response.json()
    assert [(row["id"], row["valor_importado"]) for row in data["paises"]] == [
        (3, 300),
        (4, 300),
        (1, 220),
        (5, 150),
        (6, 100),
    ]
    assert [(row["id"], row["valor_importado"]) for row in data["productos"]] == [
        (3, 300),
        (4, 300),
        (1, 200),
        (5, 150),
        (6, 100),
    ]
    assert data["paises"][0]["name"] == "País 3"
    assert data["productos"][0]["fraccion"] == 300
    assert data["productos"][0]["descripcion"] == "Producto 3"
    aggregates = [sql for sql in statements if "SUM(" in sql]
    assert len(aggregates) == 2
    assert all(
        all(clause in sql for clause in ["JOIN", "GROUP BY", "ORDER BY", "LIMIT"])
        for sql in aggregates
    )


def test_empty_rankings_are_empty_lists(client, auth_headers):
    response = client.get("/dashboard/kpis/top-5", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"paises": [], "productos": []}


def test_top_returns_fewer_than_five_and_keeps_null_labels_separate(client, app, auth_headers):
    with app.state.engine.begin() as conn:
        conn.execute(text("INSERT INTO pais (id, name) VALUES (1, NULL), (2, NULL)"))
        conn.execute(
            text(
                "INSERT INTO sac (id, fraccion, descripcion) VALUES (1, NULL, NULL), (2, NULL, NULL)"
            )
        )
        conn.execute(text("INSERT INTO polizas (id, correlativo) VALUES (1, 1)"))
        conn.execute(
            text("""INSERT INTO poliza_items (poliza_id, pais_id, sac_id, valor_cif_uds) VALUES
            (1, 1, 1, -10), (1, 2, 2, NULL), (1, 2, 2, NULL)""")
        )
    response = client.get("/dashboard/kpis/top-5", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["paises"] == [
        {"id": 2, "name": None, "valor_importado": 0.0},
        {"id": 1, "name": None, "valor_importado": -10.0},
    ]
    assert body["productos"] == [
        {"id": 2, "fraccion": None, "descripcion": None, "valor_importado": 0.0},
        {"id": 1, "fraccion": None, "descripcion": None, "valor_importado": -10.0},
    ]
