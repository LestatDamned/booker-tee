from uuid import UUID

from app.features.properties.models import Property
from app.features.properties.presentation.models import (
    PropertiesPageVM,
    PropertyFormStateVM,
    PropertyRowVM,
)


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
        return PropertiesPageVM(
            rows=[
                property_row_vm(
                    property_,
                    edit_form=edit_forms.get(property_.id),
                )
                for property_ in properties
            ],
            create_form=create_form or default_property_form_state(),
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
    resolved_edit_form = edit_form or PropertyFormStateVM(
        error=None,
        name=property_.name,
        short_name=property_.short_name or "",
        address=property_.address or "",
    )
    return PropertyRowVM(
        property=property_,
        form_id=f"property-form-{property_.id}",
        edit_form=resolved_edit_form,
        edit_panel_open=bool(resolved_edit_form.error),
    )
