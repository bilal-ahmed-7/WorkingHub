from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0004_submission_log_metadata")]

    operations = [
        migrations.AddField(
            model_name="integrationfield",
            name="config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="integrationfield",
            name="system_key",
            field=models.CharField(
                choices=[
                    ("custom", "Custom field"),
                    ("address_main", "Main address"),
                    ("address_street", "Street"),
                    ("address_city", "City"),
                    ("address_zipcode", "ZIP code"),
                ],
                default="custom",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="integrationfield",
            name="field_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"), ("textarea", "Text area"), ("number", "Number"),
                    ("email", "Email"), ("date", "Date"), ("select", "Select"),
                    ("multi_select", "Multiple select"), ("checkbox", "Checkbox"),
                    ("address_autocomplete", "Address autocomplete"),
                ],
                max_length=20,
            ),
        ),
    ]
