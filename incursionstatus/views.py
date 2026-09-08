from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render

from .models import Incursion, IncursionChange, IncursionSyncStatus


@login_required
@permission_required("incursionstatus.incursion_view", raise_exception=True)
def index(request: WSGIRequest) -> HttpResponse:
    context = {
        "incursions": Incursion.objects.filter(is_active=True).order_by("state", "constellation_name"),
        "recent_changes": IncursionChange.objects.select_related("incursion")[:25],
        "sync_status": IncursionSyncStatus.objects.filter(pk=1).first(),
    }
    return render(request, "incursionstatus/index.html", context)

