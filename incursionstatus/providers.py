from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from esi.openapi_clients import ESIClientProvider

from . import __esi_compatibility_date__, __title__, __url__, __version__

if TYPE_CHECKING:
    from esi.stubs import IncursionsGet


esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    operations=["GetIncursions", "PostUniverseNames"],
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    return {
        field: getattr(value, field)
        for field in (
            "constellation_id",
            "faction_id",
            "has_boss",
            "infested_solar_systems",
            "influence",
            "staging_solar_system_id",
            "state",
            "type",
        )
    }


def get_incursions() -> list[dict[str, Any]]:
    """Return all current incursions from the public ESI endpoint."""
    response: "IncursionsGet" = esi.client.Incursions.GetIncursions().result()
    return [_as_dict(item) for item in response]


def get_incursion_names(ids: set[int]) -> dict[int, str]:
    """Resolve all IDs used by an incursion response in one ESI call."""
    if not ids:
        return {}

    response = esi.client.Universe.PostUniverseNames(body=sorted(ids)).result(
        use_etag=False
    )
    names: dict[int, str] = {}
    for item in response:
        if isinstance(item, Mapping):
            names[int(item["id"])] = str(item["name"])
        else:
            names[int(item.id)] = str(item.name)
    return names

