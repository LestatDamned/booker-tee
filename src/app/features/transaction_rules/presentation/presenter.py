from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.presentation.models import RuleMetaVM, RuleRowVM, RulesPageVM
from app.shared.ui.actions import ActionVM
from app.templating import ru_label


class TransactionRulesPagePresenter:
    @staticmethod
    def build(
        rules: list[TransactionRule],
        *,
        can_write: bool,
    ) -> RulesPageVM:
        rows = [TransactionRulesPagePresenter._row(rule) for rule in rules]
        active_count = sum(1 for rule in rules if rule.is_active)
        return RulesPageVM(
            rules=rows,
            can_write=can_write,
            total_rule_count=len(rows),
            active_rule_count=active_count,
            inactive_rule_count=len(rows) - active_count,
        )

    @staticmethod
    def _row(rule: TransactionRule) -> RuleRowVM:
        return RuleRowVM(
            id=rule.id,
            anchor_id=f"rule-{rule.id}",
            form_id=f"rule-form-{rule.id}",
            form_action=f"/rules/{rule.id}",
            title=rule_title(rule),
            pattern=rule.pattern,
            status_label="активно" if rule.is_active else "выключено",
            status_tone="confirmed" if rule.is_active else "muted",
            is_inactive=not rule.is_active,
            match_type=rule.match_type,
            application_mode=rule.application_mode,
            direction=rule.direction,
            target_operation_type=rule.target_operation_type,
            category_id=rule.category_id,
            property_id=rule.property_id,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            meta=rule_meta(rule),
            technical_label=f"ID {rule.id}",
            save_action=ActionVM(
                id="save-rule",
                label="сохранить",
                icon="save",
                placement="primary",
                action_type="submit",
                form_id=f"rule-form-{rule.id}",
            ),
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
