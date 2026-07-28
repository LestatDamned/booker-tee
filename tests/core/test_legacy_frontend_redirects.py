import pytest

from api_client import ApiTestClient as TestClient
from app.main import create_app

DOCUMENT_ID = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8"


@pytest.mark.parametrize(
    ("historical_url", "react_url"),
    [
        (
            "/ledger/manual?type=expense&page=2",
            "/app/ledger/manual?type=expense&page=2",
        ),
        ("/imports?source=dashboard", "/app/imports?source=dashboard"),
        (
            "/imports/upload?source=dashboard",
            "/app/imports/upload?source=dashboard",
        ),
        (
            f"/imports/documents/{DOCUMENT_ID}?source=dashboard",
            f"/app/imports/documents/{DOCUMENT_ID}?source=dashboard",
        ),
        (
            f"/imports/documents/{DOCUMENT_ID}/mapping?source=document",
            f"/app/imports/documents/{DOCUMENT_ID}/mapping?source=document",
        ),
        (
            "/imports/documents/document-id/review?source=chat",
            "/app/imports/documents/document-id/review?source=chat",
        ),
    ],
)
def test_historical_frontend_get_redirects_to_react(
    historical_url: str,
    react_url: str,
) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get(historical_url, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == react_url


@pytest.mark.parametrize(
    ("historical_url", "expected_status"),
    [
        ("/imports/upload", 405),
        (f"/imports/documents/{DOCUMENT_ID}", 405),
        (f"/imports/documents/{DOCUMENT_ID}/mapping", 405),
        (f"/imports/documents/{DOCUMENT_ID}/mapping/import", 404),
        (f"/imports/documents/{DOCUMENT_ID}/review", 405),
    ],
)
def test_historical_frontend_mutations_are_not_redirected(
    historical_url: str,
    expected_status: int,
) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(historical_url, follow_redirects=False)

    assert response.status_code == expected_status
