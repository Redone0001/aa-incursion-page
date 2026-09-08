from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incursionstatus", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="incursion",
            name="security_status",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
