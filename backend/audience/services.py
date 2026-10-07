"""Convert flexible integration payloads into the canonical Audience schema."""

from django.db import IntegrityError, transaction

from audience.models import Audience, normalise_mobile


def _normalise(value):
    return "".join(character for character in value.lower() if character.isalnum())


def _value(data, *keys):
    normalised = {_normalise(key): value for key, value in data.items()}
    for key in keys:
        normalised_key = _normalise(key)
        value = normalised.get(normalised_key)
        if value not in (None, "", []):
            return str(value)
        for field_name, field_value in normalised.items():
            if field_name.endswith(normalised_key) and field_value not in (None, "", []):
                return str(field_value)
    return ""


def phone_identity(value):
    return normalise_mobile(value)


def matching_audience_records(company, values):
    identity = phone_identity(values.get("mobile", ""))
    if not identity:
        return []
    return list(
        Audience.objects.filter(company=company, mobile=identity).order_by("id")
    )


def _phone_value(data):
    value = _value(data, "mobile", "phone", "phone number", "mobile number")
    if value:
        return value
    for key, candidate in data.items():
        normalized_key = _normalise(key)
        if ("phone" in normalized_key or "mobile" in normalized_key) and candidate not in (None, "", []):
            return str(candidate)
    return ""


def audience_values(data):
    return {
        "name": _value(data, "name", "full name"),
        "mobile": _phone_value(data),
        "email": _value(data, "email", "email address"),
        "zipcode": _value(data, "address_zipcode", "zip code", "zipcode", "zip", "postal code", "post code", "postcode"),
        "city": _value(data, "address_city", "city", "town", "locality", "municipality"),
        "street": _value(data, "address_street", "street address", "street", "street number", "address line 1"),
        "state": _value(data, "address_state", "state", "province", "region", "country"),
    }


class DuplicateAudiencePhone(Exception):
    def __init__(self, mobile):
        self.mobile = mobile
        super().__init__(f"An audience with phone number {mobile} already exists.")


def sync_audience_record(integration, data):
    values = audience_values(data)
    identity = phone_identity(values["mobile"])
    record = Audience.objects.filter(mobile=identity).order_by("id").first()
    if record:
        if record.company_id != integration.company_id:
            raise DuplicateAudiencePhone(values["mobile"])
        for attribute, value in values.items():
            if value:
                setattr(record, attribute, value)
        record.save()
        return record, False

    try:
        with transaction.atomic():
            record = Audience.objects.create(
                company=integration.company,
                integration=integration,
                **values,
            )
        return record, True
    except IntegrityError:
        record = Audience.objects.filter(mobile=identity).order_by("id").first()
        if record is None:
            raise
        if record.company_id != integration.company_id:
            raise DuplicateAudiencePhone(values["mobile"]) from None
        for attribute, value in values.items():
            if value:
                setattr(record, attribute, value)
        record.save()
        return record, False
