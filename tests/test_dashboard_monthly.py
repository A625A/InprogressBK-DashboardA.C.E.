import pytest
from sqlalchemy import event, text

from app.services import dashboard


def test_monthly_requires_authentication(client):
    assert client.get("/dashboard/kpis/valor-por-mes?year=2025").status_code == 401
    assert (
        client.get(
            "/dashboard/kpis/valor-por-mes?year=2025", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )


def test_monthly_groups_in_sql_and_excludes_other_years_and_null_dates(
    client, app, auth_headers, kpi_data
):
    with app.state.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO polizas (id, correlativo, fecha_declaracion) VALUES
            (6, 106, '2025-12-31'), (7, 107, '2026-01-01'), (8, 108, '2025-01-31')""")
        )
        conn.execute(
            text("""INSERT INTO poliza_items (poliza_id, valor_cif_uds) VALUES
            (6, 25), (7, 999), (8, 5.5)""")
        )
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.upper())

    event.listen(app.state.engine, "before_cursor_execute", capture)
    try:
        response = client.get("/dashboard/kpis/valor-por-mes?year=2025", headers=auth_headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    result = response.json()
    assert result["year"] == 2025
    assert [row["mes"] for row in result["meses"]] == list(range(1, 13))
    assert [row["valor_importado"] for row in result["meses"]] == [
        205.5,
        50.5,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        25,
    ]
    queries = [sql for sql in statements if "SUM(" in sql]
    assert len(queries) == 1
    assert all(clause in queries[0] for clause in ["JOIN", "WHERE", "GROUP BY", "ORDER BY"])


@pytest.mark.parametrize(
    "query", ["", "?year=0", "?year=10000", "?year=-1", "?year=oops", "?year=2025.5"]
)
def test_monthly_rejects_missing_or_invalid_year(client, auth_headers, query):
    assert (
        client.get("/dashboard/kpis/valor-por-mes" + query, headers=auth_headers).status_code == 422
    )


def test_monthly_empty_year_returns_twelve_zeros(client, auth_headers, kpi_data):
    response = client.get("/dashboard/kpis/valor-por-mes?year=2023", headers=auth_headers)
    assert response.status_code == 200
    result = response.json()
    assert result["year"] == 2023
    assert len(result["meses"]) == 12
    assert all(row["valor_importado"] == 0 for row in result["meses"])


def test_monthly_null_amounts_are_zero_and_negative_values_are_preserved(client, app, auth_headers):
    with app.state.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO polizas (id, correlativo, fecha_declaracion) VALUES (1, 1, '2025-04-15'), (2, 2, '2025-05-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO poliza_items (poliza_id, valor_cif_uds) VALUES (1, NULL), (1, NULL), (2, -3)"
            )
        )
    response = client.get("/dashboard/kpis/valor-por-mes?year=2025", headers=auth_headers)
    assert response.status_code == 200
    values = response.json()["meses"]
    assert values[3] == {"mes": 4, "valor_importado": 0.0}
    assert values[4] == {"mes": 5, "valor_importado": -3.0}


@pytest.mark.parametrize(
    ("year", "date", "month"), [(1, "0001-01-01", 1), (9999, "9999-12-31", 12)]
)
def test_monthly_accepts_calendar_boundary_years(client, app, auth_headers, year, date, month):
    with app.state.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO polizas (id, correlativo, fecha_declaracion) VALUES (1, 1, :date)"),
            {"date": date},
        )
        conn.execute(text("INSERT INTO poliza_items (poliza_id, valor_cif_uds) VALUES (1, 10)"))
    response = client.get(f"/dashboard/kpis/valor-por-mes?year={year}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["meses"][month - 1]["valor_importado"] == 10


# Unit tests: fill only the bounded SQL aggregate result, not transaction records.
def test_complete_months_orders_and_fills_sparse_aggregates_without_mutation():
    values = {12: 12.5, 2: -5.0}
    result = dashboard.complete_months(2025, values)
    assert result.year == 2025
    assert [row.mes for row in result.meses] == list(range(1, 13))
    assert [row.valor_importado for row in result.meses] == [0, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12.5]
    assert values == {12: 12.5, 2: -5.0}


def test_complete_months_handles_empty_aggregate_result():
    result = dashboard.complete_months(2024, {})
    assert result.year == 2024
    assert len(result.meses) == 12
    assert all(row.valor_importado == 0 for row in result.meses)
