import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.schemas.provider_model import ProviderModelCreate, ProviderModelUpdate
from app.services import provider_model_service


class ProviderModelServiceTests(unittest.TestCase):
    @patch("app.services.provider_model_service._ensure_provider_model_is_available")
    @patch("app.services.provider_model_service.get_provider_or_404")
    def test_create_provider_model_persists_model(
        self,
        mock_get_provider,
        mock_ensure_available,
    ) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2
        mock_get_provider.return_value = provider

        payload = ProviderModelCreate(
            provider_id=2,
            label="Fast Default",
            model_name="gpt-4.1-mini",
            is_enabled=True,
            is_default=True,
            temperature=0.3,
            max_output_tokens=4000,
            supports_tools=True,
        )

        def refresh_model(instance: ProviderModel) -> None:
            instance.id = 8
            instance.provider = provider
            instance.created_at = datetime(2026, 3, 30, 4, 15, 0)
            instance.updated_at = datetime(2026, 3, 30, 4, 15, 0)

        db.refresh.side_effect = refresh_model

        model = provider_model_service.create_provider_model(db, payload)

        self.assertEqual(model.id, 8)
        self.assertEqual(model.provider_id, 2)
        self.assertEqual(model.provider_label, "OpenAI Main")
        self.assertEqual(model.model_name, "gpt-4.1-mini")
        self.assertTrue(model.is_default)
        self.assertTrue(model.supports_tools)
        mock_ensure_available.assert_called_once_with(db, provider, "gpt-4.1-mini")

    @patch("app.services.provider_model_service._ensure_provider_model_is_available")
    def test_update_provider_model_applies_changes(self, mock_ensure_available) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2

        model = ProviderModel(
            provider_id=2,
            label="Reasoning",
            model_name="gpt-4.1",
            is_enabled=True,
            is_default=False,
            temperature=0.2,
            max_output_tokens=8000,
            supports_tools=True,
        )
        model.id = 9
        model.provider = provider
        model.created_at = datetime(2026, 3, 30, 4, 15, 0)
        model.updated_at = datetime(2026, 3, 30, 4, 15, 0)
        db.get.return_value = model

        updated = provider_model_service.update_provider_model(
            db,
            9,
            ProviderModelUpdate(
                label="Reasoning Pro",
                model_name="gpt-4.1",
                is_default=True,
            ),
        )

        self.assertEqual(updated.label, "Reasoning Pro")
        self.assertTrue(updated.is_default)
        mock_ensure_available.assert_called_once_with(db, provider, "gpt-4.1")

    @patch("app.services.provider_model_service.select")
    def test_list_provider_models_returns_items(self, mock_select) -> None:
        db = MagicMock()
        provider = Provider(
            platform="anthropic",
            label="Claude Account",
            api_key="sk-ant-abcdef123456",
            base_url=None,
            is_enabled=True,
        )
        provider.id = 5

        model = ProviderModel(
            provider_id=5,
            label="Claude Fast",
            model_name="claude-3-5-sonnet",
            is_enabled=True,
            is_default=True,
            temperature=0.5,
            max_output_tokens=4096,
            supports_tools=False,
        )
        model.id = 10
        model.provider = provider
        model.created_at = datetime(2026, 3, 30, 4, 15, 0)
        model.updated_at = datetime(2026, 3, 30, 4, 15, 0)
        db.scalars.return_value.all.return_value = [model]

        models = provider_model_service.list_provider_models(db)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].provider_platform, "anthropic")
        self.assertEqual(models[0].label, "Claude Fast")

    def test_get_provider_model_or_404_raises_when_missing(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with self.assertRaises(HTTPException) as context:
            provider_model_service.get_provider_model_or_404(db, 88)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Provider model not found")

    @patch("app.services.provider_model_service.get_provider_or_404")
    @patch("app.services.provider_model_service.urllib_request.urlopen")
    def test_validate_provider_model_returns_success_when_model_exists(
        self,
        mock_urlopen,
        mock_get_provider,
    ) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2
        mock_get_provider.return_value = provider

        response = MagicMock()
        response.read.return_value = b'{"data":[{"id":"gpt-4.1-mini"},{"id":"gpt-4.1"}]}'
        mock_urlopen.return_value.__enter__.return_value = response

        result = provider_model_service.validate_provider_model(
            db,
            provider_model_service.ProviderModelValidationRequest(
                provider_id=2,
                model_name="gpt-4.1-mini",
            ),
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.resolved_model_name, "gpt-4.1-mini")

    @patch("app.services.provider_model_service.get_provider_or_404")
    @patch("app.services.provider_model_service.urllib_request.urlopen")
    def test_validate_provider_model_returns_failure_when_model_missing(
        self,
        mock_urlopen,
        mock_get_provider,
    ) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-1234567890",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2
        mock_get_provider.return_value = provider

        response = MagicMock()
        response.read.return_value = b'{"data":[{"id":"gpt-4.1-mini"}]}'
        mock_urlopen.return_value.__enter__.return_value = response

        result = provider_model_service.validate_provider_model(
            db,
            provider_model_service.ProviderModelValidationRequest(
                provider_id=2,
                model_name="gpt-5.3",
            ),
        )

        self.assertFalse(result.is_valid)
        self.assertIn("gpt-5.3", result.message)
