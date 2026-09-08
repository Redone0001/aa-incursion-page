import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "permissions": (("incursion_view", "Can view incursion status"),),
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="Incursion",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("constellation_id", models.PositiveBigIntegerField(unique=True)),
                ("constellation_name", models.CharField(blank=True, max_length=100)),
                ("faction_id", models.PositiveBigIntegerField()),
                ("faction_name", models.CharField(blank=True, max_length=100)),
                ("has_boss", models.BooleanField(default=False)),
                ("infested_solar_systems", models.JSONField(default=list)),
                ("infested_solar_system_names", models.JSONField(default=list)),
                ("influence", models.FloatField()),
                ("staging_solar_system_id", models.PositiveBigIntegerField()),
                ("staging_solar_system_name", models.CharField(blank=True, max_length=100)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("withdrawing", "Withdrawing"),
                            ("mobilizing", "Mobilizing"),
                            ("established", "Established"),
                        ],
                        max_length=20,
                    ),
                ),
                ("incursion_type", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("first_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_changed", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("state", "constellation_name", "constellation_id"),
            },
        ),
        migrations.CreateModel(
            name="IncursionSyncStatus",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_change_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "incursion sync status",
                "verbose_name_plural": "incursion sync status",
            },
        ),
        migrations.CreateModel(
            name="IncursionChange",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("constellation_id", models.PositiveBigIntegerField(db_index=True)),
                (
                    "change_type",
                    models.CharField(
                        choices=[
                            ("appeared", "Appeared"),
                            ("updated", "Updated"),
                            ("ended", "Ended"),
                        ],
                        max_length=20,
                    ),
                ),
                ("changed_fields", models.JSONField(default=list)),
                ("snapshot", models.JSONField(default=dict)),
                (
                    "observed_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                (
                    "incursion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="changes",
                        to="incursionstatus.incursion",
                    ),
                ),
            ],
            options={
                "ordering": ("-observed_at", "-pk"),
            },
        ),
    ]

