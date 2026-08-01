from collections.abc import Sequence
from decimal import Decimal
from urllib.parse import urlencode
from uuid import UUID

from app.features.categories.models import Category
from app.features.ledger.models import OperationType
from app.features.properties.models import Property
from app.features.transaction_rules.listing import (
    RULE_LIST_DEFAULT_LIMIT,
    RULE_LIST_LIMIT_STEP,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.presentation.models import (
    RuleFormOptionVM,
    RuleFormVM,
    RuleListFilterVM,
    RuleListPaginationVM,
    RuleRowVM,
    RulesPageVM,
)
from app.shared.ui.actions import ActionVM
from app.templating import ru_label

DEFAULT_CREATE_MATCH_TYPE = TransactionRuleMatchType.CONTAINS
DEFAULT_CREATE_APPLICATION_MODE = TransactionRuleApplicationMode.SUGGEST
DEFAULT_CREATE_DIRECTION = MoneyDirection.ANY
DEFAULT_CREATE_OPERATION_TYPE = OperationType.EXPENSE


class TransactionRulesPagePresenter:
    @staticmethod
    def build(
        rules: list[TransactionRule],
        *,
        categories: Sequence[Category],
        properties: Sequence[Property],
        can_write: bool,
        recent_rule_id: UUID | None = None,
        all_rule_count: int | None = None,
        filtered_rule_count: int | None = None,
        active_rule_count: int | None = None,
        inactive_rule_count: int | None = None,
        filter_search: str = "",
        filter_category_id: UUID | None = None,
        filter_status: str = "all",
        limit: int = RULE_LIST_DEFAULT_LIMIT,
    ) -> RulesPageVM:
        rows = [
            TransactionRulesPagePresenter.build_row(
                rule,
                is_recent=getattr(rule, "id", None) == recent_rule_id,
                filter_search=filter_search,
                filter_category_id=filter_category_id,
                filter_status=filter_status,
                limit=limit,
            )
            for rule in rules
        ]
        recent_rule = next((row for row in rows if row.is_recent), None)
        total_count = len(rows) if all_rule_count is None else all_rule_count
        filtered_count = len(rows) if filtered_rule_count is None else filtered_rule_count
        active_count = (
            sum(1 for rule in rules if rule.is_active)
            if active_rule_count is None
            else active_rule_count
        )
        inactive_count = (
            len(rows) - active_count if inactive_rule_count is None else inactive_rule_count
        )
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
                layout="create",
                selected_operation_type=DEFAULT_CREATE_OPERATION_TYPE,
                selected_match_type=DEFAULT_CREATE_MATCH_TYPE,
                selected_application_mode=DEFAULT_CREATE_APPLICATION_MODE,
                selected_direction=DEFAULT_CREATE_DIRECTION,
            ),
            seed_defaults_action=ActionVM(
                id="seed-default-rules",
                label="загрузить базовые правила",
                icon="import",
                placement="secondary",
                action_type="post",
                url="/rules/seed-defaults",
                confirm_message=(
                    "Будут добавлены базовые правила для популярных операций: продукты, "
                    "аптеки, кафе, транспорт, связь. Ваши правила не будут изменены."
                ),
            ),
            create_rule_label="создать правило",
            rule_count_label=rule_count_label(
                total=total_count,
                active=active_count,
                inactive=inactive_count,
            ),
            filters=rule_filter_vm(
                categories=categories,
                search=filter_search,
                selected_category_id=filter_category_id,
                selected_status=filter_status,
                filtered_count=filtered_count,
                total_count=total_count,
            ),
            pagination=rule_list_pagination_vm(
                visible_count=len(rows),
                filtered_count=filtered_count,
                search=filter_search,
                selected_category_id=filter_category_id,
                selected_status=filter_status,
                limit=limit,
            ),
            recent_rule=recent_rule,
            can_write=can_write,
            total_rule_count=total_count,
            active_rule_count=active_count,
            inactive_rule_count=len(rows) - active_count,
        )

    @staticmethod
    def build_row(
        rule: TransactionRule,
        *,
        is_recent: bool = False,
        filter_search: str = "",
        filter_category_id: UUID | None = None,
        filter_status: str = "all",
        limit: int = RULE_LIST_DEFAULT_LIMIT,
    ) -> RuleRowVM:
        edit_summary_id = f"rule-edit-toggle-{rule.id}"
        edit_panel_id = f"rule-edit-panel-{rule.id}"
        title = rule_title(rule)
        expected_updated_at = serialized_updated_at(rule)
        toggle_fields = {
            "is_active": "false" if rule.is_active else "true",
            "expected_active": str(rule.is_active).lower(),
        }
        delete_fields = {"expected_active": str(rule.is_active).lower()}
        if expected_updated_at is not None:
            toggle_fields["expected_updated_at"] = expected_updated_at
            delete_fields["expected_updated_at"] = expected_updated_at
        return RuleRowVM(
            anchor_id=f"rule-{rule.id}",
            title=title,
            condition_label=rule_condition_label(rule),
            secondary_label=rule_secondary_label(rule),
            status_label="активно" if rule.is_active else "выключено",
            status_tone="active" if rule.is_active else "muted",
            is_inactive=not rule.is_active,
            is_recent=is_recent,
            edit_summary_id=edit_summary_id,
            edit_panel_id=edit_panel_id,
            edit_form_url=f"/rules/{rule.id}/edit",
            edit_toggle_action=ActionVM(
                id="edit-rule",
                label="изменить правило",
                icon="settings",
                placement="primary",
                action_type="panel_toggle",
                panel_id=edit_summary_id,
            ),
            toggle_action=ActionVM(
                id="toggle-rule",
                label="выключить" if rule.is_active else "включить",
                icon="x" if rule.is_active else "check",
                placement="secondary",
                action_type="post",
                url=f"/rules/{rule.id}/toggle",
                hidden_fields=toggle_fields,
            ),
            delete_action=ActionVM(
                id="delete-rule",
                label="удалить",
                icon="trash",
                placement="danger",
                action_type="post",
                url=rule_action_url(
                    f"/rules/{rule.id}/delete",
                    search=filter_search,
                    selected_category_id=filter_category_id,
                    selected_status=filter_status,
                    limit=limit,
                ),
                style="danger",
                hidden_fields=delete_fields,
                confirm_message=(
                    f"Удалить правило “{title}”?\nОно больше не будет применяться к новым выпискам."
                ),
            ),
        )

    @staticmethod
    def build_edit_form(
        rule: TransactionRule,
        *,
        categories: Sequence[Category],
        properties: Sequence[Property],
    ) -> RuleFormVM:
        form_id = f"rule-form-{rule.id}"
        title = rule_title(rule)
        return rule_form(
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
            show_name=True,
            name=getattr(rule, "name", title),
            pattern=rule.pattern,
            selected_operation_type=rule.target_operation_type,
            selected_category_id=rule.category_id,
            selected_property_id=rule.property_id,
            selected_match_type=rule.match_type,
            selected_application_mode=rule.application_mode,
            selected_direction=rule.direction,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            expected_updated_at=serialized_updated_at(rule),
        )


def rule_count_label(*, total: int, active: int, inactive: int) -> str:
    return f"{total} правил · {active} активных · {inactive} выключенных"


def rule_filter_vm(
    *,
    categories: Sequence[Category],
    search: str,
    selected_category_id: UUID | None,
    selected_status: str,
    filtered_count: int,
    total_count: int,
) -> RuleListFilterVM:
    normalized_status = (
        selected_status if selected_status in {"all", "active", "inactive"} else "all"
    )
    normalized_search = search.strip()
    is_active = (
        bool(normalized_search) or selected_category_id is not None or normalized_status != "all"
    )
    result_label = f"найдено {filtered_count} из {total_count}" if is_active else None
    return RuleListFilterVM(
        action="/rules",
        search=normalized_search,
        category_options=[
            RuleFormOptionVM("", "любая категория", selected_category_id is None),
            *entity_options(categories, selected_category_id),
        ],
        status_options=[
            RuleFormOptionVM("all", "все статусы", normalized_status == "all"),
            RuleFormOptionVM("active", "активные", normalized_status == "active"),
            RuleFormOptionVM("inactive", "выключенные", normalized_status == "inactive"),
        ],
        is_active=is_active,
        result_label=result_label,
        reset_url="/rules",
    )


def rule_list_pagination_vm(
    *,
    visible_count: int,
    filtered_count: int,
    search: str,
    selected_category_id: UUID | None,
    selected_status: str,
    limit: int,
) -> RuleListPaginationVM:
    has_more = visible_count < filtered_count
    next_limit = min(limit + RULE_LIST_LIMIT_STEP, filtered_count)
    next_url = (
        rule_action_url(
            "/rules",
            search=search,
            selected_category_id=selected_category_id,
            selected_status=selected_status,
            limit=next_limit,
        )
        if has_more
        else None
    )
    return RuleListPaginationVM(
        visible_count=visible_count,
        filtered_count=filtered_count,
        has_more=has_more,
        next_url=next_url,
        label=f"показано {visible_count} из {filtered_count}",
    )


def rule_action_url(
    path: str,
    *,
    search: str,
    selected_category_id: UUID | None,
    selected_status: str,
    limit: int,
) -> str:
    params: dict[str, str] = {}
    normalized_search = search.strip()
    if normalized_search:
        params["q"] = normalized_search
    if selected_category_id is not None:
        params["category_id"] = str(selected_category_id)
    if selected_status != "all":
        params["status"] = selected_status
    if limit != RULE_LIST_DEFAULT_LIMIT:
        params["limit"] = str(limit)
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


def rule_form(
    *,
    form_id: str,
    action: str,
    categories: Sequence[Category],
    properties: Sequence[Property],
    submit_action: ActionVM,
    show_name: bool,
    layout: str = "edit",
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
    expected_updated_at: str | None = None,
) -> RuleFormVM:
    return RuleFormVM(
        id=form_id,
        action=action,
        layout=layout,
        pattern=pattern,
        show_name=show_name,
        name=name,
        advanced_label="Расширенные настройки",
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
        direction_options=money_direction_options(selected_direction),
        amount_min=amount_min,
        amount_max=amount_max,
        expected_updated_at=expected_updated_at,
        submit_action=submit_action,
    )


def serialized_updated_at(rule: TransactionRule) -> str | None:
    updated_at = getattr(rule, "updated_at", None)
    return updated_at.isoformat() if updated_at is not None else None


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


def money_direction_options(selected_value: MoneyDirection | None) -> list[RuleFormOptionVM]:
    return [
        RuleFormOptionVM(
            value=value.value,
            label="любое направление" if value == MoneyDirection.ANY else ru_label(value),
            selected=value == selected_value,
        )
        for value in MoneyDirection
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


def rule_condition_label(rule: TransactionRule) -> str:
    return f"Если описание {ru_label(rule.match_type)} “{rule.pattern}”"


def rule_secondary_label(rule: TransactionRule) -> str:
    labels = [
        application_mode_summary_label(rule.application_mode),
        ru_label(rule.direction),
    ]
    if rule.target_operation_type is not None:
        labels.append(ru_label(rule.target_operation_type))
    if rule.property is not None:
        labels.append(rule.property.name)
    amount_label = amount_range_label(rule.amount_min, rule.amount_max)
    if amount_label is not None:
        labels.append(amount_label)
    return " · ".join(labels)


def application_mode_summary_label(mode: TransactionRuleApplicationMode) -> str:
    if mode == TransactionRuleApplicationMode.AUTO_APPLY:
        return "автоприменение"
    return "предлагать"


def amount_range_label(amount_min: object | None, amount_max: object | None) -> str | None:
    if amount_min is not None and amount_max is not None:
        return f"{amount_min}...{amount_max}"
    if amount_min is not None:
        return f"от {amount_min}"
    if amount_max is not None:
        return f"до {amount_max}"
    return None
