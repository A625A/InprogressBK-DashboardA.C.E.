import pytest
from sqlalchemy import text


@pytest.mark.parametrize(
    ("endpoint", "table"),
    [
        ("paises", "pais"),
        ("aduanas", "aduanas"),
        ("tipos-regimen", "tipo_regimen"),
    ],
)
def test_dimensions_are_protected_ordered_and_read_only(client, app, auth_headers, endpoint, table):
    path = f"/dimensions/{endpoint}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=auth_headers).json() == []
    with app.state.engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {table} (id, name) VALUES (20, 'Segundo'), (10, 'Primero')")
        )
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == [{"id": 10, "name": "Primero"}, {"id": 20, "name": "Segundo"}]
    assert client.post(path, headers=auth_headers, json={"name": "Nuevo"}).status_code == 405
