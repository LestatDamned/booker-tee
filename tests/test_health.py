from fastapi.testclient import TestClient


def test_healthcheck_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Booker Tee"}


def test_home_page_renders_foundation_shell(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Booker Tee запущен." in response.text
