import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.task import Task
from app.models.task_run import TaskRun
from app.models.workflow_run import WorkflowRun
from app.schemas.workflow_run import WorkflowRunCreate
from app.services import workflow_run_service


class WorkflowRunServiceTests(unittest.TestCase):
    @patch("app.services.workflow_run_service.get_project_for_workspace_or_404")
    def test_create_workflow_run_under_project_creates_task_runs(
        self,
        mock_get_project,
    ) -> None:
        db = MagicMock()

        start_task = Task(
            project_id=2,
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

        ready_task = Task(
            project_id=2,
            title="Research",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=1,
            canvas_x=300,
            canvas_y=160,
            task_dependencies=[],
        )
        ready_task.id = 2

        blocked_task = Task(
            project_id=2,
            title="Review",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=2,
            canvas_x=500,
            canvas_y=160,
            task_dependencies=[2],
        )
        blocked_task.id = 3

        terminal_task = Task(
            project_id=2,
            title="Publish",
            description=None,
            node_type="task",
            status="todo",
            priority="high",
            display_order=3,
            canvas_x=700,
            canvas_y=160,
            task_dependencies=[],
        )
        terminal_task.id = 5

        end_task = Task(
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
        end_task.id = 4

        created_workflow_run = WorkflowRun(
            project_id=2,
            status="running",
            trigger_type="manual",
            input_payload={"goal": "Ship MVP"},
            started_at=None,
        )
        created_workflow_run.id = 20

        captured_task_runs = []

        def add_side_effect(instance):
            if isinstance(instance, WorkflowRun):
                instance.id = 20

        def add_all_side_effect(instances):
            captured_task_runs.extend(instances)

        db.add.side_effect = add_side_effect
        db.add_all.side_effect = add_all_side_effect

        with patch(
            "app.services.workflow_run_service._list_project_tasks",
            return_value=[start_task, ready_task, blocked_task, terminal_task, end_task],
        ), patch(
            "app.services.workflow_run_service.get_workflow_run_for_project_or_404",
            return_value=created_workflow_run,
        ) as mock_get_workflow_run:
            workflow_run = workflow_run_service.create_workflow_run_under_project(
                db,
                1,
                2,
                WorkflowRunCreate(
                    trigger_type="manual",
                    input_payload={"goal": "Ship MVP"},
                ),
            )

        mock_get_project.assert_called_once_with(db, 1, 2)
        mock_get_workflow_run.assert_called_once_with(db, 2, 20)
        self.assertIs(workflow_run, created_workflow_run)
        self.assertEqual(db.add.call_count, 1)
        db.add_all.assert_called_once()
        db.flush.assert_called_once()
        db.commit.assert_called_once()
        self.assertEqual(len(captured_task_runs), 5)

        start_task_run = next(item for item in captured_task_runs if item.task_id == 1)
        self.assertEqual(start_task_run.status, "completed")
        self.assertEqual(start_task_run.title_snapshot, "Start")

        ready_task_run = next(item for item in captured_task_runs if item.task_id == 2)
        self.assertEqual(ready_task_run.status, "ready")
        self.assertEqual(ready_task_run.task_dependencies_snapshot, [1])

        blocked_task_run = next(item for item in captured_task_runs if item.task_id == 3)
        self.assertEqual(blocked_task_run.status, "pending")
        self.assertEqual(blocked_task_run.task_dependencies_snapshot, [2])

        terminal_task_run = next(item for item in captured_task_runs if item.task_id == 5)
        self.assertEqual(terminal_task_run.status, "ready")
        self.assertEqual(terminal_task_run.task_dependencies_snapshot, [1])

        end_task_run = next(item for item in captured_task_runs if item.task_id == 4)
        self.assertEqual(end_task_run.status, "pending")
        self.assertEqual(end_task_run.task_dependencies_snapshot, [3, 5])

    def test_sort_ready_task_runs_for_queue_uses_priority_then_queue_time(self) -> None:
        now = datetime(2026, 3, 31, 9, 0, 0)
        low_task = Task(
            project_id=2,
            title="Low",
            description=None,
            node_type="task",
            status="todo",
            priority="low",
            display_order=2,
            task_dependencies=[],
        )
        low_task.id = 10
        medium_task = Task(
            project_id=2,
            title="Medium",
            description=None,
            node_type="task",
            status="todo",
            priority="medium",
            display_order=3,
            task_dependencies=[],
        )
        medium_task.id = 11
        high_task_early = Task(
            project_id=2,
            title="High Early",
            description=None,
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            task_dependencies=[],
        )
        high_task_early.id = 12
        high_task_late = Task(
            project_id=2,
            title="High Late",
            description=None,
            node_type="task",
            status="todo",
            priority="high",
            display_order=4,
            task_dependencies=[],
        )
        high_task_late.id = 13

        task_runs = []
        for task_id, task, updated_at in [
            (100, low_task, now + timedelta(minutes=3)),
            (101, medium_task, now + timedelta(minutes=2)),
            (102, high_task_late, now + timedelta(minutes=4)),
            (103, high_task_early, now + timedelta(minutes=1)),
        ]:
            task_run = TaskRun(
                workflow_run_id=20,
                task_id=task.id,
                assigned_agent_id=1,
                assigned_agent_name="Agent",
                title_snapshot=task.title,
                node_type="task",
                status="ready",
                executor_type="system",
                task_dependencies_snapshot=[],
                attempt_count=0,
            )
            task_run.id = task_id
            task_run.task = task
            task_run.created_at = now
            task_run.updated_at = updated_at
            task_runs.append(task_run)

        ordered = workflow_run_service._sort_ready_task_runs_for_queue(task_runs)
        self.assertEqual([task_run.id for task_run in ordered], [103, 102, 101, 100])

    @patch("app.services.workflow_run_service.get_project_for_workspace_or_404")
    @patch("app.services.workflow_run_service.agent_execution_service.execute_task_run")
    @patch("app.services.workflow_run_service._sync_workflow_run_state")
    @patch("app.services.workflow_run_service._load_workflow_run_for_execution_or_404")
    def test_execute_workflow_run_marks_run_queued_when_all_ready_agents_busy(
        self,
        mock_load_workflow_run,
        mock_sync_state,
        mock_execute_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        workflow_run = WorkflowRun(project_id=2, status="running", trigger_type="manual")
        workflow_run.id = 20

        ready_task = Task(
            project_id=2,
            title="Busy task",
            description=None,
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            task_dependencies=[],
        )
        ready_task.id = 2

        ready_task_run = TaskRun(
            workflow_run_id=20,
            task_id=2,
            assigned_agent_id=11,
            assigned_agent_name="Agent 1",
            title_snapshot="Busy task",
            node_type="task",
            status="ready",
            executor_type="system",
            task_dependencies_snapshot=[],
            attempt_count=0,
        )
        ready_task_run.id = 40
        ready_task_run.task = ready_task
        ready_task_run.created_at = datetime(2026, 3, 31, 9, 0, 0)
        ready_task_run.updated_at = datetime(2026, 3, 31, 9, 0, 0)
        workflow_run.task_runs = [ready_task_run]

        mock_load_workflow_run.side_effect = [workflow_run, workflow_run, workflow_run]
        mock_sync_state.return_value = workflow_run
        mock_execute_task_run.side_effect = HTTPException(
            status_code=409,
            detail="Assigned agent is busy",
        )

        result = workflow_run_service.execute_workflow_run(db, 1, 2, 20)

        self.assertIs(result, workflow_run)
        self.assertEqual(workflow_run.status, "queued")
        db.commit.assert_called()

    @patch("app.services.workflow_run_service.get_project_for_workspace_or_404")
    @patch("app.services.workflow_run_service.agent_execution_service.execute_task_run")
    @patch("app.services.workflow_run_service._sync_workflow_run_state")
    @patch("app.services.workflow_run_service._load_workflow_run_for_execution_or_404")
    def test_execute_workflow_run_advances_only_one_ready_task_run_per_call(
        self,
        mock_load_workflow_run,
        mock_sync_state,
        mock_execute_task_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        workflow_run_before = WorkflowRun(project_id=2, status="running", trigger_type="manual")
        workflow_run_before.id = 20

        high_task = Task(
            project_id=2,
            title="High task",
            description=None,
            node_type="task",
            status="todo",
            priority="high",
            display_order=1,
            task_dependencies=[],
        )
        high_task.id = 2

        low_task = Task(
            project_id=2,
            title="Low task",
            description=None,
            node_type="task",
            status="todo",
            priority="low",
            display_order=2,
            task_dependencies=[],
        )
        low_task.id = 3

        high_task_run = TaskRun(
            workflow_run_id=20,
            task_id=2,
            assigned_agent_id=11,
            assigned_agent_name="Agent 1",
            title_snapshot="High task",
            node_type="task",
            status="ready",
            executor_type="system",
            task_dependencies_snapshot=[],
            attempt_count=0,
        )
        high_task_run.id = 40
        high_task_run.task = high_task
        high_task_run.created_at = datetime(2026, 3, 31, 9, 0, 0)
        high_task_run.updated_at = datetime(2026, 3, 31, 9, 0, 0)

        low_task_run = TaskRun(
            workflow_run_id=20,
            task_id=3,
            assigned_agent_id=12,
            assigned_agent_name="Agent 2",
            title_snapshot="Low task",
            node_type="task",
            status="ready",
            executor_type="system",
            task_dependencies_snapshot=[],
            attempt_count=0,
        )
        low_task_run.id = 41
        low_task_run.task = low_task
        low_task_run.created_at = datetime(2026, 3, 31, 9, 1, 0)
        low_task_run.updated_at = datetime(2026, 3, 31, 9, 1, 0)
        workflow_run_before.task_runs = [high_task_run, low_task_run]

        workflow_run_after = WorkflowRun(project_id=2, status="running", trigger_type="manual")
        workflow_run_after.id = 20
        workflow_run_after.task_runs = [low_task_run]

        mock_load_workflow_run.side_effect = [workflow_run_before, workflow_run_after]
        mock_sync_state.side_effect = [workflow_run_before, workflow_run_after]

        result = workflow_run_service.execute_workflow_run(db, 1, 2, 20)

        self.assertIs(result, workflow_run_after)
        mock_execute_task_run.assert_called_once_with(db, 1, 2, 20, 40)


    def test_get_workflow_run_for_project_or_404_rejects_wrong_project(self) -> None:
        db = MagicMock()
        workflow_run = WorkflowRun(
            project_id=3,
            status="running",
            trigger_type="manual",
        )
        workflow_run.id = 9
        db.scalar.return_value = workflow_run

        with self.assertRaises(HTTPException) as context:
            workflow_run_service.get_workflow_run_for_project_or_404(db, 2, 9)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Workflow run does not belong to the specified project",
        )

    @patch("app.services.workflow_run_service.get_project_for_workspace_or_404")
    @patch("app.services.workflow_run_service.get_workflow_run_for_project_or_404")
    def test_delete_workflow_run_removes_run(
        self,
        mock_get_workflow_run,
        mock_get_project,
    ) -> None:
        db = MagicMock()
        workflow_run = WorkflowRun(project_id=2, status="running", trigger_type="manual")
        workflow_run.id = 33
        mock_get_workflow_run.return_value = workflow_run

        workflow_run_service.delete_workflow_run(db, 1, 2, 33)

        mock_get_project.assert_called_once_with(db, 1, 2)
        mock_get_workflow_run.assert_called_once_with(db, 2, 33)
        db.delete.assert_called_once_with(workflow_run)
        db.commit.assert_called_once()
