from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone


class General(models.Model):
    """Unmanaged model used to expose the page permission."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("incursion_view", "Can view incursion status"),)


class Incursion(models.Model):
    class State(models.TextChoices):
        WITHDRAWING = "withdrawing", "Withdrawing"
        MOBILIZING = "mobilizing", "Mobilizing"
        ESTABLISHED = "established", "Established"

    constellation_id = models.PositiveBigIntegerField(unique=True)
    constellation_name = models.CharField(max_length=100, blank=True)
    faction_id = models.PositiveBigIntegerField()
    faction_name = models.CharField(max_length=100, blank=True)
    has_boss = models.BooleanField(default=False)
    infested_solar_systems = models.JSONField(default=list)
    infested_solar_system_names = models.JSONField(default=list)
    influence = models.FloatField()
    staging_solar_system_id = models.PositiveBigIntegerField()
    staging_solar_system_name = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=20, choices=State.choices)
    incursion_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    last_changed = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("state", "constellation_name", "constellation_id")

    def __str__(self) -> str:
        return self.constellation_name or str(self.constellation_id)

    @property
    def influence_percent(self) -> int:
        return round(max(0.0, min(self.influence, 1.0)) * 100)

    @property
    def state_badge_class(self) -> str:
        return {
            self.State.MOBILIZING: "text-bg-info",
            self.State.ESTABLISHED: "text-bg-danger",
            self.State.WITHDRAWING: "text-bg-warning",
        }.get(self.state, "text-bg-secondary")

    @property
    def infested_systems_display(self) -> list[dict[str, int | str]]:
        return [
            {
                "id": system_id,
                "name": self.infested_solar_system_names[index]
                if index < len(self.infested_solar_system_names)
                else str(system_id),
            }
            for index, system_id in enumerate(self.infested_solar_systems)
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "constellation_id": self.constellation_id,
            "constellation_name": self.constellation_name,
            "faction_id": self.faction_id,
            "faction_name": self.faction_name,
            "has_boss": self.has_boss,
            "infested_solar_systems": self.infested_solar_systems,
            "infested_solar_system_names": self.infested_solar_system_names,
            "influence": self.influence,
            "staging_solar_system_id": self.staging_solar_system_id,
            "staging_solar_system_name": self.staging_solar_system_name,
            "state": self.state,
            "type": self.incursion_type,
            "is_active": self.is_active,
        }


class IncursionChange(models.Model):
    class ChangeType(models.TextChoices):
        APPEARED = "appeared", "Appeared"
        UPDATED = "updated", "Updated"
        ENDED = "ended", "Ended"

    incursion = models.ForeignKey(
        Incursion,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="changes",
    )
    constellation_id = models.PositiveBigIntegerField(db_index=True)
    change_type = models.CharField(max_length=20, choices=ChangeType.choices)
    changed_fields = models.JSONField(default=list)
    snapshot = models.JSONField(default=dict)
    observed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-observed_at", "-pk")

    def __str__(self) -> str:
        return f"{self.constellation_label}: {self.get_change_type_display()}"

    @property
    def constellation_label(self) -> str:
        return self.snapshot.get("constellation_name") or str(self.constellation_id)


class IncursionSyncStatus(models.Model):
    """Singleton row containing health information for the periodic update."""

    last_attempt_at = models.DateTimeField(blank=True, null=True)
    last_success_at = models.DateTimeField(blank=True, null=True)
    last_change_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "incursion sync status"
        verbose_name_plural = "incursion sync status"

    def __str__(self) -> str:
        return "Incursion ESI synchronization"

