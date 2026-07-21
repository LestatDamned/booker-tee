import json
from pathlib import Path
from typing import Any

from app.main import create_app

OPENAPI_PATH = Path(__file__).parents[2] / "frontend" / "openapi.json"


def test_committed_openapi_matches_application_contract() -> None:
    committed_openapi: dict[str, Any] = json.loads(OPENAPI_PATH.read_text())

    assert committed_openapi == create_app().openapi()
