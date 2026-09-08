from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from incursionstatus import providers

from .factories import incursion_payload


class ProviderTests(SimpleTestCase):
    @patch("incursionstatus.providers.esi")
    def test_get_incursions_returns_plain_dicts(self, mock_esi):
        item = SimpleNamespace(**incursion_payload())
        mock_esi.client.Incursions.GetIncursions.return_value.result.return_value = [item]

        result = providers.get_incursions()

        self.assertEqual(result, [incursion_payload()])
        mock_esi.client.Incursions.GetIncursions.assert_called_once_with()

    @patch("incursionstatus.providers.esi")
    def test_get_names_uses_one_sorted_request(self, mock_esi):
        mock_esi.client.Universe.PostUniverseNames.return_value.result.return_value = [
            SimpleNamespace(id=2, name="Two"),
            SimpleNamespace(id=1, name="One"),
        ]

        result = providers.get_incursion_names({2, 1})

        self.assertEqual(result, {1: "One", 2: "Two"})
        mock_esi.client.Universe.PostUniverseNames.assert_called_once_with(body=[1, 2])
        mock_esi.client.Universe.PostUniverseNames.return_value.result.assert_called_once_with(
            use_etag=False
        )

