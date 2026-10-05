"""Convert flexible integration payloads into the canonical Audience schema."""

from audience.models import Audience


def _normalise(value):
    return "".join(character for character in value.lower() if character.isalnum())


def _value(data, *keys):
    normalised = {_normalise(key): value for key, value in data.items()}
    for key in keys:
        value = normalised.get(_normalise(key))
        if value not in (None, "", []):
            return str(value)
    return ""


def phone_identity(value):
    return "".join(character for character in value if character.isdigit())


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
        "zipcode": _value(data, "address_zipcode", "zip code", "zipcode", "postal code", "area zip code"),
        "city": _value(data, "address_city", "city"),
        "street": _value(data, "address_street", "street", "street number"),
        "state": _value(data, "state", "province"),
    }


def consolidate_audience_phone(record):
    identity = phone_identity(record.mobile)
    if not identity:
        return record

    matches = [
        candidate for candidate in Audience.objects.filter(
            company=record.company,
            integration=record.integration,
        ).exclude(mobile="").order_by("id")
        if phone_identity(candidate.mobile) == identity
    ]
    if not matches:
        return record

    keeper = matches[0]
    fields = ("name", "mobile", "email", "zipcode", "city", "street", "state")
    for field in fields:
        setattr(keeper, field, getattr(record, field))
    keeper.save()

    duplicate_ids = [candidate.id for candidate in matches[1:]]
    if duplicate_ids:
        Audience.objects.filter(id__in=duplicate_ids).delete()
    return keeper


def sync_audience_record(integration, data):
    values = audience_values(data)
    identity = phone_identity(values["mobile"])
    if identity:
        record = next(
            (
                candidate for candidate in Audience.objects.filter(
                    company=integration.company,
                    integration=integration,
                ).exclude(mobile="").order_by("id")
                if phone_identity(candidate.mobile) == identity
            ),
            None,
        )
        if record is not None:
            for attribute, value in values.items():
                if value:
                    setattr(record, attribute, value)
            record.save()
            return consolidate_audience_phone(record)
    return Audience.objects.create(company=integration.company, integration=integration, **values)
