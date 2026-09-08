from django.test import TestCase

from incursionstatus.models import Incursion

from .factories import incursion_names, incursion_payload


class IncursionModelTests(TestCase):
    def test_display_helpers(self):
        payload = incursion_payload()
        names = incursion_names()
        incursion = Incursion(
            constellation_id=payload["constellation_id"],
            constellation_name=names[payload["constellation_id"]],
            faction_id=payload["faction_id"],
            faction_name=names[payload["faction_id"]],
            has_boss=payload["has_boss"],
            infested_solar_systems=[30003200, 30003201],
            infested_solar_system_names=["A", "B"],
            influence=0.423,
            staging_solar_system_id=payload["staging_solar_system_id"],
            staging_solar_system_name="C",
            state=payload["state"],
            incursion_type=payload["type"],
        )

        self.assertEqual(incursion.influence_percent, 42)
        self.assertEqual(
            incursion.infested_systems_display,
            [{"id": 30003200, "name": "A"}, {"id": 30003201, "name": "B"}],
        )

    def test_influence_percent_is_clamped(self):
        incursion = Incursion(influence=1.5)
        self.assertEqual(incursion.influence_percent, 100)
        incursion.influence = -1
        self.assertEqual(incursion.influence_percent, 0)

