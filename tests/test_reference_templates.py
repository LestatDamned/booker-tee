from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.properties.models import PropertyStatus
from app.templating import create_templates


def test_categories_template_uses_compact_cards() -> None:
    category_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        kinds=list(CategoryKind),
        categories=[
            SimpleNamespace(
                id=category_id,
                name="Продукты",
                kind=CategoryKind.EXPENSE,
                is_system=True,
                system_key="food",
            )
        ],
    )

    assert "form-panel" in html
    assert "entity-card-readonly" in html
    assert "badge-expense" in html
    assert "системная" in html
    assert f"ID {str(category_id)[:8]}" in html


def test_properties_template_uses_inline_card_editing() -> None:
    property_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        properties=[
            SimpleNamespace(
                id=property_id,
                name="9 Maya 20",
                short_name="9M20",
                address="Krasnoyarsk",
                status=PropertyStatus.ACTIVE,
            )
        ],
    )

    assert "form-panel" in html
    assert "entity-card" in html
    assert "form-panel-embedded" in html
    assert "badge-active" in html
    assert "сохранить" in html
    assert f"ID {str(property_id)[:8]}" in html
