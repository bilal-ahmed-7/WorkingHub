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


def audience_values(data):
    return {
        "name": _value(data, "name", "full name"),
        "mobile": _value(data, "mobile", "phone", "phone number", "mobile number"),
        "email": _value(data, "email", "email address"),
        "zipcode": _value(data, "address_zipcode", "zip code", "zipcode", "postal code", "area zip code"),
        "city": _value(data, "address_city", "city"),
        "street": _value(data, "address_street", "street", "street number"),
        "state": _value(data, "state", "province"),
    }


def sync_audience_record(integration, data):
    values = audience_values(data)
    return Audience.objects.create(company=integration.company, integration=integration, **values)
