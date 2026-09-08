import logging

from allianceauth.services.tasks import QueueOnce
from celery import shared_task
from django.utils import timezone
from esi.decorators import rate_limit_retry_task
from esi.exceptions import HTTPNotModified

from .models import IncursionSyncStatus
from .providers import get_incursion_names, get_incursions
from .services import (
    collect_incursion_ids,
    mark_active_incursions_seen,
    synchronize_incursions,
)

logger = logging.getLogger(__name__)


def run_incursion_update() -> dict[str, int]:
    """Fetch ESI and persist changes. Kept separate for direct unit testing."""
    attempted_at = timezone.now()
    status, _ = IncursionSyncStatus.objects.get_or_create(pk=1)
    status.last_attempt_at = attempted_at
    status.save(update_fields=("last_attempt_at",))

    try:
        payloads = get_incursions()
        names = get_incursion_names(collect_incursion_ids(payloads))
    except HTTPNotModified:
        mark_active_incursions_seen(attempted_at)
        status.last_success_at = attempted_at
        status.last_error = ""
        status.save(update_fields=("last_success_at", "last_error"))
        logger.debug("ESI reports that the incursion response is unchanged")
        return {"appeared": 0, "updated": 0, "ended": 0}
    except Exception as exc:
        status.last_error = str(exc)
        status.save(update_fields=("last_error",))
        logger.exception("Unable to update incursions from ESI")
        raise

    result = synchronize_incursions(payloads, names=names, observed_at=attempted_at)
    status.last_success_at = attempted_at
    status.last_error = ""
    update_fields = ["last_success_at", "last_error"]
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
def update_incursions(self) -> dict[str, int]:
    return run_incursion_update()
