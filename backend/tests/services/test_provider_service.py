import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from fastapi import HTTPException

from app.models.provider import Provider
from app.schemas.provider import ProviderCreate, ProviderUpdate, ProviderValidationRequest
from app.services import provider_service


class ProviderServiceTests(unittest.TestCase):
    def test_create_provider_persists_and_masks_api_key(self) -> None:
        db = MagicMock()
        payload = ProviderCreate(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )

        def refresh_provider(instance: Provider) -> None:
            instance.id = 3
            instance.created_at = datetime(2026, 3, 30, 3, 30, 0)
            instance.updated_at = datetime(2026, 3, 30, 3, 30, 0)

        db.refresh.side_effect = refresh_provider

        provider = provider_service.create_provider(db, payload)

        self.assertEqual(provider.id, 3)
        self.assertEqual(provider.platform, "openai")
        self.assertEqual(provider.label, "OpenAI Main")
        self.assertEqual(provider.api_key_preview, "sk-t...7890")
        self.assertEqual(provider.base_url, "https://api.openai.com/v1")
        self.assertTrue(provider.is_enabled)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_update_provider_applies_changes(self) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="Old Label",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 4
        provider.created_at = datetime(2026, 3, 30, 3, 30, 0)
        provider.updated_at = datetime(2026, 3, 30, 3, 30, 0)
        db.get.return_value = provider

        updated = provider_service.update_provider(
            db,
            4,
            ProviderUpdate(label="New Label", is_enabled=False),
        )

        self.assertEqual(updated.label, "New Label")
        self.assertFalse(updated.is_enabled)
        self.assertEqual(updated.api_key_preview, "sk-t...7890")
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(provider)

    @patch("app.services.provider_service.select")
    def test_list_providers_returns_masked_values(self, mock_select) -> None:
        db = MagicMock()
        provider = Provider(
            platform="anthropic",
            label="Claude",
            api_key="sk-ant-abcdef123456",
            base_url=None,
            is_enabled=True,
        )
        provider.id = 5
        provider.created_at = datetime(2026, 3, 30, 3, 30, 0)
        provider.updated_at = datetime(2026, 3, 30, 3, 30, 0)
        db.scalars.return_value.all.return_value = [provider]

        providers = provider_service.list_providers(db)

        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].platform, "anthropic")
        self.assertEqual(providers[0].api_key_preview, "sk-a...3456")

    def test_get_provider_or_404_raises_when_missing(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with self.assertRaises(HTTPException) as context:
            provider_service.get_provider_or_404(db, 99)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Provider not found")

    @patch("app.services.provider_service.urllib_request.urlopen")
    def test_validate_provider_credentials_returns_success(self, mock_urlopen) -> None:
        response = MagicMock()
        response.status = 200
        mock_urlopen.return_value.__enter__.return_value = response

        result = provider_service.validate_provider_credentials(
            ProviderValidationRequest(
                platform="openai",
                api_key="sk-test-1234567890",
                base_url="https://api.openai.com/v1",
            )
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.message, "API credentials look valid")
        self.assertEqual(result.resolved_base_url, "https://api.openai.com/v1")

    @patch("app.services.provider_service.urllib_request.urlopen")
    def test_validate_provider_credentials_returns_failure_for_unauthorized(
        self,
        mock_urlopen,
    ) -> None:
        mock_urlopen.side_effect = HTTPError(
            url="https://api.openai.com/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        result = provider_service.validate_provider_credentials(
            ProviderValidationRequest(
                platform="openai",
                api_key="sk-test-1234567890",
                base_url="https://api.openai.com/v1",
            )
        )

        self.assertFalse(result.is_valid)
        self.assertIn("invalid or unauthorized", result.message)
