from fastapi.testclient import TestClient


VIDEO = {
    "title": "Cours de démonstration",
    "page_url": "https://media.example/catalogue",
    "video_url": "https://cdn.example/videos/demo.mp4",
}


def test_video_crud_and_status_transition(client: TestClient) -> None:
    created = client.post("/api/v1/videos", json=VIDEO)
    assert created.status_code == 201
    video_id = created.json()["id"]
    assert created.json()["status"] == "DISCOVERED"

    fetched = client.get(f"/api/v1/videos/{video_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == VIDEO["title"]

    transitioned = client.patch(
        f"/api/v1/videos/{video_id}/status", json={"status": "VALIDATING"}
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "VALIDATING"

    invalid = client.patch(
        f"/api/v1/videos/{video_id}/status", json={"status": "SAMPLED_SAFE"}
    )
    assert invalid.status_code == 409

    deleted = client.delete(f"/api/v1/videos/{video_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/videos/{video_id}").status_code == 404


def test_list_filter_search_pagination_and_duplicate(client: TestClient) -> None:
    first = client.post("/api/v1/videos", json=VIDEO)
    assert first.status_code == 201

    second_payload = {
        **VIDEO,
        "title": "Documentaire nature",
        "video_url": "https://cdn.example/videos/nature.mp4",
    }
    assert client.post("/api/v1/videos", json=second_payload).status_code == 201

    duplicate = client.post("/api/v1/videos", json=VIDEO)
    assert duplicate.status_code == 409

    page = client.get("/api/v1/videos?page=1&size=1")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["pages"] == 2
    assert len(page.json()["items"]) == 1

    search = client.get("/api/v1/videos?search=nature")
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["title"] == "Documentaire nature"

    filtered = client.get("/api/v1/videos?status=DISCOVERED")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2


def test_error_status_requires_message(client: TestClient) -> None:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    client.patch(f"/api/v1/videos/{video_id}/status", json={"status": "VALIDATING"})

    response = client.patch(
        f"/api/v1/videos/{video_id}/status", json={"status": "ERROR"}
    )
    assert response.status_code == 422

