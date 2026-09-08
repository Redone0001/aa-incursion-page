from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from incursionstatus.models import IncursionChange, NotificationDelivery, NotificationRule
from incursionstatus.notifications import deliver_pending_notifications
from incursionstatus.services import synchronize_incursions

from .factories import incursion_names, incursion_payload


class NotificationTests(TestCase):
    def setUp(self):
        self.rule = NotificationRule.objects.create(
            name="Forge", region_name="the forge", channel_id="123", role_id="456",
        )

    def sync(self, payloads):
        return synchronize_incursions(
            payloads, incursion_names(),
            region_names={20000467: "The Forge", 20000468: "Domain"},
        )

    def test_spawn_unchanged_disappearance_and_respawn(self):
        self.sync([incursion_payload()])
        self.sync([incursion_payload()])
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        self.sync([])
        self.sync([])
        self.sync([incursion_payload()])
        deliveries = list(NotificationDelivery.objects.all())
        self.assertEqual(len(deliveries), 3)
        self.assertIn("<@&456> Incursion — Spawned", deliveries[0].content)
        self.assertIn("Disappeared", deliveries[1].content)
        self.assertIn("The Forge", deliveries[1].content)
        self.assertIn("Spawned", deliveries[2].content)

    def test_region_filter_and_disabled_rule(self):
        self.sync([incursion_payload(constellation_id=20000468)])
        self.assertFalse(NotificationDelivery.objects.exists())
        self.rule.enabled = False
        self.rule.save()
        self.sync([incursion_payload()])
        self.assertFalse(NotificationDelivery.objects.exists())

    def test_all_regions_without_role(self):
        self.rule.region_name = ""
        self.rule.role_id = ""
        self.rule.save()
        self.sync([incursion_payload(constellation_id=20000468)])
        content = NotificationDelivery.objects.get().content
        self.assertIn("Domain", content)
        self.assertNotIn("<@", content)

    def test_only_selected_changes_trigger_one_message(self):
        self.rule.notify_spawn = False
        self.rule.notify_state = True
        self.rule.notify_boss = True
        self.rule.save()
        self.sync([incursion_payload()])
        self.sync([incursion_payload(influence=0.5)])
        self.assertFalse(NotificationDelivery.objects.exists())
        self.sync([incursion_payload(influence=0.6, state="withdrawing", has_boss=True)])
        delivery = NotificationDelivery.objects.get()
        self.assertIn("Phase: withdrawing, Boss available", delivery.content)
        self.assertNotIn("Influence:", delivery.content)

    def test_influence_opt_in(self):
        self.rule.notify_spawn = False
        self.rule.notify_influence = True
        self.rule.save()
        self.sync([incursion_payload()])
        self.sync([incursion_payload(influence=0.5)])
        self.assertIn("Influence: 50.0%", NotificationDelivery.objects.get().content)

    def test_new_location_is_spawn_and_old_location_disappears(self):
        self.rule.region_name = ""
        self.rule.save()
        self.sync([incursion_payload()])
        self.sync([incursion_payload(constellation_id=20000468)])
        self.assertEqual(
            list(NotificationDelivery.objects.values_list("change__change_type", flat=True)),
            ["appeared", "appeared", "ended"],
        )

    def test_rollback_does_not_leave_notifications(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.sync([incursion_payload()])
                raise RuntimeError("rollback")
        self.assertFalse(NotificationDelivery.objects.exists())
        self.assertFalse(IncursionChange.objects.exists())

    @patch("incursionstatus.notifications.send_message")
    def test_failure_retries_and_success_is_not_sent_twice(self, send):
        self.sync([incursion_payload()])
        send.side_effect = RuntimeError("proxy offline")
        deliver_pending_notifications()
        delivery = NotificationDelivery.objects.get()
        self.assertIsNone(delivery.sent_at)
        self.assertEqual(delivery.last_error, "proxy offline")
        send.side_effect = None
        deliver_pending_notifications()
        deliver_pending_notifications()
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(delivery.last_error, "")

    @patch("incursionstatus.notifications.send_message")
    def test_disabling_rule_pauses_pending_messages(self, send):
        self.sync([incursion_payload()])
        self.rule.enabled = False
        self.rule.save()
        deliver_pending_notifications()
        send.assert_not_called()

    def test_validation(self):
        for field, value in (("channel_id", "abc"), ("role_id", "-5"), ("role_id", str(2**64))):
            rule = NotificationRule(name="bad", channel_id="123")
            setattr(rule, field, value)
            with self.assertRaises(ValidationError):
                rule.full_clean()
        self.rule.notify_spawn = False
        self.rule.notify_disappearance = False
        with self.assertRaises(ValidationError):
            self.rule.full_clean()
