from sqlalchemy import event, text


def test_totals_require_authentication(client):
    assert client.get("/dashboard/kpis/totals").status_code == 401
    assert (
        client.get(
            "/dashboard/kpis/totals", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )


def test_totals_count_headers_once_and_sum_all_linked_items(client, app, auth_headers, kpi_data):
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.upper())

    event.listen(app.state.engine, "before_cursor_execute", capture)
    try:
        response = client.get("/dashboard/kpis/totals", headers=auth_headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert response.json() == {"total_polizas": 5, "valor_importado_total": 277.5}
    queries = [sql for sql in statements if "FROM POLIZAS" in sql]
    assert len(queries) == 1
    assert "COUNT(DISTINCT" in queries[0] and "SUM(" in queries[0]
    assert "JOIN" in queries[0]


def test_empty_totals_are_zero(client, auth_headers):
    response = client.get("/dashboard/kpis/totals", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"total_polizas": 0, "valor_importado_total": 0.0}


def test_totals_count_headers_with_only_null_values_and_no_items(client, app, auth_headers):
    with app.state.engine.begin() as conn:
        conn.execute(text("INSERT INTO polizas (id, correlativo) VALUES (1, 1), (2, 2)"))
        conn.execute(
            text("INSERT INTO poliza_items (poliza_id, valor_cif_uds) VALUES (1, NULL), (1, NULL)")
        )
    assert client.get("/dashboard/kpis/totals", headers=auth_headers).json() == {
        "total_polizas": 2,
        "valor_importado_total": 0.0,
    }
