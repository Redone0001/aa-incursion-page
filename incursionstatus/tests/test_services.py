from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from incursionstatus.models import Incursion, IncursionChange
from incursionstatus.services import synchronize_incursions

from .factories import incursion_names, incursion_payload


class SynchronizeIncursionsTests(TestCase):
    def setUp(self):
        self.first_observation = timezone.now()
        self.names = incursion_names()

    def test_new_incursion_is_stored_and_recorded(self):
        result = synchronize_incursions(
            [incursion_payload()],
            self.names,
            self.first_observation,
            security_statuses={30003202: 0.6},
        )

        self.assertEqual(result.as_dict(), {"appeared": 1, "updated": 0, "ended": 0})
        incursion = Incursion.objects.get()
        self.assertTrue(incursion.is_active)
        self.assertEqual(incursion.constellation_name, "Miennue")
        self.assertEqual(
            incursion.infested_solar_systems,
            [30003200, 30003201, 30003202],
        )
        self.assertEqual(incursion.security_status, 0.6)
        self.assertEqual(IncursionChange.objects.get().change_type, "appeared")

    def test_unchanged_response_only_updates_last_seen(self):
        synchronize_incursions([incursion_payload()], self.names, self.first_observation)
        second_observation = self.first_observation + timedelta(minutes=5)

        result = synchronize_incursions(
            [incursion_payload()], self.names, second_observation
        )

        self.assertFalse(result.changed)
        self.assertEqual(IncursionChange.objects.count(), 1)
        self.assertEqual(Incursion.objects.get().last_seen, second_observation)

    def test_changed_response_creates_history(self):
        synchronize_incursions([incursion_payload()], self.names, self.first_observation)
        second_observation = self.first_observation + timedelta(minutes=5)

        result = synchronize_incursions(
            [incursion_payload(influence=0.5, has_boss=True)],
            self.names,
            second_observation,
        )

        self.assertEqual(result.updated, 1)
        change = IncursionChange.objects.first()
        self.assertEqual(change.change_type, "updated")
        self.assertEqual(change.changed_fields, ["has_boss", "influence"])
        self.assertTrue(change.snapshot["has_boss"])

    def test_missing_incursion_is_marked_ended(self):
        synchronize_incursions([incursion_payload()], self.names, self.first_observation)
        second_observation = self.first_observation + timedelta(minutes=5)

        result = synchronize_incursions([], {}, second_observation)

        self.assertEqual(result.ended, 1)
        incursion = Incursion.objects.get()
        self.assertFalse(incursion.is_active)
        self.assertEqual(incursion.ended_at, second_observation)
        self.assertEqual(IncursionChange.objects.first().change_type, "ended")

    def test_reappearing_constellation_starts_a_new_active_period(self):
        synchronize_incursions([incursion_payload()], self.names, self.first_observation)
        synchronize_incursions([], {}, self.first_observation + timedelta(minutes=5))
        third_observation = self.first_observation + timedelta(hours=12)

        result = synchronize_incursions(
            [incursion_payload(state="mobilizing")], self.names, third_observation
        )

        self.assertEqual(result.appeared, 1)
        incursion = Incursion.objects.get()
        self.assertTrue(incursion.is_active)
        self.assertEqual(incursion.first_seen, third_observation)
        self.assertEqual(IncursionChange.objects.first().change_type, "appeared")
