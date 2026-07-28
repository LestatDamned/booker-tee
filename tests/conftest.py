from collections.abc import Iterator

import pytest

from api_client import ApiTestClient
from app.main import create_app


@pytest.fixture
def client() -> Iterator[ApiTestClient]:
    with ApiTestClient(create_app()) as test_client:
        yield test_client
