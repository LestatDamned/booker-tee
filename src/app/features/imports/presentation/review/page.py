from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.features.imports.presentation.review.item import ImportReviewPresenter
from app.features.imports.presentation.review.models import (
    ActionVM,
    ReviewItemVM,
    ReviewQueueVM,
    ReviewValidationSummaryVM,
)
from app.features.imports.presentation.review.state import FINAL_RAW_STATUSES


@dataclass(frozen=True)
class ReviewPageContext:
    document: object
    review_validation: ReviewValidationSummaryVM | None
    review_queue: ReviewQueueVM
    review_items: Sequence[ReviewItemVM]
    review_items_by_id: Mapping[UUID, ReviewItemVM]

    def review_item_for(self, row_id: UUID) -> ReviewItemVM | None:
        return self.review_items_by_id.get(row_id)

    def review_items_for_row_ids(self, row_ids: Collection[UUID]) -> Sequence[ReviewItemVM]:
        return [item for item in self.review_items if item.id in row_ids]

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        return {
            "app_name": app_name,
            "document": self.document,
            "review_queue": self.review_queue,
            "review_validation": self.review_validation,
            "review_items": self.review_items,
            "workspace": workspace,
        }


def build_review_page_context(
    *,
    document: object,
    accounts: Sequence[object],
    categories: Sequence[object],
    properties: Sequence[object],
    transfer_suggestions: Mapping[UUID, Sequence[object]],
    existing_transfer_suggestions: Mapping[UUID, Sequence[object]],
    selected_category_id_by_row: Mapping[UUID, UUID] | None = None,
    open_category_editor_by_row: Mapping[UUID, bool] | None = None,
    category_dialog_error_by_row: Mapping[UUID, str] | None = None,
    category_dialog_name_by_row: Mapping[UUID, str] | None = None,
) -> ReviewPageContext:
    validation_report = latest_validation_report(document)
    balance_chain_problems = balance_chain_problem_messages(validation_report)
    review_validation = ReviewValidationPresenter().build(validation_report)
    review_queue = ReviewQueuePresenter().build(document)
    review_items_by_id = ImportReviewPresenter(
        document=document,
        accounts=accounts,
        categories=categories,
        properties=properties,
        transfer_suggestions=transfer_suggestions,
        existing_transfer_suggestions=existing_transfer_suggestions,
        balance_chain_problems=balance_chain_problems,
        selected_category_id_by_row=selected_category_id_by_row,
        open_category_editor_by_row=open_category_editor_by_row,
        category_dialog_error_by_row=category_dialog_error_by_row,
        category_dialog_name_by_row=category_dialog_name_by_row,
    ).build_items()
    review_items: list[ReviewItemVM] = []
    for row in getattr(document, "raw_transactions", []):
        row_id = getattr(row, "id", None)
        if row_id in review_items_by_id:
            review_items.append(review_items_by_id[row_id])
    return ReviewPageContext(
        document=document,
        review_validation=review_validation,
        review_queue=review_queue,
        review_items=review_items,
        review_items_by_id=review_items_by_id,
    )


class ReviewQueuePresenter:
    def build(self, document: object) -> ReviewQueueVM:
        rows = list(getattr(document, "raw_transactions", []))
        total = len(rows)
        done = sum(1 for row in rows if getattr(row, "status", None) in FINAL_RAW_STATUSES)
        remaining = total - done
        first_remaining_id = next(
            (
                getattr(row, "id", None)
                for row in rows
                if getattr(row, "status", None) not in FINAL_RAW_STATUSES
            ),
            None,
        )
        progress_percent = (done * 100 / total) if total else 0
        document_id = getattr(document, "id", "")
        document_filename = str(getattr(document, "original_filename", ""))

        if total == 0:
            return ReviewQueueVM(
                total=total,
                remaining=remaining,
                done=done,
                first_remaining_id=first_remaining_id,
                progress_percent=progress_percent,
                title="Вернитесь к документу",
                message="Сырых строк пока нет. Проверьте парсинг или настройку колонок.",
                document_filename=document_filename,
                primary_action=ActionVM(
                    id="open_document",
                    label="открыть документ",
                    icon="file-text",
                    placement="secondary",
                    action_type="link",
                    url=f"/imports/documents/{document_id}",
                ),
                secondary_url=None,
                secondary_label=None,
                workflow_upload="done",
                workflow_extract="blocked",
                workflow_mapping="pending",
                workflow_review="pending",
                workflow_ledger="pending",
            )

        if remaining > 0:
            return ReviewQueueVM(
                total=total,
                remaining=remaining,
                done=done,
                first_remaining_id=first_remaining_id,
                progress_percent=progress_percent,
                title="Продолжайте проверку",
                message=f"Осталось обработать {remaining} из {total} строк.",
                document_filename=document_filename,
                primary_action=ActionVM(
                    id="next_review_item",
                    label="к следующей",
                    icon="clipboard-check",
                    placement="primary",
                    action_type="link",
                    url=f"#raw-{first_remaining_id}",
                ),
                secondary_url=None,
                secondary_label=None,
                workflow_upload="done",
                workflow_extract="done",
                workflow_mapping="skipped",
                workflow_review="current",
                workflow_ledger="pending",
            )

        return ReviewQueueVM(
            total=total,
            remaining=remaining,
            done=done,
            first_remaining_id=first_remaining_id,
            progress_percent=progress_percent,
            title="Импорт разобран",
            message="Все строки подтверждены, проигнорированы или отмечены как дубли.",
            document_filename=document_filename,
            primary_action=ActionVM(
                id="open_reports",
                label="открыть отчеты",
                icon="list-check",
                placement="primary",
                action_type="link",
                url="/reports",
            ),
            secondary_url="/imports",
            secondary_label="к импортам",
            workflow_upload="done",
            workflow_extract="done",
            workflow_mapping="skipped",
            workflow_review="done",
            workflow_ledger="done",
        )


class ReviewValidationPresenter:
    def build(
        self,
        validation: dict[str, object] | None,
    ) -> ReviewValidationSummaryVM | None:
        if validation is None:
            return None
        return ReviewValidationSummaryVM(
            status_label=str(validation.get("status", "")),
            message=str(validation.get("message", "")),
            extracted_count=validation.get("extracted_count", ""),
            needs_review_count=validation.get("needs_review_count", ""),
            currency=validation.get("currency") or "",
            calculated_total_inflow=validation.get("calculated_total_inflow", ""),
            calculated_total_outflow=validation.get("calculated_total_outflow", ""),
            statement_total_inflow=validation.get("statement_total_inflow") or "нет",
            statement_total_outflow=validation.get("statement_total_outflow") or "нет",
            inflow_difference=validation.get("inflow_difference") or "нет",
            outflow_difference=validation.get("outflow_difference") or "нет",
            warning_message=self._warning_message(validation),
        )

    def _warning_message(self, validation: dict[str, object]) -> str | None:
        if validation.get("status") in {"mismatch", "failed", "failed_to_parse"}:
            return self._mismatch_warning()
        if validation.get("inflow_difference") or validation.get("outflow_difference"):
            return self._mismatch_warning()
        return None

    def _mismatch_warning(self) -> str:
        return (
            "Проверьте строки с пометками перед подтверждением: суммы или остатки "
            "не сходятся с выпиской, поэтому отчет может быть неверным."
        )


def review_redirect_url(document_id: UUID) -> str:
    return f"/imports/documents/{document_id}/review"


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
