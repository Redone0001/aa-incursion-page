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
    @patch("incursionstatus.tasks.get_incursion_sde_data")
    @patch("incursionstatus.tasks.get_incursion_names")
    @patch("incursionstatus.tasks.get_incursions")
    def test_update_fetches_names_and_synchronizes(
        self,
        mock_get_incursions,
        mock_get_names,
        mock_get_sde_data,
    ):
        mock_get_incursions.return_value = [incursion_payload()]
        mock_get_names.return_value = incursion_names()
        mock_get_sde_data.return_value.names = {
            20000467: "Miennue",
            30003202: "C",
            30003200: "A",
            30003201: "B",
        }
        mock_get_sde_data.return_value.security_statuses = {30003202: 0.6}
        mock_get_sde_data.return_value.system_roles = {30003202: "headquarter"}
        mock_get_sde_data.return_value.region_names = {20000467: "The Forge"}

        result = run_incursion_update()

        self.assertEqual(result, {"appeared": 1, "updated": 0, "ended": 0})
        self.assertEqual(Incursion.objects.get().security_status, 0.6)
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

    @patch("incursionstatus.tasks.get_incursions")
    def test_wrapped_timeout_preserves_data_and_backs_off(self, fetch):
        import httpx

        from incursionstatus.models import IncursionChange, NotificationDelivery

        now = timezone.now()
        synchronize_incursions([incursion_payload()], incursion_names(), now)
        IncursionSyncStatus.objects.create(pk=1, last_success_at=now)
        original = Incursion.objects.get().snapshot()
        error = RuntimeError("verbose OpenAPI wrapper")
        error.__cause__ = httpx.ReadTimeout("read timed out")
        fetch.side_effect = error

        with patch("incursionstatus.tasks.timezone.now", return_value=now):
            self.assertEqual(run_incursion_update(), {"status": "unavailable"})
            self.assertEqual(run_incursion_update(), {"status": "deferred"})
        self.assertEqual(fetch.call_count, 1)
        status = IncursionSyncStatus.objects.get()
        self.assertEqual(status.next_retry_at, now + timedelta(minutes=5))
        self.assertEqual(status.last_success_at, now)
        self.assertNotIn("OpenAPI", status.last_error)
        self.assertEqual(Incursion.objects.get().snapshot(), original)
        self.assertEqual(IncursionChange.objects.count(), 1)
        self.assertFalse(NotificationDelivery.objects.exists())

        for minute, next_minute in ((5, 15), (15, 30), (30, 45)):
            with patch("incursionstatus.tasks.timezone.now", return_value=now + timedelta(minutes=minute)):
                self.assertEqual(run_incursion_update(), {"status": "unavailable"})
            status.refresh_from_db()
            self.assertEqual(status.next_retry_at, now + timedelta(minutes=next_minute))

        fetch.side_effect = HTTPNotModified(status_code=304, headers={})
        with patch("incursionstatus.tasks.timezone.now", return_value=now + timedelta(minutes=45)):
            self.assertEqual(run_incursion_update(), {"appeared": 0, "updated": 0, "ended": 0})
        status.refresh_from_db()
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNone(status.next_retry_at)
        self.assertEqual(status.last_error, "")
        self.assertEqual(status.last_success_at, now + timedelta(minutes=45))

    @patch("incursionstatus.tasks.get_incursions")
    def test_server_failure_then_successful_empty_response(self, fetch):
        from esi.exceptions import HTTPServerError

        now = timezone.now()
        synchronize_incursions([incursion_payload()], incursion_names(), now)
        fetch.side_effect = HTTPServerError(status_code=503, headers={}, data=None)
        with patch("incursionstatus.tasks.timezone.now", return_value=now):
            self.assertEqual(run_incursion_update(), {"status": "unavailable"})
        self.assertTrue(Incursion.objects.get().is_active)
        fetch.side_effect = None
        fetch.return_value = []
        with (
            patch("incursionstatus.tasks.timezone.now", return_value=now + timedelta(minutes=5)),
            patch("incursionstatus.tasks.get_incursion_names", return_value={}),
            patch("incursionstatus.tasks.get_incursion_sde_data") as sde,
        ):
            sde.return_value.names = {}
            sde.return_value.security_statuses = {}
            sde.return_value.system_roles = {}
            sde.return_value.region_names = {}
            self.assertEqual(run_incursion_update()["ended"], 1)
        status = IncursionSyncStatus.objects.get()
        self.assertIsNone(status.next_retry_at)
        self.assertEqual(status.consecutive_failures, 0)

    def test_temporary_classification_does_not_hide_client_or_code_errors(self):
        import httpx
        from esi.exceptions import HTTPClientError, HTTPServerError

        from incursionstatus.tasks import is_temporary_esi_failure

        for error in (httpx.ConnectError("offline"), httpx.ReadTimeout("timeout"),
                      HTTPServerError(status_code=502, headers={}, data=None)):
            self.assertTrue(is_temporary_esi_failure(error))
        for error in (ValueError("bad payload"), RuntimeError("bug"),
                      HTTPClientError(status_code=403, headers={}, data=None)):
            self.assertFalse(is_temporary_esi_failure(error))
