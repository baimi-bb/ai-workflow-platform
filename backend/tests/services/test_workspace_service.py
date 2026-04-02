import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services import workspace_service


class WorkspaceServiceTests(unittest.TestCase):
    @patch("app.services.workspace_service.os.access", return_value=True)
    @patch("app.services.workspace_service.Path.resolve")
    def test_create_workspace_persists_and_refreshes_workspace(
        self,
        mock_resolve,
        mock_access,
    ) -> None:
        db = MagicMock()
        resolved_path = MagicMock()
        resolved_path.exists.return_value = True
        resolved_path.is_dir.return_value = True
        resolved_path.__str__.return_value = "D:\\Workspaces\\Platform"
        mock_resolve.return_value = resolved_path

        payload = WorkspaceCreate(
            name="Platform",
            description="Main workspace",
            root_path="D:\\Workspaces\\Platform",
        )

        def refresh_workspace(instance: Workspace) -> None:
            instance.id = 1

        db.refresh.side_effect = refresh_workspace

        workspace = workspace_service.create_workspace(db, payload)

        self.assertEqual(workspace.name, "Platform")
        self.assertEqual(workspace.description, "Main workspace")
        self.assertEqual(workspace.root_path, "D:\\Workspaces\\Platform")
        self.assertEqual(workspace.id, 1)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(workspace)
        self.assertEqual(mock_access.call_count, 2)

    @patch("app.services.workspace_service.os.access", return_value=True)
    @patch("app.services.workspace_service.Path.resolve")
    def test_update_workspace_applies_partial_updates(
        self,
        mock_resolve,
        mock_access,
    ) -> None:
        db = MagicMock()
        resolved_path = MagicMock()
        resolved_path.exists.return_value = True
        resolved_path.is_dir.return_value = True
        resolved_path.__str__.return_value = "D:\\Workspaces\\Updated"
        mock_resolve.return_value = resolved_path

        workspace = Workspace(
            name="Old",
            description="Before",
            root_path="D:\\Workspaces\\Old",
        )
        workspace.id = 1
        db.get.return_value = workspace

        updated = workspace_service.update_workspace(
            db,
            1,
            WorkspaceUpdate(
                description="After",
                root_path="D:\\Workspaces\\Updated",
            ),
        )

        self.assertIs(updated, workspace)
        self.assertEqual(updated.name, "Old")
        self.assertEqual(updated.description, "After")
        self.assertEqual(updated.root_path, "D:\\Workspaces\\Updated")
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(workspace)
        self.assertEqual(mock_access.call_count, 2)

    def test_get_workspace_or_404_raises_when_missing(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with self.assertRaises(HTTPException) as context:
            workspace_service.get_workspace_or_404(db, 99)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Workspace not found")

    @patch("app.services.workspace_service.Path.resolve")
    def test_create_workspace_rejects_missing_root_path(self, mock_resolve) -> None:
        db = MagicMock()
        resolved_path = MagicMock()
        resolved_path.exists.return_value = False
        mock_resolve.return_value = resolved_path

        with self.assertRaises(HTTPException) as context:
            workspace_service.create_workspace(
                db,
                WorkspaceCreate(
                    name="Platform",
                    description="Main workspace",
                    root_path="D:\\Missing",
                ),
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Workspace root path does not exist",
        )
        db.add.assert_not_called()

    @patch("app.services.workspace_service._normalize_workspace_root_path")
    @patch("app.services.workspace_service.Path")
    def test_list_workspace_files_returns_sorted_entries(
        self,
        mock_path,
        mock_normalize_root_path,
    ) -> None:
        db = MagicMock()
        workspace = Workspace(
            name="Platform",
            description="Main workspace",
            root_path="D:\\Workspaces\\Platform",
        )
        workspace.id = 7
        db.get.return_value = workspace
        mock_normalize_root_path.return_value = "D:\\Workspaces\\Platform"

        root_path_obj = MagicMock()
        root_path_obj.resolve.return_value = root_path_obj
        root_path_obj.__str__.return_value = "D:\\Workspaces\\Platform"
        root_path_obj.__eq__.side_effect = lambda other: other is root_path_obj
        root_path_obj.exists.return_value = True
        root_path_obj.is_dir.return_value = True
        root_path_obj.relative_to.return_value.as_posix.return_value = ""
        mock_path.return_value = root_path_obj

        dir_entry = MagicMock()
        dir_entry.name = "docs"
        dir_entry.is_dir.return_value = True
        dir_entry.relative_to.return_value.as_posix.return_value = "docs"
        dir_entry.stat.return_value.st_mtime = 1_700_000_000

        file_entry = MagicMock()
        file_entry.name = "readme.md"
        file_entry.is_dir.return_value = False
        file_entry.relative_to.return_value.as_posix.return_value = "readme.md"
        file_entry.stat.return_value.st_mtime = 1_700_000_100
        file_entry.stat.return_value.st_size = 11

        root_path_obj.iterdir.return_value = [file_entry, dir_entry]

        result = workspace_service.list_workspace_files(db, 7)

        self.assertEqual(result.workspace_id, 7)
        self.assertEqual(result.root_path, "D:\\Workspaces\\Platform")
        self.assertEqual(result.current_path, "")
        self.assertEqual(len(result.entries), 2)
        self.assertEqual(result.entries[0].name, "docs")
        self.assertEqual(result.entries[0].entry_type, "directory")
        self.assertIsNone(result.entries[0].size)
        self.assertEqual(result.entries[1].name, "readme.md")
        self.assertEqual(result.entries[1].entry_type, "file")
        self.assertEqual(result.entries[1].size, 11)
        self.assertIsInstance(result.entries[1].modified_at, datetime)

    @patch("app.services.workspace_service._normalize_workspace_root_path")
    @patch("app.services.workspace_service.Path")
    def test_list_workspace_files_supports_subdirectory(
        self,
        mock_path,
        mock_normalize_root_path,
    ) -> None:
        db = MagicMock()
        workspace = Workspace(
            name="Platform",
            description="Main workspace",
            root_path="D:\\Workspaces\\Platform",
        )
        workspace.id = 8
        db.get.return_value = workspace
        mock_normalize_root_path.return_value = "D:\\Workspaces\\Platform"

        root_path_obj = MagicMock()
        root_path_obj.resolve.return_value = root_path_obj
        root_path_obj.__str__.return_value = "D:\\Workspaces\\Platform"
        root_path_obj.exists.return_value = True
        root_path_obj.is_dir.return_value = True

        target_path_obj = MagicMock()
        target_path_obj.resolve.return_value = target_path_obj
        target_path_obj.__str__.return_value = "D:\\Workspaces\\Platform\\docs"
        target_path_obj.exists.return_value = True
        target_path_obj.is_dir.return_value = True
        target_path_obj.relative_to.return_value.as_posix.return_value = "docs"

        guide_entry = MagicMock()
        guide_entry.name = "guide.md"
        guide_entry.is_dir.return_value = False
        guide_entry.relative_to.return_value.as_posix.return_value = "docs/guide.md"
        guide_entry.stat.return_value.st_mtime = 1_700_000_100
        guide_entry.stat.return_value.st_size = 5
        target_path_obj.iterdir.return_value = [guide_entry]

        root_path_obj.__truediv__.return_value = target_path_obj
        mock_path.return_value = root_path_obj

        result = workspace_service.list_workspace_files(db, 8, "docs")

        self.assertEqual(result.current_path, "docs")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].name, "guide.md")

    @patch("app.services.workspace_service._normalize_workspace_root_path")
    @patch("app.services.workspace_service.Path")
    def test_list_workspace_files_rejects_path_outside_root(
        self,
        mock_path,
        mock_normalize_root_path,
    ) -> None:
        db = MagicMock()
        workspace = Workspace(
            name="Platform",
            description="Main workspace",
            root_path="D:\\Workspaces\\Platform",
        )
        workspace.id = 9
        db.get.return_value = workspace
        mock_normalize_root_path.return_value = "D:\\Workspaces\\Platform"

        root_path_obj = MagicMock()
        root_path_obj.resolve.return_value = root_path_obj

        target_path_obj = MagicMock()
        target_path_obj.resolve.return_value = target_path_obj
        target_path_obj.relative_to.side_effect = ValueError("outside root")

        root_path_obj.__truediv__.return_value = target_path_obj
        mock_path.return_value = root_path_obj

        with self.assertRaises(HTTPException) as context:
            workspace_service.list_workspace_files(db, 9, "../secret")

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Requested path must stay within the workspace root path",
        )
