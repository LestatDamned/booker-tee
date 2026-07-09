from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.properties.models import PropertyStatus
from app.features.properties.presentation.presenter import (
    PropertiesPagePresenter,
    property_form_state,
)


def test_properties_presenter_builds_create_and_row_edit_state() -> None:
    property_id = uuid4()
    other_property_id = uuid4()
    properties = cast(
        Any,
        [
            SimpleNamespace(
                id=property_id,
                name="9 Maya 20",
                short_name="9M20",
                address="Krasnoyarsk",
                status=PropertyStatus.ACTIVE,
            ),
            SimpleNamespace(
                id=other_property_id,
                name="Office",
                short_name=None,
                address=None,
                status=PropertyStatus.ARCHIVED,
            ),
        ],
    )

    page = PropertiesPagePresenter.build_index(
        properties,
        create_form=property_form_state(
            error="Название объекта обязательно.",
            name="Дом",
            short_name="D",
            address="Красноярск",
        ),
        edit_forms_by_property_id={
            property_id: property_form_state(
                error="Название объекта обязательно.",
                name="Дом",
                short_name="D",
                address="Красноярск",
            )
        },
        lifecycle_error="Объект не найден в этом workspace.",
    )

    assert page.create_form.name == "Дом"
    assert page.lifecycle_error == "Объект не найден в этом workspace."
    assert page.rows[0].form_id == f"property-form-{property_id}"
    assert page.rows[0].edit_panel_open
    assert page.rows[0].edit_form.name == "Дом"
    assert page.rows[1].edit_form.name == "Office"
    assert page.rows[1].edit_form.short_name == ""
