from copy import deepcopy

import pytest
from sqlalchemy import text


def counts(app):
    with app.state.engine.connect() as conn:
        return tuple(
            conn.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in ["polizas", "poliza_items"]
        )


def test_create_and_detail_persist_header_and_items(client, app, auth_headers, policy_payload):
    response = client.post("/polizas", json=policy_payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["correlativo"] == 12345
    assert body["fecha_declaracion"] == "2025-05-01"
    assert [item["valor_cif_uds"] for item in body["items"]] == [200, 30]
    assert counts(app) == (1, 2)
    detail = client.get(f"/polizas/{body['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json() == body
    assert client.get("/polizas/999", headers=auth_headers).status_code == 404


def test_creation_and_detail_require_authentication(client, policy_payload):
    assert client.post("/polizas", json=policy_payload).status_code == 401
    assert client.get("/polizas/1").status_code == 401


def test_duplicate_correlativo_does_not_add_items(client, app, auth_headers, policy_payload):
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 201
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 409
    assert counts(app) == (1, 2)


@pytest.mark.parametrize(
    "field", ["aduana_id", "tipo_regimen_id", "sac_id", "pais_id", "tipo_unidad_medida_id"]
)
def test_unknown_foreign_keys_rejected_without_writes(
    client, app, auth_headers, policy_payload, field
):
    target = policy_payload if field in policy_payload else policy_payload["items"][1]
    target[field] = 999
    response = client.post("/polizas", json=policy_payload, headers=auth_headers)
    assert response.status_code == 422
    assert counts(app) == (0, 0)


@pytest.mark.parametrize(
    "mutation", ["empty_items", "date", "numeric", "overflow", "extra", "missing", "invalid_id"]
)
def test_invalid_payload_is_rejected(client, app, auth_headers, policy_payload, mutation):
    if mutation == "empty_items":
        policy_payload["items"] = []
    elif mutation == "date":
        policy_payload["fecha_declaracion"] = "2025-02-30"
    elif mutation == "numeric":
        policy_payload["items"][0]["valor_cif_uds"] = "Infinity"
    elif mutation == "overflow":
        policy_payload["correlativo"] = 2**63
    elif mutation == "extra":
        policy_payload["unexpected"] = "value"
    elif mutation == "missing":
        del policy_payload["correlativo"]
    else:
        policy_payload["aduana_id"] = 0
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 422
    assert counts(app) == (0, 0)


def test_late_item_database_failure_rolls_back_entire_policy(
    client, app, auth_headers, policy_payload
):
    assert client.post("/polizas", json=policy_payload, headers=auth_headers).status_code == 201
    with app.state.engine.begin() as conn:
        conn.execute(
            text("""CREATE TRIGGER reject_second_item BEFORE INSERT ON poliza_items
                             WHEN NEW.cantidad_fraccion = 999
                             BEGIN SELECT RAISE(ABORT, 'test late failure'); END""")
        )
    failed = deepcopy(policy_payload)
    failed["correlativo"] = 54321
    failed["items"][1]["cantidad_fraccion"] = 999
    assert client.post("/polizas", json=failed, headers=auth_headers).status_code == 409
    # The earlier committed policy survives; no header or first item from the failed one.
    assert counts(app) == (1, 2)
    failed["items"][1]["cantidad_fraccion"] = 1
    assert client.post("/polizas", json=failed, headers=auth_headers).status_code == 201
    assert counts(app) == (2, 4)


def test_reads_nullable_legacy_fields(client, app, auth_headers, policy_payload):
    response = client.post("/polizas", json=policy_payload, headers=auth_headers)
    assert response.status_code == 201
    with app.state.engine.begin() as conn:
        conn.execute(text("UPDATE polizas SET aduana_id = NULL"))
        conn.execute(text("UPDATE poliza_items SET tasa_cif_cantidad_fraccion = NULL"))
    body = client.get("/polizas/1", headers=auth_headers).json()
    assert body["aduana_id"] is None
    assert body["items"][0]["tasa_cif_cantidad_fraccion"] is None


def test_creation_respects_nullable_fields_in_supplied_schema(client, app, auth_headers):
    response = client.post(
        "/polizas",
        headers=auth_headers,
        json={
            "correlativo": 777,
            "items": [{"valor_cif_uds": 100, "pais_id": None}],
        },
    )
    assert response.status_code == 201
    assert response.json()["aduana_id"] is None
    assert response.json()["items"][0]["pais_id"] is None
    assert counts(app) == (1, 1)
