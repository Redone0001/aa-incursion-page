from allianceauth.eveonline.models import EveCharacter
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from incursionstatus.services import synchronize_incursions

from .factories import incursion_names, incursion_payload


class IncursionStatusViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="test-user", password="test-password"
        )
        self.user.profile.main_character = EveCharacter.objects.create(
            character_id=90000001,
            character_name="Test Character",
            corporation_id=1000001,
        )
        self.user.profile.save(update_fields=["main_character"])
        self.client.force_login(self.user)

    def test_permission_is_required(self):
        response = self.client.get(reverse("incursionstatus:index"))
        self.assertEqual(response.status_code, 403, response.get("Location"))

    def test_authorized_user_can_view_page(self):
        permission = Permission.objects.get(
            content_type__app_label="incursionstatus",
            codename="incursion_view",
        )
        self.user.user_permissions.add(permission)
        synchronize_incursions(
            [incursion_payload()],
            incursion_names(),
            security_statuses={30003202: 0.6},
            region_names={20000467: "The Forge"},
        )

        response = self.client.get(reverse("incursionstatus:index"))

        self.assertEqual(response.status_code, 200, response.get("Location"))
        self.assertContains(response, "Incursion Status")
        self.assertContains(response, "The Forge")
        self.assertContains(response, "incursion-card-highsec")
        self.assertContains(response, "text-bg-success")
        self.assertNotContains(response, "Attacking faction")
        self.assertNotContains(response, ">Type<")
