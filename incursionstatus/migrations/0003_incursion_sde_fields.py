from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incursionstatus", "0002_incursion_security_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="incursion",
            name="headquarter_solar_system_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incursion",
            name="headquarter_solar_system_name",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="incursion",
            name="infested_solar_system_roles",
            field=models.JSONField(default=list),
        ),
    ]
