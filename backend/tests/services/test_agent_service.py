import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.agent import Agent
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services import agent_service


class AgentServiceTests(unittest.TestCase):
    @patch("app.services.agent_service.get_workspace_or_404")
    @patch("app.services.agent_service.get_provider_model_or_404")
    def test_create_agent_persists_agent(
        self,
        mock_get_provider_model,
        mock_get_workspace,
    ) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-123",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2
        provider_model = ProviderModel(
            provider_id=2,
            label="Fast Default",
            model_name="gpt-4.1-mini",
            is_enabled=True,
            is_default=True,
            temperature=0.2,
            max_output_tokens=4000,
            supports_tools=True,
        )
        provider_model.id = 7
        provider_model.provider = provider
        mock_get_provider_model.return_value = provider_model

        def refresh_agent(instance: Agent) -> None:
            instance.id = 11
            instance.provider_model = provider_model
            instance.created_at = datetime(2026, 3, 30, 6, 0, 0)
            instance.updated_at = datetime(2026, 3, 30, 6, 0, 0)

        db.refresh.side_effect = refresh_agent

        created = agent_service.create_agent(
            db,
            5,
            AgentCreate(
                provider_model_id=7,
                name="Research Agent",
                description="Handles research tasks",
                system_prompt="Focus on concise outputs.",
                is_enabled=True,
                max_concurrency=1,
            ),
        )

        mock_get_workspace.assert_called_once_with(db, 5)
        self.assertEqual(created.id, 11)
        self.assertEqual(created.workspace_id, 5)
        self.assertEqual(created.provider_model_id, 7)
        self.assertEqual(created.name, "Research Agent")

    def test_update_agent_applies_changes(self) -> None:
        db = MagicMock()
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-123",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 2
        provider_model = ProviderModel(
            provider_id=2,
            label="Reasoning",
            model_name="gpt-4.1",
            is_enabled=True,
            is_default=True,
            temperature=0.2,
            max_output_tokens=8000,
            supports_tools=True,
        )
        provider_model.id = 7
        provider_model.provider = provider

        agent = Agent(
            workspace_id=5,
            provider_model_id=7,
            name="Research Agent",
            description="Old",
            system_prompt="Old prompt",
            is_enabled=True,
            max_concurrency=1,
        )
        agent.id = 11
        agent.provider_model = provider_model
        agent.created_at = datetime(2026, 3, 30, 6, 0, 0)
        agent.updated_at = datetime(2026, 3, 30, 6, 0, 0)

        with patch(
            "app.services.agent_service.get_agent_for_workspace_or_404",
            return_value=agent,
        ):
            updated = agent_service.update_agent(
                db,
                5,
                11,
                AgentUpdate(name="Writer Agent", description="New"),
            )

        self.assertEqual(updated.name, "Writer Agent")
        self.assertEqual(updated.description, "New")

    def test_get_agent_for_workspace_or_404_raises_for_wrong_workspace(self) -> None:
        db = MagicMock()
        agent = Agent(
            workspace_id=8,
            provider_model_id=3,
            name="Test Agent",
            description=None,
            system_prompt=None,
            is_enabled=True,
            max_concurrency=1,
        )
        agent.id = 20
        db.get.return_value = agent

        with self.assertRaises(HTTPException) as context:
            agent_service.get_agent_for_workspace_or_404(db, 5, 20)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Agent does not belong to the specified workspace",
        )
