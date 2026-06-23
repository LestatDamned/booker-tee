from app.features.transaction_rules.models import MoneyDirection
from app.templating import create_templates, icon, ru_label


def test_icon_helper_renders_accessible_inline_svg() -> None:
    rendered = str(icon("upload"))

    assert '<svg class="icon" aria-hidden="true"' in rendered
    assert 'viewBox="0 0 24 24"' in rendered


def test_templates_register_icon_helper() -> None:
    templates = create_templates()

    assert templates.env.globals["icon"] is icon


def test_money_direction_labels_do_not_duplicate_operation_type_labels() -> None:
    assert ru_label(MoneyDirection.OUTFLOW) == "списание"
    assert ru_label(MoneyDirection.INFLOW) == "поступление"
