from decimal import Decimal

from app.api.v1.import_review.schemas.responses import (
    ImportReviewAccountApiResponse,
    ImportReviewApiResponse,
    ImportReviewBalanceChainApiResponse,
    ImportReviewCapabilitiesApiResponse,
    ImportReviewDocumentApiResponse,
    ImportReviewItemApiResponse,
    ImportReviewNormalizedSourceApiResponse,
    ImportReviewQueueApiResponse,
    ImportReviewRawSourceApiResponse,
    ImportReviewRowProblemApiResponse,
    ImportReviewValidationApiResponse,
)
from app.features.imports.application.review.read_model import (
    ImportReviewAccountDto,
    ImportReviewReadModel,
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
                )
                for item in review.items
            ],
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
