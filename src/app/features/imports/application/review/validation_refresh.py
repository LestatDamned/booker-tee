from app.features.imports.application.pipelines.validation_result import (
    store_import_validation_result,
)
from app.features.imports.application.review.validation_calculation import (
    calculate_document_validation,
)
from app.features.imports.models import UploadedDocument
from app.features.imports.repository import ImportRepository


async def refresh_document_validation(
    imports: ImportRepository,
    document: UploadedDocument,
) -> None:
    validation = calculate_document_validation(document)
    if validation is None:
        return
    await store_import_validation_result(
        imports,
        document,
        validation.attempt,
        control_totals=validation.control_totals,
        report=validation.report,
    )
