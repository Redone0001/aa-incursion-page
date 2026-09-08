from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incursionstatus", "0003_incursion_sde_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="incursion",
            name="region_name",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
