from unittest.mock import patch

from django.test import TestCase
from eve_sde.models.map import Constellation, Region, SolarSystem

from incursionstatus.sde import get_incursion_sde_data, incursion_layout

from .factories import incursion_payload


class IncursionSdeTests(TestCase):
    def test_bundled_layout_contains_screenshot_systems(self):
        layout = incursion_layout()

        self.assertEqual(layout["y-m5jn"], "headquarter")
        self.assertEqual(layout["mj-x5v"], "assault")
        self.assertEqual(layout["3fku-h"], "vanguard")
        self.assertEqual(layout["m9-fib"], "vanguard")
        self.assertEqual(layout["d2ez-x"], "vanguard")
        self.assertEqual(layout["djk-67"], "staging")

    def test_resolves_constellation_systems_security_and_roles(self):
        region = Region.objects.create(id=10000001, name="The Forge")
        Constellation.objects.create(id=20000467, name="Miennue", region=region)
        SolarSystem.objects.create(
            id=30003200,
            name="Vanguard System",
            security_status=0.6,
        )
        SolarSystem.objects.create(
            id=30003201,
            name="Headquarter System",
            security_status=0.6,
        )

        payload = incursion_payload(
            staging_solar_system_id=30003200,
            infested_solar_systems=[30003200, 30003201],
        )

        with patch(
            "incursionstatus.sde.incursion_layout",
            return_value={"vanguard system": "vanguard", "headquarter system": "headquarter"},
        ):
            result = get_incursion_sde_data([payload])

        self.assertEqual(result.names[20000467], "Miennue")
        self.assertEqual(result.region_names, {20000467: "The Forge"})
        self.assertEqual(result.security_statuses, {30003200: 0.6, 30003201: 0.6})
        self.assertEqual(result.system_roles, {30003200: "vanguard", 30003201: "headquarter"})
