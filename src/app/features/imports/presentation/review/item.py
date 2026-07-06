from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.features.imports.presentation.review.actions import ReviewActionPolicy
from app.features.imports.presentation.review.labels import (
    ReviewAccountLabeler,
    ReviewLabeler,
    ReviewMoneyTonePresenter,
    ReviewOperationLinkPresenter,
    ReviewProposalSummaryPresenter,
)
from app.features.imports.presentation.review.models import (
    BadgeVM,
    ClassificationVM,
    ProblemVM,
    ReviewItemVM,
    ReviewOutcomeVM,
    ReviewPanelVM,
)
from app.features.imports.presentation.review.panels import ReviewPanelPresenter
from app.features.imports.presentation.review.references import ReviewReferenceResolver
from app.features.imports.presentation.review.state import (
    FINAL_RAW_STATUSES,
    ReviewClassificationResolver,
    ReviewConfirmabilityPolicy,
    ReviewQueueResolver,
    ReviewRuleSuggestionResolver,
    ReviewStateResolver,
)

FINAL_VISUAL_STATES = {status.value for status in FINAL_RAW_STATUSES}
FINAL_STATE_CONFIRMABILITY_MESSAGE = "строка уже в финальном состоянии"


@dataclass(frozen=True)
class ReviewItemPresenterDependencies:
    labeler: ReviewLabeler
    money_tone_presenter: ReviewMoneyTonePresenter
    account_labeler: ReviewAccountLabeler
    proposal_summary_presenter: ReviewProposalSummaryPresenter
    operation_link_presenter: ReviewOperationLinkPresenter
    classifier: ReviewClassificationResolver
    confirmability: ReviewConfirmabilityPolicy
    state_resolver: ReviewStateResolver
    queue_resolver: ReviewQueueResolver
    panel_presenter: ReviewPanelPresenter
    action_policy: ReviewActionPolicy

    @classmethod
    def build(
        cls,
        *,
        document: object,
        accounts: Sequence[object],
        categories: Sequence[object],
        properties: Sequence[object],
        transfer_suggestions: Mapping[UUID, Sequence[object]],
        existing_transfer_suggestions: Mapping[UUID, Sequence[object]],
        selected_category_id_by_row: Mapping[UUID, UUID] | None,
        open_category_editor_by_row: Mapping[UUID, bool] | None,
        category_dialog_error_by_row: Mapping[UUID, str] | None,
        category_dialog_name_by_row: Mapping[UUID, str] | None,
    ) -> "ReviewItemPresenterDependencies":
        labeler = ReviewLabeler()
        return cls(
            labeler=labeler,
            money_tone_presenter=ReviewMoneyTonePresenter(),
            account_labeler=ReviewAccountLabeler(),
            proposal_summary_presenter=ReviewProposalSummaryPresenter(),
            operation_link_presenter=ReviewOperationLinkPresenter(labeler=labeler),
            classifier=ReviewClassificationResolver(),
            confirmability=ReviewConfirmabilityPolicy(categories=categories),
            state_resolver=ReviewStateResolver(),
            queue_resolver=ReviewQueueResolver(),
            panel_presenter=ReviewPanelPresenter(
                document=document,
                accounts=accounts,
                categories=categories,
                properties=properties,
                transfer_suggestions=transfer_suggestions,
                existing_transfer_suggestions=existing_transfer_suggestions,
                selected_category_id_by_row=selected_category_id_by_row,
                open_category_editor_by_row=open_category_editor_by_row,
                category_dialog_error_by_row=category_dialog_error_by_row,
                category_dialog_name_by_row=category_dialog_name_by_row,
            ),
            action_policy=ReviewActionPolicy(
                document_id=ReviewReferenceResolver.required_id(document),
            ),
        )


class ImportReviewPresenter:
    def __init__(
        self,
        *,
        document: object,
        accounts: Sequence[object],
        categories: Sequence[object],
        properties: Sequence[object],
        transfer_suggestions: Mapping[UUID, Sequence[object]],
        existing_transfer_suggestions: Mapping[UUID, Sequence[object]],
        balance_chain_problems: dict[int, list[str]],
        selected_category_id_by_row: Mapping[UUID, UUID] | None = None,
        open_category_editor_by_row: Mapping[UUID, bool] | None = None,
        category_dialog_error_by_row: Mapping[UUID, str] | None = None,
        category_dialog_name_by_row: Mapping[UUID, str] | None = None,
        dependencies: ReviewItemPresenterDependencies | None = None,
    ) -> None:
        self.document = document
        self.accounts = accounts
        self.categories = categories
        self.balance_chain_problems = balance_chain_problems
        self.dependencies = dependencies or ReviewItemPresenterDependencies.build(
            document=document,
            accounts=accounts,
            categories=categories,
            properties=properties,
            transfer_suggestions=transfer_suggestions,
            existing_transfer_suggestions=existing_transfer_suggestions,
            selected_category_id_by_row=selected_category_id_by_row,
            open_category_editor_by_row=open_category_editor_by_row,
            category_dialog_error_by_row=category_dialog_error_by_row,
            category_dialog_name_by_row=category_dialog_name_by_row,
        )

    def build_items(self) -> dict[UUID, ReviewItemVM]:
        first_remaining_id = self.dependencies.queue_resolver.first_remaining_raw_transaction_id(
            self.document,
        )
        return {
            row.id: self.build_item(row, is_next=row.id == first_remaining_id)
            for row in getattr(self.document, "raw_transactions", [])
        }

    def build_item(self, row: object, *, is_next: bool, oob: bool = False) -> ReviewItemVM:
        classification = self.dependencies.classifier.resolve(row)
        category_panel = self.dependencies.panel_presenter.category_panel(row)
        transfer_panel = self.dependencies.panel_presenter.transfer_panel(row)
        confirmability_problems = self.dependencies.confirmability.check(
            row,
            document=self.document,
            classification=classification,
            selected_category_id=category_panel.selected_category_id,
        )
        is_confirmable = not confirmability_problems
        visual_state = self.dependencies.state_resolver.resolve(
            row,
            is_confirmable=is_confirmable,
        )
        row_id = ReviewReferenceResolver.required_id(row)
        panels = [
            ReviewPanelVM(
                id=f"category-panel-{row_id}",
                title="Категория",
                summary_note="основной разбор строки",
                role="primary",
                panel_type="category",
                template_name="imports/review/_category_panel.html",
                is_open=category_panel.open_category_editor,
                payload=category_panel,
            ),
            ReviewPanelVM(
                id=f"transfer-panel-{row_id}",
                title="Перевод",
                summary_note="если это перемещение между счетами",
                role="alternative",
                panel_type="transfer",
                template_name="imports/review/_transfer_panel.html",
                is_open=False,
                payload=transfer_panel,
            ),
        ]
        actions = self.dependencies.action_policy.actions_for(
            row,
            visual_state=visual_state,
            is_confirmable=is_confirmable,
            category_panel_id=panels[0].id,
            transfer_panel_id=panels[1].id,
            category_id=category_panel.selected_category_id,
            property_id=getattr(row, "suggested_property_id", None),
        )
        proposed_category = ReviewReferenceResolver.category_by_id(
            self.categories,
            getattr(row, "suggested_category_id", None),
        )
        suggested_property = ReviewReferenceResolver.object_by_id(
            self.dependencies.panel_presenter.properties,
            getattr(row, "suggested_property_id", None),
        )
        return ReviewItemVM(
            row=row,
            id=row_id,
            anchor_id=review_row_anchor(row_id),
            row_index=getattr(row, "row_index", 0),
            visual_state=visual_state,
            is_confirmable=is_confirmable,
            is_next=is_next,
            status_label=self.dependencies.labeler.raw_status(getattr(row, "status", None)),
            description=self.dependencies.labeler.description(row),
            date_label=getattr(row, "operation_date", None)
            or getattr(row, "operation_date_raw", None)
            or "",
            amount_label=getattr(row, "amount", None) or getattr(row, "amount_raw", None) or "",
            currency=getattr(row, "currency", None) or "",
            money_tone=self.dependencies.money_tone_presenter.tone(
                getattr(row, "amount", None),
                classification.operation_type,
            ),
            operation_type=classification.operation_type.value
            if classification.operation_type is not None
            else None,
            operation_type_label=self.dependencies.labeler.classification_label(classification),
            operation_type_source=classification.source,
            operation_type_source_label=self.dependencies.labeler.classification_source_label(
                classification,
            ),
            state_badge=self.state_badge(visual_state),
            classification_badge=self.classification_badge(classification),
            classification_source_badge=self.classification_source_badge(classification),
            account_label=self.dependencies.account_labeler.account(
                row,
                self.document,
                self.accounts,
            ),
            problems=self.build_problems(
                row,
                confirmability_problems,
                visual_state=visual_state,
            ),
            primary_action=actions.primary,
            visible_secondary_action=actions.visible_secondary,
            menu_actions=actions.menu,
            danger_actions=actions.danger,
            initial_active_panel_id=self.initial_active_panel_id(panels),
            panels=self.visible_panels(visual_state=visual_state, panels=panels),
            proposal_summary=self.build_proposal_summary(
                row,
                visual_state=visual_state,
                category=proposed_category,
                property_=suggested_property,
            ),
            outcome_summary=self.build_outcome_summary(
                row,
                visual_state=visual_state,
                classification=classification,
                category=proposed_category,
            ),
            operation_link=self.dependencies.operation_link_presenter.operation_link(
                getattr(row, "linked_operation", None),
            ),
            oob=oob,
        )

    def state_badge(self, visual_state: str) -> BadgeVM:
        return BadgeVM(self.dependencies.labeler.raw_status(visual_state), visual_state)

    def classification_badge(self, classification: ClassificationVM) -> BadgeVM:
        return BadgeVM(
            self.dependencies.labeler.classification_label(classification),
            self.dependencies.labeler.classification_tone(classification),
        )

    def classification_source_badge(self, classification: ClassificationVM) -> BadgeVM | None:
        if classification.source in {"explicit", "suggested"}:
            return None
        return BadgeVM(
            self.dependencies.labeler.classification_source_label(classification),
            "muted",
        )

    def build_problems(
        self,
        row: object,
        confirmability_problems: Sequence[str],
        *,
        visual_state: str,
    ) -> list[ProblemVM]:
        problems: list[ProblemVM] = []
        normalization_error = getattr(row, "normalization_error", None)
        if normalization_error:
            problems.append(ProblemVM(str(normalization_error), "danger"))
        for problem in self.balance_chain_problems.get(getattr(row, "row_index", -1), []):
            problems.append(ProblemVM(problem, "warning"))
        for problem in self.visible_confirmability_problems(
            confirmability_problems,
            visual_state=visual_state,
        ):
            problems.append(ProblemVM(problem, "muted"))
        return problems

    def build_proposal_summary(
        self,
        row: object,
        *,
        visual_state: str,
        category: object | None,
        property_: object | None,
    ) -> str | None:
        if visual_state in FINAL_VISUAL_STATES:
            return None
        return self.dependencies.proposal_summary_presenter.summary(
            row,
            category=category,
            property_=property_,
        )

    def build_outcome_summary(
        self,
        row: object,
        *,
        visual_state: str,
        classification: ClassificationVM,
        category: object | None,
    ) -> ReviewOutcomeVM | None:
        if (
            visual_state != "suggested"
            or not ReviewRuleSuggestionResolver.has_active_suggestion(row)
            or classification.operation_type is None
        ):
            return None
        return ReviewOutcomeVM(
            title=self.dependencies.labeler.raw_status(visual_state),
            detail=self.suggested_outcome_detail(classification, category=category),
            type_value=self.dependencies.labeler.operation_type_value(
                classification.operation_type,
            ),
            type_label=self.dependencies.labeler.operation_type(classification.operation_type),
            tone=visual_state,
        )

    def suggested_outcome_detail(
        self,
        classification: ClassificationVM,
        *,
        category: object | None,
    ) -> str:
        category_name = getattr(category, "name", None)
        if category_name:
            return str(category_name)
        if classification.operation_type is not None:
            return self.dependencies.labeler.operation_type(classification.operation_type)
        return "предложение"

    def visible_confirmability_problems(
        self,
        confirmability_problems: Sequence[str],
        *,
        visual_state: str,
    ) -> list[str]:
        if visual_state in FINAL_VISUAL_STATES:
            return []
        return [
            problem
            for problem in confirmability_problems
            if problem != FINAL_STATE_CONFIRMABILITY_MESSAGE
        ]

    def visible_panels(
        self,
        *,
        visual_state: str,
        panels: Sequence[ReviewPanelVM],
    ) -> Sequence[ReviewPanelVM]:
        if visual_state in {"confirmed", "matched"}:
            return []
        return panels

    def initial_active_panel_id(self, panels: Sequence[ReviewPanelVM]) -> str:
        panel = next((panel for panel in panels if panel.is_open), None)
        return panel.id if panel is not None else ""


def review_row_anchor(raw_transaction_id: UUID) -> str:
    return f"raw-{raw_transaction_id}"
