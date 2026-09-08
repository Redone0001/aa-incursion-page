from unittest.mock import patch

from django.test import TestCase
from eve_sde.models.map import Constellation, SolarSystem

from incursionstatus.sde import get_incursion_sde_data

from .factories import incursion_payload


class IncursionSdeTests(TestCase):
    def test_resolves_constellation_systems_security_and_roles(self):
        Constellation.objects.create(id=20000467, name="Miennue")
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
        self.assertEqual(result.security_statuses, {30003200: 0.6, 30003201: 0.6})
        self.assertEqual(result.system_roles, {30003200: "vanguard", 30003201: "headquarter"})
