"""Definitions for system-managed composite integration fields."""

from integrations.models import IntegrationField


IDENTIFIER_FIELDS = (
    {
        "name": "Email",
        "field_type": IntegrationField.FieldTypes.EMAIL,
        "system_key": IntegrationField.SystemKeys.EMAIL,
        "aliases": {"email", "emailaddress"},
        "message": "Please enter your email address.",
    },
    {
        "name": "Phone number",
        "field_type": IntegrationField.FieldTypes.NUMBER,
        "system_key": IntegrationField.SystemKeys.PHONE,
        "aliases": {"phone", "phonenumber", "mobile", "mobilenumber"},
        "message": "Please enter your phone number.",
    },
)


def normalise_field_name(value):
    return "".join(character for character in value.lower() if character.isalnum())


def identifier_field_for_name(name):
    normalized_name = normalise_field_name(name)
    return next(
        (
            field for field in IDENTIFIER_FIELDS
            if any(normalized_name.endswith(alias) for alias in field["aliases"])
        ),
        None,
    )


ADDRESS_CHILDREN = (
    ("Street", IntegrationField.SystemKeys.ADDRESS_STREET),
    ("City", IntegrationField.SystemKeys.ADDRESS_CITY),
    ("ZIP Code", IntegrationField.SystemKeys.ADDRESS_ZIPCODE),
    ("State", IntegrationField.SystemKeys.ADDRESS_STATE),
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
