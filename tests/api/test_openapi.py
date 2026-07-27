import json
from pathlib import Path
from typing import Any

from app.main import create_app

OPENAPI_PATH = Path(__file__).parents[2] / "frontend" / "openapi.json"


def test_committed_openapi_matches_application_contract() -> None:
    committed_openapi: dict[str, Any] = json.loads(OPENAPI_PATH.read_text())

    assert committed_openapi == create_app().openapi()


def test_openapi_exposes_only_versioned_import_mapping_mutations() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/imports/documents/{document_id}/mapping/preview" in paths
    assert "/api/v1/imports/documents/{document_id}/mapping/import" in paths
    assert "/imports/documents/{document_id}" not in paths
    assert "/imports/documents/{document_id}/mapping" not in paths
    assert "/imports/documents/{document_id}/mapping/import" not in paths
