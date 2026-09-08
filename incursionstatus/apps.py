from django.apps import AppConfig

from . import __version__


class IncursionStatusConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "incursionstatus"
    label = "incursionstatus"
    verbose_name = f"Incursion Status v{__version__}"

