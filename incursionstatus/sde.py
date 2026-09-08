from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from eve_sde.models.map import Constellation, SolarSystem


@dataclass(frozen=True)
class IncursionSdeData:
    names: dict[int, str]
    security_statuses: dict[int, float]
    system_roles: dict[int, str]


@lru_cache(maxsize=1)
def incursion_layout() -> dict[str, str]:
    """Load the bundled system-to-incursion-role mapping once per process."""
    path = Path(__file__).with_name("data") / "incursion_layout.csv"
    with path.open(newline="", encoding="utf-8") as layout_file:
        rows = csv.DictReader(layout_file)
        return {
            row["solarSystemName"].strip().casefold(): row["solarSystemInucrsionType"].strip().casefold()
            for row in rows
            if row.get("solarSystemName") and row.get("solarSystemInucrsionType")
        }


def _localized_name(obj: Any) -> str:
    return str(getattr(obj, "name", "") or obj.pk)


def _canonical_name(obj: Any) -> str:
    # modeltranslation adds name_en while exposing the active locale through name.
    return str(getattr(obj, "name_en", None) or getattr(obj, "name", "") or obj.pk)


def get_incursion_sde_data(payloads: list[dict[str, Any]]) -> IncursionSdeData:
    """Resolve map names, security and site roles from the loaded SDE tables."""
    constellation_ids = {int(payload["constellation_id"]) for payload in payloads}
    system_ids = {
        int(system_id)
        for payload in payloads
        for system_id in [
            payload["staging_solar_system_id"],
            *payload["infested_solar_systems"],
        ]
    }

    constellations = Constellation.objects.in_bulk(constellation_ids)
    systems = SolarSystem.objects.in_bulk(system_ids)
    layout = incursion_layout()

    names = {
        constellation_id: _localized_name(constellation)
        for constellation_id, constellation in constellations.items()
    }
    names.update({system_id: _localized_name(system) for system_id, system in systems.items()})
    security_statuses = {
        system_id: float(system.security_status)
        for system_id, system in systems.items()
        if system.security_status is not None
    }
    system_roles = {
        system_id: layout[canonical_name.casefold()]
        for system_id, system in systems.items()
        for canonical_name in [_canonical_name(system)]
        if canonical_name.casefold() in layout
    }

    return IncursionSdeData(
        names=names,
        security_statuses=security_statuses,
        system_roles=system_roles,
    )
