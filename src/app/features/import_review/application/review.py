"""Authoritative import-review read workflow."""

from typing import Protocol
from uuid import UUID

from app.features.accounts.models import Account
from app.features.import_review.application.classification import (
    ImportReviewReferenceReader,
    build_import_review_draft_evaluation,
)
from app.features.import_review.domain.lifecycle import (
    import_review_lifecycle_snapshot,
)
from app.features.import_review.domain.queue import (
    is_review_terminal,
    is_reviewable,
    review_queue_snapshot,
)
from app.features.import_review.schemas.review import (
    EMPTY_TRANSFER_OPTIONS,
    ImportReviewAccountDto,
    ImportReviewBalanceChainDto,
    ImportReviewCapabilitiesDto,
    ImportReviewDocumentDto,
    ImportReviewDraftEvaluationDto,
    ImportReviewDuplicateCandidateDto,
    ImportReviewDuplicateEvidenceDto,
    ImportReviewDuplicateMatchingField,
    ImportReviewDuplicateMatchReasonCode,
    ImportReviewItemDto,
    ImportReviewNormalizedSourceDto,
    ImportReviewPostingDto,
    ImportReviewQueueDto,
    ImportReviewRawSourceDto,
    ImportReviewReadModel,
    ImportReviewReadonlyReasonCode,
    ImportReviewReferencesDto,
    ImportReviewRowProblemCode,
    ImportReviewRowProblemDto,
    ImportReviewTransferOptionsDto,
    ImportReviewValidationDto,
    ImportReviewValidationReasonCode,
)
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.deduplication import (
    RawTransactionFingerprint,
    possible_duplicate_fingerprint,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import (
    StatementValidationReport,
    resolve_statement_validation_reason,
)
from app.features.imports.statements.validation_service import StatementValidationService
from app.features.ledger.domain.types import OperationStatus, OperationType


class ImportReviewDocumentSource(Protocol):
    async def get_document_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None: ...


class ImportReviewTransferSource(Protocol):
    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewTransferOptionsDto]: ...


class ImportReviewDuplicateEvidenceSource(Protocol):
    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewDuplicateEvidenceDto]: ...


class ImportReviewDuplicateSource(Protocol):
    async def list_possible_duplicate_candidates(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[RawTransactionFingerprint],
        exclude_document_id: UUID,
    ) -> list[RawTransaction]: ...


class ImportReviewDuplicateReader:
    def __init__(self, source: ImportReviewDuplicateSource) -> None:
        self._source = source

    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewDuplicateEvidenceDto]:
        targets = [
            row
            for row in document.raw_transactions
            if row.status is RawTransactionStatus.POSSIBLE_DUPLICATE
        ]
        target_fingerprints = {
            fingerprint
            for row in targets
            if (fingerprint := possible_duplicate_fingerprint(row)) is not None
        }
        candidates = await self._source.list_possible_duplicate_candidates(
            workspace_id=workspace_id,
            fingerprints=target_fingerprints,
            exclude_document_id=document.id,
        )
        candidates_by_fingerprint: dict[RawTransactionFingerprint, RawTransaction] = {}
        for candidate in candidates:
            fingerprint = possible_duplicate_fingerprint(candidate)
            if fingerprint is not None:
                candidates_by_fingerprint.setdefault(fingerprint, candidate)

        evidence: dict[UUID, ImportReviewDuplicateEvidenceDto] = {}
        for target in targets:
            fingerprint = possible_duplicate_fingerprint(target)
            candidate = candidates_by_fingerprint.get(fingerprint) if fingerprint else None
            if candidate is None:
                continue
            candidate_document = candidate.uploaded_document
            if (
                candidate.operation_date is None
                or candidate.amount is None
                or candidate.currency is None
            ):
                continue
            evidence[target.id] = ImportReviewDuplicateEvidenceDto(
                reason_code=(
                    ImportReviewDuplicateMatchReasonCode.SAME_ACCOUNT_DATE_AMOUNT_CURRENCY
                ),
                matching_fields=(
                    ImportReviewDuplicateMatchingField.ACCOUNT,
                    ImportReviewDuplicateMatchingField.OPERATION_DATE,
                    ImportReviewDuplicateMatchingField.AMOUNT,
                    ImportReviewDuplicateMatchingField.CURRENCY,
                ),
                candidate=ImportReviewDuplicateCandidateDto(
                    item_id=candidate.id,
                    document_id=candidate.uploaded_document_id,
                    document_filename=candidate_document.original_filename,
                    operation_id=candidate.linked_operation_id,
                    operation_date=candidate.operation_date,
                    description=candidate.description_normalized,
                    amount=candidate.amount,
                    currency=candidate.currency,
                ),
            )
        return evidence


class ImportReviewReader:
    def __init__(
        self,
        documents: ImportReviewDocumentSource,
        references: ImportReviewReferenceReader,
        transfers: ImportReviewTransferSource,
        duplicates: ImportReviewDuplicateEvidenceSource,
    ) -> None:
        self._documents = documents
        self._references = references
        self._transfers = transfers
        self._duplicates = duplicates

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        can_write: bool,
    ) -> ImportReviewReadModel | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        references = await self._references.read(workspace_id)
        transfers = await self._transfers.read_for_document(
            workspace_id=workspace_id,
            document=document,
        )
        duplicates = await self._duplicates.read_for_document(
            workspace_id=workspace_id,
            document=document,
        )
        return build_import_review_read_model(
            document,
            references=references,
            can_write=can_write,
            transfers=transfers,
            duplicates=duplicates,
        )


def build_import_review_read_model(
    document: UploadedDocument,
    *,
    references: ImportReviewReferencesDto,
    can_write: bool,
    transfers: dict[UUID, ImportReviewTransferOptionsDto],
    duplicates: dict[UUID, ImportReviewDuplicateEvidenceDto],
) -> ImportReviewReadModel:
    queue = review_queue_snapshot(document.raw_transactions)
    rows_by_id = {row.id: row for row in document.raw_transactions}
    document_account = _account_dto(document.account)
    categories_by_id = {category.id: category for category in references.categories}
    properties_by_id = {property_.id: property_ for property_ in references.properties}
    items: list[ImportReviewItemDto] = []
    for item_id in queue.ordered_item_ids:
        row = rows_by_id[item_id]
        linked_operation = row.linked_operation
        if linked_operation is not None:
            category_id = linked_operation.category_id
            category = linked_operation.category
            category_is_uncategorized = (
                category.system_key == "uncategorized" if category is not None else False
            )
            property_id = linked_operation.property_id
            explicit_operation_type = linked_operation.type
        else:
            category = (
                categories_by_id.get(row.suggested_category_id)
                if row.suggested_category_id is not None
                else None
            )
            category_id = category.id if category is not None else None
            category_is_uncategorized = category.is_uncategorized if category is not None else False
            property_ = (
                properties_by_id.get(row.suggested_property_id)
                if row.suggested_property_id is not None
                else None
            )
            property_id = property_.id if property_ is not None else None
            explicit_operation_type = None
        items.append(
            _item_dto(
                row,
                document=document,
                document_account=document_account,
                explicit_operation_type=explicit_operation_type,
                category_id=category_id,
                category_is_uncategorized=category_is_uncategorized,
                property_id=property_id,
                transfer=transfers.get(row.id, EMPTY_TRANSFER_OPTIONS),
                duplicate_evidence=duplicates.get(row.id),
            )
        )
    return ImportReviewReadModel(
        document=ImportReviewDocumentDto(
            id=document.id,
            filename=document.original_filename,
            status=document.status,
            source_account=document_account,
        ),
        queue=ImportReviewQueueDto.model_validate(queue),
        items=items,
        references=references,
        validation=build_import_review_validation(document),
        capabilities=ImportReviewCapabilitiesDto(
            can_write=can_write,
            readonly_reason_code=(
                None if can_write else ImportReviewReadonlyReasonCode.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )


def _item_dto(
    row: RawTransaction,
    *,
    document: UploadedDocument,
    document_account: ImportReviewAccountDto | None,
    explicit_operation_type: OperationType | None,
    category_id: UUID | None,
    category_is_uncategorized: bool,
    property_id: UUID | None,
    transfer: ImportReviewTransferOptionsDto,
    duplicate_evidence: ImportReviewDuplicateEvidenceDto | None,
) -> ImportReviewItemDto:
    status = row.status
    draft: ImportReviewDraftEvaluationDto = build_import_review_draft_evaluation(
        document=document,
        row=row,
        explicit_operation_type=explicit_operation_type,
        category_id=category_id,
        property_id=property_id,
        category_is_uncategorized=category_is_uncategorized,
    )
    return ImportReviewItemDto(
        id=row.id,
        row_index=row.row_index,
        status=status,
        is_terminal=is_review_terminal(status),
        is_reviewable=is_reviewable(status),
        source_account=_account_dto(row.account) or document_account,
        raw=ImportReviewRawSourceDto(
            operation_date=row.operation_date_raw,
            posting_date=row.posting_date_raw,
            description=row.description_raw,
            amount=row.amount_raw,
            currency=row.currency_raw,
            balance_after=row.balance_after_raw,
            account_hint=row.account_hint_raw,
        ),
        normalized=ImportReviewNormalizedSourceDto(
            operation_date=row.operation_date,
            posting_date=row.posting_date,
            description=row.description_normalized,
            amount=row.amount,
            currency=row.currency,
            balance_after=row.balance_after,
        ),
        classification=draft.classification,
        selection=draft.selection,
        confirmability=draft.confirmability,
        rule_suggestion=draft.rule_suggestion,
        posting=_posting_dto(row),
        transfer=transfer,
        lifecycle=import_review_lifecycle_snapshot(
            status=status,
            linked_operation_id=row.linked_operation_id,
        ),
        duplicate_evidence=duplicate_evidence,
    )


def _account_dto(account: Account | None) -> ImportReviewAccountDto | None:
    return ImportReviewAccountDto.model_validate(account) if account is not None else None


def _posting_dto(row: RawTransaction) -> ImportReviewPostingDto:
    operation = row.linked_operation
    return ImportReviewPostingDto(
        operation_id=row.linked_operation_id,
        can_undo=operation is not None and operation.status is OperationStatus.CONFIRMED,
    )


def build_import_review_validation(
    document: UploadedDocument,
) -> ImportReviewValidationDto | None:
    calculated = StatementValidationService.calculate_for_document(document)
    if calculated is None:
        return None
    report = calculated.report
    control_totals = report.control_totals
    return ImportReviewValidationDto(
        status=report.status,
        reason_code=ImportReviewValidationReasonCode(
            resolve_statement_validation_reason(
                status=report.status,
                balance_chain_status=report.balance_chain.status,
                unexplained_inflow_difference=report.unexplained_inflow_difference,
                unexplained_outflow_difference=report.unexplained_outflow_difference,
            ).value
        ),
        currency=report.totals.currency or (control_totals.currency if control_totals else None),
        extracted_count=report.totals.extracted_count,
        normalized_count=report.totals.normalized_count,
        needs_review_count=report.totals.needs_review_count,
        calculated_total_inflow=report.totals.calculated_total_inflow,
        calculated_total_outflow=report.totals.calculated_total_outflow,
        ignored_total_inflow=report.totals.ignored_total_inflow,
        ignored_total_outflow=report.totals.ignored_total_outflow,
        statement_total_inflow=(control_totals.total_inflow if control_totals else None),
        statement_total_outflow=(control_totals.total_outflow if control_totals else None),
        opening_balance=(control_totals.opening_balance if control_totals else None),
        closing_balance=(control_totals.closing_balance if control_totals else None),
        inflow_difference=report.inflow_difference,
        outflow_difference=report.outflow_difference,
        unexplained_inflow_difference=report.unexplained_inflow_difference,
        unexplained_outflow_difference=report.unexplained_outflow_difference,
        balance_chain=ImportReviewBalanceChainDto.model_validate(report.balance_chain),
        row_problems=_row_problems(document.raw_transactions, report),
    )


def _row_problems(
    rows: list[RawTransaction],
    report: StatementValidationReport,
) -> tuple[ImportReviewRowProblemDto, ...]:
    problems: list[ImportReviewRowProblemDto] = []
    for mismatch in report.balance_chain.mismatches:
        if mismatch.row_index >= len(rows) or mismatch.previous_row_index >= len(rows):
            continue
        row = rows[mismatch.row_index]
        previous = rows[mismatch.previous_row_index]
        problems.append(
            ImportReviewRowProblemDto(
                item_id=row.id,
                row_index=row.row_index,
                previous_item_id=previous.id,
                previous_row_index=previous.row_index,
                code=ImportReviewRowProblemCode.BALANCE_CHAIN_MISMATCH,
                expected_balance_after=mismatch.expected_balance_after,
                actual_balance_after=mismatch.actual_balance_after,
            )
        )
    return tuple(problems)
