import logging
from datetime import timedelta

import httpx
from aiopenapi3.errors import HTTPServerError
from allianceauth.services.tasks import QueueOnce
from celery import shared_task
from django.utils import timezone
from esi.decorators import rate_limit_retry_task
from esi.exceptions import HTTPNotModified

from .models import IncursionSyncStatus
from .providers import get_incursion_names, get_incursions
from .sde import get_incursion_sde_data
from .services import (
    mark_active_incursions_seen,
    synchronize_incursions,
)

logger = logging.getLogger(__name__)


def is_temporary_esi_failure(exc):
    """Recognize transport failures even when aiopenapi3 wraps the cause."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, (httpx.TransportError, HTTPServerError)):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def run_incursion_update() -> dict[str, int | str]:
    """Fetch ESI and persist changes. Kept separate for direct unit testing."""
    attempted_at = timezone.now()
    status, _ = IncursionSyncStatus.objects.get_or_create(pk=1)
    if status.next_retry_at and attempted_at < status.next_retry_at:
        return {"status": "deferred"}
    status.last_attempt_at = attempted_at
    status.save(update_fields=("last_attempt_at",))

    try:
        payloads = get_incursions()
        faction_ids = {int(payload["faction_id"]) for payload in payloads}
        faction_names = get_incursion_names(faction_ids)
        sde_data = get_incursion_sde_data(payloads)
    except HTTPNotModified:
        mark_active_incursions_seen(attempted_at)
        status.last_success_at = attempted_at
        status.last_error = ""
        status.consecutive_failures = 0
        status.next_retry_at = None
        status.save(update_fields=("last_success_at", "last_error", "consecutive_failures", "next_retry_at"))
        logger.debug("ESI reports that the incursion response is unchanged")
        return {"appeared": 0, "updated": 0, "ended": 0}
    except Exception as exc:
        if is_temporary_esi_failure(exc):
            status.consecutive_failures += 1
            delay = min(status.consecutive_failures * 5, 15)
            status.next_retry_at = attempted_at + timedelta(minutes=delay)
            status.last_error = (
                "ESI is temporarily unavailable (maintenance or a connection problem). "
                "Previously fetched data is retained. Polling will retry automatically."
            )
            status.save(update_fields=("last_error", "consecutive_failures", "next_retry_at"))
            logger.warning("Incursion ESI temporarily unavailable; next attempt at %s", status.next_retry_at)
            return {"status": "unavailable"}
        status.last_error = str(exc)
        status.next_retry_at = None
        status.save(update_fields=("last_error", "next_retry_at"))
        logger.exception("Unable to update incursions from ESI")
        raise

    result = synchronize_incursions(
        payloads,
        names={**sde_data.names, **faction_names},
        observed_at=attempted_at,
        security_statuses=sde_data.security_statuses,
        system_roles=sde_data.system_roles,
        region_names=sde_data.region_names,
    )
    status.last_success_at = attempted_at
    status.last_error = ""
    status.consecutive_failures = 0
    status.next_retry_at = None
    update_fields = ["last_success_at", "last_error", "consecutive_failures", "next_retry_at"]
    if result.changed:
        status.last_change_at = attempted_at
        update_fields.append("last_change_at")
    status.save(update_fields=update_fields)

    logger.info(
        "Incursion update complete: %s appeared, %s updated, %s ended",
        result.appeared,
        result.updated,
        result.ended,
    )
    return result.as_dict()


@shared_task(
    bind=True,
    name="incursionstatus.update_incursions",
    base=QueueOnce,
)
@rate_limit_retry_task
def update_incursions(self) -> dict[str, int | str]:
    return run_incursion_update()


@shared_task(name="incursionstatus.deliver_notifications", base=QueueOnce)
def deliver_notifications():
    from .notifications import deliver_pending_notifications

    deliver_pending_notifications()
