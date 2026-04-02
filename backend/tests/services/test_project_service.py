import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.project import Project
from app.models.task import Task
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project_service


class ProjectServiceTests(unittest.TestCase):
    @patch("app.services.project_service.get_workspace_or_404")
    def test_create_project_under_workspace_persists_project(self, mock_get_workspace) -> None:
        db = MagicMock()
        payload = ProjectCreate(
            name="Frontend",
            description="UI work",
            status="active",
        )

        def refresh_project(instance: Project) -> None:
            instance.id = 10
            if isinstance(instance, Task):
                instance.id = 100

        db.refresh.side_effect = refresh_project

        project = project_service.create_project_under_workspace(db, 1, payload)

        mock_get_workspace.assert_called_once_with(db, 1)
        self.assertEqual(project.workspace_id, 1)
        self.assertEqual(project.name, "Frontend")
        self.assertEqual(project.status, "active")
        self.assertEqual(project.id, 10)
        self.assertEqual(db.add.call_count, 3)
        self.assertEqual(db.commit.call_count, 3)
        db.refresh.assert_called_once_with(project)

        created_start_task = db.add.call_args_list[1].args[0]
        self.assertEqual(created_start_task.project_id, 10)
        self.assertEqual(created_start_task.node_type, "start")
        self.assertEqual(created_start_task.title, "Start")
        self.assertEqual(created_start_task.status, "done")
        self.assertEqual(created_start_task.canvas_x, 40)
        self.assertEqual(created_start_task.canvas_y, 120)

        created_end_task = db.add.call_args_list[2].args[0]
        self.assertEqual(created_end_task.project_id, 10)
        self.assertEqual(created_end_task.node_type, "end")
        self.assertEqual(created_end_task.title, "End")
        self.assertEqual(created_end_task.status, "todo")
        self.assertEqual(created_end_task.canvas_x, 1160)
        self.assertEqual(created_end_task.canvas_y, 120)

    def test_update_project_applies_changes(self) -> None:
        db = MagicMock()
        project = Project(
            workspace_id=1,
            name="Old project",
            description="Before",
            status="active",
        )
        project.id = 2
        db.get.return_value = project

        updated = project_service.update_project(
            db,
            1,
            2,
            ProjectUpdate(name="New project", status="done"),
        )

        self.assertIs(updated, project)
        self.assertEqual(updated.name, "New project")
        self.assertEqual(updated.status, "done")
        self.assertEqual(updated.description, "Before")
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(project)

    def test_get_project_for_workspace_or_404_raises_for_wrong_parent(self) -> None:
        db = MagicMock()
        project = Project(
            workspace_id=2,
            name="Misplaced",
            description=None,
            status="active",
        )
        project.id = 3
        db.get.return_value = project

        with self.assertRaises(HTTPException) as context:
            project_service.get_project_for_workspace_or_404(db, 1, 3)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Project does not belong to the specified workspace",
        )
