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
            security_status=0.6,
            state=payload["state"],
            incursion_type=payload["type"],
        )

        self.assertEqual(incursion.influence_percent, 42)
        self.assertEqual(
            incursion.infested_systems_display,
            [
                {"id": 30003200, "name": "A", "role": ""},
                {"id": 30003201, "name": "B", "role": ""},
            ],
        )
        self.assertEqual(incursion.state_badge_class, "text-bg-success")
        self.assertEqual(incursion.security_band, "highsec")
        self.assertEqual(incursion.security_border_class, "incursion-card-highsec")

    def test_state_badge_colors(self):
        incursion = Incursion(state=Incursion.State.ESTABLISHED)
        self.assertEqual(incursion.state_badge_class, "text-bg-success")

        incursion.state = Incursion.State.MOBILIZING
        self.assertEqual(incursion.state_badge_class, "incursion-state-mobilizing")

        incursion.state = Incursion.State.WITHDRAWING
        self.assertEqual(incursion.state_badge_class, "text-bg-danger")

    def test_security_band_thresholds(self):
        incursion = Incursion(security_status=0.5001)
        self.assertEqual(incursion.security_band, "highsec")

        incursion.security_status = 0.5
        self.assertEqual(incursion.security_band, "lowsec")
        incursion.security_status = 0
        self.assertEqual(incursion.security_band, "lowsec")

        incursion.security_status = -0.0001
        self.assertEqual(incursion.security_band, "nullsec")

        incursion.security_status = None
        self.assertEqual(incursion.security_band, "unknown")

    def test_influence_percent_is_clamped(self):
        incursion = Incursion(influence=1.5)
        self.assertEqual(incursion.influence_percent, 100)
        incursion.influence = -1
        self.assertEqual(incursion.influence_percent, 0)
