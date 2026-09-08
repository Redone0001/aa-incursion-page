"""Transactional notification outbox and Discord Proxy transport."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import IncursionChange, NotificationDelivery, NotificationRule

logger = logging.getLogger(__name__)


def record_change(**kwargs):
    change = IncursionChange.objects.create(**kwargs)
    snapshot = change.snapshot
    for rule in NotificationRule.objects.filter(enabled=True):
        if rule.region_name and rule.region_name.casefold() != snapshot.get("region_name", "").casefold():
            continue
        events = []
        if change.change_type == "appeared" and rule.notify_spawn:
            events.append("Spawned")
        elif change.change_type == "ended" and rule.notify_disappearance:
            events.append("Disappeared")
        elif change.change_type == "updated":
            for field, enabled, label in (
                ("state", rule.notify_state, "Phase: " + snapshot.get("state", "")),
                ("has_boss", rule.notify_boss, "Boss available" if snapshot.get("has_boss") else "Boss unavailable"),
                ("influence", rule.notify_influence, f"Influence: {snapshot.get('influence', 0):.1%}"),
            ):
                if enabled and field in change.changed_fields:
                    events.append(label)
        if not events:
            continue
        # Only the explicitly configured role may introduce a mention.
        location = f"{change.constellation_label} ({snapshot.get('region_name') or 'Unknown region'})"
        location = location.replace("@", "@\u200b")
        ping = f"<@&{rule.role_id}> " if rule.role_id else ""
        content = f"{ping}Incursion — {', '.join(events)}\n{location}\nObserved: {change.observed_at.isoformat()}"
        NotificationDelivery.objects.create(
            rule=rule, change=change, channel_id=rule.channel_id, content=content,
        )
    return change


def send_message(channel_id, content):
    from discordproxy.client import DiscordClient

    client = DiscordClient(
        target=getattr(settings, "INCURSIONSTATUS_DISCORD_PROXY_TARGET", "localhost:50051"),
        timeout=30,
    )
    client.create_channel_message(channel_id=int(channel_id), content=content)


def deliver_pending_notifications():
    """Retry unsent messages; locking prevents concurrent workers sending the same row."""
    pending_ids = list(NotificationDelivery.objects.filter(
        sent_at__isnull=True, rule__enabled=True,
    ).order_by("attempts", "pk").values_list("pk", flat=True)[:100])
    for delivery_id in pending_ids:
        with transaction.atomic():
            delivery = NotificationDelivery.objects.select_for_update().filter(
                pk=delivery_id, sent_at__isnull=True, rule__enabled=True,
            ).first()
            if delivery is None:
                continue
            delivery.attempts += 1
            try:
                send_message(delivery.channel_id, delivery.content)
            except Exception as exc:
                delivery.last_error = str(exc)
                logger.exception("Incursion notification %s failed", delivery.pk)
            else:
                delivery.sent_at = timezone.now()
                delivery.last_error = ""
            delivery.save(update_fields=("attempts", "sent_at", "last_error"))
