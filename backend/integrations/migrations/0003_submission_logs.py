from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("integrations", "0002_integrationsubmission")]

    operations = [
        migrations.AddField(
            model_name="integrationsubmission",
            name="identity_key",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="integrationsubmission",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name="IntegrationSubmissionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.JSONField(default=dict)),
                ("identity_key", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("success", "Success"), ("error", "Error")], max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("integration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submission_logs", to="integrations.integration")),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
    ]