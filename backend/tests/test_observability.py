from fastapi.testclient import TestClient


def test_security_headers_and_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_rejects_oversized_request(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scraping/discover",
        content=b"{}",
        headers={"Content-Length": str(3 * 1024 * 1024)},
    )
    assert response.status_code == 413


def test_rejects_invalid_content_length(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scraping/discover",
        content=b"{}",
        headers={"Content-Length": "invalid"},
    )
    assert response.status_code == 400


def test_prometheus_metrics(client: TestClient) -> None:
    client.get("/health/live")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "nsfw_http_requests_total" in response.text
    assert "nsfw_http_request_duration_seconds" in response.text
