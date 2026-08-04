import pytest

from api_client import ApiTestClient as TestClient
from app.main import create_app

DOCUMENT_ID = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8"
ACCOUNT_ID = "11111111-1111-1111-1111-111111111111"
PROPERTY_ID = "22222222-2222-2222-2222-222222222222"
CATEGORY_ID = "33333333-3333-3333-3333-333333333333"


@pytest.mark.parametrize(
    ("historical_url", "react_url"),
    [
        (
            "/ledger/manual?type=expense&page=2",
            "/app/ledger/manual?type=expense&page=2",
        ),
        ("/accounts?source=dashboard", "/app/accounts?source=dashboard"),
        (
            f"/accounts/{ACCOUNT_ID}?status=confirmed&search=такси&page=2",
            f"/app/accounts/{ACCOUNT_ID}"
            "?status=confirmed&search=%D1%82%D0%B0%D0%BA%D1%81%D0%B8&page=2",
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
        (
            "/reports?date_from=2026-07-01&currency=RUB&category_sort=expense",
            "/app/reports?date_from=2026-07-01&currency=RUB&category_sort=expense",
        ),
        (
            "/properties?view=archived&search=дом",
            "/app/properties?view=archived&search=%D0%B4%D0%BE%D0%BC",
        ),
        (
            "/categories?view=archived&search=такси",
            "/app/categories?view=archived&search=%D1%82%D0%B0%D0%BA%D1%81%D0%B8",
        ),
        (
            f"/categories/{CATEGORY_ID}?date_from=2026-07-01&currency=RUB"
            "&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
            f"/app/categories/{CATEGORY_ID}?date_from=2026-07-01&currency=RUB"
            "&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
        ),
        (
            f"/rules?q=ozon&category_id={CATEGORY_ID}&status=disabled&page=2",
            f"/app/rules?q=ozon&category_id={CATEGORY_ID}&status=disabled&page=2",
        ),
        (
            "/workspaces?source=profile&view=inactive",
            "/app/workspaces?source=profile&view=inactive",
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
        ("/accounts", 405),
        (f"/accounts/{ACCOUNT_ID}", 405),
        ("/imports/upload", 405),
        (f"/imports/documents/{DOCUMENT_ID}", 405),
        (f"/imports/documents/{DOCUMENT_ID}/mapping", 405),
        (f"/imports/documents/{DOCUMENT_ID}/mapping/import", 404),
        (f"/imports/documents/{DOCUMENT_ID}/review", 405),
        ("/reports", 405),
        ("/properties", 405),
        (f"/properties/{PROPERTY_ID}", 404),
        (f"/properties/{PROPERTY_ID}/archive", 404),
        (f"/properties/{PROPERTY_ID}/restore", 404),
        ("/categories", 405),
        (f"/categories/{CATEGORY_ID}", 405),
        (f"/categories/{CATEGORY_ID}/archive", 404),
        (f"/categories/{CATEGORY_ID}/restore", 404),
        (f"/categories/{CATEGORY_ID}/delete", 404),
        ("/rules", 405),
        (f"/rules/{CATEGORY_ID}", 404),
        (f"/rules/{CATEGORY_ID}/toggle", 404),
        (f"/rules/{CATEGORY_ID}/delete", 404),
        ("/rules/seed-defaults", 404),
        ("/workspaces", 405),
        (f"/workspaces/{ACCOUNT_ID}", 404),
        (f"/workspaces/{ACCOUNT_ID}/select", 404),
        (f"/workspaces/{ACCOUNT_ID}/members/{CATEGORY_ID}/disable", 404),
        (f"/workspaces/{ACCOUNT_ID}/invitations", 404),
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
