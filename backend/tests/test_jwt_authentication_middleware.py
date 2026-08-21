def test_rejects_business_endpoint_without_bearer_token(client) -> None:
    response = client.get("/api/v1/videos", headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.json() == {"detail": "Session expirée."}


def test_allows_public_health_without_bearer_token(client) -> None:
    response = client.get("/health", headers={"Authorization": ""})

    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_rejects_non_public_system_endpoint_without_bearer_token(client) -> None:
    response = client.get("/metrics", headers={"Authorization": ""})

    assert response.status_code == 401

