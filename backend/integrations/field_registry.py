"""Definitions for system-managed composite integration fields."""

from integrations.models import IntegrationField


ADDRESS_CHILDREN = (
    ("Street", IntegrationField.SystemKeys.ADDRESS_STREET),
    ("City", IntegrationField.SystemKeys.ADDRESS_CITY),
    ("ZIP Code", IntegrationField.SystemKeys.ADDRESS_ZIPCODE),
)

COMPOSITE_FIELD_GROUPS = {
    "address": {
        "parent_type": IntegrationField.FieldTypes.ADDRESS_AUTOCOMPLETE,
        "parent_key": IntegrationField.SystemKeys.ADDRESS_MAIN,
        "children": ADDRESS_CHILDREN,
        "blocked_standalone_names": {"street", "city", "zip", "zip code", "zipcode", "postal code"},
    },
}


def submission_key(field):
    """Keep custom-field payloads backward compatible while system fields use stable keys."""
    return field.name if field.system_key == IntegrationField.SystemKeys.CUSTOM else field.system_key
