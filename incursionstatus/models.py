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
    region_name = models.CharField(max_length=100, blank=True)
    faction_id = models.PositiveBigIntegerField()
    faction_name = models.CharField(max_length=100, blank=True)
    has_boss = models.BooleanField(default=False)
    infested_solar_systems = models.JSONField(default=list)
    infested_solar_system_names = models.JSONField(default=list)
    infested_solar_system_roles = models.JSONField(default=list)
    influence = models.FloatField()
    staging_solar_system_id = models.PositiveBigIntegerField()
    staging_solar_system_name = models.CharField(max_length=100, blank=True)
    security_status = models.FloatField(blank=True, null=True)
    headquarter_solar_system_id = models.PositiveBigIntegerField(blank=True, null=True)
    headquarter_solar_system_name = models.CharField(max_length=100, blank=True)
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
            self.State.MOBILIZING: "incursion-state-mobilizing",
            self.State.ESTABLISHED: "text-bg-success",
            self.State.WITHDRAWING: "text-bg-danger",
        }.get(self.state, "text-bg-secondary")

    @property
    def security_band(self) -> str:
        if self.security_status is None:
            return "unknown"
        if self.security_status > 0.5:
            return "highsec"
        if self.security_status < 0:
            return "nullsec"
        return "lowsec"

    @property
    def security_band_label(self) -> str:
        return {
            "highsec": "Highsec",
            "lowsec": "Lowsec",
            "nullsec": "Nullsec",
        }.get(self.security_band, "Unknown security")

    @property
    def security_border_class(self) -> str:
        return f"incursion-card-{self.security_band}"

    @property
    def infested_systems_display(self) -> list[dict[str, int | str]]:
        return [
            {
                "id": system_id,
                "name": self.infested_solar_system_names[index]
                if index < len(self.infested_solar_system_names)
                else str(system_id),
                "role": self.infested_solar_system_roles[index]
                if index < len(self.infested_solar_system_roles)
                else "",
            }
            for index, system_id in enumerate(self.infested_solar_systems)
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "constellation_id": self.constellation_id,
            "constellation_name": self.constellation_name,
            "region_name": self.region_name,
            "faction_id": self.faction_id,
            "faction_name": self.faction_name,
            "has_boss": self.has_boss,
            "infested_solar_systems": self.infested_solar_systems,
            "infested_solar_system_names": self.infested_solar_system_names,
            "infested_solar_system_roles": self.infested_solar_system_roles,
            "influence": self.influence,
            "staging_solar_system_id": self.staging_solar_system_id,
            "staging_solar_system_name": self.staging_solar_system_name,
            "security_status": self.security_status,
            "headquarter_solar_system_id": self.headquarter_solar_system_id,
            "headquarter_solar_system_name": self.headquarter_solar_system_name,
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


class NotificationRule(models.Model):
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    region_name = models.CharField(
        max_length=100, blank=True,
        help_text="Exact region name (case-insensitive). Leave empty for all regions.",
    )
    channel_id = models.CharField(max_length=20)
    role_id = models.CharField(max_length=20, blank=True, help_text="Optional Discord role ID to ping.")
    notify_spawn = models.BooleanField(default=True)
    notify_disappearance = models.BooleanField(default=True)
    notify_state = models.BooleanField(default=False, verbose_name="Notify phase changes")
    notify_boss = models.BooleanField(default=False, verbose_name="Notify boss availability changes")
    notify_influence = models.BooleanField(default=False, help_text="May send an alert every ESI update.")

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        for field in ("channel_id", "role_id"):
            value = getattr(self, field)
            if (field == "channel_id" or value) and (
                not value.isascii() or not value.isdecimal() or not 0 < int(value) < 2**64
            ):
                errors[field] = "Enter a positive Discord ID (up to 64 bits)."
        if not any((self.notify_spawn, self.notify_disappearance, self.notify_state,
                    self.notify_boss, self.notify_influence)):
            errors["notify_spawn"] = "Select at least one notification event."
        self.region_name = self.region_name.strip()
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class NotificationDelivery(models.Model):
    rule = models.ForeignKey(NotificationRule, on_delete=models.CASCADE)
    change = models.ForeignKey(IncursionChange, on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=20)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("rule", "change"), name="incursion_notification_rule_change"),
        ]
        ordering = ("pk",)
