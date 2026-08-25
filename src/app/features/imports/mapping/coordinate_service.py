import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.documents.attempts import latest_parse_attempt
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import (
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.documents.validation_report import StoredValidationReport
from app.features.imports.mapping.commands.import_rows import MappedStatementRowImporter
from app.features.imports.mapping.coordinate_dto import (
    CoordinateCapability,
    CoordinateControlRegion,
    CoordinateControlTotalKind,
    CoordinateMappingOverview,
    CoordinateMappingSpec,
    CoordinatePreview,
    CoordinatePreviewRow,
)
from app.features.imports.mapping.coordinate_engine import (
    CoordinateMappingEngine,
    _normalization_spec,
)
from app.features.imports.mapping.coordinate_pdf import CoordinatePdfError, CoordinatePdfReader
from app.features.imports.mapping.coordinate_validation import CoordinateMappingValidator
from app.features.imports.mapping.dto import StatementMappingImportResult
from app.features.imports.mapping.errors import (
    MappingImportIdempotencyConflictError,
    MappingImportNotFoundError,
    MappingImportUnavailableError,
    UnknownStatementMappingError,
)
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.mapping.templates import clean_template_name
from app.features.imports.models import ImportMappingExecution
from app.features.imports.statements.dto import StatementControlTotals
from app.features.imports.statements.repository import StatementRepository
from app.features.imports.statements.types import RawTransactionStatus

MAX_COORDINATE_PREVIEW_ROWS = 20


class CoordinateMappingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._documents = DocumentRepository(session)
        self._templates = MappingRepository(session)
        self._pdf = CoordinatePdfReader(settings.upload_storage_dir)

    async def overview(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        workspace_default_currency: str,
    ) -> CoordinateMappingOverview | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        reasons = _document_reasons(document)
        pages = [] if reasons else await self._pdf.inspect(document.storage_key)
        if pages and not all(page.has_text_layer for page in pages):
            reasons.append("text_layer_required")
        return CoordinateMappingOverview(
            document_id=document.id,
            filename=document.original_filename,
            page_count=len(pages),
            pages=tuple(pages),
            default_currency=document.account.currency
            if document.account
            else workspace_default_currency,
            capability=CoordinateCapability(
                allowed=not reasons, blocking_reason_codes=tuple(reasons)
            ),
            templates=tuple(
                await self._templates.list_coordinate_templates(workspace_id=workspace_id)
            ),
        )

    async def preview(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        spec: CoordinateMappingSpec,
        control_regions: tuple[CoordinateControlRegion, ...] = (),
    ) -> CoordinatePreview | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        words = await self._validated_words(document, spec, control_regions)
        result = CoordinateMappingEngine.apply(words, spec)
        control_totals = CoordinateMappingEngine.resolve_control_totals(words, control_regions)
        rows = tuple(
            CoordinatePreviewRow(
                page_number=row.page_number,
                source_row_number=row.source_row_number + 1,
                layout=result.layouts[index],
                operation_date_raw=row.operation_date_raw[:1000],
                operation_date=row.operation_date.isoformat() if row.operation_date else None,
                posting_date_raw=row.posting_date_raw[:1000],
                posting_date=row.posting_date.isoformat() if row.posting_date else None,
                description_raw=row.description_raw[:2000],
                description=(row.description or row.description_raw)[:2000],
                amount_raw=row.amount_raw[:1000],
                amount=str(row.amount) if row.amount is not None else None,
                currency_raw=row.currency_raw[:1000],
                currency=row.currency,
                balance_after_raw=row.balance_after_raw[:1000],
                balance_after=str(row.balance_after) if row.balance_after is not None else None,
                status=row.status,
                errors=tuple(part for part in row.error.split("; ") if part),
            )
            for index, row in enumerate(result.rows[:MAX_COORDINATE_PREVIEW_ROWS])
        )
        valid_count = sum(row.status == "valid" for row in result.rows)
        return CoordinatePreview(
            rows=rows,
            total_row_count=len(result.rows),
            valid_row_count=valid_count,
            invalid_row_count=len(result.rows) - valid_count,
            row_limit=MAX_COORDINATE_PREVIEW_ROWS,
            rows_truncated=len(result.rows) > len(rows),
            warnings=tuple(result.warnings),
            control_totals=control_totals,
            reconciliation=CoordinateMappingEngine.reconcile(result.rows, control_totals),
            can_import=valid_count > 0
            and not any(warning.severity == "error" for warning in result.warnings)
            and not any(item.error for item in control_totals),
        )

    async def render_page(
        self, *, workspace_id: UUID, document_id: UUID, page_number: int
    ) -> bytes | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        reasons = _document_reasons(document)
        if reasons:
            raise MappingImportUnavailableError(reasons[0])
        return await self._pdf.render_page(document.storage_key, page_number)

    async def _validated_words(
        self,
        document,
        spec: CoordinateMappingSpec,
        control_regions: tuple[CoordinateControlRegion, ...] = (),
    ):
        _require_coordinate_eligible(document)
        try:
            pages = await self._pdf.inspect(document.storage_key)
        except CoordinatePdfError as exc:
            raise MappingImportUnavailableError("Source PDF could not be read.") from exc
        if not pages or not all(page.has_text_layer for page in pages):
            raise MappingImportUnavailableError("PDF text layer is required.")
        issues = CoordinateMappingValidator.validate(
            spec,
            page_aspect_ratios=[page.aspect_ratio for page in pages],
            control_regions=control_regions,
        )
        if issues:
            raise UnknownStatementMappingError(issues[0].message)
        try:
            return await self._pdf.extract_words(document.storage_key)
        except CoordinatePdfError as exc:
            raise MappingImportUnavailableError("Source PDF could not be read.") from exc


class CoordinateMappingImportService(CoordinateMappingService):
    async def import_rows_idempotently(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        spec: CoordinateMappingSpec,
        idempotency_key: UUID,
        template_name: str | None,
        control_regions: tuple[CoordinateControlRegion, ...] = (),
    ) -> StatementMappingImportResult:
        name = clean_template_name(template_name) if template_name is not None else None
        fingerprint = _fingerprint(spec, control_regions, name)
        document = await self._documents.get_document_for_workspace_for_update(
            workspace_id, document_id
        )
        if document is None:
            raise MappingImportNotFoundError("Document was not found.")
        existing = await self._templates.get_mapping_execution(
            workspace_id=workspace_id, document_id=document_id, idempotency_key=idempotency_key
        )
        if existing:
            if existing.payload_fingerprint != fingerprint:
                raise MappingImportIdempotencyConflictError(
                    "Idempotency key has different geometry."
                )
            return StatementMappingImportResult(
                document_id=document.id,
                document_status=document.status,
                imported_row_count=existing.imported_row_count,
                template_id=existing.template_id,
                replayed=True,
            )
        _require_coordinate_eligible(document)
        attempt = latest_parse_attempt(document)
        if attempt is None:
            raise MappingImportUnavailableError("Parse attempt is unavailable.")
        words = await self._validated_words(document, spec, control_regions)
        extraction = CoordinateMappingEngine.apply(words, spec)
        control_totals = CoordinateMappingEngine.resolve_control_totals(words, control_regions)
        if not extraction.rows or not any(row.status == "valid" for row in extraction.rows):
            raise MappingImportUnavailableError("Refresh preview and fix blocking errors.")
        if any(item.error for item in control_totals):
            raise MappingImportUnavailableError("Refresh preview and fix control total areas.")
        if control_totals:
            previous = (
                StatementControlTotals.model_validate(attempt.control_totals_json)
                if attempt.control_totals_json is not None
                else StatementControlTotals(currency=spec.default_currency)
            )
            values = {
                item.kind: Decimal(item.amount)
                for item in control_totals
                if item.amount is not None
            }
            attempt.control_totals_json = StatementControlTotals(
                currency=previous.currency or spec.default_currency,
                opening_balance=values.get(
                    CoordinateControlTotalKind.OPENING_BALANCE,
                    previous.opening_balance,
                ),
                closing_balance=values.get(
                    CoordinateControlTotalKind.CLOSING_BALANCE,
                    previous.closing_balance,
                ),
                total_inflow=values.get(
                    CoordinateControlTotalKind.TOTAL_INFLOW,
                    previous.total_inflow,
                ),
                total_outflow=values.get(
                    CoordinateControlTotalKind.TOTAL_OUTFLOW,
                    previous.total_outflow,
                ),
            ).model_dump(mode="json")
        raw_transactions = await MappedStatementRowImporter(
            self._session,
            self._documents,
            StatementRepository(self._session),
        ).replace_mapped_rows(
            document=document,
            attempt=attempt,
            spec=_normalization_spec(spec),
            rows=extraction.rows,
            exclude_duplicate_document_id=document.id,
        )
        if control_regions:
            attempt.control_totals_json = {
                **(attempt.control_totals_json or {}),
                "visual_coordinate_sources": {
                    region.kind.value: {
                        "page_number": region.page_number,
                        "rect": region.rect.model_dump(mode="json"),
                    }
                    for region in control_regions
                },
            }
        attempt.validation_report_json = {
            **(attempt.validation_report_json or {}),
            "source": "visual_coordinate_mapping",
        }
        template = (
            await self._templates.create_coordinate_template(
                workspace_id=workspace_id, name=name, spec=spec
            )
            if name is not None
            else None
        )
        await self._templates.create_mapping_execution(
            ImportMappingExecution(
                workspace_id=workspace_id,
                uploaded_document_id=document.id,
                idempotency_key=str(idempotency_key),
                payload_fingerprint=fingerprint,
                imported_row_count=len(raw_transactions),
                template_id=template.id if template else None,
            )
        )
        await self._session.commit()
        return StatementMappingImportResult(
            document_id=document.id,
            document_status=document.status,
            imported_row_count=len(raw_transactions),
            template_id=template.id if template else None,
            replayed=False,
        )


def _document_reasons(document) -> list[str]:
    reasons = []
    if (
        document.content_type != "application/pdf"
        or document.document_type is not UploadedDocumentType.BANK_STATEMENT
    ):
        reasons.append("pdf_required")
    if document.source is not UploadedDocumentSource.WEB_UPLOAD:
        reasons.append("web_upload_required")
    if document.status is not UploadedDocumentStatus.REQUIRES_REVIEW:
        reasons.append("status_not_eligible")
    attempt = latest_parse_attempt(document)
    try:
        report = (
            StoredValidationReport.model_validate(attempt.validation_report_json)
            if attempt is not None and attempt.validation_report_json is not None
            else None
        )
    except ValueError:
        report = None
    if report is None or (
        not report.needs_mapping and report.source != "visual_coordinate_mapping"
    ):
        reasons.append("mapping_not_required")
    if not document.storage_key:
        reasons.append("source_missing")
    if document.account_id is None:
        reasons.append("account_required")
    if any(row.status is RawTransactionStatus.CONFIRMED for row in document.raw_transactions):
        reasons.append("confirmed_rows_exist")
    return reasons


def _require_coordinate_eligible(document) -> None:
    reasons = _document_reasons(document)
    if reasons:
        raise MappingImportUnavailableError(reasons[0])


def _fingerprint(
    spec: CoordinateMappingSpec,
    control_regions: tuple[CoordinateControlRegion, ...],
    template_name: str | None,
) -> str:
    payload = {
        "kind": "visual_coordinates",
        "version": 1,
        "spec": spec.model_dump(mode="json"),
        "control_regions": [region.model_dump(mode="json") for region in control_regions],
        "template_name": template_name,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
