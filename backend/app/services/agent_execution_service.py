import json
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
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
    if not isinstance(files_payload, list):
        raise HTTPException(
            status_code=502,
            detail="Agent final response must include a files array",
        )

    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise HTTPException(
            status_code=502,
            detail="Agent final response summary must be a string",
        )

    return payload


def _task_requires_artifact_output(task_run: TaskRun) -> bool:
    task = task_run.task
    text = "\n".join(
        part for part in [task.title, task.description or ""] if isinstance(part, str) and part
    ).casefold()
    keywords = [
        "collect",
        "gather",
        "export",
        "generate file",
        "dataset",
        "csv",
        "excel",
        "json",
        "markdown",
        "报告数据",
        "收集",
        "整理",
        "校验",
        "导出",
        "原始数据",
        "数据源",
        "台账",
        "报表",
        "文件",
        ".csv",
        ".xlsx",
        ".json",
        ".md",
    ]
    return any(keyword in text for keyword in keywords)


def _detect_incomplete_task_result(
    task_run: TaskRun,
    text: str,
    artifacts: list[dict[str, str]],
) -> str | None:
    normalized_text = text.strip().casefold()
    if _task_requires_artifact_output(task_run) and not artifacts:
        return "Task expected file or dataset output, but the agent produced no artifacts"

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


def _build_user_prompt(task_run: TaskRun) -> tuple[str, list[dict[str, str]]]:
    task = task_run.task
    workflow_run = task_run.workflow_run
    project = workflow_run.project
    workspace = project.workspace
    input_file_context, input_files = _load_input_file_context(task_run)

    prompt = "\n".join(
        [
            f"Workspace: {workspace.name}",
            f"Workspace root path: {workspace.root_path or 'not configured'}",
            f"Project: {project.name}",
            f"Task title: {task.title}",
            f"Task description: {task.description or 'No description provided.'}",
            f"Task priority: {task.priority}",
            f"Task dependencies: {', '.join(map(str, task_run.task_dependencies_snapshot or [])) or 'None'}",
            input_file_context,
            "You may use controlled web tools if the task needs current online information.",
            (
                'Tool request JSON format: {"summary":"short note","files":[],'
                '"tool_calls":[{"tool":"web_search","query":"topic","max_results":5},'
                '{"tool":"fetch_url","url":"https://example.com","max_chars":6000}]}'
            ),
            "Use tool_calls only when necessary. Keep them minimal and specific.",
            "If you need to create or edit files, respond with strict JSON only.",
            'Final JSON format: {"summary":"short result","files":[{"path":"relative/path.txt","content":"file content"}]}',
            "Only use paths relative to the workspace root path.",
            "If no file changes are needed, respond with strict JSON: {\"summary\":\"short result\",\"files\":[]}",
        ]
    )
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
            }
            db.commit()
            raw_text, raw_payload, tool_results = _execute_agent_roundtrip(agent, user_prompt)
            text, artifacts = _apply_file_operations(task_run, raw_text)
            incomplete_reason = _detect_incomplete_task_result(task_run, text, artifacts)
            if incomplete_reason is None:
                break
            last_error_message = incomplete_reason
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
                continue
            task_run.status = "failed"
            task_run.error_message = str(exc.detail)
            task_run.finished_at = _utcnow()
            workflow_run.status = "failed"
            workflow_run.error_message = task_run.error_message
            workflow_run.finished_at = task_run.finished_at
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
    task_run.output_payload = {
        "text": text,
        "model": agent.provider_model.model_name,
        "provider": agent.provider_model.provider.platform,
        "artifacts": artifacts,
        "tool_results": tool_results,
        "raw_response": raw_payload,
    }
    task_run.error_message = None
    task_run.finished_at = _utcnow()
    _promote_ready_task_runs(db, workflow_run_id)
    _finalize_workflow_run_if_complete(workflow_run)
    db.commit()
    db.refresh(workflow_run)
    return workflow_run
