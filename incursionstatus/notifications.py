"""Transactional notification outbox and Discord Proxy transport."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
        if rule.ping_everyone:
            ping = "@everyone"
        else:
            ping = f"<@&{rule.role_id}>" if rule.role_id else ""
        NotificationDelivery.objects.create(
            rule=rule, change=change, channel_id=rule.channel_id,
            content=ping, embed=build_embed(change, events),
        )
    return change


def expected_lifetime_string(snapshot, observed_at):
    if not snapshot.get("is_active", True):
        return "Ended"
    days = {"established": 8, "mobilizing": 3, "withdrawing": 1}.get(
        snapshot.get("state", "").lower()
    )
    started = snapshot.get("last_state_change")
    if not days or not started:
        return "Unknown"
    started = parse_datetime(started)
    if started is None or timezone.is_naive(started):
        return "Unknown"
    end_time = started + timedelta(days=days)
    if end_time <= observed_at:
        return "Estimated incursion lifetime elapsed"
    return f"Estimated incursion end: <t:{int(end_time.timestamp())}:R> (<t:{int(end_time.timestamp())}:f>)"


def build_embed(change, events):
    snapshot = change.snapshot
    active = snapshot.get("is_active", True)
    state = snapshot.get("state", "")
    return {
        "title": "Incursion — " + ", ".join(events),
        "description": change.constellation_label,
        "color": (
            {"established": 0x2ECC71, "mobilizing": 0xE67E22, "withdrawing": 0xE74C3C}.get(state, 0x95A5A6)
            if active else 0x95A5A6
        ),
        "timestamp": change.observed_at.isoformat(),
        "fields": [
            {"name": "HQ", "value": snapshot.get("headquarter_solar_system_name") or "Unknown", "inline": False},
            {"name": "Status", "value": (state.title() or "Unknown") if active else "Ended", "inline": True},
            {"name": "Region", "value": snapshot.get("region_name") or "Unknown", "inline": True},
            {"name": "Expected Life", "value": expected_lifetime_string(snapshot, change.observed_at), "inline": False},
        ],
        "footer": {"text": "Incursion end is estimated from the first observation of the current phase."},
    }


def send_message(channel_id, content, embed_data=None):
    from discordproxy.client import DiscordClient
    from discordproxy.discord_api_pb2 import Embed

    client = DiscordClient(
        target=getattr(settings, "INCURSIONSTATUS_DISCORD_PROXY_TARGET", "localhost:50051"),
        timeout=30,
    )
    client.create_channel_message(
        channel_id=int(channel_id), content=content, embed=Embed(**embed_data) if embed_data else None,
    )


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
                send_message(delivery.channel_id, delivery.content, delivery.embed)
            except Exception as exc:
                delivery.last_error = str(exc)
                logger.exception("Incursion notification %s failed", delivery.pk)
            else:
                delivery.sent_at = timezone.now()
                delivery.last_error = ""
            delivery.save(update_fields=("attempts", "sent_at", "last_error"))
