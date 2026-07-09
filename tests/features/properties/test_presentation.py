from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

import app.features.properties.router as properties_router
from app.features.properties.models import PropertyStatus
from app.features.properties.presentation.presenter import (
    PropertiesPagePresenter,
    property_form_state,
)
from app.features.properties.router import property_recent_url


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
        recent_property_id=property_id,
    )

    assert page.create_form.name == "Дом"
    assert page.create_form_id == "property-create-form"
    assert page.create_label == "создать объект"
    assert page.create_panel_open
    assert page.create_submit_action.form_id == "property-create-form"
    assert page.lifecycle_error == "Объект не найден в этом workspace."
    assert page.recent_property is page.rows[0]
    assert page.rows[0].form_id == f"property-form-{property_id}"
    assert page.rows[0].anchor_id == f"property-{property_id}"
    assert page.rows[0].edit_panel_open
    assert page.rows[0].is_recent
    assert page.rows[0].edit_form.name == "Дом"
    assert page.rows[0].edit_toggle_action.action_type == "panel_toggle"
    assert page.rows[0].lifecycle_action.label == "в архив"
    assert page.rows[0].save_action.form_id == f"property-form-{property_id}"
    assert page.rows[1].edit_form.name == "Office"
    assert page.rows[1].edit_form.short_name == ""
    assert page.rows[1].is_inactive
    assert page.rows[1].lifecycle_action.label == "восстановить"


def test_properties_presenter_keeps_create_panel_closed_for_existing_clean_list() -> None:
    property_id = uuid4()
    page = PropertiesPagePresenter.build_index(
        cast(
            Any,
            [
                SimpleNamespace(
                    id=property_id,
                    name="9 Maya 20",
                    short_name=None,
                    address=None,
                    status=PropertyStatus.ACTIVE,
                )
            ],
        )
    )

    assert not page.create_panel_open


def test_property_recent_url_targets_created_property_anchor() -> None:
    property_id = uuid4()

    assert property_recent_url(property_id) == (
        f"/properties?recent_property_id={property_id}#property-{property_id}"
    )


@pytest.mark.asyncio
async def test_property_update_redirect_keeps_row_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    property_id = uuid4()
    monkeypatch.setattr(properties_router, "PropertyService", fake_property_service(property_id))

    response = await properties_router.update_property(
        property_id=property_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
        name="Дом",
        short_name=None,
        address=None,
    )

    assert response.status_code == 303
    assert response.headers["location"] == property_recent_url(property_id)


@pytest.mark.asyncio
async def test_property_lifecycle_redirect_keeps_row_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    property_id = uuid4()
    monkeypatch.setattr(properties_router, "PropertyService", fake_property_service(property_id))

    archive_response = await properties_router.archive_property(
        property_id=property_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
    )
    restore_response = await properties_router.restore_property(
        property_id=property_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
    )

    assert archive_response.status_code == 303
    assert archive_response.headers["location"] == property_recent_url(property_id)
    assert restore_response.status_code == 303
    assert restore_response.headers["location"] == property_recent_url(property_id)


def fake_property_service(property_id: object) -> type:
    class FakePropertyService:
        def __init__(self, _session: object) -> None:
            pass

        async def update(self, **_kwargs: object) -> object:
            return SimpleNamespace(id=property_id)

        async def set_status(self, **_kwargs: object) -> object:
            return SimpleNamespace(id=property_id)

    return FakePropertyService


def workspace_context() -> Any:
    return cast(Any, SimpleNamespace(workspace=SimpleNamespace(id=uuid4())))
