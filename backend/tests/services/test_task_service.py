import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.agent import Agent
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskStatusUpdate, TaskUpdate
from app.services import task_service


class TaskServiceTests(unittest.TestCase):
    @patch("app.services.task_service.get_project_for_workspace_or_404")
    def test_create_task_under_project_persists_task(self, mock_get_project) -> None:
        db = MagicMock()
        payload = TaskCreate(
            title="Build dashboard",
            description="Initial dashboard",
            status="todo",
            priority="high",
            task_dependencies=[],
        )

        def refresh_task(instance: Task) -> None:
            instance.id = 20

        db.refresh.side_effect = refresh_task

        task = task_service.create_task_under_project(db, 1, 2, payload)

        mock_get_project.assert_called_once_with(db, 1, 2)
        self.assertEqual(task.project_id, 2)
        self.assertEqual(task.title, "Build dashboard")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.node_type, "task")
        self.assertEqual(task.task_dependencies, [])
        self.assertEqual(task.id, 20)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(task)

    @patch("app.services.task_service.get_project_for_workspace_or_404")
    def test_update_task_status_updates_and_refreshes_task(self, mock_get_project) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="Task",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            task_dependencies=[3],
        )
        task.id = 8

        dependency = Task(
            project_id=2,
            title="Dependency",
            description=None,
            node_type="task",
            status="done",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        dependency.id = 3

        with patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ) as mock_get_task, patch(
            "app.services.task_service._list_project_tasks",
            return_value=[task, dependency],
        ):
            updated = task_service.update_task_status(
                db,
                1,
                2,
                8,
                TaskStatusUpdate(status="done"),
            )

        mock_get_project.assert_called_once_with(db, 1, 2)
        mock_get_task.assert_called_once_with(db, 2, 8)
        self.assertIs(updated, task)
        self.assertEqual(updated.status, "done")
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(task)

    def test_update_task_applies_partial_updates(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="Before",
            description="Old",
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        task.id = 9

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ), patch(
            "app.services.task_service._list_project_tasks",
            return_value=[task],
        ):
            updated = task_service.update_task(
                db,
                1,
                2,
                9,
                TaskUpdate(title="After", priority="high"),
            )

        self.assertIs(updated, task)
        self.assertEqual(updated.title, "After")
        self.assertEqual(updated.priority, "high")
        self.assertEqual(updated.description, "Old")
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(task)

    def test_get_task_for_project_or_404_raises_for_wrong_project(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=3,
            title="Task",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        task.id = 10
        db.get.return_value = task

        with self.assertRaises(HTTPException) as context:
            task_service.get_task_for_project_or_404(db, 2, 10)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Task does not belong to the specified project",
        )

    @patch("app.services.task_service.get_project_for_workspace_or_404")
    def test_create_task_rejects_incomplete_dependencies_for_started_task(
        self,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        dependency = Task(
            project_id=2,
            title="Dependency",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        dependency.id = 3

        with patch(
            "app.services.task_service._list_project_tasks",
            return_value=[dependency],
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.create_task_under_project(
                    db,
                    1,
                    2,
                    SimpleNamespace(
                        title="Blocked task",
                        description="",
                        node_type="task",
                        status="in_progress",
                        priority="medium",
                        display_order=None,
                        canvas_x=None,
                        canvas_y=None,
                        task_dependencies=[3],
                    ),
                )

        mock_get_project.assert_called_once_with(db, 1, 2)
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("dependencies are done", context.exception.detail)

    def test_update_task_rejects_cycles(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="Task A",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        task.id = 1
        dependency = Task(
            project_id=2,
            title="Task B",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            task_dependencies=[1],
        )
        dependency.id = 2

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ), patch(
            "app.services.task_service._list_project_tasks",
            return_value=[task, dependency],
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.update_task(
                    db,
                    1,
                    2,
                    1,
                    TaskUpdate(task_dependencies=[2]),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Task dependencies cannot contain cycles",
        )

    def test_delete_task_rejects_when_other_tasks_depend_on_it(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="Task A",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            task_dependencies=[],
        )
        task.id = 1
        dependent = Task(
            project_id=2,
            title="Task B",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            task_dependencies=[1],
        )
        dependent.id = 2

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ), patch(
            "app.services.task_service._list_project_tasks",
            return_value=[task, dependent],
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.delete_task(db, 1, 2, 1)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(
            context.exception.detail,
            "Task is still required by tasks: [2]",
        )

    def test_delete_task_rejects_start_node(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="Start",
            description=None,
            node_type="start",
            status="done",
            priority="low",
            display_order=0,
            task_dependencies=[],
        )
        task.id = 1

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.delete_task(db, 1, 2, 1)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Start node cannot be deleted")

    @patch("app.services.task_service.get_project_for_workspace_or_404")
    def test_create_task_rejects_end_node(self, mock_get_project) -> None:
        db = MagicMock()

        with patch(
            "app.services.task_service._list_project_tasks",
            return_value=[],
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.create_task_under_project(
                    db,
                    1,
                    2,
                    SimpleNamespace(
                        title="End",
                        description="",
                        node_type="end",
                        status="todo",
                        priority="low",
                        display_order=None,
                        canvas_x=None,
                        canvas_y=None,
                        task_dependencies=[],
                    ),
                )

        mock_get_project.assert_called_once_with(db, 1, 2)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "End node is created automatically")

    def test_delete_task_rejects_end_node(self) -> None:
        db = MagicMock()
        task = Task(
            project_id=2,
            title="End",
            description=None,
            node_type="end",
            status="todo",
            priority="low",
            display_order=99,
            canvas_x=1160,
            canvas_y=120,
            task_dependencies=[],
        )
        task.id = 2

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service.get_task_for_project_or_404",
            return_value=task,
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.delete_task(db, 1, 2, 2)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "End node cannot be deleted")

    def test_create_task_rejects_agent_from_other_workspace(self) -> None:
        db = MagicMock()
        agent = Agent(
            workspace_id=9,
            provider_model_id=3,
            name="Other Workspace Agent",
            description=None,
            system_prompt=None,
            is_enabled=True,
            max_concurrency=1,
        )
        agent.id = 4
        db.get.return_value = agent

        with patch(
            "app.services.task_service.get_project_for_workspace_or_404",
            return_value=MagicMock(),
        ), patch(
            "app.services.task_service._list_project_tasks",
            return_value=[],
        ):
            with self.assertRaises(HTTPException) as context:
                task_service.create_task_under_project(
                    db,
                    1,
                    2,
                    SimpleNamespace(
                        agent_id=4,
                        title="Assigned Task",
                        description="",
                        node_type="task",
                        status="todo",
                        priority="medium",
                        display_order=None,
                        canvas_x=None,
                        canvas_y=None,
                        task_dependencies=[],
                    ),
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Assigned agent must belong to the same workspace",
        )
