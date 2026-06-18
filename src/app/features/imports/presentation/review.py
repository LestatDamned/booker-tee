from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReviewPageContext:
    document: object
    accounts: Sequence[object]
    categories: Sequence[object]
    properties: Sequence[object]
    transfer_suggestions: Mapping[UUID, Sequence[object]]
    balance_chain_problems: dict[int, list[str]]

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        return {
            "accounts": self.accounts,
            "app_name": app_name,
            "categories": self.categories,
            "document": self.document,
            "balance_chain_problems": self.balance_chain_problems,
            "properties": self.properties,
            "transfer_suggestions": self.transfer_suggestions,
            "workspace": workspace,
        }


def build_review_page_context(
    *,
    document: object,
    accounts: Sequence[object],
    categories: Sequence[object],
    properties: Sequence[object],
    transfer_suggestions: Mapping[UUID, Sequence[object]],
) -> ReviewPageContext:
    return ReviewPageContext(
        document=document,
        accounts=accounts,
        categories=categories,
        properties=properties,
        transfer_suggestions=transfer_suggestions,
        balance_chain_problems=balance_chain_problem_messages(latest_validation_report(document)),
    )


def review_redirect_url(document_id: UUID, raw_transaction_id: UUID | None = None) -> str:
    url = f"/imports/documents/{document_id}/review"
    if raw_transaction_id is None:
        return url
    return f"{url}#{review_row_anchor(raw_transaction_id)}"


def review_row_anchor(raw_transaction_id: UUID) -> str:
    return f"raw-{raw_transaction_id}"


def latest_validation_report(document: object) -> dict[str, object] | None:
    parse_attempts = getattr(document, "parse_attempts", None)
    if not parse_attempts:
        return None
    latest_attempt = parse_attempts[0]
    validation = getattr(latest_attempt, "validation_report_json", None)
    return validation if isinstance(validation, dict) else None


def balance_chain_problem_messages(
    validation: dict[str, object] | None,
) -> dict[int, list[str]]:
    if validation is None:
        return {}
    balance_chain = validation.get("balance_chain")
    if not isinstance(balance_chain, dict):
        return {}
    mismatches = balance_chain.get("mismatches")
    if not isinstance(mismatches, list):
        return {}

    messages: dict[int, list[str]] = {}
    for mismatch in mismatches:
        if not isinstance(mismatch, dict):
            continue
        row_index = int_or_none(mismatch.get("row_index"))
        if row_index is None:
            continue
        expected = mismatch.get("expected_balance_after")
        actual = mismatch.get("actual_balance_after")
        if isinstance(expected, str) and isinstance(actual, str):
            message = f"остаток не сходится: ожидалось {expected}, в строке {actual}"
        else:
            message = "остаток не сходится с соседними строками"
        messages.setdefault(row_index, []).append(message)
    return messages


def int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
