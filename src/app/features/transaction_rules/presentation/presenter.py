from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from app.features.categories.models import Category
from app.features.ledger.models import OperationType
from app.features.properties.models import Property
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.presentation.models import (
    RuleFormOptionVM,
    RuleFormVM,
    RuleMetaVM,
    RuleRowVM,
    RulesPageVM,
)
from app.shared.ui.actions import ActionVM
from app.templating import ru_label


class TransactionRulesPagePresenter:
    @staticmethod
    def build(
        rules: list[TransactionRule],
        *,
        categories: Sequence[Category],
        properties: Sequence[Property],
        can_write: bool,
    ) -> RulesPageVM:
        rows = [
            TransactionRulesPagePresenter._row(
                rule,
                categories=categories,
                properties=properties,
            )
            for rule in rules
        ]
        active_count = sum(1 for rule in rules if rule.is_active)
        return RulesPageVM(
            rules=rows,
            create_form=rule_form(
                form_id="new-rule",
                action="/rules",
                categories=categories,
                properties=properties,
                submit_action=ActionVM(
                    id="create-rule",
                    label="создать правило",
                    icon="plus",
                    placement="primary",
                    action_type="submit",
                    form_id="new-rule",
                ),
                show_name=True,
            ),
            seed_defaults_action=ActionVM(
                id="seed-default-rules",
                label="загрузить базовые правила",
                icon="import",
                placement="secondary",
                action_type="post",
                url="/rules/seed-defaults",
            ),
            create_rule_label="новое правило",
            rule_count_label=rule_count_label(
                total=len(rows),
                active=active_count,
                inactive=len(rows) - active_count,
            ),
            can_write=can_write,
            total_rule_count=len(rows),
            active_rule_count=active_count,
            inactive_rule_count=len(rows) - active_count,
        )

    @staticmethod
    def _row(
        rule: TransactionRule,
        *,
        categories: Sequence[Category],
        properties: Sequence[Property],
    ) -> RuleRowVM:
        form_id = f"rule-form-{rule.id}"
        return RuleRowVM(
            anchor_id=f"rule-{rule.id}",
            title=rule_title(rule),
            status_label="активно" if rule.is_active else "выключено",
            status_tone="confirmed" if rule.is_active else "muted",
            is_inactive=not rule.is_active,
            meta=rule_meta(rule),
            form=rule_form(
                form_id=form_id,
                action=f"/rules/{rule.id}",
                categories=categories,
                properties=properties,
                submit_action=ActionVM(
                    id="save-rule",
                    label="сохранить",
                    icon="save",
                    placement="primary",
                    action_type="submit",
                    form_id=form_id,
                ),
                show_name=False,
                pattern=rule.pattern,
                selected_operation_type=rule.target_operation_type,
                selected_category_id=rule.category_id,
                selected_property_id=rule.property_id,
                selected_match_type=rule.match_type,
                selected_application_mode=rule.application_mode,
                selected_direction=rule.direction,
                amount_min=rule.amount_min,
                amount_max=rule.amount_max,
            ),
            technical_label=f"ID {rule.id}",
            toggle_action=ActionVM(
                id="toggle-rule",
                label="выключить" if rule.is_active else "включить",
                icon="settings",
                placement="secondary",
                action_type="post",
                url=f"/rules/{rule.id}/toggle",
                hidden_fields={"is_active": "false" if rule.is_active else "true"},
            ),
            delete_action=ActionVM(
                id="delete-rule",
                label="удалить",
                icon="trash",
                placement="danger",
                action_type="post",
                url=f"/rules/{rule.id}/delete",
                style="danger",
                confirm_message="Удалить правило транзакций?",
            ),
        )


def rule_count_label(*, total: int, active: int, inactive: int) -> str:
    return f"{total} правил · {active} активных · {inactive} выключенных"


def rule_form(
    *,
    form_id: str,
    action: str,
    categories: Sequence[Category],
    properties: Sequence[Property],
    submit_action: ActionVM,
    show_name: bool,
    pattern: str = "",
    name: str = "",
    selected_operation_type: OperationType | None = None,
    selected_category_id: UUID | None = None,
    selected_property_id: UUID | None = None,
    selected_match_type: TransactionRuleMatchType | None = None,
    selected_application_mode: TransactionRuleApplicationMode | None = None,
    selected_direction: MoneyDirection | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
) -> RuleFormVM:
    return RuleFormVM(
        id=form_id,
        action=action,
        pattern=pattern,
        show_name=show_name,
        name=name,
        operation_type_options=[
            RuleFormOptionVM("", "тип операции", selected_operation_type is None),
            *enum_options(list(OperationType), selected_operation_type),
        ],
        category_options=[
            RuleFormOptionVM("", "без категории", selected_category_id is None),
            *entity_options(categories, selected_category_id),
        ],
        property_options=[
            RuleFormOptionVM("", "без объекта", selected_property_id is None),
            *entity_options(properties, selected_property_id),
        ],
        match_type_options=enum_options(list(TransactionRuleMatchType), selected_match_type),
        application_mode_options=enum_options(
            list(TransactionRuleApplicationMode),
            selected_application_mode,
        ),
        direction_options=enum_options(list(MoneyDirection), selected_direction),
        amount_min=amount_min,
        amount_max=amount_max,
        submit_action=submit_action,
    )


def enum_options(
    enum_values: Sequence[object], selected_value: object | None
) -> list[RuleFormOptionVM]:
    return [
        RuleFormOptionVM(
            value=str(getattr(value, "value", value)),
            label=ru_label(value),
            selected=value == selected_value,
        )
        for value in enum_values
    ]


def entity_options(
    entities: Sequence[Category | Property],
    selected_id: UUID | None,
) -> list[RuleFormOptionVM]:
    return [
        RuleFormOptionVM(
            value=str(entity.id),
            label=entity.name,
            selected=entity.id == selected_id,
        )
        for entity in entities
    ]


def rule_title(rule: TransactionRule) -> str:
    category = rule.category
    if category is not None:
        target = category.name
    elif rule.target_operation_type is not None:
        target = ru_label(rule.target_operation_type)
    else:
        target = "без категории"
    return f"{rule.pattern} -> {target}"


def rule_meta(rule: TransactionRule) -> list[RuleMetaVM]:
    meta = [
        RuleMetaVM(ru_label(rule.match_type)),
        RuleMetaVM(ru_label(rule.application_mode), rule.application_mode.value),
        RuleMetaVM(ru_label(rule.direction), rule.direction.value),
    ]
    if rule.target_operation_type is not None:
        meta.append(
            RuleMetaVM(ru_label(rule.target_operation_type), rule.target_operation_type.value)
        )
    if rule.property is not None:
        meta.append(RuleMetaVM(rule.property.name))
    amount_label = amount_range_label(rule.amount_min, rule.amount_max)
    if amount_label is not None:
        meta.append(RuleMetaVM(amount_label))
    return meta


def amount_range_label(amount_min: object | None, amount_max: object | None) -> str | None:
    if amount_min is not None and amount_max is not None:
        return f"{amount_min}...{amount_max}"
    if amount_min is not None:
        return f"от {amount_min}"
    if amount_max is not None:
        return f"до {amount_max}"
    return None
