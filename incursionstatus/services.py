from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import Incursion, IncursionChange

TRACKED_FIELDS = (
    "constellation_name",
    "region_name",
    "faction_id",
    "faction_name",
    "has_boss",
    "infested_solar_systems",
    "infested_solar_system_names",
    "infested_solar_system_roles",
    "influence",
    "staging_solar_system_id",
    "staging_solar_system_name",
    "security_status",
    "headquarter_solar_system_id",
    "headquarter_solar_system_name",
    "state",
    "incursion_type",
)


@dataclass(frozen=True)
class SyncResult:
    appeared: int = 0
    updated: int = 0
    ended: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.appeared or self.updated or self.ended)

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _model_values(
    payload: dict[str, Any],
    names: dict[int, str],
    security_statuses: dict[int, float],
    system_roles: dict[int, str],
    region_names: dict[int, str],
) -> dict[str, Any]:
    constellation_id = int(payload["constellation_id"])
    faction_id = int(payload["faction_id"])
    staging_id = int(payload["staging_solar_system_id"])
    system_ids = sorted({int(value) for value in payload["infested_solar_systems"]})
    roles = [system_roles.get(system_id, "") for system_id in system_ids]
    headquarter_index = next(
        (index for index, role in enumerate(roles) if role == "headquarter"),
        None,
    )
    headquarter_id = system_ids[headquarter_index] if headquarter_index is not None else None

    return {
        "constellation_name": names.get(constellation_id, ""),
        "region_name": region_names.get(constellation_id, ""),
        "faction_id": faction_id,
        "faction_name": names.get(faction_id, ""),
        "has_boss": bool(payload["has_boss"]),
        "infested_solar_systems": system_ids,
        "infested_solar_system_names": [names.get(value, str(value)) for value in system_ids],
        "infested_solar_system_roles": roles,
        "influence": float(payload["influence"]),
        "staging_solar_system_id": staging_id,
        "staging_solar_system_name": names.get(staging_id, ""),
        "security_status": security_statuses.get(staging_id),
        "headquarter_solar_system_id": headquarter_id,
        "headquarter_solar_system_name": names.get(headquarter_id, "") if headquarter_id else "",
        "state": str(payload["state"]),
        "incursion_type": str(payload["type"]),
    }


def mark_active_incursions_seen(observed_at: datetime | None = None) -> None:
    """A 304 confirms the active set is unchanged without returning a body."""
    Incursion.objects.filter(is_active=True).update(last_seen=observed_at or timezone.now())


@transaction.atomic
def synchronize_incursions(
    payloads: list[dict[str, Any]],
    names: dict[int, str] | None = None,
    observed_at: datetime | None = None,
    security_statuses: dict[int, float] | None = None,
    system_roles: dict[int, str] | None = None,
    region_names: dict[int, str] | None = None,
) -> SyncResult:
    """Persist a complete ESI incursion snapshot and record only changes."""
    names = names or {}
    security_statuses = security_statuses or {}
    system_roles = system_roles or {}
    region_names = region_names or {}
    observed_at = observed_at or timezone.now()
    seen_constellations: set[int] = set()
    appeared = 0
    updated = 0

    for payload in payloads:
        constellation_id = int(payload["constellation_id"])
        seen_constellations.add(constellation_id)
        values = _model_values(payload, names, security_statuses, system_roles, region_names)

        try:
            incursion = Incursion.objects.select_for_update().get(
                constellation_id=constellation_id
            )
        except Incursion.DoesNotExist:
            incursion = Incursion.objects.create(
                constellation_id=constellation_id,
                **values,
                is_active=True,
                first_seen=observed_at,
                last_seen=observed_at,
                last_changed=observed_at,
            )
            IncursionChange.objects.create(
                incursion=incursion,
                constellation_id=constellation_id,
                change_type=IncursionChange.ChangeType.APPEARED,
                changed_fields=list(TRACKED_FIELDS),
                snapshot=incursion.snapshot(),
                observed_at=observed_at,
            )
            appeared += 1
            continue

        was_active = incursion.is_active
        changed_fields = [
            field for field, value in values.items() if getattr(incursion, field) != value
        ]
        for field, value in values.items():
            setattr(incursion, field, value)

        incursion.is_active = True
        incursion.last_seen = observed_at
        incursion.ended_at = None

        if not was_active:
            incursion.first_seen = observed_at
            incursion.last_changed = observed_at
            incursion.save()
            IncursionChange.objects.create(
                incursion=incursion,
                constellation_id=constellation_id,
                change_type=IncursionChange.ChangeType.APPEARED,
                changed_fields=["is_active", *changed_fields],
                snapshot=incursion.snapshot(),
                observed_at=observed_at,
            )
            appeared += 1
        elif changed_fields:
            incursion.last_changed = observed_at
            incursion.save()
            IncursionChange.objects.create(
                incursion=incursion,
                constellation_id=constellation_id,
                change_type=IncursionChange.ChangeType.UPDATED,
                changed_fields=changed_fields,
                snapshot=incursion.snapshot(),
                observed_at=observed_at,
            )
            updated += 1
        else:
            incursion.save(update_fields=("last_seen",))

    ended = 0
    ended_incursions = Incursion.objects.select_for_update().filter(is_active=True)
    if seen_constellations:
        ended_incursions = ended_incursions.exclude(
            constellation_id__in=seen_constellations
        )

    for incursion in ended_incursions:
        incursion.is_active = False
        incursion.ended_at = observed_at
        incursion.last_changed = observed_at
        incursion.save(update_fields=("is_active", "ended_at", "last_changed"))
        IncursionChange.objects.create(
            incursion=incursion,
            constellation_id=incursion.constellation_id,
            change_type=IncursionChange.ChangeType.ENDED,
            changed_fields=["is_active"],
            snapshot=incursion.snapshot(),
            observed_at=observed_at,
        )
        ended += 1

    return SyncResult(appeared=appeared, updated=updated, ended=ended)
