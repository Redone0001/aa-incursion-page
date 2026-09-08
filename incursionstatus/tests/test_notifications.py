from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from incursionstatus.models import Incursion, IncursionChange, NotificationDelivery, NotificationRule
from incursionstatus.notifications import deliver_pending_notifications, expected_lifetime_string
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
        self.assertEqual(deliveries[0].content, "<@&456>")
        self.assertIn("Spawned", deliveries[0].embed["title"])
        self.assertIn("Disappeared", str(deliveries[1].embed))
        self.assertIn("The Forge", str(deliveries[1].embed))
        self.assertIn("Spawned", deliveries[2].embed["title"])

    def test_everyone_overrides_role(self):
        self.rule.ping_everyone = True
        self.rule.save()
        self.sync([incursion_payload()])
        content = NotificationDelivery.objects.get().content
        self.assertTrue(content == "@everyone")
        self.assertNotIn("<@&456>", content)

    def test_everyone_without_role(self):
        self.rule.ping_everyone = True
        self.rule.role_id = ""
        self.rule.full_clean()
        self.rule.save()
        self.sync([incursion_payload()])
        self.assertTrue(NotificationDelivery.objects.get().content == "@everyone")

    def test_disabling_everyone_restores_role_for_new_events(self):
        self.rule.ping_everyone = True
        self.rule.save()
        self.sync([incursion_payload()])
        self.rule.ping_everyone = False
        self.rule.save()
        self.sync([])
        deliveries = list(NotificationDelivery.objects.all())
        self.assertTrue(deliveries[0].content == "@everyone")
        self.assertTrue(deliveries[1].content == "<@&456>")

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
        self.assertIn("Domain", str(NotificationDelivery.objects.get().embed))
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
        self.assertIn("Phase: withdrawing, Boss available", delivery.embed["title"])
        self.assertNotIn("Influence:", delivery.embed["title"])

    def test_influence_opt_in(self):
        self.rule.notify_spawn = False
        self.rule.notify_influence = True
        self.rule.save()
        self.sync([incursion_payload()])
        self.sync([incursion_payload(influence=0.5)])
        self.assertIn("Influence: 50.0%", NotificationDelivery.objects.get().embed["title"])

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

    def test_embed_fields_and_phase_clock(self):
        self.rule.region_name = ""
        self.rule.save()
        now = timezone.now()
        synchronize_incursions(
            [incursion_payload()], incursion_names(), observed_at=now,
            region_names={20000467: "The Forge"}, system_roles={30003202: "headquarter"},
        )
        fields = NotificationDelivery.objects.get().embed["fields"]
        self.assertEqual([field["name"] for field in fields], ["HQ", "Status", "Region", "Expected Life"])
        self.assertEqual(fields[0]["value"], "C")
        self.assertEqual(fields[1]["value"], "Established")
        self.assertIn(str(int((now + timedelta(days=8)).timestamp())), fields[3]["value"])
        synchronize_incursions([incursion_payload(influence=0.5)], observed_at=now + timedelta(hours=1))
        self.assertEqual(Incursion.objects.get().last_state_change, now)
        later = now + timedelta(days=2)
        synchronize_incursions([incursion_payload(state="withdrawing")], observed_at=later)
        self.assertEqual(Incursion.objects.get().last_state_change, later)
        # Previously queued embeds retain their original phase and deadline.
        self.assertEqual(NotificationDelivery.objects.first().embed["fields"], fields)
        synchronize_incursions([], observed_at=later)
        self.assertEqual(NotificationDelivery.objects.last().embed["fields"][3]["value"], "Ended")
        respawn = later + timedelta(days=1)
        synchronize_incursions([incursion_payload()], observed_at=respawn)
        self.assertEqual(Incursion.objects.get().last_state_change, respawn)

    def test_expected_lifetime_unknown_expired_and_each_phase(self):
        now = timezone.now()
        for state, days in (("established", 8), ("mobilizing", 3), ("withdrawing", 1)):
            snapshot = {"state": state, "last_state_change": now.isoformat()}
            self.assertIn(str(int((now + timedelta(days=days)).timestamp())),
                          expected_lifetime_string(snapshot, now))
            self.assertEqual(expected_lifetime_string(snapshot, now + timedelta(days=days)),
                             "Estimated incursion lifetime elapsed")
        self.assertEqual(expected_lifetime_string({"state": "established"}, now), "Unknown")
        self.assertEqual(expected_lifetime_string({"state": "other", "last_state_change": now.isoformat()}, now),
                         "Unknown")

    def test_backfill_uses_latest_phase_in_current_active_period(self):
        from importlib import import_module

        from django.apps import apps
        from django.db import connection

        self.sync([incursion_payload()])
        now = timezone.now()
        synchronize_incursions([incursion_payload(state="withdrawing")], observed_at=now)
        synchronize_incursions([incursion_payload(state="withdrawing", influence=0.1)],
                               observed_at=now + timedelta(hours=1))
        Incursion.objects.update(last_state_change=None)
        migration = import_module("incursionstatus.migrations.0007_incursion_last_state_change_and_more")
        migration.backfill_phase_times(apps, connection.schema_editor())
        self.assertEqual(Incursion.objects.get().last_state_change, now)

    def test_real_proxy_embed_serialization_without_sending(self):
        try:
            from discordproxy.discord_api_pb2 import Embed
        except ImportError:
            self.skipTest("Optional Discord Proxy client is not installed")
        from incursionstatus.notifications import send_message

        self.sync([incursion_payload()])
        delivery = NotificationDelivery.objects.get()
        with patch("discordproxy.client.DiscordClient") as client:
            send_message(delivery.channel_id, delivery.content, delivery.embed)
            kwargs = client.return_value.create_channel_message.call_args.kwargs
            self.assertEqual(kwargs["content"], "<@&456>")
            self.assertEqual(kwargs["channel_id"], 123)
            embed = Embed.FromString(kwargs["embed"].SerializeToString())
            self.assertEqual([field.name for field in embed.fields], ["HQ", "Status", "Region", "Expected Life"])
            self.assertEqual(embed.fields[0].value, "Unknown")
            self.assertEqual(embed.fields[1].value, "Established")
            send_message(delivery.channel_id, "Legacy queued message", {})
            self.assertIsNone(client.return_value.create_channel_message.call_args.kwargs["embed"])
