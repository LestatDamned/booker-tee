from typing import Any


def test_openapi_exposes_only_versioned_import_mapping_mutations(
    canonical_openapi_schema: dict[str, Any],
) -> None:
    paths = canonical_openapi_schema["paths"]

    assert "/api/v1/imports/documents/{document_id}/mapping/preview" in paths
    assert "/api/v1/imports/documents/{document_id}/mapping/import" in paths
    assert "/imports/documents/{document_id}" not in paths
    assert "/imports/documents/{document_id}/mapping" not in paths
    assert "/imports/documents/{document_id}/mapping/import" not in paths
