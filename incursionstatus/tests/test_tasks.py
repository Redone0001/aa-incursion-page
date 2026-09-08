from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from esi.exceptions import HTTPNotModified

from incursionstatus.models import Incursion, IncursionSyncStatus
from incursionstatus.services import synchronize_incursions
from incursionstatus.tasks import run_incursion_update

from .factories import incursion_names, incursion_payload


class IncursionTaskTests(TestCase):
    @patch("incursionstatus.tasks.get_incursion_names")
    @patch("incursionstatus.tasks.get_incursions")
    def test_update_fetches_names_and_synchronizes(self, mock_get_incursions, mock_get_names):
        mock_get_incursions.return_value = [incursion_payload()]
        mock_get_names.return_value = incursion_names()

        result = run_incursion_update()

        self.assertEqual(result, {"appeared": 1, "updated": 0, "ended": 0})
        self.assertEqual(Incursion.objects.count(), 1)
        self.assertIsNotNone(IncursionSyncStatus.objects.get(pk=1).last_success_at)

    @patch("incursionstatus.tasks.get_incursions")
    def test_not_modified_marks_active_rows_seen(self, mock_get_incursions):
        initial_time = timezone.now() - timedelta(minutes=10)
        synchronize_incursions([incursion_payload()], incursion_names(), initial_time)
        mock_get_incursions.side_effect = HTTPNotModified(status_code=304, headers={})

        result = run_incursion_update()

        self.assertEqual(result, {"appeared": 0, "updated": 0, "ended": 0})
        self.assertGreater(Incursion.objects.get().last_seen, initial_time)

    @patch("incursionstatus.tasks.get_incursions")
    def test_failure_is_recorded_and_reraised(self, mock_get_incursions):
        mock_get_incursions.side_effect = RuntimeError("ESI unavailable")

        with self.assertRaisesMessage(RuntimeError, "ESI unavailable"):
            run_incursion_update()

        status = IncursionSyncStatus.objects.get(pk=1)
        self.assertEqual(status.last_error, "ESI unavailable")
        self.assertIsNone(status.last_success_at)
