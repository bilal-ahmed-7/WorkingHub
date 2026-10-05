from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("integrations", "0005_integrationfield_composite_metadata"), ("audience", "0001_initial")]

    operations = [
        migrations.AddField(model_name="audience", name="name", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(
            model_name="audience",
            name="integration",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audience_records", to="integrations.integration"),
        ),
        migrations.AlterField(model_name="audience", name="mobile", field=models.CharField(blank=True, max_length=32)),
        migrations.AlterField(model_name="audience", name="email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AlterField(model_name="audience", name="zipcode", field=models.CharField(blank=True, max_length=20)),
        migrations.AlterField(model_name="audience", name="city", field=models.CharField(blank=True, max_length=120)),
        migrations.AlterField(model_name="audience", name="street", field=models.CharField(blank=True, max_length=255)),
        migrations.AlterField(model_name="audience", name="state", field=models.CharField(blank=True, max_length=120)),
    ]
