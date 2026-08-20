from app.main import create_app


def test_openapi_exposes_only_versioned_import_mapping_mutations() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/imports/documents/{document_id}/mapping/preview" in paths
    assert "/api/v1/imports/documents/{document_id}/mapping/import" in paths
    assert "/imports/documents/{document_id}" not in paths
    assert "/imports/documents/{document_id}/mapping" not in paths
    assert "/imports/documents/{document_id}/mapping/import" not in paths
