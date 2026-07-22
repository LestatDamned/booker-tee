from decimal import Decimal

from app.api.v1.import_review.schemas.responses import (
    ImportReviewAccountApiResponse,
    ImportReviewApiResponse,
    ImportReviewBalanceChainApiResponse,
    ImportReviewCapabilitiesApiResponse,
    ImportReviewCategoryReferenceApiResponse,
    ImportReviewClassificationApiResponse,
    ImportReviewConfirmabilityApiResponse,
    ImportReviewDocumentApiResponse,
    ImportReviewDraftEvaluationApiResponse,
    ImportReviewExistingTransferCandidateApiResponse,
    ImportReviewItemApiResponse,
    ImportReviewLifecycleApiResponse,
    ImportReviewNormalizedSourceApiResponse,
    ImportReviewPostingApiResponse,
    ImportReviewPropertyReferenceApiResponse,
    ImportReviewQueueApiResponse,
    ImportReviewRawSourceApiResponse,
    ImportReviewRawTransferCandidateApiResponse,
    ImportReviewReferencesApiResponse,
    ImportReviewRowProblemApiResponse,
    ImportReviewRuleSuggestionApiResponse,
    ImportReviewSelectionApiResponse,
    ImportReviewTransferAccountApiResponse,
    ImportReviewTransferOptionsApiResponse,
    ImportReviewValidationApiResponse,
)
from app.features.imports.application.review.classification import (
    ImportReviewCategoryReferenceDto,
    ImportReviewClassificationDto,
    ImportReviewConfirmabilityDto,
    ImportReviewDraftEvaluationDto,
    ImportReviewRuleSuggestionDto,
    ImportReviewSelectionDto,
)
from app.features.imports.application.review.read_model import (
    ImportReviewAccountDto,
    ImportReviewReadModel,
)
from app.features.imports.application.review.transfers import (
    ImportReviewTransferAccountDto,
    ImportReviewTransferOptionsDto,
)


class ImportReviewResponseMapper:
    @staticmethod
    def response(review: ImportReviewReadModel) -> ImportReviewApiResponse:
        return ImportReviewApiResponse(
            document=ImportReviewDocumentApiResponse(
                id=review.document.id,
                filename=review.document.filename,
                status=review.document.status,
                source_account=ImportReviewResponseMapper._account(review.document.source_account),
            ),
            queue=ImportReviewQueueApiResponse(
                total=review.queue.total,
                completed=review.queue.completed,
                remaining=review.queue.remaining,
                first_remaining_item_id=review.queue.first_remaining_item_id,
                ordered_item_ids=list(review.queue.ordered_item_ids),
            ),
            items=[
                ImportReviewItemApiResponse(
                    id=item.id,
                    row_index=item.row_index,
                    status=item.status,
                    is_terminal=item.is_terminal,
                    is_reviewable=item.is_reviewable,
                    source_account=ImportReviewResponseMapper._account(item.source_account),
                    raw=ImportReviewRawSourceApiResponse(
                        operation_date=item.raw.operation_date,
                        posting_date=item.raw.posting_date,
                        description=item.raw.description,
                        amount=item.raw.amount,
                        currency=item.raw.currency,
                        balance_after=item.raw.balance_after,
                        account_hint=item.raw.account_hint,
                    ),
                    normalized=ImportReviewNormalizedSourceApiResponse(
                        operation_date=item.normalized.operation_date,
                        posting_date=item.normalized.posting_date,
                        description=item.normalized.description,
                        amount=ImportReviewResponseMapper._decimal(item.normalized.amount),
                        currency=item.normalized.currency,
                        balance_after=ImportReviewResponseMapper._decimal(
                            item.normalized.balance_after
                        ),
                    ),
                    classification=ImportReviewResponseMapper._classification(item.classification),
                    selection=ImportReviewResponseMapper._selection(item.selection),
                    confirmability=ImportReviewResponseMapper._confirmability(item.confirmability),
                    rule_suggestion=ImportReviewResponseMapper._rule_suggestion(
                        item.rule_suggestion
                    ),
                    posting=ImportReviewPostingApiResponse(
                        operation_id=item.posting.operation_id,
                        can_undo=item.posting.can_undo,
                    ),
                    transfer=ImportReviewResponseMapper._transfer(item.transfer),
                    lifecycle=ImportReviewLifecycleApiResponse(
                        allowed_actions=list(item.lifecycle.allowed_actions),
                    ),
                )
                for item in review.items
            ],
            references=ImportReviewReferencesApiResponse(
                categories=[
                    ImportReviewResponseMapper.category_reference(category)
                    for category in review.references.categories
                ],
                properties=[
                    ImportReviewPropertyReferenceApiResponse(
                        id=property_.id,
                        name=property_.name,
                    )
                    for property_ in review.references.properties
                ],
            ),
            validation=(
                ImportReviewValidationApiResponse(
                    status=review.validation.status,
                    reason_code=review.validation.reason_code,
                    currency=review.validation.currency,
                    extracted_count=review.validation.extracted_count,
                    normalized_count=review.validation.normalized_count,
                    needs_review_count=review.validation.needs_review_count,
                    calculated_total_inflow=ImportReviewResponseMapper._decimal_required(
                        review.validation.calculated_total_inflow
                    ),
                    calculated_total_outflow=ImportReviewResponseMapper._decimal_required(
                        review.validation.calculated_total_outflow
                    ),
                    ignored_total_inflow=ImportReviewResponseMapper._decimal_required(
                        review.validation.ignored_total_inflow
                    ),
                    ignored_total_outflow=ImportReviewResponseMapper._decimal_required(
                        review.validation.ignored_total_outflow
                    ),
                    statement_total_inflow=ImportReviewResponseMapper._decimal(
                        review.validation.statement_total_inflow
                    ),
                    statement_total_outflow=ImportReviewResponseMapper._decimal(
                        review.validation.statement_total_outflow
                    ),
                    opening_balance=ImportReviewResponseMapper._decimal(
                        review.validation.opening_balance
                    ),
                    closing_balance=ImportReviewResponseMapper._decimal(
                        review.validation.closing_balance
                    ),
                    inflow_difference=ImportReviewResponseMapper._decimal(
                        review.validation.inflow_difference
                    ),
                    outflow_difference=ImportReviewResponseMapper._decimal(
                        review.validation.outflow_difference
                    ),
                    unexplained_inflow_difference=ImportReviewResponseMapper._decimal(
                        review.validation.unexplained_inflow_difference
                    ),
                    unexplained_outflow_difference=ImportReviewResponseMapper._decimal(
                        review.validation.unexplained_outflow_difference
                    ),
                    balance_chain=ImportReviewBalanceChainApiResponse(
                        status=review.validation.balance_chain.status,
                        direction=review.validation.balance_chain.direction,
                        checked_pair_count=review.validation.balance_chain.checked_pair_count,
                        mismatch_count=review.validation.balance_chain.mismatch_count,
                    ),
                    row_problems=[
                        ImportReviewRowProblemApiResponse(
                            item_id=problem.item_id,
                            row_index=problem.row_index,
                            previous_item_id=problem.previous_item_id,
                            previous_row_index=problem.previous_row_index,
                            code=problem.code,
                            expected_balance_after=ImportReviewResponseMapper._decimal_required(
                                problem.expected_balance_after
                            ),
                            actual_balance_after=ImportReviewResponseMapper._decimal_required(
                                problem.actual_balance_after
                            ),
                        )
                        for problem in review.validation.row_problems
                    ],
                )
                if review.validation is not None
                else None
            ),
            capabilities=ImportReviewCapabilitiesApiResponse(
                can_write=review.capabilities.can_write,
                readonly_reason_code=review.capabilities.readonly_reason_code,
            ),
        )

    @staticmethod
    def draft_evaluation(
        evaluation: ImportReviewDraftEvaluationDto,
    ) -> ImportReviewDraftEvaluationApiResponse:
        return ImportReviewDraftEvaluationApiResponse(
            item_id=evaluation.item_id,
            classification=ImportReviewResponseMapper._classification(evaluation.classification),
            selection=ImportReviewResponseMapper._selection(evaluation.selection),
            confirmability=ImportReviewResponseMapper._confirmability(evaluation.confirmability),
            rule_suggestion=ImportReviewResponseMapper._rule_suggestion(evaluation.rule_suggestion),
        )

    @staticmethod
    def category_reference(
        category: ImportReviewCategoryReferenceDto,
    ) -> ImportReviewCategoryReferenceApiResponse:
        return ImportReviewCategoryReferenceApiResponse(
            id=category.id,
            name=category.name,
            kind=category.kind,
            is_uncategorized=category.is_uncategorized,
        )

    @staticmethod
    def _account(
        account: ImportReviewAccountDto | None,
    ) -> ImportReviewAccountApiResponse | None:
        if account is None:
            return None
        return ImportReviewAccountApiResponse(
            id=account.id,
            name=account.name,
            currency=account.currency,
        )

    @staticmethod
    def _decimal(value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @staticmethod
    def _decimal_required(value: Decimal) -> str:
        return format(value, "f")

    @staticmethod
    def _classification(
        classification: ImportReviewClassificationDto,
    ) -> ImportReviewClassificationApiResponse:
        return ImportReviewClassificationApiResponse(
            operation_type=classification.operation_type,
            source=classification.source,
        )

    @staticmethod
    def _selection(selection: ImportReviewSelectionDto) -> ImportReviewSelectionApiResponse:
        return ImportReviewSelectionApiResponse(
            category_id=selection.category_id,
            property_id=selection.property_id,
        )

    @staticmethod
    def _confirmability(
        confirmability: ImportReviewConfirmabilityDto,
    ) -> ImportReviewConfirmabilityApiResponse:
        return ImportReviewConfirmabilityApiResponse(
            can_confirm=confirmability.can_confirm,
            blocking_reason_codes=list(confirmability.blocking_reason_codes),
        )

    @staticmethod
    def _rule_suggestion(
        rule_suggestion: ImportReviewRuleSuggestionDto,
    ) -> ImportReviewRuleSuggestionApiResponse:
        return ImportReviewRuleSuggestionApiResponse(
            is_active=rule_suggestion.is_active,
            was_auto_applied=rule_suggestion.was_auto_applied,
            rule_id=rule_suggestion.rule_id,
            rule_name=rule_suggestion.rule_name,
            pattern=rule_suggestion.pattern,
            operation_type=rule_suggestion.operation_type,
            category_id=rule_suggestion.category_id,
            property_id=rule_suggestion.property_id,
        )

    @staticmethod
    def _transfer(
        transfer: ImportReviewTransferOptionsDto,
    ) -> ImportReviewTransferOptionsApiResponse:
        return ImportReviewTransferOptionsApiResponse(
            direction=transfer.direction,
            ordinary_operation_type=transfer.ordinary_operation_type,
            accounts=[
                ImportReviewResponseMapper._transfer_account(item) for item in transfer.accounts
            ],
            raw_row_candidates=[
                ImportReviewRawTransferCandidateApiResponse(
                    item_id=item.item_id,
                    document_id=item.document_id,
                    row_index=item.row_index,
                    operation_date=item.operation_date,
                    description=item.description,
                    amount=ImportReviewResponseMapper._decimal_required(item.amount),
                    currency=item.currency,
                    account=ImportReviewResponseMapper._transfer_account(item.account),
                    day_distance=item.day_distance,
                )
                for item in transfer.raw_row_candidates
            ],
            existing_operation_candidates=[
                ImportReviewExistingTransferCandidateApiResponse(
                    operation_id=item.operation_id,
                    operation_date=item.operation_date,
                    description=item.description,
                    amount=ImportReviewResponseMapper._decimal_required(item.amount),
                    currency=item.currency,
                    counterparty_account=(
                        ImportReviewResponseMapper._transfer_account(item.counterparty_account)
                        if item.counterparty_account is not None
                        else None
                    ),
                    day_distance=item.day_distance,
                )
                for item in transfer.existing_operation_candidates
            ],
        )

    @staticmethod
    def _transfer_account(
        account: ImportReviewTransferAccountDto,
    ) -> ImportReviewTransferAccountApiResponse:
        return ImportReviewTransferAccountApiResponse(
            id=account.id,
            name=account.name,
            currency=account.currency,
        )
