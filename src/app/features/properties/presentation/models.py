from dataclasses import dataclass

from app.features.properties.models import Property
from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class PropertyFormStateVM:
    error: str | None
    name: str
    short_name: str
    address: str


@dataclass(frozen=True)
class PropertyRowVM:
    property: Property
    anchor_id: str
    form_id: str
    edit_summary_id: str
    edit_form: PropertyFormStateVM
    edit_panel_open: bool
    is_inactive: bool
    is_recent: bool
    status_label: str
    status_tone: str
    short_name_label: str | None
    address_label: str | None
    technical_label: str
    edit_toggle_action: ActionVM
    lifecycle_action: ActionVM
    save_action: ActionVM


@dataclass(frozen=True)
class PropertiesPageVM:
    rows: list[PropertyRowVM]
    recent_property: PropertyRowVM | None
    create_form: PropertyFormStateVM
    create_form_id: str
    create_label: str
    create_panel_open: bool
    create_submit_action: ActionVM
    lifecycle_error: str | None
