import io
import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.observability import RequestLogFormatter, logger


def capture_logs(monkeypatch):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RequestLogFormatter())
    monkeypatch.setattr(logger, "handlers", [handler])
    return stream


def test_server_errors_are_safe_and_logged(app, monkeypatch):
    stream = capture_logs(monkeypatch)
    secret = "private-password-token-secret"

    @app.get("/unexpected-error")
    def unexpected_error():
        raise RuntimeError(secret)

    @app.get("/service-error")
    def service_error():
        raise HTTPException(503, secret, headers={"Retry-After": "5"})

    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [client.get("/unexpected-error"), client.get("/service-error")]
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(records) == 2
    for response, record, status, path in zip(
        responses, records, [500, 503], ["/unexpected-error", "/service-error"], strict=True
    ):
        assert response.status_code == status
        assert response.json() == {"detail": "Error interno del servidor"}
        assert record == {
            "timestamp": record["timestamp"],
            "level": "ERROR",
            "request_id": response.headers["x-request-id"],
            "method": "GET",
            "path": path,
            "status_code": status,
        }
        assert datetime.fromisoformat(record["timestamp"]).utcoffset().total_seconds() == 0
        assert UUID(record["request_id"]).version == 4
    assert responses[1].headers["retry-after"] == "5"
    assert secret not in stream.getvalue()
    assert "Traceback" not in stream.getvalue()


def test_sensitive_inputs_are_absent_from_responses_and_logs(client, monkeypatch):
    stream = capture_logs(monkeypatch)
    secret = "sensitive-value-never-echo"
    headers = {"Authorization": f"Bearer {secret}", "X-Request-ID": secret}
    responses = [
        client.post("/register", json={"username": "tester", "password": secret}),
        client.post(
            f"/register?token={secret}",
            headers=headers,
            json={"username": "x", "password": secret, secret: secret},
        ),
        client.get("/protected-test", headers=headers),
        client.get(f"/{secret}?password={secret}", headers=headers),
        client.get(f"/polizas/{secret}", headers=headers),
        client.post("/register", json={"username": "tester", "password": secret}),
        client.put("/register", headers=headers),
    ]
    statuses = [201, 422, 401, 404, 401, 409, 405]
    assert [response.status_code for response in responses] == statuses
    assert responses[2].headers["www-authenticate"] == "Bearer"
    assert responses[-1].headers["allow"] == "POST"
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(records) == len(responses)
    assert [record["status_code"] for record in records] == statuses
    assert [record["level"] for record in records] == ["INFO"] + ["WARNING"] * 6
    assert records[3]["path"] == "<unmatched>"
    assert records[4]["path"] == "/polizas/{poliza_id}"
    assert len({record["request_id"] for record in records}) == len(responses)
    for response, record in zip(responses, records, strict=True):
        assert record["request_id"] == response.headers["x-request-id"]
        assert secret not in response.text + str(response.headers)
    assert secret not in stream.getvalue()
    assert "Traceback" not in stream.getvalue()
    assert logging.getLogger("uvicorn.access").disabled
