from fastapi.testclient import TestClient


def test_home_redirects_authenticated_user_to_dashboard(client: TestClient, monkeypatch) -> None:
    class FakeAuthenticationService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def resolve_login_session(self, session_token: str) -> object | None:
            if session_token == "valid-session":
                return object()
            return None

    monkeypatch.setattr("app.main.AuthenticationService", FakeAuthenticationService)
    client.cookies.set("booker_session", "valid-session")

    response = client.get(
        "/",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_healthcheck_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Booker Tee"}


def test_home_page_renders_foundation_shell(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "финансовый рабочий стол" in response.text
    assert "Загрузить выписку" in response.text
