from uuid import uuid4

from api_client import ApiTestClient as TestClient
from app.main import create_app


def test_historical_account_detail_preserves_query_in_react_redirect() -> None:
    account_id = uuid4()

    with TestClient(create_app(), follow_redirects=False) as client:
        response = client.get(
            f"/accounts/{account_id}?status=confirmed&search=такси&page=2"
        )

    assert response.status_code == 307
    assert response.headers["location"] == (
        f"/app/accounts/{account_id}?status=confirmed&search="
        "%D1%82%D0%B0%D0%BA%D1%81%D0%B8&page=2"
    )
