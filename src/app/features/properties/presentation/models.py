from dataclasses import dataclass

from app.features.properties.models import Property


@dataclass(frozen=True)
class PropertyFormStateVM:
    error: str | None
    name: str
    short_name: str
    address: str


@dataclass(frozen=True)
class PropertyRowVM:
    property: Property
    form_id: str
    edit_form: PropertyFormStateVM
    edit_panel_open: bool


@dataclass(frozen=True)
class PropertiesPageVM:
    rows: list[PropertyRowVM]
    create_form: PropertyFormStateVM
    lifecycle_error: str | None
