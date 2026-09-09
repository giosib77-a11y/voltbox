"""Phase 0 — ჩონჩხის ტესტები: health, შეცდომის კონვერტი, request-id."""

import httpx


async def test_health_reports_ok_and_database_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]


async def test_every_response_carries_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["X-Request-ID"]


async def test_incoming_request_id_is_preserved(client: httpx.AsyncClient) -> None:
    # ლოგების კვალი front-იდან backend-ამდე რომ არ გაწყდეს
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-me-123"})

    assert response.headers["X-Request-ID"] == "trace-me-123"


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found", "details": None}
    }


async def test_health_response_is_camel_case(client: httpx.AsyncClient) -> None:
    # frontend camelCase-ს ელოდება; snake_case-ის გაპარვა მდუმარე ბაგია
    body = await client.get("/api/v1/health")

    assert "_" not in "".join(body.json().keys())
