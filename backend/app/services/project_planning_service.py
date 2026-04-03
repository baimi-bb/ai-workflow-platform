from collections import deque
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.models.task import Task
from app.schemas.project_planning import ProjectPlanCreate
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import agent_execution_service, task_service
from app.services.project_service import get_project_for_workspace_or_404


START_X = 40
START_Y = 120
NODE_WIDTH = 340
NODE_HEIGHT = 300
HORIZONTAL_GAP = 260
VERTICAL_GAP = 90
LAYOUT_BASE_X = START_X + NODE_WIDTH + 120
LAYOUT_BASE_Y = 120
ROW_STEP = NODE_HEIGHT + VERTICAL_GAP
ROW_LANE_MULTIPLIER = 1
WORKSPACE_FILE_CONTEXT_LIMIT = 40


def _load_planner_agent_or_400(db: Session, workspace_id: int, planner_agent_id: int) -> Agent:
    agent = db.get(Agent, planner_agent_id)
    if agent is None:
        raise HTTPException(status_code=400, detail="Planner agent not found")
    if agent.workspace_id != workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Planner agent must belong to the same workspace",
        )
    if not agent.is_enabled:
        raise HTTPException(status_code=400, detail="Planner agent must be enabled")

    provider_model = agent.provider_model
    if provider_model is None or not provider_model.is_enabled:
        raise HTTPException(status_code=400, detail="Planner model config must be enabled")

    provider = provider_model.provider
    if provider is None or not provider.is_enabled:
        raise HTTPException(status_code=400, detail="Planner provider must be enabled")

    return agent


def _normalize_task_title(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="Planner task title must be a string")
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Planner task title cannot be empty")
    if len(normalized) > 140:
        raise HTTPException(
            status_code=400,
            detail=f"Planner task title is too long: {normalized[:40]}...",
        )
    return normalized


def _normalize_task_description(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400,
            detail="Planner task description must be a string when provided",
        )
    normalized = value.strip()
    return normalized or None


def _normalize_optional_text(value: object, *, field_name: str, max_length: int = 400) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"Planner {field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Planner {field_name} is too long: {normalized[:40]}...",
        )
    return normalized


def _normalize_task_priority(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() in {"low", "medium", "high"}:
        return value.strip().lower()
    return "medium"


def _resolve_assignment(raw_task: dict, enabled_agents: list[Agent]) -> int | None:
    raw_agent_id = raw_task.get("assigned_agent_id")
    if isinstance(raw_agent_id, int) and raw_agent_id > 0:
        agent = next((item for item in enabled_agents if item.id == raw_agent_id), None)
        if agent is None:
            raise HTTPException(
                status_code=400,
                detail=f"Planner assigned unknown agent id: {raw_agent_id}",
            )
        return agent.id

    raw_agent_name = raw_task.get("assigned_agent_name")
    if isinstance(raw_agent_name, str) and raw_agent_name.strip():
        normalized_name = raw_agent_name.strip().casefold()
        agent = next(
            (item for item in enabled_agents if item.name.strip().casefold() == normalized_name),
            None,
        )
        if agent is None:
            raise HTTPException(
                status_code=400,
                detail=f"Planner assigned unknown agent name: {raw_agent_name.strip()}",
            )
        return agent.id

    return None


def _normalize_depends_on_titles(raw_task: dict, known_titles: set[str]) -> list[str]:
    raw_dependencies = raw_task.get("depends_on_titles")
    if raw_dependencies is None:
        return []
    if not isinstance(raw_dependencies, list):
        raise HTTPException(
            status_code=400,
            detail="Planner depends_on_titles must be an array",
        )

    normalized_dependencies: list[str] = []
    seen: set[str] = set()
    for item in raw_dependencies:
        dependency_title = _normalize_task_title(item)
        if dependency_title not in known_titles:
            raise HTTPException(
                status_code=400,
                detail=f"Planner referenced unknown dependency title: {dependency_title}",
            )
        if dependency_title in seen:
            continue
        seen.add(dependency_title)
        normalized_dependencies.append(dependency_title)
    return normalized_dependencies


def _normalize_workspace_paths(raw_task: dict) -> list[str]:
    raw_paths = raw_task.get("required_workspace_paths")
    return _normalize_path_list(raw_paths, field_name="required_workspace_paths")


def _normalize_output_paths(raw_task: dict) -> list[str]:
    raw_paths = raw_task.get("suggested_output_paths")
    return _normalize_path_list(raw_paths, field_name="suggested_output_paths")


def _normalize_path_list(raw_paths: object, *, field_name: str) -> list[str]:
    if raw_paths is None:
        return []
    if not isinstance(raw_paths, list):
        raise HTTPException(
            status_code=400,
            detail=f"Planner {field_name} must be an array",
        )

    normalized_paths: list[str] = []
    seen: set[str] = set()
    for item in raw_paths:
        if not isinstance(item, str):
            raise HTTPException(
                status_code=400,
                detail=f"Planner {field_name} entries must be strings",
            )
        normalized = item.strip().replace("\\", "/").strip("/")
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_paths.append(normalized)
    return normalized_paths


def _merge_title_dependencies(*dependency_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in dependency_groups:
        for title in group:
            if title in seen:
                continue
            seen.add(title)
            merged.append(title)
    return merged


def _build_standard_task_description(planned_task: dict[str, object]) -> str:
    lines: list[str] = []
    summary = planned_task.get("description")
    objective = planned_task.get("objective")
    deliverable = planned_task.get("deliverable")
    workspace_paths = planned_task.get("required_workspace_paths") or []
    output_paths = planned_task.get("suggested_output_paths") or []
    input_task_titles = planned_task.get("input_from_titles") or []

    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())
        lines.append("")

    lines.append("Execution Standard:")
    if isinstance(objective, str) and objective.strip():
        lines.append(f"- Objective: {objective.strip()}")
    if isinstance(deliverable, str) and deliverable.strip():
        lines.append(f"- Deliverable: {deliverable.strip()}")
    if isinstance(workspace_paths, list) and workspace_paths:
        lines.append(f"- Required workspace files: {', '.join(workspace_paths)}")
    if isinstance(output_paths, list) and output_paths:
        lines.append(f"- Suggested output files: {', '.join(output_paths)}")
    if isinstance(input_task_titles, list) and input_task_titles:
        lines.append(f"- Required upstream task outputs: {', '.join(input_task_titles)}")
    lines.append("- Complete the work directly. Do not stop at a plan or explanation.")
    lines.append("- If the task needs files or datasets, write the actual output files.")
    return "\n".join(lines).strip()


def _collect_workspace_file_context(root_path: str | None) -> list[str]:
    if not isinstance(root_path, str) or not root_path.strip():
        return []

    try:
        normalized_root = Path(root_path).expanduser().resolve()
    except OSError:
        return []

    if not normalized_root.exists() or not normalized_root.is_dir():
        return []

    collected: list[str] = []
    try:
        for entry in sorted(normalized_root.rglob("*")):
            if len(collected) >= WORKSPACE_FILE_CONTEXT_LIMIT:
                break
            if not entry.is_file():
                continue
            try:
                relative_path = entry.relative_to(normalized_root).as_posix()
            except ValueError:
                continue
            if any(part.startswith(".") for part in entry.parts):
                continue
            collected.append(relative_path)
    except OSError:
        return collected

    return collected


def _assert_acyclic(tasks: list[dict[str, object]]) -> None:
    indegree: dict[str, int] = {task["title"]: 0 for task in tasks}
    graph: dict[str, list[str]] = {task["title"]: [] for task in tasks}

    for task in tasks:
        title = task["title"]
        for dependency_title in task["depends_on_titles"]:
            graph[dependency_title].append(title)
            indegree[title] += 1

    queue = deque(title for title, count in indegree.items() if count == 0)
    visited_count = 0
    while queue:
        title = queue.popleft()
        visited_count += 1
        for next_title in graph[title]:
            indegree[next_title] -= 1
            if indegree[next_title] == 0:
                queue.append(next_title)

    if visited_count != len(tasks):
        raise HTTPException(
            status_code=400,
            detail="Planner task dependencies cannot contain cycles",
        )


def _parse_plan_payload(plan_payload: dict, enabled_agents: list[Agent]) -> tuple[str, list[dict[str, object]]]:
    summary = plan_payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise HTTPException(status_code=400, detail="Planner summary is required")

    raw_tasks = plan_payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise HTTPException(status_code=400, detail="Planner must return at least one task")

    normalized_tasks: list[dict[str, object]] = []
    seen_titles: set[str] = set()
    for raw_task in raw_tasks:
        if not isinstance(raw_task, dict):
            raise HTTPException(status_code=400, detail="Planner task entries must be objects")
        title = _normalize_task_title(raw_task.get("title"))
        if title in seen_titles:
            raise HTTPException(
                status_code=400,
                detail=f"Planner task titles must be unique: {title}",
            )
        seen_titles.add(title)
        normalized_tasks.append(
            {
                "title": title,
                "description": _normalize_task_description(raw_task.get("description")),
                "objective": _normalize_optional_text(raw_task.get("objective"), field_name="objective"),
                "deliverable": _normalize_optional_text(raw_task.get("deliverable"), field_name="deliverable"),
                "priority": _normalize_task_priority(raw_task.get("priority")),
                "assigned_agent_id": _resolve_assignment(raw_task, enabled_agents),
                "required_workspace_paths": _normalize_workspace_paths(raw_task),
                "suggested_output_paths": _normalize_output_paths(raw_task),
            }
        )

    for normalized_task, raw_task in zip(normalized_tasks, raw_tasks, strict=False):
        blocking_titles = _normalize_depends_on_titles(raw_task, seen_titles)
        input_from_titles = _normalize_depends_on_titles(
            {"depends_on_titles": raw_task.get("input_from_titles")},
            seen_titles,
        )
        normalized_task["input_from_titles"] = input_from_titles
        normalized_task["depends_on_titles"] = _merge_title_dependencies(
            blocking_titles,
            input_from_titles,
        )
        normalized_task["description"] = _build_standard_task_description(normalized_task)
        if normalized_task["title"] in normalized_task["depends_on_titles"]:
            raise HTTPException(
                status_code=400,
                detail=f"Planner task cannot depend on itself: {normalized_task['title']}",
            )

    _assert_acyclic(normalized_tasks)
    return summary.strip(), normalized_tasks


def _build_project_plan_prompt(project, payload: ProjectPlanCreate, enabled_agents: list[Agent]) -> str:
    existing_task_lines = [
        f"- {task.title} | agent={task.agent_name or 'unassigned'} | status={task.status} | deps={task.task_dependencies}"
        for task in sorted(project.tasks, key=lambda item: (item.display_order, item.id))
        if task.node_type == "task"
    ]
    agent_lines = [
        (
            f"- id={agent.id}; name={agent.name}; model={agent.provider_model_label or 'unknown'}; "
            f"description={agent.description or 'none'}"
        )
        for agent in enabled_agents
    ]
    workspace_file_lines = _collect_workspace_file_context(project.workspace.root_path)
    return "\n".join(
        [
            "You are planning tasks for an AI workflow project inside a real workspace environment.",
            "Generate a practical execution plan as strict JSON only.",
            "Do not include markdown fences.",
            "Do not modify existing tasks; append a new plan that can coexist with them.",
            "Return JSON with this shape exactly:",
            (
                '{"summary":"short summary","tasks":[{"title":"Task title","description":"short task summary",'
                '"objective":"clear execution goal","deliverable":"specific expected output",'
                '"priority":"high|medium|low","assigned_agent_id":123,'
                '"depends_on_titles":["blocking task"],'
                '"input_from_titles":["task whose outputs or information are needed"],'
                '"required_workspace_paths":["relative/path/to/file.ext"],'
                '"suggested_output_paths":["relative/path/to/output.ext"]}]}'
            ),
            "Use only agent ids that appear below. Use null or omit assigned_agent_id if no suitable agent exists.",
            "Keep task titles unique within this generated plan.",
            "Create only normal work tasks. Do not create start or end nodes.",
            "Design tasks that fit the actual workspace and available files, not a generic template.",
            "Prefer concrete, execution-ready tasks over vague planning tasks.",
            "Use multiple dependencies whenever a task truly needs multiple upstream outputs.",
            "If a task needs information or files from another task, include that task in input_from_titles.",
            "If a task needs an existing workspace file, include it in required_workspace_paths.",
            "If a task should create files, include suggested_output_paths with concrete workspace-relative target paths.",
            "Make dependencies accurate. Do not force a single-chain workflow when parallel work is possible.",
            "",
            f"Project name: {project.name}",
            f"Project description: {project.description or 'None'}",
            f"Workspace root path: {project.workspace.root_path or 'not configured'}",
            "",
            "Available enabled agents:",
            "\n".join(agent_lines) if agent_lines else "- none",
            "",
            "Workspace files you can plan around:",
            "\n".join(f"- {path}" for path in workspace_file_lines) if workspace_file_lines else "- none",
            "",
            "Existing project tasks:",
            "\n".join(existing_task_lines) if existing_task_lines else "- none",
        ]
    )


def _call_planner(agent: Agent, prompt: str) -> dict:
    try:
        raw_text, _raw_payload = agent_execution_service._call_provider(agent, prompt)
    except agent_execution_service.urllib_error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=agent_execution_service._extract_http_error_message(exc),
        ) from exc
    except agent_execution_service.urllib_error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Planner request failed: {exc.reason}",
        ) from exc

    parsed = agent_execution_service._extract_json_object_from_text(raw_text)
    if parsed is None:
        compact_text = " ".join(raw_text.split())
        if len(compact_text) > 200:
            compact_text = f"{compact_text[:197]}..."
        raise HTTPException(
            status_code=502,
            detail=f"Planner returned invalid JSON: {compact_text or 'empty response'}",
        )
    return parsed


def _find_boundary_tasks(project_tasks: list[Task]) -> tuple[Task | None, Task | None]:
    start_task = next((task for task in project_tasks if task.node_type == "start"), None)
    end_task = next((task for task in project_tasks if task.node_type == "end"), None)
    return start_task, end_task


def _build_task_successor_map(project_tasks: list[Task]) -> dict[int, set[int]]:
    task_nodes = [task for task in project_tasks if task.node_type == "task"]
    task_node_ids = {task.id for task in task_nodes}
    successor_map: dict[int, set[int]] = {task.id: set() for task in task_nodes}

    for task in task_nodes:
        for dependency_id in task.task_dependencies or []:
            if dependency_id in task_node_ids:
                successor_map.setdefault(dependency_id, set()).add(task.id)

    return successor_map


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _snap_to_lane(value: float) -> int:
    return max(0, int((value / ROW_LANE_MULTIPLIER) + 0.5) * ROW_LANE_MULTIPLIER)


def _sync_project_workflow_defaults(db: Session, workspace_id: int, project_id: int) -> None:
    project_tasks = task_service._list_project_tasks(db, project_id)
    start_task, end_task = _find_boundary_tasks(project_tasks)
    task_nodes = [task for task in project_tasks if task.node_type == "task"]

    if start_task is not None:
        for task in task_nodes:
            if task.task_dependencies:
                continue
            desired_dependencies = [start_task.id]
            if task.task_dependencies == desired_dependencies:
                continue
            task_service.update_task(
                db,
                workspace_id,
                project_id,
                task.id,
                TaskUpdate(task_dependencies=desired_dependencies),
            )

        project_tasks = task_service._list_project_tasks(db, project_id)
        _start_task, end_task = _find_boundary_tasks(project_tasks)
        task_nodes = [task for task in project_tasks if task.node_type == "task"]

    if end_task is None:
        return

    successor_map = _build_task_successor_map(project_tasks)
    terminal_task_ids = sorted(
        task.id for task in task_nodes if not successor_map.get(task.id)
    )
    desired_end_dependencies = terminal_task_ids or ([start_task.id] if start_task is not None else [])

    if end_task.task_dependencies == desired_end_dependencies:
        return

    task_service.update_task(
        db,
        workspace_id,
        project_id,
        end_task.id,
        TaskUpdate(task_dependencies=desired_end_dependencies),
    )


def _build_depth_map(project_tasks: list[Task]) -> dict[int, int]:
    task_map = {task.id: task for task in project_tasks}
    depth_cache: dict[int, int] = {}

    def get_depth(task_id: int) -> int:
        if task_id in depth_cache:
            return depth_cache[task_id]

        task = task_map.get(task_id)
        if task is None:
            depth_cache[task_id] = 0
            return 0
        if task.node_type == "start":
            depth_cache[task_id] = 0
            return 0

        dependency_depths = [
            get_depth(dependency_id)
            for dependency_id in (task.task_dependencies or [])
            if dependency_id in task_map
        ]
        depth = (max(dependency_depths) + 1) if dependency_depths else 1
        if task.node_type == "end":
            depth = max(depth, 2)
        depth_cache[task_id] = depth
        return depth

    for task in project_tasks:
        get_depth(task.id)

    return depth_cache


def _build_layout_row_map(
    project_tasks: list[Task],
    generated_task_ids: set[int],
    depth_map: dict[int, int],
) -> dict[int, int]:
    task_map = {task.id: task for task in project_tasks}
    row_map: dict[int, int] = {}
    tasks_by_depth: dict[int, list[Task]] = {}

    for task_id in generated_task_ids:
        task = task_map.get(task_id)
        if task is None or task.node_type != "task":
            continue
        tasks_by_depth.setdefault(depth_map.get(task.id, 1), []).append(task)

    for depth in sorted(tasks_by_depth):
        tasks_in_depth = tasks_by_depth[depth]
        sortable_tasks: list[tuple[float, int, Task]] = []
        for task in tasks_in_depth:
            dependency_rows = [
                row_map[dependency_id]
                for dependency_id in (task.task_dependencies or [])
                if dependency_id in row_map
            ]
            anchor = (
                _average([float(row) for row in dependency_rows])
                if dependency_rows
                else 0.0
            )
            sortable_tasks.append((anchor, task.display_order, task))

        sortable_tasks.sort(key=lambda item: (item[0], item[1], item[2].id))

        if len(sortable_tasks) == 1:
            _anchor, _display_order, task = sortable_tasks[0]
            dependency_rows = [
                row_map[dependency_id]
                for dependency_id in (task.task_dependencies or [])
                if dependency_id in row_map
            ]
            if len(dependency_rows) == 1:
                parent_row = dependency_rows[0]
                zigzag_offset = (
                    ROW_LANE_MULTIPLIER if depth % 2 == 0 else -ROW_LANE_MULTIPLIER
                )
                row_map[task.id] = max(0, parent_row + zigzag_offset)
            elif dependency_rows:
                row_map[task.id] = _snap_to_lane(
                    _average([float(row) for row in dependency_rows])
                )
            else:
                row_map[task.id] = 0
            continue

        anchor_mean = _average([item[0] for item in sortable_tasks])
        start_row = max(0, round(anchor_mean - (len(sortable_tasks) - 1) / 2))

        for index, (_anchor, _display_order, task) in enumerate(sortable_tasks):
            row_map[task.id] = (start_row + index) * ROW_LANE_MULTIPLIER

    return row_map


def _apply_generated_task_layout(
    db: Session,
    workspace_id: int,
    project_id: int,
    generated_task_ids: list[int],
) -> None:
    if not generated_task_ids:
        return

    project_tasks = task_service._list_project_tasks(db, project_id)
    task_map = {task.id: task for task in project_tasks}
    generated_tasks = [
        task_map[task_id]
        for task_id in generated_task_ids
        if task_id in task_map and task_map[task_id].node_type == "task"
    ]
    if not generated_tasks:
        return

    depth_map = _build_depth_map(project_tasks)
    row_map = _build_layout_row_map(project_tasks, set(generated_task_ids), depth_map)

    for task in generated_tasks:
        depth = depth_map.get(task.id, 1)
        row_index = row_map.get(task.id, 0)
        canvas_x = LAYOUT_BASE_X + max(depth - 1, 0) * (NODE_WIDTH + HORIZONTAL_GAP)
        canvas_y = LAYOUT_BASE_Y + row_index * ROW_STEP
        task_service.update_task(
            db,
            workspace_id,
            project_id,
            task.id,
            TaskUpdate(canvas_x=canvas_x, canvas_y=canvas_y),
        )

    refreshed_tasks = task_service._list_project_tasks(db, project_id)
    start_task, end_task = _find_boundary_tasks(refreshed_tasks)
    task_rows = _build_layout_row_map(refreshed_tasks, set(generated_task_ids), _build_depth_map(refreshed_tasks))
    root_task_rows = [
        task_rows[task.id]
        for task in refreshed_tasks
        if task.node_type == "task"
        and task.id in task_rows
        and start_task is not None
        and start_task.id in (task.task_dependencies or [])
    ]
    next_start_y = (
        LAYOUT_BASE_Y + round(_average([float(row) for row in root_task_rows])) * ROW_STEP
        if root_task_rows
        else START_Y
    )
    if start_task is not None and (
        start_task.canvas_x != START_X or start_task.canvas_y != next_start_y
    ):
        task_service.update_task(
            db,
            workspace_id,
            project_id,
            start_task.id,
            TaskUpdate(canvas_x=START_X, canvas_y=next_start_y),
        )

    if end_task is None:
        return

    refreshed_tasks = task_service._list_project_tasks(db, project_id)
    depth_map = _build_depth_map(refreshed_tasks)
    max_depth = max(
        (
            depth_map.get(task.id, 1)
            for task in refreshed_tasks
            if task.node_type in {"task", "end"}
        ),
        default=1,
    )
    end_x = LAYOUT_BASE_X + max(max_depth - 1, 0) * (NODE_WIDTH + HORIZONTAL_GAP)
    end_dependency_rows = [
        task_rows[dependency_id]
        for dependency_id in (end_task.task_dependencies or [])
        if dependency_id in task_rows
    ]
    end_y = (
        LAYOUT_BASE_Y + round(_average([float(row) for row in end_dependency_rows])) * ROW_STEP
        if end_dependency_rows
        else next_start_y
    )
    if end_task.canvas_x == end_x and end_task.canvas_y == end_y:
        return
    task_service.update_task(
        db,
        workspace_id,
        project_id,
        end_task.id,
        TaskUpdate(canvas_x=end_x, canvas_y=end_y),
    )


def plan_project_tasks(
    db: Session,
    workspace_id: int,
    project_id: int,
    payload: ProjectPlanCreate,
) -> dict[str, object]:
    project = get_project_for_workspace_or_404(db, workspace_id, project_id)
    planner_agent = _load_planner_agent_or_400(db, workspace_id, payload.planner_agent_id)
    enabled_agents = [
        agent
        for agent in project.workspace.agents
        if agent.is_enabled
        and isinstance(agent.provider_model, ProviderModel)
        and agent.provider_model.is_enabled
        and isinstance(agent.provider_model.provider, Provider)
        and agent.provider_model.provider.is_enabled
    ]
    if not enabled_agents:
        raise HTTPException(status_code=400, detail="No enabled agents are available")

    prompt = _build_project_plan_prompt(project, payload, enabled_agents)
    plan_payload = _call_planner(planner_agent, prompt)
    summary, planned_tasks = _parse_plan_payload(plan_payload, enabled_agents)

    existing_project_tasks = task_service._list_project_tasks(db, project_id)
    next_display_order = max((task.display_order for task in existing_project_tasks), default=0) + 1
    created_tasks: list[Task] = []

    for index, planned_task in enumerate(planned_tasks):
        created_task = task_service.create_task_under_project(
            db,
            workspace_id,
            project_id,
            TaskCreate(
                agent_id=planned_task["assigned_agent_id"],
                title=planned_task["title"],
                description=planned_task["description"],
                status="todo",
                priority=planned_task["priority"],
                display_order=next_display_order + index,
                task_dependencies=[],
            ),
        )
        created_tasks.append(created_task)

    created_task_by_title = {task.title: task for task in created_tasks}
    for planned_task in planned_tasks:
        task = created_task_by_title[planned_task["title"]]
        dependency_ids = [
            created_task_by_title[dependency_title].id
            for dependency_title in planned_task["depends_on_titles"]
        ]
        updated_task = task_service.update_task(
            db,
            workspace_id,
            project_id,
            task.id,
            TaskUpdate(task_dependencies=dependency_ids),
        )
        created_task_by_title[planned_task["title"]] = updated_task

    _sync_project_workflow_defaults(db, workspace_id, project_id)
    _apply_generated_task_layout(
        db,
        workspace_id,
        project_id,
        [task.id for task in created_tasks],
    )

    refreshed_project_tasks = task_service._list_project_tasks(db, project_id)
    refreshed_task_map = {task.id: task for task in refreshed_project_tasks}

    final_created_tasks = [
        refreshed_task_map.get(created_task_by_title[planned_task["title"]].id)
        or created_task_by_title[planned_task["title"]]
        for planned_task in planned_tasks
    ]
    return {
        "summary": summary,
        "created_task_count": len(final_created_tasks),
        "created_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "assigned_agent_id": task.agent_id,
                "assigned_agent_name": task.agent_name,
                "priority": task.priority,
                "task_dependencies": task.task_dependencies,
            }
            for task in final_created_tasks
        ],
    }
