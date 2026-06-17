from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.models import RawTransactionStatus
from app.features.imports.parsing.parser_types import RawTransactionDraft


def extracted_text(extracted: ExtractedPdf) -> str:
    return "\n".join(page_text or "" for page_text in extracted.text_by_page)


def cell(row: Sequence[str | None], index: int) -> str | None:
    if index >= len(row):
        return None
    return row[index]


def parse_with_error[T](
    parser: Callable[[str | None], T | None],
    raw: str | None,
    normalization_errors: list[str],
) -> T | None:
    try:
        return parser(raw)
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None


def build_raw_transaction_draft(
    *,
    row_index: int,
    raw_payload: dict[str, object],
    operation_date_raw: str | None,
    posting_date_raw: str | None,
    description_raw: str | None,
    amount_raw: str | None,
    currency_raw: str | None,
    balance_after_raw: str | None,
    account_hint_raw: str | None,
    account_id: UUID | None,
    operation_date: date | None,
    posting_date: date | None,
    description_normalized: str | None,
    amount: Decimal | None,
    currency: str | None,
    balance_after: Decimal | None,
    dedupe_hash: str | None,
    is_normalized: bool,
    normalized_confidence: Decimal,
    review_confidence: Decimal = Decimal("0.5000"),
    normalization_errors: Sequence[str] = (),
) -> RawTransactionDraft:
    return RawTransactionDraft(
        row_index=row_index,
        status=RawTransactionStatus.NORMALIZED
        if is_normalized
        else RawTransactionStatus.NEEDS_REVIEW,
        raw_payload=raw_payload,
        operation_date_raw=operation_date_raw,
        posting_date_raw=posting_date_raw,
        description_raw=description_raw,
        amount_raw=amount_raw,
        currency_raw=currency_raw,
        balance_after_raw=balance_after_raw,
        account_hint_raw=account_hint_raw,
        account_id=account_id,
        operation_date=operation_date,
        posting_date=posting_date,
        description_normalized=description_normalized,
        amount=amount,
        currency=currency,
        balance_after=balance_after,
        dedupe_hash=dedupe_hash,
        confidence_score=normalized_confidence if is_normalized else review_confidence,
        normalization_error="; ".join(normalization_errors) if normalization_errors else None,
    )
