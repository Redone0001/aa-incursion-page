"""Alliance Auth menu and URL hooks."""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook
from django.utils.translation import gettext_lazy as _

from . import urls


class IncursionStatusMenuItem(MenuItemHook):
    def __init__(self):
        super().__init__(
            _("Incursion Status"),
            "fas fa-biohazard fa-fw",
            "incursionstatus:index",
            navactive=["incursionstatus:"],
        )

    def render(self, request):
        if request.user.has_perm("incursionstatus.incursion_view"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return IncursionStatusMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "incursionstatus", r"^incursions/")

