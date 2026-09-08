def incursion_payload(**overrides):
    payload = {
        "constellation_id": 20000467,
        "faction_id": 500019,
        "has_boss": False,
        "infested_solar_systems": [30003202, 30003200, 30003201],
        "influence": 0.42,
        "staging_solar_system_id": 30003202,
        "state": "established",
        "type": "Incursion",
    }
    payload.update(overrides)
    return payload


def incursion_names():
    return {
        20000467: "Miennue",
        500019: "Sansha's Nation",
        30003200: "A",
        30003201: "B",
        30003202: "C",
    }

