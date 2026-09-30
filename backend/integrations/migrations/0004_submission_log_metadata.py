from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0003_submission_logs")]

    operations = [
        migrations.AddField(
            model_name="integrationsubmissionlog",
            name="request_meta",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="integrationsubmissionlog",
            name="response_status",
            field=models.PositiveSmallIntegerField(default=201),
        ),
    ]