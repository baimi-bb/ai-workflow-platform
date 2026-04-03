import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.agent import Agent
from app.models.project import Project
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.models.task import Task
from app.schemas.project_planning import ProjectPlanCreate
from app.services import project_planning_service


class ProjectPlanningServiceTests(unittest.TestCase):
    def _build_project_and_agents(self) -> tuple[Project, Agent, list[Agent]]:
        provider = Provider(
            platform="openai",
            label="OpenAI",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            is_enabled=True,
        )
        provider.id = 5

        planner_model = ProviderModel(
            provider_id=5,
            label="Planner Model",
            model_name="gpt-4.1-mini",
            is_enabled=True,
            is_default=True,
            temperature=0.2,
            max_output_tokens=2000,
            supports_tools=True,
        )
        planner_model.id = 7
        planner_model.provider = provider

        planner_agent = Agent(
            workspace_id=3,
            provider_model_id=7,
            name="Planner Agent",
            description="Plans the project",
            system_prompt="You plan tasks.",
            is_enabled=True,
            max_concurrency=1,
        )
        planner_agent.id = 11
        planner_agent.provider_model = planner_model

        build_model = ProviderModel(
            provider_id=5,
            label="Builder Model",
            model_name="gpt-4.1-mini",
            is_enabled=True,
            is_default=False,
            temperature=0.2,
            max_output_tokens=2000,
            supports_tools=True,
        )
        build_model.id = 9
        build_model.provider = provider

        build_agent = Agent(
            workspace_id=3,
            provider_model_id=9,
            name="Builder Agent",
            description="Implements code",
            system_prompt="You build things.",
            is_enabled=True,
            max_concurrency=1,
        )
        build_agent.id = 12
        build_agent.provider_model = build_model

        review_agent = Agent(
            workspace_id=3,
            provider_model_id=9,
            name="Review Agent",
            description="Reviews output",
            system_prompt="You review things.",
            is_enabled=True,
            max_concurrency=1,
        )
        review_agent.id = 13
        review_agent.provider_model = build_model

        project = Project(
            workspace_id=3,
            name="Workflow Planner",
            description="Build project planning",
            status="active",
        )
        project.id = 21
        project.workspace = MagicMock()
        project.workspace.agents = [planner_agent, build_agent, review_agent]
        project.workspace.root_path = None
        project.tasks = []
        return project, planner_agent, [planner_agent, build_agent, review_agent]

    @patch("app.services.project_planning_service.task_service.update_task")
    @patch("app.services.project_planning_service.task_service.create_task_under_project")
    @patch("app.services.project_planning_service.task_service._list_project_tasks")
    @patch("app.services.project_planning_service._call_planner")
    @patch("app.services.project_planning_service.get_project_for_workspace_or_404")
    def test_plan_project_tasks_creates_tasks_and_dependencies(
        self,
        mock_get_project,
        mock_call_planner,
        mock_list_tasks,
        mock_create_task,
        mock_update_task,
    ) -> None:
        db = MagicMock()
        project, planner_agent, _agents = self._build_project_and_agents()
        db.get.return_value = planner_agent
        mock_get_project.return_value = project
        start_task = Task(
            project_id=21,
            agent_id=None,
            title="Start",
            description="Default start node",
            node_type="start",
            status="done",
            priority="low",
            display_order=0,
            canvas_x=40,
            canvas_y=120,
            task_dependencies=[],
        )
        start_task.id = 1

        end_task = Task(
            project_id=21,
            agent_id=None,
            title="End",
            description="Default end node",
            node_type="end",
            status="todo",
            priority="low",
            display_order=99,
            canvas_x=1160,
            canvas_y=120,
            task_dependencies=[],
        )
        end_task.id = 2
        mock_call_planner.return_value = {
            "summary": "Generated an implementation plan",
            "tasks": [
                {
                    "title": "Design API",
                    "description": "Define the new planning endpoint",
                    "objective": "Create the project planning API contract",
                    "deliverable": "A concrete API design task description",
                    "priority": "high",
                    "assigned_agent_id": 12,
                    "depends_on_titles": [],
                    "required_workspace_paths": ["project-docs/api-spec.md"],
                    "suggested_output_paths": ["project-docs/generated-plan.md"],
                },
                {
                    "title": "Review flow",
                    "description": "Check the generated workflow",
                    "objective": "Validate dependencies and runtime flow",
                    "deliverable": "A reviewed workflow plan",
                    "priority": "medium",
                    "assigned_agent_name": "Review Agent",
                    "depends_on_titles": ["Design API"],
                    "input_from_titles": ["Design API"],
                },
            ],
        }

        created_one = Task(
            project_id=21,
            agent_id=12,
            title="Design API",
            description="Define the new planning endpoint",
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[],
        )
        created_one.id = 101
        created_one.task_dependencies = []

        created_two = Task(
            project_id=21,
            agent_id=13,
            title="Review flow",
            description="Check the generated workflow",
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[],
        )
        created_two.id = 102
        created_two.task_dependencies = []
        mock_create_task.side_effect = [created_one, created_two]

        updated_one_internal = Task(
            project_id=21,
            agent_id=12,
            title="Design API",
            description="Define the new planning endpoint",
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[],
        )
        updated_one_internal.id = 101

        updated_two_internal = Task(
            project_id=21,
            agent_id=13,
            title="Review flow",
            description="Check the generated workflow",
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[101],
        )
        updated_two_internal.id = 102

        updated_one_with_start = Task(
            project_id=21,
            agent_id=12,
            title="Design API",
            description="Define the new planning endpoint",
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[1],
        )
        updated_one_with_start.id = 101

        updated_end = Task(
            project_id=21,
            agent_id=None,
            title="End",
            description="Default end node",
            node_type="end",
            status="todo",
            priority="low",
            display_order=99,
            canvas_x=1160,
            canvas_y=120,
            task_dependencies=[102],
        )
        updated_end.id = 2

        layout_start = Task(
            project_id=21,
            agent_id=None,
            title="Start",
            description="Default start node",
            node_type="start",
            status="done",
            priority="low",
            display_order=0,
            canvas_x=40,
            canvas_y=120,
            task_dependencies=[],
        )
        layout_start.id = 1

        layout_design = Task(
            project_id=21,
            agent_id=12,
            title="Design API",
            description="Define the new planning endpoint",
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            canvas_x=500,
            canvas_y=120,
            task_dependencies=[1],
        )
        layout_design.id = 101

        layout_review = Task(
            project_id=21,
            agent_id=13,
            title="Review flow",
            description="Check the generated workflow",
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=1100,
            canvas_y=120,
            task_dependencies=[101],
        )
        layout_review.id = 102

        layout_end = Task(
            project_id=21,
            agent_id=None,
            title="End",
            description="Default end node",
            node_type="end",
            status="todo",
            priority="low",
            display_order=99,
            canvas_x=1700,
            canvas_y=120,
            task_dependencies=[102],
        )
        layout_end.id = 2
        mock_update_task.side_effect = [
            updated_one_internal,
            updated_two_internal,
            updated_one_with_start,
            updated_end,
            layout_design,
            layout_review,
            layout_end,
        ]
        mock_list_tasks.side_effect = [
            [start_task, end_task],
            [start_task, end_task, updated_one_internal, updated_two_internal],
            [start_task, end_task, updated_one_with_start, updated_two_internal],
            [start_task, updated_end, updated_one_with_start, updated_two_internal],
            [layout_start, updated_end, updated_one_with_start, updated_two_internal],
            [layout_start, updated_end, layout_design, updated_two_internal],
            [layout_start, updated_end, layout_design, layout_review],
            [layout_start, layout_end, layout_design, layout_review],
        ]

        result = project_planning_service.plan_project_tasks(
            db,
            3,
            21,
            ProjectPlanCreate(planner_agent_id=11),
        )

        self.assertEqual(result["created_task_count"], 2)
        self.assertEqual(result["created_tasks"][0]["title"], "Design API")
        self.assertEqual(result["created_tasks"][0]["task_dependencies"], [1])
        self.assertEqual(result["created_tasks"][0]["id"], 101)
        self.assertEqual(result["created_tasks"][1]["task_dependencies"], [101])
        self.assertEqual(result["created_tasks"][1]["id"], 102)
        self.assertEqual(mock_create_task.call_count, 2)
        self.assertEqual(mock_update_task.call_count, 7)
        self.assertIn("Execution Standard:", mock_create_task.call_args_list[0].args[3].description)
        self.assertIn("Required workspace files: project-docs/api-spec.md", mock_create_task.call_args_list[0].args[3].description)
        self.assertIn("Suggested output files: project-docs/generated-plan.md", mock_create_task.call_args_list[0].args[3].description)
        self.assertIn("Required upstream task outputs: Design API", mock_create_task.call_args_list[1].args[3].description)
        self.assertEqual(mock_update_task.call_args_list[4].args[4].canvas_x, 500)
        self.assertEqual(mock_update_task.call_args_list[4].args[4].canvas_y, 120)
        self.assertEqual(mock_update_task.call_args_list[5].args[4].canvas_x, 1100)
        self.assertEqual(mock_update_task.call_args_list[5].args[4].canvas_y, 510)
        self.assertEqual(mock_update_task.call_args_list[6].args[4].canvas_x, 1700)
        self.assertEqual(mock_update_task.call_args_list[6].args[4].canvas_y, 510)

    def test_parse_plan_payload_merges_input_titles_into_dependencies(self) -> None:
        _project, _planner_agent, agents = self._build_project_and_agents()

        summary, tasks = project_planning_service._parse_plan_payload(
            {
                "summary": "structured",
                "tasks": [
                    {
                        "title": "Collect source data",
                        "description": "Collect data from workspace files",
                        "objective": "Prepare the raw dataset",
                        "deliverable": "A normalized csv file",
                        "required_workspace_paths": ["data/template.csv"],
                        "suggested_output_paths": ["data/normalized.csv"],
                    },
                    {
                        "title": "Analyze trend",
                        "description": "Analyze the prepared data",
                        "objective": "Generate the trend analysis",
                        "deliverable": "A markdown report",
                        "depends_on_titles": ["Collect source data"],
                        "input_from_titles": ["Collect source data"],
                        "required_workspace_paths": ["reports/notes.md"],
                        "suggested_output_paths": ["reports/ne-trend.md"],
                    },
                ],
            },
            agents,
        )

        self.assertEqual(summary, "structured")
        self.assertEqual(tasks[1]["depends_on_titles"], ["Collect source data"])
        self.assertEqual(tasks[1]["input_from_titles"], ["Collect source data"])
        self.assertIn("Execution Standard:", tasks[0]["description"])
        self.assertIn("Required workspace files: data/template.csv", tasks[0]["description"])
        self.assertIn("Suggested output files: data/normalized.csv", tasks[0]["description"])
        self.assertIn("Deliverable: A markdown report", tasks[1]["description"])

    def test_build_project_plan_prompt_includes_workspace_files_context(self) -> None:
        project, _planner_agent, agents = self._build_project_and_agents()

        with patch(
            "app.services.project_planning_service._collect_workspace_file_context",
            return_value=["data/template.csv", "reports/outline.md"],
        ):
            prompt = project_planning_service._build_project_plan_prompt(
                project,
                ProjectPlanCreate(planner_agent_id=11),
                agents,
            )

        self.assertIn("Workspace files you can plan around:", prompt)
        self.assertIn("- data/template.csv", prompt)
        self.assertIn('"input_from_titles"', prompt)
        self.assertIn('"required_workspace_paths"', prompt)
        self.assertIn('"suggested_output_paths"', prompt)

    def test_parse_plan_payload_rejects_duplicate_titles(self) -> None:
        _project, _planner_agent, agents = self._build_project_and_agents()

        with self.assertRaises(HTTPException) as context:
            project_planning_service._parse_plan_payload(
                {
                    "summary": "dup",
                    "tasks": [
                        {"title": "Task A"},
                        {"title": "Task A"},
                    ],
                },
                agents,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("must be unique", context.exception.detail)

    def test_build_layout_row_map_groups_branching_tasks_by_parent_center(self) -> None:
        start_task = Task(
            project_id=21,
            agent_id=None,
            title="Start",
            description=None,
            node_type="start",
            status="done",
            priority="low",
            display_order=0,
            canvas_x=40,
            canvas_y=120,
            task_dependencies=[],
        )
        start_task.id = 1

        root_a = Task(
            project_id=21,
            agent_id=None,
            title="Root A",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[1],
        )
        root_a.id = 10

        root_b = Task(
            project_id=21,
            agent_id=None,
            title="Root B",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[1],
        )
        root_b.id = 11

        child_a = Task(
            project_id=21,
            agent_id=None,
            title="Child A",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=3,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[10],
        )
        child_a.id = 12

        child_b = Task(
            project_id=21,
            agent_id=None,
            title="Child B",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=4,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[11],
        )
        child_b.id = 13

        merge_task = Task(
            project_id=21,
            agent_id=None,
            title="Merge",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=5,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[12, 13],
        )
        merge_task.id = 14

        project_tasks = [start_task, root_a, root_b, child_a, child_b, merge_task]
        depth_map = project_planning_service._build_depth_map(project_tasks)
        row_map = project_planning_service._build_layout_row_map(
            project_tasks,
            {10, 11, 12, 13, 14},
            depth_map,
        )

        self.assertEqual(row_map[10], 0)
        self.assertEqual(row_map[11], 1)
        self.assertEqual(row_map[12], 0)
        self.assertEqual(row_map[13], 1)
        self.assertEqual(row_map[14], 1)

    def test_parse_plan_payload_rejects_unknown_dependency(self) -> None:
        _project, _planner_agent, agents = self._build_project_and_agents()

        with self.assertRaises(HTTPException) as context:
            project_planning_service._parse_plan_payload(
                {
                    "summary": "unknown dep",
                    "tasks": [
                        {
                            "title": "Task A",
                            "depends_on_titles": ["Missing"],
                        }
                    ],
                },
                agents,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("unknown dependency title", context.exception.detail)

    def test_build_layout_row_map_zigzags_single_path_instead_of_single_line(self) -> None:
        start_task = Task(
            project_id=21,
            agent_id=None,
            title="Start",
            description=None,
            node_type="start",
            status="done",
            priority="low",
            display_order=0,
            canvas_x=40,
            canvas_y=120,
            task_dependencies=[],
        )
        start_task.id = 1

        task_a = Task(
            project_id=21,
            agent_id=None,
            title="Task A",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[1],
        )
        task_a.id = 10

        task_b = Task(
            project_id=21,
            agent_id=None,
            title="Task B",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[10],
        )
        task_b.id = 11

        task_c = Task(
            project_id=21,
            agent_id=None,
            title="Task C",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=3,
            canvas_x=0,
            canvas_y=0,
            task_dependencies=[11],
        )
        task_c.id = 12

        project_tasks = [start_task, task_a, task_b, task_c]
        depth_map = project_planning_service._build_depth_map(project_tasks)
        row_map = project_planning_service._build_layout_row_map(
            project_tasks,
            {10, 11, 12},
            depth_map,
        )

        self.assertEqual(row_map[10], 0)
        self.assertEqual(row_map[11], 1)
        self.assertEqual(row_map[12], 0)

    @patch("app.services.project_planning_service.agent_execution_service._extract_json_object_from_text")
    @patch("app.services.project_planning_service.agent_execution_service._call_provider")
    def test_call_planner_rejects_invalid_json(
        self,
        mock_call_provider,
        mock_extract_json,
    ) -> None:
        _project, planner_agent, _agents = self._build_project_and_agents()
        mock_call_provider.return_value = ("not json", {"id": "resp_1"})
        mock_extract_json.return_value = None

        with self.assertRaises(HTTPException) as context:
            project_planning_service._call_planner(planner_agent, "plan this")

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("invalid JSON", context.exception.detail)
