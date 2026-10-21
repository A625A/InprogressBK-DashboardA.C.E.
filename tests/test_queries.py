import pytest
from sqlalchemy import event, text


@pytest.fixture
def policies(app, dimensions):
    with app.state.engine.begin() as conn:
        for i in reversed(range(1, 26)):
            conn.execute(
                text("""INSERT INTO polizas
                (id, correlativo, fecha_declaracion, tipo_cambio_dolar, aduana_id, tipo_regimen_id)
                VALUES (:id, :correlativo, :fecha, 7.65, :aduana, :regimen)"""),
                {
                    "id": i,
                    "correlativo": 1000 + i,
                    "fecha": "2025-01-01" if i <= 2 else "2025-02-01",
                    "aduana": 1 if i % 2 else 2,
                    "regimen": 1 if i <= 3 else 2,
                },
            )
        for poliza, pais, sac in [(1, 1, 1), (1, 1, 1), (1, 2, 2), (2, 1, 2), (3, 2, 1)]:
            conn.execute(
                text("INSERT INTO poliza_items (poliza_id, pais_id, sac_id) VALUES (:p, :c, :s)"),
                {"p": poliza, "c": pais, "s": sac},
            )


def test_default_page_and_stable_sql_pagination(client, app, auth_headers, policies):
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(app.state.engine, "before_cursor_execute", capture)
    try:
        assert client.get("/polizas").status_code == 401
        response = client.get("/polizas", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 25
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert [p["id"] for p in body["items"]] == list(range(1, 21))
        assert all("items" not in p for p in body["items"])
        page2 = client.get("/polizas?page=2", headers=auth_headers).json()
        assert [p["id"] for p in page2["items"]] == [21, 22, 23, 24, 25]
        beyond = client.get("/polizas?page=3", headers=auth_headers).json()
        assert beyond["items"] == [] and beyond["total"] == 25
        all_rows = client.get("/polizas?page_size=100", headers=auth_headers).json()
        assert len(all_rows["items"]) == 25
    finally:
        event.remove(app.state.engine, "before_cursor_execute", capture)
    list_sql = [s.upper() for s in statements if "FROM polizas" in s and "COUNT(" not in s.upper()]
    assert list_sql
    assert all("ORDER BY POLIZAS.ID" in s and "LIMIT" in s and "OFFSET" in s for s in list_sql)
    assert not any("FROM poliza_items" in s for s in statements)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("correlativo=1002", [2]),
        ("fecha_desde=2025-01-01&fecha_hasta=2025-01-01", [1, 2]),
        ("tipo_regimen_id=1", [1, 2, 3]),
        ("aduana_id=2&tipo_regimen_id=1", [2]),
        ("pais_id=1", [1, 2]),
        ("sac_id=1", [1, 3]),
        ("pais_id=1&sac_id=2", [2]),
        ("pais_id=1&aduana_id=1&fecha_hasta=2025-01-01", [1]),
        ("correlativo=9999", []),
    ],
)
def test_filters_run_before_pagination_without_duplicate_headers(
    client, auth_headers, policies, query, expected
):
    body = client.get("/polizas?" + query + "&page_size=1", headers=auth_headers).json()
    assert body["total"] == len(expected)
    assert [p["id"] for p in body["items"]] == expected[:1]
    if len(expected) > 1:
        page2 = client.get("/polizas?" + query + "&page_size=1&page=2", headers=auth_headers).json()
        assert [p["id"] for p in page2["items"]] == expected[1:2]


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=0",
        "page_size=101",
        "page=-1",
        "page=abc",
        "fecha_desde=invalid",
        "fecha_desde=2025-02-01&fecha_hasta=2025-01-01",
        "aduana_id=0",
        "pais_id=1%20OR%201=1",
        f"correlativo={2**63}",
        f"page={2**63 - 1}&page_size=100",
        "unknown=value",
    ],
)
def test_rejects_invalid_query_parameters(client, auth_headers, query):
    assert client.get("/polizas?" + query, headers=auth_headers).status_code == 422


def test_empty_database_has_empty_page(client, auth_headers):
    assert client.get("/polizas", headers=auth_headers).json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
    }
