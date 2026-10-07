from django.db import migrations, models
from django.db.models import F


IDENTIFIERS = (
    {
        "name": "Email",
        "field_type": "email",
        "system_key": "email",
        "aliases": {"email", "emailaddress"},
    },
    {
        "name": "Phone number",
        "field_type": "number",
        "system_key": "phone",
        "aliases": {"phone", "phonenumber", "mobile", "mobilenumber"},
    },
)


def normalise(value):
    return "".join(character for character in value.lower() if character.isalnum())


def add_required_identifiers(apps, schema_editor):
    Integration = apps.get_model("integrations", "Integration")
    IntegrationField = apps.get_model("integrations", "IntegrationField")
    database = schema_editor.connection.alias

    for integration in Integration.objects.using(database).all().iterator():
        fields = list(
            IntegrationField.objects.using(database)
            .filter(integration_id=integration.pk)
            .order_by("position", "id")
        )
        IntegrationField.objects.using(database).filter(
            integration_id=integration.pk,
        ).update(position=F("position") + len(IDENTIFIERS))

        for position, identifier in enumerate(IDENTIFIERS):
            field = next(
                (
                    existing for existing in fields
                    if normalise(existing.name) in identifier["aliases"]
                    or any(
                        normalise(existing.name).endswith(alias)
                        for alias in identifier["aliases"]
                    )
                ),
                None,
            )
            if field:
                field.field_type = identifier["field_type"]
                field.system_key = identifier["system_key"]
                field.required = True
                field.position = position
                field.save(
                    using=database,
                    update_fields=[
                        "field_type",
                        "system_key",
                        "required",
                        "position",
                    ],
                )
            else:
                IntegrationField.objects.using(database).create(
                    integration_id=integration.pk,
                    name=identifier["name"],
                    field_type=identifier["field_type"],
                    system_key=identifier["system_key"],
                    required=True,
                    position=position,
                )


class Migration(migrations.Migration):
    dependencies = [("integrations", "0005_integrationfield_composite_metadata")]

    operations = [
        migrations.AlterField(
            model_name="integrationfield",
            name="system_key",
            field=models.CharField(
                choices=[
                    ("custom", "Custom field"),
                    ("email", "Email"),
                    ("phone", "Phone number"),
                    ("address_main", "Main address"),
                    ("address_street", "Street"),
                    ("address_city", "City"),
                    ("address_zipcode", "ZIP code"),
                ],
                default="custom",
                max_length=50,
            ),
        ),
        migrations.RunPython(add_required_identifiers, migrations.RunPython.noop),
    ]
