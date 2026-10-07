from django.db import migrations, models


def normalise_existing_mobile_numbers(apps, schema_editor):
    Audience = apps.get_model("audience", "Audience")
    database = schema_editor.connection.alias
    records_by_mobile = {}

    for record in Audience.objects.using(database).order_by("id").iterator():
        mobile = "".join(character for character in record.mobile if character.isdigit())
        if not mobile:
            raise RuntimeError(
                "Cannot require audience phone numbers while a record has no valid "
                f"phone number (audience record {record.pk}). Resolve it and rerun migrations."
            )
        records_by_mobile.setdefault(mobile, []).append(record.pk)

    duplicates = {
        mobile: record_ids
        for mobile, record_ids in records_by_mobile.items()
        if len(record_ids) > 1
    }
    if duplicates:
        duplicate_summary = "; ".join(
            f"{len(record_ids)} records ({', '.join(map(str, record_ids))})"
            for record_ids in duplicates.values()
        )
        raise RuntimeError(
            "Cannot enforce unique audience phone numbers because normalized phone "
            f"numbers are duplicated: {duplicate_summary}. Resolve these records and "
            "rerun migrations."
        )

    for record in Audience.objects.using(database).order_by("id").iterator():
        mobile = "".join(character for character in record.mobile if character.isdigit())
        if record.mobile != mobile:
            record.mobile = mobile
            record.save(using=database, update_fields=["mobile"])


class Migration(migrations.Migration):
    dependencies = [
        ("audience", "0002_audience_standard_records"),
        ("integrations", "0007_alter_integrationfield_system_key"),
    ]

    operations = [
        migrations.RunPython(
            normalise_existing_mobile_numbers,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="audience",
            name="mobile",
            field=models.CharField(max_length=32, unique=True),
        ),
        migrations.AddConstraint(
            model_name="audience",
            constraint=models.CheckConstraint(
                condition=models.Q(("mobile__gt", "")),
                name="audience_mobile_not_blank",
            ),
        ),
    ]
