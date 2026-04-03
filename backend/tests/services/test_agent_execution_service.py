import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from fastapi import HTTPException

from app.models.agent import Agent
from app.models.project import Project
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.models.task import Task
from app.models.task_run import TaskRun
from app.models.workflow_run import WorkflowRun
from app.services import agent_execution_service


class AgentExecutionServiceTests(unittest.TestCase):
    def _build_ready_task_run(self) -> tuple[TaskRun, WorkflowRun]:
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
            max_output_tokens=2000,
            supports_tools=True,
        )
        provider_model.id = 7
        provider_model.provider = provider

        agent = Agent(
            workspace_id=5,
            provider_model_id=7,
            name="Research Agent",
            description=None,
            system_prompt="You are helpful.",
            is_enabled=True,
            max_concurrency=1,
        )
        agent.id = 11
        agent.provider_model = provider_model

        project = Project(
            workspace_id=5,
            name="Project A",
            description=None,
            status="active",
        )
        project.id = 20
        project.workspace = MagicMock(name="workspace", root_path="D:\\AI\\demo")
        project.workspace.name = "Demo Workspace"

        workflow_run = WorkflowRun(
            project_id=20,
            status="running",
            trigger_type="manual",
            input_payload=None,
        )
        workflow_run.id = 30
        workflow_run.project = project

        task = Task(
            project_id=20,
            agent_id=11,
            title="Summarize notes",
            description="Create a concise summary",
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[],
        )
        task.id = 40
        task.project = project

        task_run = TaskRun(
            workflow_run_id=30,
            task_id=40,
            assigned_agent_id=11,
            assigned_agent_name="Research Agent",
            title_snapshot="Summarize notes",
            node_type="task",
            status="ready",
            executor_type="system",
            task_dependencies_snapshot=[],
            attempt_count=0,
        )
        task_run.id = 50
        task_run.workflow_run = workflow_run
        task_run.task = task
        task_run.assigned_agent = agent
        workflow_run.task_runs = [task_run]
        return task_run, workflow_run

    @patch("app.services.agent_execution_service.get_project_for_workspace_or_404")
    @patch("app.services.agent_execution_service._load_task_run_or_404")
    @patch("app.services.agent_execution_service._execute_agent_roundtrip_with_activity")
    @patch("app.services.agent_execution_service._promote_ready_task_runs")
    @patch("app.services.agent_execution_service._finalize_workflow_run_if_complete")
    def test_execute_task_run_completes_successfully(
        self,
        mock_finalize,
        mock_promote,
        mock_execute_roundtrip,
        mock_load_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        task_run, workflow_run = self._build_ready_task_run()
        mock_load_task_run.return_value = task_run
        mock_execute_roundtrip.return_value = ("Final answer", {"id": "resp_1"}, [])

        result = agent_execution_service.execute_task_run(db, 5, 20, 30, 50)

        self.assertIs(result, workflow_run)
        self.assertEqual(task_run.status, "completed")
        self.assertEqual(task_run.executor_type, "agent")
        self.assertEqual(
            task_run.input_payload,
            {
                "files": [],
                "auto_retry_attempt": 1,
                "auto_retry_max_attempts": agent_execution_service.settings.agent_task_auto_retry_attempts,
                "activity_log": task_run.input_payload["activity_log"],
            },
        )
        self.assertGreaterEqual(len(task_run.input_payload["activity_log"]), 3)
        self.assertEqual(task_run.output_payload["text"], "Final answer")
        self.assertGreaterEqual(len(task_run.output_payload["activity_log"]), 1)
        self.assertEqual(task_run.attempt_count, 1)
        mock_promote.assert_called_once_with(db, 30)
        mock_finalize.assert_called_once_with(workflow_run)
        self.assertGreaterEqual(db.commit.call_count, 2)

    @patch("app.services.agent_execution_service.get_project_for_workspace_or_404")
    @patch("app.services.agent_execution_service._load_task_run_or_404")
    def test_execute_task_run_rejects_non_ready_status(
        self,
        mock_load_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        task_run, _ = self._build_ready_task_run()
        task_run.status = "pending"
        mock_load_task_run.return_value = task_run

        with self.assertRaises(HTTPException) as context:
            agent_execution_service.execute_task_run(db, 5, 20, 30, 50)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Only ready or failed task runs can be executed",
        )

    @patch("app.services.agent_execution_service.get_project_for_workspace_or_404")
    @patch("app.services.agent_execution_service._load_task_run_or_404")
    @patch("app.services.agent_execution_service._execute_agent_roundtrip_with_activity")
    @patch("app.services.agent_execution_service._promote_ready_task_runs")
    @patch("app.services.agent_execution_service._finalize_workflow_run_if_complete")
    def test_execute_task_run_allows_retry_from_failed_status(
        self,
        mock_finalize,
        mock_promote,
        mock_execute_roundtrip,
        mock_load_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        task_run, workflow_run = self._build_ready_task_run()
        task_run.status = "failed"
        task_run.error_message = "old error"
        workflow_run.status = "failed"
        workflow_run.error_message = "workflow error"
        mock_load_task_run.return_value = task_run
        mock_execute_roundtrip.return_value = ("Retry success", {"id": "resp_retry"}, [])

        result = agent_execution_service.execute_task_run(db, 5, 20, 30, 50)

        self.assertIs(result, workflow_run)
        self.assertEqual(task_run.status, "completed")
        self.assertEqual(task_run.output_payload["text"], "Retry success")
        self.assertEqual(workflow_run.status, "running")
        self.assertIsNone(workflow_run.error_message)

    @patch("app.services.agent_execution_service.get_project_for_workspace_or_404")
    @patch("app.services.agent_execution_service._load_task_run_or_404")
    @patch("app.services.agent_execution_service._execute_agent_roundtrip_with_activity")
    @patch("app.services.agent_execution_service._promote_ready_task_runs")
    @patch("app.services.agent_execution_service._finalize_workflow_run_if_complete")
    def test_execute_task_run_retries_incomplete_result_before_completing(
        self,
        mock_finalize,
        mock_promote,
        mock_execute_roundtrip,
        mock_load_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        task_run, workflow_run = self._build_ready_task_run()
        task_run.task.title = "收集新能源汽车销量原始数据"
        task_run.task.description = "请输出 csv 文件"
        mock_load_task_run.return_value = task_run
        mock_execute_roundtrip.side_effect = [
            (
                json.dumps({"summary": "需要先联网搜索数据来源", "files": []}, ensure_ascii=False),
                {"id": "resp_retry_1"},
                [],
            ),
            (
                json.dumps(
                    {
                        "summary": "已收集数据并写入文件",
                        "files": [
                            {
                                "path": "data/nevsales.csv",
                                "content": "week,sales\n2026-W13,12345\n",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                {"id": "resp_retry_2"},
                [],
            ),
        ]

        with patch("app.services.agent_execution_service._resolve_workspace_file_path") as mock_resolve_path:
            target_path = MagicMock()
            target_path.parent = MagicMock()
            mock_resolve_path.return_value = target_path

            result = agent_execution_service.execute_task_run(db, 5, 20, 30, 50)

        self.assertIs(result, workflow_run)
        self.assertEqual(task_run.status, "completed")
        self.assertEqual(task_run.output_payload["text"], "已收集数据并写入文件")
        self.assertEqual(mock_execute_roundtrip.call_count, 2)
        mock_promote.assert_called_once_with(db, 30)
        mock_finalize.assert_called_once_with(workflow_run)

    @patch("app.services.agent_execution_service._call_provider")
    @patch("app.services.agent_execution_service._execute_tool_call")
    def test_execute_agent_roundtrip_handles_tool_calls(
        self,
        mock_execute_tool_call,
        mock_call_provider,
    ) -> None:
        task_run, _ = self._build_ready_task_run()
        agent = task_run.assigned_agent
        mock_call_provider.side_effect = [
            (
                json.dumps(
                    {
                        "summary": "Need web data",
                        "files": [],
                        "tool_calls": [
                            {"tool": "web_search", "query": "EV sales", "max_results": 3}
                        ],
                    }
                ),
                {"id": "resp_tool_1"},
            ),
            (
                json.dumps(
                    {
                        "summary": "Final answer",
                        "files": [],
                    }
                ),
                {"id": "resp_final"},
            ),
        ]
        mock_execute_tool_call.return_value = {
            "tool": "web_search",
            "query": "EV sales",
            "results": [{"title": "Example", "url": "https://example.com"}],
        }

        raw_text, raw_payload, tool_results = agent_execution_service._execute_agent_roundtrip(
            agent,
            "Run the task.",
        )

        self.assertIn("Final answer", raw_text)
        self.assertEqual(raw_payload, {"id": "resp_final"})
        self.assertEqual(len(tool_results), 1)
        self.assertTrue(tool_results[0]["ok"])
        self.assertEqual(tool_results[0]["request"]["tool"], "web_search")
        second_prompt = mock_call_provider.call_args_list[1].args[1]
        self.assertIn("Tool results:", second_prompt)
        self.assertIn("web_search", second_prompt)

    def test_extract_tool_calls_from_text_returns_valid_list(self) -> None:
        tool_calls = agent_execution_service._extract_tool_calls_from_text(
            json.dumps(
                {
                    "summary": "Use tools",
                    "files": [],
                    "tool_calls": [
                        {"tool": "web_search", "query": "workflow automation"},
                        {"tool": "fetch_url", "url": "https://example.com"},
                    ],
                }
            )
        )

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["tool"], "web_search")
        self.assertEqual(tool_calls[1]["tool"], "fetch_url")

    def test_extract_tool_calls_from_text_accepts_single_tool_request_object(self) -> None:
        tool_calls = agent_execution_service._extract_tool_calls_from_text(
            json.dumps(
                {
                    "tool": "web_search",
                    "query": "新能源汽车周销量",
                    "max_results": 5,
                }
            )
        )

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["tool"], "web_search")

    def test_extract_json_object_from_text_prefers_last_json_object(self) -> None:
        payload = agent_execution_service._extract_json_object_from_text(
            '\n'.join(
                [
                    '{"summary":"Need tool","files":[],"tool_calls":[{"tool":"web_search","query":"EV sales"}]}',
                    '{"summary":"Final answer","files":[]}',
                ]
            )
        )

        self.assertEqual(payload, {"summary": "Final answer", "files": []})

    @patch("app.services.agent_execution_service._call_provider")
    @patch("app.services.agent_execution_service._execute_tool_call")
    def test_execute_agent_roundtrip_accepts_response_with_previous_json_and_final_json(
        self,
        mock_execute_tool_call,
        mock_call_provider,
    ) -> None:
        task_run, _ = self._build_ready_task_run()
        agent = task_run.assigned_agent
        first_response = json.dumps(
            {
                "summary": "Need web data",
                "files": [],
                "tool_calls": [
                    {"tool": "web_search", "query": "EV sales", "max_results": 3}
                ],
            }
        )
        final_response = json.dumps(
            {
                "summary": "Final answer",
                "files": [],
            }
        )
        mock_call_provider.side_effect = [
            (first_response, {"id": "resp_tool_1"}),
            (f"{first_response}\n{final_response}", {"id": "resp_final"}),
        ]
        mock_execute_tool_call.return_value = {
            "tool": "web_search",
            "query": "EV sales",
            "results": [{"title": "Example", "url": "https://example.com"}],
        }

        raw_text, raw_payload, tool_results = agent_execution_service._execute_agent_roundtrip(
            agent,
            "Run the task.",
        )

        self.assertEqual(raw_payload, {"id": "resp_final"})
        self.assertEqual(json.loads(raw_text), {"summary": "Final answer", "files": []})
        self.assertEqual(len(tool_results), 1)

    @patch("app.services.agent_execution_service._fetch_text_url")
    def test_execute_web_search_parses_results(self, mock_fetch_text_url) -> None:
        mock_fetch_text_url.return_value = """
        <html>
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnews">
            EV sales rise
          </a>
        </html>
        """

        result = agent_execution_service._execute_web_search("EV sales")

        self.assertEqual(result["tool"], "web_search")
        self.assertEqual(result["query"], "EV sales")
        self.assertEqual(result["results"][0]["url"], "https://example.com/news")

    @patch("app.services.agent_execution_service._fetch_text_url")
    def test_execute_web_search_parses_fallback_duckduckgo_redirect_links(self, mock_fetch_text_url) -> None:
        mock_fetch_text_url.return_value = """
        <html>
          <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Freport&amp;rut=123">
            Example report
          </a>
        </html>
        """

        result = agent_execution_service._execute_web_search("EV report")

        self.assertEqual(result["results"][0]["title"], "Example report")
        self.assertEqual(result["results"][0]["url"], "https://example.com/report")

    @patch("app.services.agent_execution_service._fetch_text_url")
    def test_execute_fetch_url_truncates_large_content(self, mock_fetch_text_url) -> None:
        mock_fetch_text_url.return_value = "A" * (agent_execution_service.settings.agent_web_fetch_max_chars + 50)

        result = agent_execution_service._execute_fetch_url("https://example.com/report")

        self.assertEqual(result["tool"], "fetch_url")
        self.assertEqual(result["url"], "https://example.com/report")
        self.assertTrue(result["content"].endswith("...[truncated]"))

    def test_validate_final_response_payload_rejects_single_tool_request_object(self) -> None:
        with self.assertRaises(HTTPException) as context:
            agent_execution_service._validate_final_response_payload(
                json.dumps(
                    {
                        "tool": "web_search",
                        "query": "新能源汽车周销量",
                        "max_results": 5,
                    }
                )
            )

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("tool request", str(context.exception.detail))

    def test_validate_final_response_payload_rejects_tool_calls_payload(self) -> None:
        with self.assertRaises(HTTPException) as context:
            agent_execution_service._validate_final_response_payload(
                json.dumps(
                    {
                        "summary": "Need web data",
                        "files": [],
                        "tool_calls": [
                            {"tool": "web_search", "query": "新能源汽车周销量"}
                        ],
                    }
                )
            )

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("tool_calls", str(context.exception.detail))

    def test_validate_final_response_payload_accepts_summary_without_files(self) -> None:
        payload = agent_execution_service._validate_final_response_payload(
            json.dumps(
                {
                    "summary": "Checked the weather and prepared the answer.",
                }
            )
        )

        self.assertEqual(
            payload,
            {"summary": "Checked the weather and prepared the answer."},
        )

    def test_detect_incomplete_task_result_does_not_require_artifacts(self) -> None:
        task_run, _ = self._build_ready_task_run()

        incomplete_reason = agent_execution_service._detect_incomplete_task_result(
            task_run,
            "已完成天气查询并整理结果。",
            [],
        )

        self.assertIsNone(incomplete_reason)

    @patch("app.services.agent_execution_service.get_project_for_workspace_or_404")
    @patch("app.services.agent_execution_service._load_task_run_or_404")
    @patch("app.services.agent_execution_service._execute_agent_roundtrip_with_activity")
    def test_execute_task_run_fails_when_agent_returns_single_tool_request_object(
        self,
        mock_execute_roundtrip,
        mock_load_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        task_run, workflow_run = self._build_ready_task_run()
        mock_load_task_run.return_value = task_run
        mock_execute_roundtrip.return_value = (
            json.dumps(
                {
                    "tool": "web_search",
                    "query": "新能源汽车周销量",
                    "max_results": 5,
                }
            ),
            {"id": "resp_invalid"},
            [],
        )

        with self.assertRaises(HTTPException) as context:
            agent_execution_service.execute_task_run(db, 5, 20, 30, 50)

        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(task_run.status, "failed")
        self.assertEqual(workflow_run.status, "failed")
        self.assertIn("tool request", str(task_run.error_message))

    def test_ensure_agent_available_rejects_busy_agent(self) -> None:
        db = MagicMock()
        task_run, _ = self._build_ready_task_run()
        db.scalar.return_value = 999

        with self.assertRaises(HTTPException) as context:
            agent_execution_service._ensure_agent_available(db, task_run)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "Assigned agent is busy")

    def test_extract_http_error_message_prefers_provider_message(self) -> None:
        error = HTTPError(
            url="https://api.example.com/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"Invalid API key"}}'),
        )

        try:
            message = agent_execution_service._extract_http_error_message(error)
        finally:
            error.close()

        self.assertEqual(
            message,
            "Provider request failed with HTTP 401: Invalid API key",
        )

    def test_get_openai_max_tokens_field_for_gpt5_family(self) -> None:
        self.assertEqual(
            agent_execution_service._get_openai_max_tokens_field("gpt-5.3"),
            "max_completion_tokens",
        )

    @patch("app.services.agent_execution_service.urllib_request.urlopen")
    def test_execute_openai_compatible_uses_max_completion_tokens_for_gpt5(
        self,
        mock_urlopen,
    ) -> None:
        provider = Provider(
            platform="openai",
            label="OpenAI Main",
            api_key="sk-test-123",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider_model = ProviderModel(
            provider_id=2,
            label="GPT-5",
            model_name="gpt-5.3",
            is_enabled=True,
            is_default=True,
            temperature=0.2,
            max_output_tokens=1200,
            supports_tools=True,
        )

        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "done",
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        agent_execution_service._execute_openai_compatible(
            provider=provider,
            provider_model=provider_model,
            system_prompt="You are helpful.",
            user_prompt="Run the task.",
        )

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["max_completion_tokens"], 1200)
        self.assertNotIn("max_tokens", payload)

    @patch("app.services.agent_execution_service._resolve_workspace_file_path")
    def test_apply_file_operations_writes_file_into_workspace(self, mock_resolve_path) -> None:
        task_run, _ = self._build_ready_task_run()
        task_run.workflow_run.project.workspace.root_path = "D:\\AI\\demo"
        target_path = MagicMock()
        target_path.parent = MagicMock()
        mock_resolve_path.return_value = target_path

        text, artifacts = agent_execution_service._apply_file_operations(
            task_run,
            json.dumps(
                {
                    "summary": "已创建文件",
                    "files": [
                        {
                            "path": "outputs/poem.txt",
                            "content": "床前明月光\n疑是地上霜",
                        }
                    ],
                }
            ),
        )

        self.assertEqual(text, "已创建文件")
        target_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        target_path.write_text.assert_called_once_with(
            "床前明月光\n疑是地上霜",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(artifacts[0]["path"], "outputs/poem.txt")

    def test_resolve_workspace_file_path_rejects_path_outside_workspace(self) -> None:
        with self.assertRaises(HTTPException) as context:
            agent_execution_service._resolve_workspace_file_path(
                str(Path.cwd()),
                "../escape.txt",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Requested file path must stay within the workspace root path",
        )

    @patch("app.services.agent_execution_service._resolve_workspace_file_path")
    def test_build_user_prompt_includes_referenced_file_content(self, mock_resolve_path) -> None:
        task_run, _ = self._build_ready_task_run()
        task_run.task.description = "Please edit `docs/notes.txt` and polish it."
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "Draft note content"
        mock_resolve_path.return_value = mock_file

        prompt, input_files = agent_execution_service._build_user_prompt(task_run)

        self.assertIn("File: docs/notes.txt", prompt)
        self.assertIn("Source: referenced", prompt)
        self.assertIn("Draft note content", prompt)
        self.assertEqual(
            input_files,
            [{"path": "docs/notes.txt", "source": "referenced"}],
        )

    def test_build_user_prompt_uses_native_tool_guidance_for_tool_models(self) -> None:
        task_run, _ = self._build_ready_task_run()

        prompt, _input_files = agent_execution_service._build_user_prompt(task_run)

        self.assertIn("call the provided web tools directly", prompt)
        self.assertNotIn("Tool request JSON format", prompt)

    def test_collect_input_files_includes_dependency_artifacts(self) -> None:
        task_run, workflow_run = self._build_ready_task_run()
        task_run.task_dependencies_snapshot = [41]

        dependency_task = Task(
            project_id=20,
            agent_id=11,
            title="Create draft",
            description=None,
            node_type="task",
            status="done",
            priority="medium",
            display_order=0,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[],
        )
        dependency_task.id = 41

        dependency_task_run = TaskRun(
            workflow_run_id=30,
            task_id=41,
            assigned_agent_id=11,
            assigned_agent_name="Research Agent",
            title_snapshot="Create draft",
            node_type="task",
            status="completed",
            executor_type="agent",
            task_dependencies_snapshot=[],
            attempt_count=1,
            output_payload={
                "artifacts": [
                    {"path": "outputs/draft.md", "operation": "write_file"},
                ]
            },
        )
        dependency_task_run.id = 49
        dependency_task_run.task = dependency_task

        workflow_run.task_runs = [dependency_task_run, task_run]

        self.assertEqual(
            agent_execution_service._collect_input_files(task_run),
            [{"path": "outputs/draft.md", "source": "dependency_task_run:49"}],
        )

    @patch("app.services.agent_execution_service._execute_tool_call")
    @patch("app.services.agent_execution_service.urllib_request.urlopen")
    def test_execute_agent_roundtrip_native_tools_for_openai_compatible(
        self,
        mock_urlopen,
        mock_execute_tool_call,
    ) -> None:
        task_run, _ = self._build_ready_task_run()
        agent = task_run.assigned_agent
        response_with_tool_call = MagicMock()
        response_with_tool_call.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "web_search",
                                        "arguments": json.dumps(
                                            {"query": "Rizhao weather today", "max_results": 3}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ).encode("utf-8")
        response_with_final = MagicMock()
        response_with_final.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Sunny, 24C",
                                    "files": [],
                                }
                            )
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.side_effect = [
            response_with_tool_call,
            response_with_final,
        ]
        mock_execute_tool_call.return_value = {
            "tool": "web_search",
            "query": "Rizhao weather today",
            "results": [{"title": "Weather", "url": "https://example.com/weather"}],
        }

        raw_text, raw_payload, tool_results = agent_execution_service._execute_agent_roundtrip_native_tools(
            agent,
            "Get today's weather in Rizhao.",
        )

        self.assertEqual(json.loads(raw_text), {"summary": "Sunny, 24C", "files": []})
        self.assertEqual(raw_payload["choices"][0]["message"]["content"], json.dumps({"summary": "Sunny, 24C", "files": []}))
        self.assertEqual(len(tool_results), 1)
        self.assertTrue(tool_results[0]["ok"])
        self.assertEqual(tool_results[0]["request"]["tool"], "web_search")
        first_request = mock_urlopen.call_args_list[0].args[0]
        second_request = mock_urlopen.call_args_list[1].args[0]
        first_payload = json.loads(first_request.data.decode("utf-8"))
        second_payload = json.loads(second_request.data.decode("utf-8"))
        self.assertEqual(first_payload["tool_choice"], "auto")
        self.assertIn("tools", first_payload)
        self.assertEqual(second_payload["messages"][-1]["role"], "tool")
