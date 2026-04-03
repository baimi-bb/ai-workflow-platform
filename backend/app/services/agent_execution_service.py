import json
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Callable
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.agent import Agent
from app.models.project import Project
from app.models.provider import Provider
from app.models.provider_model import ProviderModel
from app.models.task import Task
from app.models.task_run import TaskRun
from app.models.workflow_run import WorkflowRun
from app.core.config import settings
from app.services.project_service import get_project_for_workspace_or_404


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_task_run_or_404(
    db: Session,
    workflow_run_id: int,
    task_run_id: int,
) -> TaskRun:
    statement = (
        select(TaskRun)
        .where(TaskRun.id == task_run_id)
        .options(
            selectinload(TaskRun.workflow_run)
            .selectinload(WorkflowRun.project)
            .selectinload(Project.workspace),
            selectinload(TaskRun.task).selectinload(Task.project),
            selectinload(TaskRun.assigned_agent)
            .selectinload(Agent.provider_model)
            .selectinload(ProviderModel.provider),
        )
    )
    task_run = db.scalar(statement)
    if task_run is None:
        raise HTTPException(status_code=404, detail="Task run not found")
    if task_run.workflow_run_id != workflow_run_id:
        raise HTTPException(
            status_code=400,
            detail="Task run does not belong to the specified workflow run",
        )
    return task_run


def _ensure_agent_available(db: Session, task_run: TaskRun) -> Agent:
    agent = task_run.assigned_agent
    if agent is None:
        raise HTTPException(status_code=400, detail="Task run has no assigned agent")
    if not agent.is_enabled:
        raise HTTPException(status_code=400, detail="Assigned agent must be enabled")

    provider_model = agent.provider_model
    if provider_model is None or not provider_model.is_enabled:
        raise HTTPException(status_code=400, detail="Assigned model config must be enabled")

    provider = provider_model.provider
    if provider is None or not provider.is_enabled:
        raise HTTPException(status_code=400, detail="Assigned provider must be enabled")

    busy_statement = (
        select(TaskRun.id)
        .where(
            TaskRun.assigned_agent_id == agent.id,
            TaskRun.status == "running",
            TaskRun.id != task_run.id,
        )
        .limit(1)
    )
    if db.scalar(busy_statement) is not None:
        raise HTTPException(status_code=409, detail="Assigned agent is busy")

    return agent


def _stringify_response_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
        return "\n".join(chunk for chunk in chunks if chunk).strip()
    return str(content)


def _extract_json_object_from_text(text: str) -> dict | None:
    payloads = _extract_json_objects_from_text(text)
    if not payloads:
        return None
    return payloads[-1]


def _extract_json_objects_from_text(text: str) -> list[dict]:
    stripped = text.strip()
    if not stripped:
        return []

    candidates = [stripped]
    if "```json" in stripped:
        start = stripped.find("```json") + len("```json")
        end = stripped.find("```", start)
        if end != -1:
            candidates.append(stripped[start:end].strip())
    elif "```" in stripped:
        start = stripped.find("```") + 3
        end = stripped.find("```", start)
        if end != -1:
            candidates.append(stripped[start:end].strip())

    decoder = json.JSONDecoder()
    payloads: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            if serialized not in seen:
                seen.add(serialized)
                payloads.append(payload)
            continue

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            if serialized in seen:
                continue
            seen.add(serialized)
            payloads.append(payload)

    return payloads


def _strip_html_to_text(html: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    normalized = unescape(without_tags)
    return re.sub(r"\s+", " ", normalized).strip()


def _native_tool_platform_supported(platform: str) -> bool:
    return platform in {"openai", "deepseek", "openrouter", "custom", "anthropic", "google"}


def _agent_prefers_native_tools(agent: Agent) -> bool:
    provider_model = agent.provider_model
    provider = provider_model.provider if provider_model is not None else None
    if provider_model is None or provider is None:
        return False
    return provider_model.supports_tools and _native_tool_platform_supported(provider.platform)


def _build_openai_tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current public information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query keywords."},
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of search results to return.",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch the text content of an HTTP or HTTPS URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The absolute URL to fetch."},
                        "max_chars": {
                            "type": "integer",
                            "description": "Maximum number of characters to return.",
                        },
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def _build_anthropic_tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "web_search",
            "description": "Search the web for current public information.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "fetch_url",
            "description": "Fetch the text content of an HTTP or HTTPS URL.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["url"],
            },
        },
    ]


def _build_google_tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "functionDeclarations": [
                {
                    "name": "web_search",
                    "description": "Search the web for current public information.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {"type": "STRING"},
                            "max_results": {"type": "INTEGER"},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "fetch_url",
                    "description": "Fetch the text content of an HTTP or HTTPS URL.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "url": {"type": "STRING"},
                            "max_chars": {"type": "INTEGER"},
                        },
                        "required": ["url"],
                    },
                },
            ]
        }
    ]


def _normalize_tool_arguments(arguments: object) -> dict[str, object]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid tool arguments JSON: {exc}") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Tool arguments must be a JSON object")


def _normalize_provider_tool_call(
    *,
    tool_name: str,
    arguments: object,
    call_id: str | None = None,
) -> dict[str, object]:
    normalized_name = tool_name.strip()
    if not normalized_name:
        raise ValueError("Tool name cannot be empty")

    normalized_arguments = _normalize_tool_arguments(arguments)
    normalized_call: dict[str, object] = {"tool": normalized_name}
    if call_id:
        normalized_call["_tool_call_id"] = call_id

    if normalized_name == "web_search":
        query = normalized_arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("web_search requires a query string")
        normalized_call["query"] = query.strip()
        max_results = normalized_arguments.get("max_results")
        if isinstance(max_results, int):
            normalized_call["max_results"] = max_results
        return normalized_call

    if normalized_name == "fetch_url":
        url = normalized_arguments.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("fetch_url requires a url string")
        normalized_call["url"] = url.strip()
        max_chars = normalized_arguments.get("max_chars")
        if isinstance(max_chars, int):
            normalized_call["max_chars"] = max_chars
        return normalized_call

    raise ValueError(f"Unsupported tool call: {normalized_name}")


def _stringify_tool_result_for_provider(result: dict[str, object]) -> str:
    return json.dumps(result, ensure_ascii=False)


def _extract_tool_calls_from_text(response_text: str) -> list[dict[str, object]]:
    payload = _extract_json_object_from_text(response_text)
    if payload is None:
        return []

    if isinstance(payload.get("tool"), str) and payload.get("tool"):
        return [payload]

    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []

    normalized_calls: list[dict[str, object]] = []
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            continue
        normalized_calls.append(item)
    return normalized_calls


def _validate_final_response_payload(response_text: str) -> dict | None:
    payload = _extract_json_object_from_text(response_text)
    if payload is None:
        return None

    if isinstance(payload.get("tool"), str) and payload.get("tool"):
        raise HTTPException(
            status_code=502,
            detail="Agent returned a tool request instead of a final summary/files payload",
        )

    if "tool_calls" in payload:
        raise HTTPException(
            status_code=502,
            detail="Agent returned tool_calls instead of a final summary/files payload",
        )

    files_payload = payload.get("files")
    if files_payload is not None and not isinstance(files_payload, list):
        raise HTTPException(
            status_code=502,
            detail="Agent final response files field must be an array when provided",
        )

    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise HTTPException(
            status_code=502,
            detail="Agent final response summary must be a string",
        )

    return payload


def _detect_incomplete_task_result(
    task_run: TaskRun,
    text: str,
    artifacts: list[dict[str, str]],
) -> str | None:
    normalized_text = text.strip().casefold()
    deferral_markers = [
        "需要先",
        "请提供",
        "当前未提供",
        "暂无法",
        "无法继续",
        "无法执行",
        "缺少",
        "cannot continue",
        "cannot proceed",
        "please provide",
        "need to first",
        "first need to",
        "not provided",
    ]
    for marker in deferral_markers:
        if marker.casefold() in normalized_text:
            return "Agent returned a deferral/incomplete response instead of completing the task"

    return None


def _resolve_workspace_file_path(root_path: str, relative_path: str) -> Path:
    normalized_root_path = Path(root_path).expanduser().resolve()
    requested_path = relative_path.strip().replace("\\", "/").strip("/")
    if not requested_path:
        raise HTTPException(status_code=400, detail="File path cannot be empty")

    target_path = (normalized_root_path / requested_path).resolve()
    try:
        target_path.relative_to(normalized_root_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Requested file path must stay within the workspace root path",
        ) from exc
    return target_path


def _append_activity_event(
    task_run: TaskRun,
    *,
    stage: str,
    message: str,
    details: dict[str, object] | None = None,
) -> None:
    payload = task_run.input_payload if isinstance(task_run.input_payload, dict) else {}
    existing_log = payload.get("activity_log")
    activity_log = existing_log if isinstance(existing_log, list) else []
    activity_log.append(
        {
            "timestamp": _utcnow().isoformat(),
            "stage": stage,
            "message": message,
            "details": details or {},
        }
    )
    payload["activity_log"] = activity_log[-50:]
    task_run.input_payload = payload


def _fetch_text_url(url: str, timeout: int = 20, *, strip_html: bool = True) -> str:
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    with urllib_request.urlopen(request, timeout=timeout) as response:
        raw_content = response.read()
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
    text = raw_content.decode(charset, errors="replace")
    if strip_html and ("html" in content_type.lower() or "<html" in text[:500].lower()):
        return _strip_html_to_text(text)
    return text


def _execute_web_search(query: str, *, max_results: int | None = None) -> dict[str, object]:
    if not settings.agent_web_enabled:
        raise HTTPException(status_code=400, detail="Agent web access is disabled")

    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    limited_max_results = min(
        max_results or settings.agent_web_search_max_results,
        settings.agent_web_search_max_results,
    )
    request_url = (
        "https://html.duckduckgo.com/html/?"
        + urllib_parse.urlencode({"q": normalized_query})
    )
    page_text = _fetch_text_url(request_url, strip_html=False)
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    matches = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        page_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not matches:
        matches = re.findall(
            r'<a[^>]+href="([^"]*duckduckgo\.com/l/\?[^"]+|[^"]*uddg=[^"]+)"[^>]*>(.*?)</a>',
            page_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    for raw_url, raw_title in matches:
        parsed_url = urllib_parse.urlparse(raw_url)
        final_url = raw_url
        if parsed_url.netloc.endswith("duckduckgo.com"):
            query_params = urllib_parse.parse_qs(parsed_url.query)
            redirect_url = query_params.get("uddg", [None])[0]
            if isinstance(redirect_url, str) and redirect_url.strip():
                final_url = urllib_parse.unquote(redirect_url)
        elif raw_url.startswith("//duckduckgo.com"):
            query_part = urllib_parse.urlparse(f"https:{raw_url}").query
            query_params = urllib_parse.parse_qs(query_part)
            redirect_url = query_params.get("uddg", [None])[0]
            if isinstance(redirect_url, str) and redirect_url.strip():
                final_url = urllib_parse.unquote(redirect_url)
            else:
                final_url = f"https:{raw_url}"
        elif raw_url.startswith("//"):
            final_url = f"https:{raw_url}"

        cleaned_title = _strip_html_to_text(raw_title)
        if not cleaned_title or cleaned_title.casefold() == "duckduckgo":
            continue
        if final_url in seen_urls:
            continue
        seen_urls.add(final_url)
        results.append(
            {
                "title": cleaned_title,
                "url": final_url,
            }
        )
        if len(results) >= limited_max_results:
            break

    return {
        "tool": "web_search",
        "query": normalized_query,
        "results": results,
    }


def _execute_fetch_url(url: str, *, max_chars: int | None = None) -> dict[str, object]:
    if not settings.agent_web_enabled:
        raise HTTPException(status_code=400, detail="Agent web access is disabled")

    normalized_url = url.strip()
    if not normalized_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    parsed_url = urllib_parse.urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Only http and https URLs are supported")

    content = _fetch_text_url(normalized_url)
    limited_chars = min(
        max_chars or settings.agent_web_fetch_max_chars,
        settings.agent_web_fetch_max_chars,
    )
    if len(content) > limited_chars:
        content = f"{content[:limited_chars]}\n...[truncated]"

    return {
        "tool": "fetch_url",
        "url": normalized_url,
        "content": content,
    }


def _execute_tool_call(tool_call: dict[str, object]) -> dict[str, object]:
    tool_name = str(tool_call.get("tool", "")).strip()
    if tool_name == "web_search":
        query = tool_call.get("query")
        if not isinstance(query, str):
            raise HTTPException(status_code=400, detail="web_search requires a query string")
        max_results = tool_call.get("max_results")
        if max_results is not None and not isinstance(max_results, int):
            raise HTTPException(status_code=400, detail="web_search max_results must be an integer")
        return _execute_web_search(query, max_results=max_results)

    if tool_name == "fetch_url":
        url = tool_call.get("url")
        if not isinstance(url, str):
            raise HTTPException(status_code=400, detail="fetch_url requires a url string")
        max_chars = tool_call.get("max_chars")
        if max_chars is not None and not isinstance(max_chars, int):
            raise HTTPException(status_code=400, detail="fetch_url max_chars must be an integer")
        return _execute_fetch_url(url, max_chars=max_chars)

    raise HTTPException(status_code=400, detail=f"Unsupported tool call: {tool_name}")


def _execute_agent_roundtrip(agent: Agent, initial_prompt: str) -> tuple[str, dict, list[dict[str, object]]]:
    prompt = initial_prompt
    raw_payload: dict = {}
    tool_results: list[dict[str, object]] = []

    for _ in range(settings.agent_web_max_iterations):
        raw_text, raw_payload = _call_provider(agent, prompt)
        tool_calls = _extract_tool_calls_from_text(raw_text)
        if not tool_calls:
            final_payload = _extract_json_object_from_text(raw_text)
            if final_payload is not None:
                return (
                    json.dumps(final_payload, ensure_ascii=False),
                    raw_payload,
                    tool_results,
                )
            return raw_text, raw_payload, tool_results

        executed_results: list[dict[str, object]] = []
        for tool_call in tool_calls:
            try:
                result = _execute_tool_call(tool_call)
                executed_results.append({"ok": True, "request": tool_call, "result": result})
            except HTTPException as exc:
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": str(exc.detail),
                    }
                )
            except urllib_error.HTTPError as exc:
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": _extract_http_error_message(exc),
                    }
                )
            except urllib_error.URLError as exc:
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": f"Web request failed: {exc.reason}",
                    }
                )

        tool_results.extend(executed_results)
        prompt = "\n\n".join(
            [
                initial_prompt,
                "Previous assistant response:",
                raw_text,
                "Tool results:",
                json.dumps(executed_results, ensure_ascii=False),
                (
                    "Continue the task using the tool results. "
                    "Return strict JSON only. If you still need tools, include tool_calls again. "
                    "Otherwise return the final summary/files payload."
                ),
            ]
        )

    raise HTTPException(
        status_code=502,
        detail="Agent exceeded the maximum number of web tool iterations",
    )


def _execute_agent_roundtrip_with_activity(
    db: Session,
    task_run: TaskRun,
    agent: Agent,
    initial_prompt: str,
) -> tuple[str, dict, list[dict[str, object]]]:
    if _agent_prefers_native_tools(agent):
        def activity_callback(stage: str, message: str, details: dict[str, object]) -> None:
            _append_activity_event(
                task_run,
                stage=stage,
                message=message,
                details=details,
            )
            db.commit()

        return _execute_agent_roundtrip_native_tools(
            agent,
            initial_prompt,
            activity_callback=activity_callback,
        )

    prompt = initial_prompt
    raw_payload: dict = {}
    tool_results: list[dict[str, object]] = []

    for iteration_index in range(settings.agent_web_max_iterations):
        _append_activity_event(
            task_run,
            stage="model_request",
            message=f"Calling model for iteration {iteration_index + 1}",
            details={"iteration": iteration_index + 1},
        )
        db.commit()
        raw_text, raw_payload = _call_provider(agent, prompt)
        tool_calls = _extract_tool_calls_from_text(raw_text)
        if not tool_calls:
            final_payload = _extract_json_object_from_text(raw_text)
            _append_activity_event(
                task_run,
                stage="model_response",
                message="Model returned a final response",
                details={
                    "iteration": iteration_index + 1,
                    "has_json_payload": final_payload is not None,
                },
            )
            db.commit()
            if final_payload is not None:
                return (
                    json.dumps(final_payload, ensure_ascii=False),
                    raw_payload,
                    tool_results,
                )
            return raw_text, raw_payload, tool_results

        _append_activity_event(
            task_run,
            stage="tool_request",
            message=f"Model requested {len(tool_calls)} tool call(s)",
            details={
                "iteration": iteration_index + 1,
                "tools": [str(tool_call.get('tool', '')) for tool_call in tool_calls],
            },
        )
        db.commit()

        executed_results: list[dict[str, object]] = []
        for tool_call in tool_calls:
            tool_name = str(tool_call.get("tool", "")).strip()
            _append_activity_event(
                task_run,
                stage="tool_execute",
                message=f"Executing tool: {tool_name}",
                details={"tool_request": tool_call},
            )
            db.commit()
            try:
                result = _execute_tool_call(tool_call)
                executed_results.append({"ok": True, "request": tool_call, "result": result})
                _append_activity_event(
                    task_run,
                    stage="tool_result",
                    message=f"Tool {tool_name} completed",
                    details={"tool_result": result},
                )
                db.commit()
            except HTTPException as exc:
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": str(exc.detail),
                    }
                )
                _append_activity_event(
                    task_run,
                    stage="tool_result",
                    message=f"Tool {tool_name} failed",
                    details={"error": str(exc.detail)},
                )
                db.commit()
            except urllib_error.HTTPError as exc:
                error_message = _extract_http_error_message(exc)
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": error_message,
                    }
                )
                _append_activity_event(
                    task_run,
                    stage="tool_result",
                    message=f"Tool {tool_name} failed",
                    details={"error": error_message},
                )
                db.commit()
            except urllib_error.URLError as exc:
                error_message = f"Web request failed: {exc.reason}"
                executed_results.append(
                    {
                        "ok": False,
                        "request": tool_call,
                        "error": error_message,
                    }
                )
                _append_activity_event(
                    task_run,
                    stage="tool_result",
                    message=f"Tool {tool_name} failed",
                    details={"error": error_message},
                )
                db.commit()

        tool_results.extend(executed_results)
        prompt = "\n\n".join(
            [
                initial_prompt,
                "Previous assistant response:",
                raw_text,
                "Tool results:",
                json.dumps(executed_results, ensure_ascii=False),
                (
                    "Continue the task using the tool results. "
                    "Return strict JSON only. If you still need tools, include tool_calls again. "
                    "Otherwise return the final summary/files payload."
                ),
            ]
        )

    raise HTTPException(
        status_code=502,
        detail="Agent exceeded the maximum number of web tool iterations",
    )


def _apply_file_operations(task_run: TaskRun, response_text: str) -> tuple[str, list[dict[str, str]]]:
    workspace = task_run.workflow_run.project.workspace
    root_path = workspace.root_path
    payload = _validate_final_response_payload(response_text)
    if payload is None:
        return response_text.strip(), []

    summary = payload.get("summary")
    final_text = summary.strip() if isinstance(summary, str) and summary.strip() else response_text.strip()
    files_payload = payload.get("files")
    if not isinstance(files_payload, list):
        return final_text, []

    if not root_path:
        return final_text, []

    artifacts: list[dict[str, str]] = []
    for item in files_payload:
        if not isinstance(item, dict):
            continue
        relative_path = item.get("path")
        content = item.get("content")
        if not isinstance(relative_path, str) or not relative_path.strip():
            continue
        if not isinstance(content, str):
            continue

        target_path = _resolve_workspace_file_path(root_path, relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8", newline="\n")
        artifacts.append(
            {
                "path": relative_path.strip().replace("\\", "/"),
                "absolute_path": str(target_path),
                "operation": "write_file",
            }
        )

    return final_text, artifacts


def _task_run_requires_agent_execution(task_run: TaskRun) -> bool:
    return task_run.assigned_agent_id is not None


def _extract_referenced_workspace_paths(task_run: TaskRun) -> list[str]:
    task = task_run.task
    candidates_text = "\n".join(
        part for part in [task.title, task.description or ""] if part
    )
    found_paths: list[str] = []
    seen: set[str] = set()

    patterns = [
        r"`([^`\n]+)`",
        r'"([^"\n]+)"',
        r"'([^'\n]+)'",
        r"([A-Za-z0-9_\-./\\]+\.[A-Za-z0-9]{1,10})",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, candidates_text):
            candidate = str(match).strip().replace("\\", "/")
            if "/" not in candidate and "." not in candidate:
                continue
            if candidate.startswith(("http://", "https://")):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            found_paths.append(candidate)

    return found_paths[:5]


def _extract_output_artifact_paths(task_run: TaskRun) -> list[str]:
    output_payload = task_run.output_payload
    if not isinstance(output_payload, dict):
        return []

    artifacts = output_payload.get("artifacts")
    if not isinstance(artifacts, list):
        return []

    artifact_paths: list[str] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str):
            continue
        normalized_path = raw_path.strip().replace("\\", "/").strip("/")
        if not normalized_path or normalized_path in seen:
            continue
        seen.add(normalized_path)
        artifact_paths.append(normalized_path)
    return artifact_paths


def _collect_input_files(task_run: TaskRun) -> list[dict[str, str]]:
    workspace = task_run.workflow_run.project.workspace
    root_path = workspace.root_path
    if not root_path:
        return []

    input_files: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    referenced_paths = _extract_referenced_workspace_paths(task_run)
    dependency_task_ids = set(task_run.task_dependencies_snapshot or [])

    for candidate_path in referenced_paths:
        normalized_path = candidate_path.strip().replace("\\", "/").strip("/")
        if not normalized_path or normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        input_files.append({"path": normalized_path, "source": "referenced"})

    for dependency_task_run in task_run.workflow_run.task_runs:
        if dependency_task_run.task_id not in dependency_task_ids:
            continue
        for artifact_path in _extract_output_artifact_paths(dependency_task_run):
            if artifact_path in seen_paths:
                continue
            seen_paths.add(artifact_path)
            input_files.append(
                {
                    "path": artifact_path,
                    "source": f"dependency_task_run:{dependency_task_run.id}",
                }
            )

    return input_files


def _load_input_file_context(task_run: TaskRun) -> tuple[str, list[dict[str, str]]]:
    workspace = task_run.workflow_run.project.workspace
    root_path = workspace.root_path
    if not root_path:
        return "Input files: none", []

    file_sections: list[str] = []
    available_input_files: list[dict[str, str]] = []
    for input_file in _collect_input_files(task_run):
        relative_path = input_file["path"]
        try:
            target_path = _resolve_workspace_file_path(root_path, relative_path)
        except HTTPException:
            continue
        if not target_path.exists() or not target_path.is_file():
            continue

        try:
            content = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = target_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if len(content) > 12000:
            content = f"{content[:12000]}\n...[truncated]"

        available_input_files.append(input_file)
        file_sections.append(
            "\n".join(
                [
                    f"File: {relative_path}",
                    f"Source: {input_file['source']}",
                    "Content:",
                    content,
                ]
            )
        )

    if not file_sections:
        return "Input files: none", []

    return "Input file contents:\n\n" + "\n\n---\n\n".join(file_sections), available_input_files


def _extract_http_error_message(exc: urllib_error.HTTPError) -> str:
    try:
        raw_body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        raw_body = ""

    if not raw_body:
        return f"Provider request failed with HTTP {exc.code}"

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            error_message = payload["error"].get("message")
            if isinstance(error_message, str) and error_message.strip():
                return f"Provider request failed with HTTP {exc.code}: {error_message.strip()}"
        if isinstance(payload.get("message"), str) and payload["message"].strip():
            return f"Provider request failed with HTTP {exc.code}: {payload['message'].strip()}"

    compact_body = " ".join(raw_body.split())
    if len(compact_body) > 200:
        compact_body = f"{compact_body[:197]}..."
    return f"Provider request failed with HTTP {exc.code}: {compact_body}"


def _get_openai_max_tokens_field(model_name: str) -> str:
    normalized = model_name.strip().casefold()
    if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
        return "max_completion_tokens"
    return "max_tokens"


def _execute_openai_compatible(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    user_prompt: str,
) -> tuple[str, dict]:
    base_url = (provider.base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
    request_url = f"{base_url}/chat/completions"
    payload: dict[str, object] = {
        "model": provider_model.model_name,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful task execution agent."},
            {"role": "user", "content": user_prompt},
        ],
    }
    if provider_model.temperature is not None:
        payload["temperature"] = provider_model.temperature
    if provider_model.max_output_tokens is not None:
        payload[_get_openai_max_tokens_field(provider_model.model_name)] = (
            provider_model.max_output_tokens
        )

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    choice = ((raw_payload.get("choices") or [{}])[0]).get("message", {})
    text = _stringify_response_text(choice.get("content", ""))
    return text, raw_payload


def _execute_anthropic(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    user_prompt: str,
) -> tuple[str, dict]:
    base_url = (provider.base_url or "").strip().rstrip("/") or "https://api.anthropic.com"
    request_url = f"{base_url}/v1/messages"
    payload: dict[str, object] = {
        "model": provider_model.model_name,
        "max_tokens": provider_model.max_output_tokens or 1024,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt
    if provider_model.temperature is not None:
        payload["temperature"] = provider_model.temperature

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    text = _stringify_response_text(raw_payload.get("content", []))
    return text, raw_payload


def _execute_google(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    user_prompt: str,
) -> tuple[str, dict]:
    base_url = (
        (provider.base_url or "").strip().rstrip("/")
        or "https://generativelanguage.googleapis.com"
    )
    model_name = provider_model.model_name
    query_string = urllib_parse.urlencode({"key": provider.api_key})
    request_url = f"{base_url}/v1beta/models/{model_name}:generateContent?{query_string}"
    parts = []
    if system_prompt:
        parts.append(f"System instruction:\n{system_prompt}")
    parts.append(user_prompt)

    payload: dict[str, object] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "\n\n".join(parts)}],
            }
        ]
    }

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    candidates = raw_payload.get("candidates") or []
    parts_payload = []
    if candidates:
        parts_payload = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "\n".join(
        part.get("text", "")
        for part in parts_payload
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()
    return text, raw_payload


def _execute_openai_compatible_with_native_tools(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    messages: list[dict[str, object]],
) -> tuple[str, dict, list[dict[str, object]], dict[str, object]]:
    base_url = (provider.base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
    request_url = f"{base_url}/chat/completions"
    payload: dict[str, object] = {
        "model": provider_model.model_name,
        "messages": messages,
        "tools": _build_openai_tool_definitions(),
        "tool_choice": "auto",
    }
    if provider_model.temperature is not None:
        payload["temperature"] = provider_model.temperature
    if provider_model.max_output_tokens is not None:
        payload[_get_openai_max_tokens_field(provider_model.model_name)] = (
            provider_model.max_output_tokens
        )
    if system_prompt:
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    message = ((raw_payload.get("choices") or [{}])[0]).get("message", {})
    text = _stringify_response_text(message.get("content", ""))
    raw_tool_calls = message.get("tool_calls")
    tool_calls: list[dict[str, object]] = []
    if isinstance(raw_tool_calls, list):
        for item in raw_tool_calls:
            if not isinstance(item, dict):
                continue
            function_payload = item.get("function")
            if not isinstance(function_payload, dict):
                continue
            tool_name = function_payload.get("name")
            if not isinstance(tool_name, str):
                continue
            tool_calls.append(
                _normalize_provider_tool_call(
                    tool_name=tool_name,
                    arguments=function_payload.get("arguments", {}),
                    call_id=str(item.get("id", "")).strip() or None,
                )
            )
    return text, raw_payload, tool_calls, message


def _execute_anthropic_with_native_tools(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    messages: list[dict[str, object]],
) -> tuple[str, dict, list[dict[str, object]], list[dict[str, object]]]:
    base_url = (provider.base_url or "").strip().rstrip("/") or "https://api.anthropic.com"
    request_url = f"{base_url}/v1/messages"
    payload: dict[str, object] = {
        "model": provider_model.model_name,
        "max_tokens": provider_model.max_output_tokens or 1024,
        "messages": messages,
        "tools": _build_anthropic_tool_definitions(),
    }
    if system_prompt:
        payload["system"] = system_prompt
    if provider_model.temperature is not None:
        payload["temperature"] = provider_model.temperature

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    content_blocks = raw_payload.get("content") or []
    text_parts: list[str] = []
    tool_calls: list[dict[str, object]] = []
    if isinstance(content_blocks, list):
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
                continue
            if block_type != "tool_use":
                continue
            tool_name = block.get("name")
            if not isinstance(tool_name, str):
                continue
            tool_calls.append(
                _normalize_provider_tool_call(
                    tool_name=tool_name,
                    arguments=block.get("input", {}),
                    call_id=str(block.get("id", "")).strip() or None,
                )
            )
    return "\n".join(part for part in text_parts if part).strip(), raw_payload, tool_calls, content_blocks


def _execute_google_with_native_tools(
    *,
    provider: Provider,
    provider_model: ProviderModel,
    system_prompt: str | None,
    contents: list[dict[str, object]],
) -> tuple[str, dict, list[dict[str, object]], list[dict[str, object]]]:
    base_url = (
        (provider.base_url or "").strip().rstrip("/")
        or "https://generativelanguage.googleapis.com"
    )
    model_name = provider_model.model_name
    query_string = urllib_parse.urlencode({"key": provider.api_key})
    request_url = f"{base_url}/v1beta/models/{model_name}:generateContent?{query_string}"
    payload: dict[str, object] = {
        "contents": contents,
        "tools": _build_google_tool_definitions(),
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}],
        }

    request = urllib_request.Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=60) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    candidates = raw_payload.get("candidates") or []
    parts_payload: list[dict[str, object]] = []
    if candidates:
        parts_payload = ((candidates[0].get("content") or {}).get("parts")) or []

    text_parts: list[str] = []
    tool_calls: list[dict[str, object]] = []
    for part in parts_payload:
        if not isinstance(part, dict):
            continue
        text_value = part.get("text")
        if isinstance(text_value, str) and text_value.strip():
            text_parts.append(text_value)
        function_call = part.get("functionCall")
        if not isinstance(function_call, dict):
            continue
        tool_name = function_call.get("name")
        if not isinstance(tool_name, str):
            continue
        tool_calls.append(
            _normalize_provider_tool_call(
                tool_name=tool_name,
                arguments=function_call.get("args", {}),
                call_id=str(function_call.get("id", "")).strip() or None,
            )
        )
    return "\n".join(text_parts).strip(), raw_payload, tool_calls, parts_payload


def _build_user_prompt(task_run: TaskRun) -> tuple[str, list[dict[str, str]]]:
    task = task_run.task
    workflow_run = task_run.workflow_run
    project = workflow_run.project
    workspace = project.workspace
    input_file_context, input_files = _load_input_file_context(task_run)

    prompt_parts = [
        f"Workspace: {workspace.name}",
        f"Workspace root path: {workspace.root_path or 'not configured'}",
        f"Project: {project.name}",
        f"Task title: {task.title}",
        f"Task description: {task.description or 'No description provided.'}",
        f"Task priority: {task.priority}",
        f"Task dependencies: {', '.join(map(str, task_run.task_dependencies_snapshot or [])) or 'None'}",
        input_file_context,
    ]
    if task_run.assigned_agent is not None and _agent_prefers_native_tools(task_run.assigned_agent):
        prompt_parts.extend(
            [
                "If the task needs current online information, call the provided web tools directly.",
                "Do not describe tool calls in plain text and do not pretend that a tool has already run.",
            ]
        )
    else:
        prompt_parts.extend(
            [
                "You may use controlled web tools if the task needs current online information.",
                (
                    'Tool request JSON format: {"summary":"short note","files":[],'
                    '"tool_calls":[{"tool":"web_search","query":"topic","max_results":5},'
                    '{"tool":"fetch_url","url":"https://example.com","max_chars":6000}]}'
                ),
                "Use tool_calls only when necessary. Keep them minimal and specific.",
            ]
        )
    prompt_parts.extend(
        [
            "Respond with strict JSON only.",
            'If you need to create or edit files, use: {"summary":"short result","files":[{"path":"relative/path.txt","content":"file content"}]}',
            "Only use paths relative to the workspace root path.",
            'If no file changes are needed, you may respond with: {"summary":"short result"}',
        ]
    )
    prompt = "\n".join(prompt_parts)
    return prompt, input_files


def _call_provider(agent: Agent, user_prompt: str) -> tuple[str, dict]:
    provider_model = agent.provider_model
    provider = provider_model.provider
    system_prompt = agent.system_prompt

    if provider.platform in {"openai", "deepseek", "openrouter", "custom"}:
        return _execute_openai_compatible(
            provider=provider,
            provider_model=provider_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider.platform == "anthropic":
        return _execute_anthropic(
            provider=provider,
            provider_model=provider_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider.platform == "google":
        return _execute_google(
            provider=provider,
            provider_model=provider_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    raise HTTPException(status_code=400, detail="Unsupported provider platform")


def _run_tool_call_with_error_capture(tool_call: dict[str, object]) -> dict[str, object]:
    try:
        result = _execute_tool_call(tool_call)
        return {"ok": True, "request": tool_call, "result": result}
    except HTTPException as exc:
        return {"ok": False, "request": tool_call, "error": str(exc.detail)}
    except urllib_error.HTTPError as exc:
        return {
            "ok": False,
            "request": tool_call,
            "error": _extract_http_error_message(exc),
        }
    except urllib_error.URLError as exc:
        return {
            "ok": False,
            "request": tool_call,
            "error": f"Web request failed: {exc.reason}",
        }


def _execute_agent_roundtrip_native_tools(
    agent: Agent,
    initial_prompt: str,
    activity_callback: Callable[[str, str, dict[str, object]], None] | None = None,
) -> tuple[str, dict, list[dict[str, object]]]:
    provider_model = agent.provider_model
    provider = provider_model.provider
    system_prompt = agent.system_prompt
    raw_payload: dict = {}
    tool_results: list[dict[str, object]] = []

    def emit(stage: str, message: str, details: dict[str, object] | None = None) -> None:
        if activity_callback is not None:
            activity_callback(stage, message, details or {})

    if provider.platform in {"openai", "deepseek", "openrouter", "custom"}:
        messages: list[dict[str, object]] = [{"role": "user", "content": initial_prompt}]
        for iteration_index in range(settings.agent_web_max_iterations):
            emit("model_request", f"Calling model for iteration {iteration_index + 1}", {"iteration": iteration_index + 1})
            raw_text, raw_payload, tool_calls, assistant_message = _execute_openai_compatible_with_native_tools(
                provider=provider,
                provider_model=provider_model,
                system_prompt=system_prompt,
                messages=messages,
            )
            if not tool_calls:
                emit(
                    "model_response",
                    "Model returned a final response",
                    {
                        "iteration": iteration_index + 1,
                        "has_json_payload": _extract_json_object_from_text(raw_text) is not None,
                    },
                )
                return raw_text, raw_payload, tool_results

            emit(
                "tool_request",
                f"Model requested {len(tool_calls)} tool call(s)",
                {
                    "iteration": iteration_index + 1,
                    "tools": [str(tool_call.get("tool", "")) for tool_call in tool_calls],
                },
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.get("content", "") or "",
                    "tool_calls": assistant_message.get("tool_calls", []),
                }
            )
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("tool", "")).strip()
                emit("tool_execute", f"Executing tool: {tool_name}", {"tool_request": tool_call})
                executed_result = _run_tool_call_with_error_capture(tool_call)
                tool_results.append(executed_result)
                if executed_result.get("ok"):
                    emit("tool_result", f"Tool {tool_name} completed", {"tool_result": executed_result.get("result")})
                else:
                    emit("tool_result", f"Tool {tool_name} failed", {"error": executed_result.get("error")})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("_tool_call_id"),
                        "content": _stringify_tool_result_for_provider(executed_result),
                    }
                )
        raise HTTPException(status_code=502, detail="Agent exceeded the maximum number of web tool iterations")

    if provider.platform == "anthropic":
        messages = [{"role": "user", "content": initial_prompt}]
        for iteration_index in range(settings.agent_web_max_iterations):
            emit("model_request", f"Calling model for iteration {iteration_index + 1}", {"iteration": iteration_index + 1})
            raw_text, raw_payload, tool_calls, content_blocks = _execute_anthropic_with_native_tools(
                provider=provider,
                provider_model=provider_model,
                system_prompt=system_prompt,
                messages=messages,
            )
            if not tool_calls:
                emit(
                    "model_response",
                    "Model returned a final response",
                    {
                        "iteration": iteration_index + 1,
                        "has_json_payload": _extract_json_object_from_text(raw_text) is not None,
                    },
                )
                return raw_text, raw_payload, tool_results

            emit(
                "tool_request",
                f"Model requested {len(tool_calls)} tool call(s)",
                {
                    "iteration": iteration_index + 1,
                    "tools": [str(tool_call.get("tool", "")) for tool_call in tool_calls],
                },
            )
            messages.append({"role": "assistant", "content": content_blocks})
            tool_result_blocks: list[dict[str, object]] = []
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("tool", "")).strip()
                emit("tool_execute", f"Executing tool: {tool_name}", {"tool_request": tool_call})
                executed_result = _run_tool_call_with_error_capture(tool_call)
                tool_results.append(executed_result)
                if executed_result.get("ok"):
                    emit("tool_result", f"Tool {tool_name} completed", {"tool_result": executed_result.get("result")})
                else:
                    emit("tool_result", f"Tool {tool_name} failed", {"error": executed_result.get("error")})
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.get("_tool_call_id"),
                        "content": _stringify_tool_result_for_provider(executed_result),
                    }
                )
            messages.append({"role": "user", "content": tool_result_blocks})
        raise HTTPException(status_code=502, detail="Agent exceeded the maximum number of web tool iterations")

    if provider.platform == "google":
        contents: list[dict[str, object]] = [
            {"role": "user", "parts": [{"text": initial_prompt}]}
        ]
        for iteration_index in range(settings.agent_web_max_iterations):
            emit("model_request", f"Calling model for iteration {iteration_index + 1}", {"iteration": iteration_index + 1})
            raw_text, raw_payload, tool_calls, parts_payload = _execute_google_with_native_tools(
                provider=provider,
                provider_model=provider_model,
                system_prompt=system_prompt,
                contents=contents,
            )
            if not tool_calls:
                emit(
                    "model_response",
                    "Model returned a final response",
                    {
                        "iteration": iteration_index + 1,
                        "has_json_payload": _extract_json_object_from_text(raw_text) is not None,
                    },
                )
                return raw_text, raw_payload, tool_results

            emit(
                "tool_request",
                f"Model requested {len(tool_calls)} tool call(s)",
                {
                    "iteration": iteration_index + 1,
                    "tools": [str(tool_call.get("tool", "")) for tool_call in tool_calls],
                },
            )
            contents.append({"role": "model", "parts": parts_payload})
            response_parts: list[dict[str, object]] = []
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("tool", "")).strip()
                emit("tool_execute", f"Executing tool: {tool_name}", {"tool_request": tool_call})
                executed_result = _run_tool_call_with_error_capture(tool_call)
                tool_results.append(executed_result)
                if executed_result.get("ok"):
                    emit("tool_result", f"Tool {tool_name} completed", {"tool_result": executed_result.get("result")})
                else:
                    emit("tool_result", f"Tool {tool_name} failed", {"error": executed_result.get("error")})
                response_parts.append(
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": executed_result,
                        }
                    }
                )
            contents.append({"role": "user", "parts": response_parts})
        raise HTTPException(status_code=502, detail="Agent exceeded the maximum number of web tool iterations")

    raise HTTPException(status_code=400, detail="Unsupported provider platform")


def _promote_ready_task_runs(db: Session, workflow_run_id: int) -> None:
    statement = (
        select(TaskRun)
        .where(TaskRun.workflow_run_id == workflow_run_id)
        .order_by(TaskRun.id)
    )
    task_runs = list(db.scalars(statement).all())
    completed_task_ids = {
        task_run.task_id
        for task_run in task_runs
        if task_run.status == "completed"
    }

    for task_run in task_runs:
        if task_run.status != "pending" or task_run.node_type == "start":
            continue
        if all(
            dependency_id in completed_task_ids
            for dependency_id in (task_run.task_dependencies_snapshot or [])
        ):
            task_run.status = "ready"
            if task_run.node_type in {"start", "end"} and not _task_run_requires_agent_execution(task_run):
                now = _utcnow()
                task_run.status = "completed"
                task_run.started_at = task_run.started_at or now
                task_run.finished_at = now


def _finalize_workflow_run_if_complete(workflow_run: WorkflowRun) -> None:
    if workflow_run.task_runs and all(
        task_run.status == "completed" for task_run in workflow_run.task_runs
    ):
        workflow_run.status = "completed"
        workflow_run.finished_at = _utcnow()


def execute_task_run(
    db: Session,
    workspace_id: int,
    project_id: int,
    workflow_run_id: int,
    task_run_id: int,
) -> WorkflowRun:
    get_project_for_workspace_or_404(db, workspace_id, project_id)
    task_run = _load_task_run_or_404(db, workflow_run_id, task_run_id)
    workflow_run = task_run.workflow_run
    if workflow_run.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Workflow run does not belong to the specified project",
        )

    if task_run.status not in {"ready", "failed"}:
        raise HTTPException(
            status_code=400,
            detail="Only ready or failed task runs can be executed",
        )

    agent = _ensure_agent_available(db, task_run)
    now = _utcnow()
    if workflow_run.status == "failed":
        workflow_run.status = "running"
        workflow_run.error_message = None
        workflow_run.finished_at = None
    task_run.status = "running"
    task_run.executor_type = "agent"
    task_run.started_at = now
    task_run.finished_at = None
    task_run.error_message = None
    task_run.attempt_count += 1
    task_run.input_payload = {}
    _append_activity_event(
        task_run,
        stage="start",
        message="Task run started",
        details={"attempt_count": task_run.attempt_count},
    )
    db.commit()
    db.refresh(task_run)

    max_attempts = settings.agent_task_auto_retry_attempts
    raw_payload: dict = {}
    tool_results: list[dict[str, object]] = []
    text = ""
    artifacts: list[dict[str, str]] = []
    last_error_message: str | None = None

    for retry_index in range(max_attempts):
        try:
            user_prompt, input_files = _build_user_prompt(task_run)
            if retry_index > 0:
                user_prompt = "\n\n".join(
                    [
                        user_prompt,
                        (
                            "Previous attempt did not successfully complete the task. "
                            "Do not explain what is missing. Actually complete the task now."
                        ),
                        f"Retry reason: {last_error_message or 'Previous result was incomplete.'}",
                        "If the task requires data or files, produce the actual output files in the files array.",
                    ]
                )
            task_run.input_payload = {
                "files": input_files,
                "auto_retry_attempt": retry_index + 1,
                "auto_retry_max_attempts": max_attempts,
                "activity_log": (
                    task_run.input_payload.get("activity_log", [])
                    if isinstance(task_run.input_payload, dict)
                    else []
                ),
            }
            _append_activity_event(
                task_run,
                stage="prepare",
                message=f"Prepared attempt {retry_index + 1} of {max_attempts}",
                details={
                    "attempt": retry_index + 1,
                    "max_attempts": max_attempts,
                    "input_file_count": len(input_files),
                },
            )
            db.commit()
            raw_text, raw_payload, tool_results = _execute_agent_roundtrip_with_activity(
                db,
                task_run,
                agent,
                user_prompt,
            )
            text, artifacts = _apply_file_operations(task_run, raw_text)
            _append_activity_event(
                task_run,
                stage="result",
                message="Validated final response",
                details={
                    "artifact_count": len(artifacts),
                    "text_preview": text[:160],
                },
            )
            db.commit()
            incomplete_reason = _detect_incomplete_task_result(task_run, text, artifacts)
            if incomplete_reason is None:
                break
            last_error_message = incomplete_reason
            _append_activity_event(
                task_run,
                stage="retry",
                message="Result was incomplete, retrying task",
                details={"reason": incomplete_reason},
            )
            db.commit()
            if retry_index == max_attempts - 1:
                raise HTTPException(status_code=502, detail=incomplete_reason)
        except urllib_error.HTTPError as exc:
            task_run.status = "failed"
            task_run.error_message = _extract_http_error_message(exc)
            task_run.finished_at = _utcnow()
            workflow_run.status = "failed"
            workflow_run.error_message = task_run.error_message
            workflow_run.finished_at = task_run.finished_at
            db.commit()
            raise HTTPException(status_code=502, detail=task_run.error_message) from exc
        except urllib_error.URLError as exc:
            task_run.status = "failed"
            task_run.error_message = f"Provider request failed: {exc.reason}"
            task_run.finished_at = _utcnow()
            workflow_run.status = "failed"
            workflow_run.error_message = task_run.error_message
            workflow_run.finished_at = task_run.finished_at
            db.commit()
            raise HTTPException(status_code=502, detail=task_run.error_message) from exc
        except HTTPException as exc:
            last_error_message = str(exc.detail)
            if retry_index < max_attempts - 1 and exc.status_code == 502:
                _append_activity_event(
                    task_run,
                    stage="retry",
                    message="Attempt failed, scheduling automatic retry",
                    details={"reason": str(exc.detail), "next_attempt": retry_index + 2},
                )
                db.commit()
                continue
            task_run.status = "failed"
            task_run.error_message = str(exc.detail)
            task_run.finished_at = _utcnow()
            workflow_run.status = "failed"
            workflow_run.error_message = task_run.error_message
            workflow_run.finished_at = task_run.finished_at
            _append_activity_event(
                task_run,
                stage="failed",
                message="Task run failed",
                details={"reason": str(exc.detail)},
            )
            db.commit()
            raise
        except ValueError as exc:
            task_run.status = "failed"
            task_run.error_message = f"Agent web tool handling failed: {exc}"
            task_run.finished_at = _utcnow()
            workflow_run.status = "failed"
            workflow_run.error_message = task_run.error_message
            workflow_run.finished_at = task_run.finished_at
            db.commit()
            raise HTTPException(status_code=502, detail=task_run.error_message) from exc

    task_run.status = "completed"
    task_run.error_message = None
    task_run.finished_at = _utcnow()
    _append_activity_event(
        task_run,
        stage="completed",
        message="Task run completed",
        details={"artifact_count": len(artifacts)},
    )
    task_run.output_payload = {
        "text": text,
        "model": agent.provider_model.model_name,
        "provider": agent.provider_model.provider.platform,
        "artifacts": artifacts,
        "tool_results": tool_results,
        "activity_log": (
            task_run.input_payload.get("activity_log", [])
            if isinstance(task_run.input_payload, dict)
            else []
        ),
        "raw_response": raw_payload,
    }
    _promote_ready_task_runs(db, workflow_run_id)
    _finalize_workflow_run_if_complete(workflow_run)
    db.commit()
    db.refresh(workflow_run)
    return workflow_run
