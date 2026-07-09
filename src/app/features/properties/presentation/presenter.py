from uuid import UUID

from app.features.properties.models import Property, PropertyStatus
from app.features.properties.presentation.models import (
    PropertiesPageVM,
    PropertyFormStateVM,
    PropertyRowVM,
)
from app.shared.ui.actions import ActionVM
from app.templating import ru_label


class PropertiesPagePresenter:
    @staticmethod
    def build_index(
        properties: list[Property],
        *,
        create_form: PropertyFormStateVM | None = None,
        edit_forms_by_property_id: dict[UUID, PropertyFormStateVM] | None = None,
        lifecycle_error: str | None = None,
    ) -> PropertiesPageVM:
        edit_forms = edit_forms_by_property_id or {}
        resolved_create_form = create_form or default_property_form_state()
        return PropertiesPageVM(
            rows=[
                property_row_vm(
                    property_,
                    edit_form=edit_forms.get(property_.id),
                )
                for property_ in properties
            ],
            create_form=resolved_create_form,
            create_form_id="property-create-form",
            create_label="создать объект",
            create_panel_open=bool(resolved_create_form.error or not properties),
            create_submit_action=ActionVM(
                id="create-property",
                label="создать объект",
                icon="plus",
                placement="primary",
                action_type="submit",
                form_id="property-create-form",
            ),
            lifecycle_error=lifecycle_error,
        )


def default_property_form_state() -> PropertyFormStateVM:
    return PropertyFormStateVM(
        error=None,
        name="",
        short_name="",
        address="",
    )


def property_form_state(
    *,
    error: str | None,
    name: str,
    short_name: str | None,
    address: str | None,
) -> PropertyFormStateVM:
    return PropertyFormStateVM(
        error=error,
        name=name,
        short_name=short_name or "",
        address=address or "",
    )


def property_row_vm(
    property_: Property,
    *,
    edit_form: PropertyFormStateVM | None = None,
) -> PropertyRowVM:
    form_id = f"property-form-{property_.id}"
    edit_summary_id = f"property-edit-toggle-{property_.id}"
    resolved_edit_form = edit_form or PropertyFormStateVM(
        error=None,
        name=property_.name,
        short_name=property_.short_name or "",
        address=property_.address or "",
    )
    is_archived = property_.status == PropertyStatus.ARCHIVED
    return PropertyRowVM(
        property=property_,
        anchor_id=f"property-{property_.id}",
        form_id=form_id,
        edit_summary_id=edit_summary_id,
        edit_form=resolved_edit_form,
        edit_panel_open=bool(resolved_edit_form.error),
        is_inactive=is_archived,
        status_label=ru_label(property_.status),
        status_tone="archived" if is_archived else "active",
        short_name_label=property_.short_name,
        address_label=property_.address,
        technical_label=f"ID {property_.id}",
        edit_toggle_action=ActionVM(
            id="edit-property",
            label="изменить объект",
            icon="settings",
            placement="primary",
            action_type="panel_toggle",
            panel_id=edit_summary_id,
        ),
        lifecycle_action=ActionVM(
            id="restore-property" if is_archived else "archive-property",
            label="восстановить" if is_archived else "в архив",
            icon="rotate-ccw" if is_archived else "archive",
            placement="secondary",
            action_type="post",
            url=f"/properties/{property_.id}/restore"
            if is_archived
            else f"/properties/{property_.id}/archive",
        ),
        save_action=ActionVM(
            id="save-property",
            label="сохранить",
            icon="save",
            placement="primary",
            action_type="submit",
            form_id=form_id,
        ),
    )
