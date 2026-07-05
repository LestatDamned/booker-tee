from uuid import UUID

from app.features.imports.application.review.actions import RawTransactionReviewCommand


def parse_optional_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    return UUID(raw_value)


class RawTransactionReviewFormParser:
    def build_command(
        self,
        *,
        document_id: UUID,
        raw_transaction_id: UUID,
        action: str,
        category_id: str | None = None,
        counterparty_account_id: str | None = None,
        matched_raw_transaction_id: str | None = None,
        matched_operation_id: str | None = None,
        property_id: str | None = None,
        remember_rule: str | None = None,
        rule_pattern: str | None = None,
    ) -> RawTransactionReviewCommand:
        return RawTransactionReviewCommand(
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            action=action,
            category_id=parse_optional_uuid(category_id),
            property_id=parse_optional_uuid(property_id),
            counterparty_account_id=parse_optional_uuid(counterparty_account_id),
            matched_raw_transaction_id=parse_optional_uuid(matched_raw_transaction_id),
            matched_operation_id=parse_optional_uuid(matched_operation_id),
            remember_rule=remember_rule is not None,
            rule_pattern=rule_pattern,
        )
