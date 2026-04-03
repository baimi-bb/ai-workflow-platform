"use client";

import { useRouter } from "next/navigation";
import type { FormEvent, PointerEvent as ReactPointerEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Agent, Task, TaskRun, WorkflowRunDetail } from "@/lib/types";
import { priorityTone, statusTone } from "@/lib/ui";

import { ExecuteTaskRunButton } from "./execute-task-run-button";
import { ExecuteWorkflowRunButton } from "./execute-workflow-run-button";

type WorkflowCanvasProps = {
  workspaceId: number;
  projectId: number;
  tasks: Task[];
  agents: Agent[];
  selectedRun: WorkflowRunDetail | null;
};

type Point = {
  x: number;
  y: number;
};

type DragState = {
  taskIds: number[];
  initialPointer: Point;
  initialPositions: Record<number, Point>;
};

type PanState = {
  initialPointer: Point;
  initialScroll: Point;
};

type MarqueeState = {
  start: Point;
  current: Point;
};

const NODE_WIDTH = 340;
const NODE_HEIGHT = 300;
const MIN_GAP = 220;
const CANVAS_PADDING = 160;
const VIEWPORT_HEIGHT = "clamp(560px, 78vh, 960px)";

function getRuntimeStatus(task: Task, taskRun: TaskRun | null, workflowRunStatus: string | null) {
  if (!taskRun) {
    return task.status;
  }

  if (taskRun.status === "completed") {
    return "done";
  }

  if (taskRun.status === "running" || taskRun.status === "waiting_human") {
    return "in_progress";
  }

  if (taskRun.status === "failed") {
    return "failed";
  }

  if (workflowRunStatus === "queued" && taskRun.status === "ready") {
    return "queued";
  }

  return "todo";
}

function getRuntimeCardTone(status: string) {
  const value = status.toLowerCase();

  if (value === "done") {
    return "border-emerald-200 bg-emerald-50/80";
  }

  if (value === "in_progress") {
    return "border-amber-200 bg-amber-50/80";
  }

  if (value === "failed") {
    return "border-rose-200 bg-rose-50/80";
  }

  if (value === "queued") {
    return "border-sky-200 bg-sky-50/80";
  }

  return "border-slate-200 bg-white/95";
}

async function patchTask(
  workspaceId: number,
  projectId: number,
  taskId: number,
  payload: Record<string, unknown>,
) {
  const response = await fetch(
    `/api/workspaces/${workspaceId}/projects/${projectId}/tasks/${taskId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to update task ${taskId}: ${detail}`);
  }

  return (await response.json()) as Task;
}

function intersectsNode(box: MarqueeState, task: Task) {
  const minX = Math.min(box.start.x, box.current.x);
  const maxX = Math.max(box.start.x, box.current.x);
  const minY = Math.min(box.start.y, box.current.y);
  const maxY = Math.max(box.start.y, box.current.y);

  return !(
    task.canvas_x > maxX ||
    task.canvas_x + NODE_WIDTH < minX ||
    task.canvas_y > maxY ||
    task.canvas_y + NODE_HEIGHT < minY
  );
}

function getLatestActivityMessage(taskRun: TaskRun | null): string | null {
  if (!taskRun) {
    return null;
  }

  const payloads = [taskRun.input_payload, taskRun.output_payload];
  const entries: Array<{ timestamp: string; message: string }> = [];
  for (const payload of payloads) {
    const activityLog = payload?.activity_log;
    if (!Array.isArray(activityLog)) {
      continue;
    }
    for (const entry of activityLog) {
      if (typeof entry !== "object" || entry === null) {
        continue;
      }
      const timestamp = "timestamp" in entry ? String(entry.timestamp) : "";
      const message = "message" in entry ? String(entry.message) : "";
      if (!timestamp || !message) {
        continue;
      }
      entries.push({ timestamp, message });
    }
  }

  if (entries.length === 0) {
    return null;
  }

  entries.sort((left, right) => left.timestamp.localeCompare(right.timestamp));
  return entries[entries.length - 1]?.message ?? null;
}

function shouldIgnoreSpaceShortcut(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  const tagName = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select"
  );
}

export function WorkflowCanvas({
  workspaceId,
  projectId,
  tasks,
  agents,
  selectedRun,
}: WorkflowCanvasProps) {
  const router = useRouter();
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const [nodes, setNodes] = useState(tasks);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [panState, setPanState] = useState<PanState | null>(null);
  const [marqueeState, setMarqueeState] = useState<MarqueeState | null>(null);
  const [linkSourceId, setLinkSourceId] = useState<number | null>(null);
  const [hoveredLinkTargetId, setHoveredLinkTargetId] = useState<number | null>(null);
  const [previewPoint, setPreviewPoint] = useState<Point | null>(null);
  const [optimisticRunningTaskIds, setOptimisticRunningTaskIds] = useState<number[]>([]);
  const [savingTaskIds, setSavingTaskIds] = useState<number[]>([]);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [spacePressed, setSpacePressed] = useState(false);

  useEffect(() => {
    setNodes(tasks);
  }, [tasks]);

  useEffect(() => {
    setOptimisticRunningTaskIds([]);
  }, [selectedRun?.id, selectedRun?.updated_at]);

  useEffect(() => {
    const handleStart = (event: Event) => {
      const customEvent = event as CustomEvent<{ taskId?: number }>;
      const taskId = customEvent.detail?.taskId;
      if (!taskId) {
        return;
      }
      setOptimisticRunningTaskIds((current) =>
        current.includes(taskId) ? current : [...current, taskId],
      );
    };

    const handleEnd = (event: Event) => {
      const customEvent = event as CustomEvent<{ taskId?: number }>;
      const taskId = customEvent.detail?.taskId;
      if (!taskId) {
        return;
      }
      setOptimisticRunningTaskIds((current) => current.filter((item) => item !== taskId));
    };

    window.addEventListener("workflow-task-run-start", handleStart as EventListener);
    window.addEventListener("workflow-task-run-end", handleEnd as EventListener);

    return () => {
      window.removeEventListener("workflow-task-run-start", handleStart as EventListener);
      window.removeEventListener("workflow-task-run-end", handleEnd as EventListener);
    };
  }, []);

  const taskMap = useMemo(() => new Map(nodes.map((task) => [task.id, task])), [nodes]);
  const taskRunMap = useMemo(
    () => new Map((selectedRun?.task_runs ?? []).map((taskRun) => [taskRun.task_id, taskRun])),
    [selectedRun],
  );
  const editingTask = editingTaskId ? taskMap.get(editingTaskId) ?? null : null;
  const enabledAgents = useMemo(() => agents.filter((agent) => agent.is_enabled), [agents]);
  const canvasWidth = useMemo(() => {
    const maxX = Math.max(...nodes.map((task) => task.canvas_x + NODE_WIDTH), NODE_WIDTH);
    return maxX + MIN_GAP + CANVAS_PADDING;
  }, [nodes]);
  const canvasHeight = useMemo(() => {
    const maxY = Math.max(...nodes.map((task) => task.canvas_y + NODE_HEIGHT), NODE_HEIGHT);
    return maxY + MIN_GAP + CANVAS_PADDING;
  }, [nodes]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        if (shouldIgnoreSpaceShortcut(event.target)) {
          return;
        }
        event.preventDefault();
        setSpacePressed(true);
      }
    };

    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        if (shouldIgnoreSpaceShortcut(event.target)) {
          return;
        }
        event.preventDefault();
        setSpacePressed(false);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  const toCanvasPoint = useCallback((clientX: number, clientY: number): Point => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return { x: 0, y: 0 };
    }

    const bounds = viewport.getBoundingClientRect();
    return {
      x: (clientX - bounds.left + viewport.scrollLeft) / zoom,
      y: (clientY - bounds.top + viewport.scrollTop) / zoom,
    };
  }, [zoom]);

  useEffect(() => {
    if (!dragState && !panState && !marqueeState && !linkSourceId) {
      return;
    }

    const onPointerMove = (event: PointerEvent) => {
      const pointer = toCanvasPoint(event.clientX, event.clientY);

      if (dragState) {
        const deltaX = pointer.x - dragState.initialPointer.x;
        const deltaY = pointer.y - dragState.initialPointer.y;
        setNodes((current) =>
          current.map((task) => {
            if (!dragState.taskIds.includes(task.id)) {
              return task;
            }
            const initialPosition = dragState.initialPositions[task.id];
            return {
              ...task,
              canvas_x: Math.max(24, initialPosition.x + deltaX),
              canvas_y: Math.max(24, initialPosition.y + deltaY),
            };
          }),
        );
      }

      if (panState) {
        const viewport = viewportRef.current;
        if (viewport) {
          viewport.scrollLeft =
            panState.initialScroll.x - (event.clientX - panState.initialPointer.x);
          viewport.scrollTop =
            panState.initialScroll.y - (event.clientY - panState.initialPointer.y);
        }
      }

      if (marqueeState) {
        setMarqueeState((current) =>
          current
            ? {
                ...current,
                current: pointer,
              }
            : current,
        );
      }

      if (linkSourceId) {
        setPreviewPoint(pointer);
      }
    };

    const onPointerUp = async () => {
      const completedDrag = dragState;
      const completedMarquee = marqueeState;

      setDragState(null);
      setPanState(null);
      setMarqueeState(null);

      if (completedMarquee) {
        const nextSelection = nodes
          .filter((task) => intersectsNode(completedMarquee, task))
          .map((task) => task.id);
        setSelectedIds(nextSelection);
      }

      if (!completedDrag) {
        return;
      }

      const movedTasks = nodes.filter((task) => completedDrag.taskIds.includes(task.id));
      setSavingTaskIds(movedTasks.map((task) => task.id));
      try {
        await Promise.all(
          movedTasks.map((task) =>
            patchTask(workspaceId, projectId, task.id, {
              canvas_x: Math.round(task.canvas_x),
              canvas_y: Math.round(task.canvas_y),
            }),
          ),
        );
        router.refresh();
      } finally {
        setSavingTaskIds([]);
      }
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [
    dragState,
    linkSourceId,
    marqueeState,
    nodes,
    panState,
    projectId,
    router,
    workspaceId,
    toCanvasPoint,
  ]);

  const handleViewportPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("[data-node-card='true']")) {
      return;
    }

    if (linkSourceId) {
      setLinkSourceId(null);
      setHoveredLinkTargetId(null);
      setPreviewPoint(null);
      return;
    }

    if (spacePressed) {
      setPanState({
        initialPointer: { x: event.clientX, y: event.clientY },
        initialScroll: {
          x: viewportRef.current?.scrollLeft ?? 0,
          y: viewportRef.current?.scrollTop ?? 0,
        },
      });
      return;
    }

    const start = toCanvasPoint(event.clientX, event.clientY);
    setSelectedIds([]);
    setMarqueeState({
      start,
      current: start,
    });
  };

  const handleCardPointerDown = (
    event: ReactPointerEvent<HTMLElement>,
    taskId: number,
  ) => {
    if ((event.target as HTMLElement).closest("[data-node-control='true']")) {
      return;
    }

    const currentSelection = selectedIds.includes(taskId) ? selectedIds : [taskId];
    setSelectedIds(currentSelection);

    const pointer = toCanvasPoint(event.clientX, event.clientY);
    const initialPositions = Object.fromEntries(
      nodes
        .filter((task) => currentSelection.includes(task.id))
        .map((task) => [task.id, { x: task.canvas_x, y: task.canvas_y }]),
    );

    setDragState({
      taskIds: currentSelection,
      initialPointer: pointer,
      initialPositions,
    });
  };

  const handleNodeClick = async (taskId: number) => {
    if (linkSourceId && linkSourceId !== taskId) {
      await handleConnect(taskId);
      return;
    }

    if (!linkSourceId) {
      setSelectedIds([taskId]);
    }
  };

  const handleConnect = async (targetTaskId: number) => {
    if (!linkSourceId || linkSourceId === targetTaskId) {
      setLinkSourceId(null);
      setHoveredLinkTargetId(null);
      setPreviewPoint(null);
      return;
    }

    const targetTask = taskMap.get(targetTaskId);
    if (!targetTask) {
      setLinkSourceId(null);
      setPreviewPoint(null);
      return;
    }

    const nextDependencies = Array.from(
      new Set([...targetTask.task_dependencies, linkSourceId]),
    );

    setSavingTaskIds([targetTaskId]);
    try {
      await patchTask(workspaceId, projectId, targetTaskId, {
        task_dependencies: nextDependencies,
      });
      setLinkSourceId(null);
      setHoveredLinkTargetId(null);
      setPreviewPoint(null);
      router.refresh();
    } finally {
      setSavingTaskIds([]);
    }
  };

  const handleRemoveEdge = async (dependencyId: number, taskId: number) => {
    const task = taskMap.get(taskId);
    if (!task) {
      return;
    }

    setSavingTaskIds([taskId]);
    try {
      await patchTask(workspaceId, projectId, taskId, {
        task_dependencies: task.task_dependencies.filter((item) => item !== dependencyId),
      });
      router.refresh();
    } finally {
      setSavingTaskIds([]);
    }
  };

  const handleSaveConfig = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingTask) {
      return;
    }

    const formData = new FormData(event.currentTarget);
    const title = String(formData.get("title") ?? "").trim();
    const description = String(formData.get("description") ?? "").trim();
    const status = String(formData.get("status") ?? editingTask.status);
    const priority = String(formData.get("priority") ?? editingTask.priority);
    const rawAgentId = String(formData.get("agent_id") ?? "").trim();
    const taskDependencies = String(formData.get("task_dependencies") ?? "")
      .split(",")
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isInteger(item) && item > 0);

    setSavingTaskIds([editingTask.id]);
    try {
      await patchTask(workspaceId, projectId, editingTask.id, {
        title,
        description,
        status,
        priority,
        agent_id:
          rawAgentId === ""
            ? null
            : Number.isInteger(Number(rawAgentId)) && Number(rawAgentId) > 0
              ? Number(rawAgentId)
              : undefined,
        task_dependencies: editingTask.node_type === "start" ? [] : taskDependencies,
      });
      setEditingTaskId(null);
      router.refresh();
    } finally {
      setSavingTaskIds([]);
    }
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!spacePressed) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }

    const bounds = viewport.getBoundingClientRect();
    const pointerOffsetX = event.clientX - bounds.left;
    const pointerOffsetY = event.clientY - bounds.top;
    const canvasPointX = (viewport.scrollLeft + pointerOffsetX) / zoom;
    const canvasPointY = (viewport.scrollTop + pointerOffsetY) / zoom;
    const delta = event.deltaY < 0 ? 0.1 : -0.1;
    const nextZoom = Math.min(2, Math.max(0.5, Number((zoom + delta).toFixed(2))));

    if (nextZoom === zoom) {
      return;
    }

    setZoom(nextZoom);

    requestAnimationFrame(() => {
      const nextViewport = viewportRef.current;
      if (!nextViewport) {
        return;
      }

      nextViewport.scrollLeft = Math.max(0, canvasPointX * nextZoom - pointerOffsetX);
      nextViewport.scrollTop = Math.max(0, canvasPointY * nextZoom - pointerOffsetY);
    });
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.12),_transparent_45%),linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-3 text-sm text-slate-600">
            <span className="rounded-full bg-white px-4 py-2">框选支持多选节点</span>
            <span className="rounded-full bg-white px-4 py-2">按住空格可拖动画布</span>
            <span className="rounded-full bg-white px-4 py-2">按住空格再滚轮可缩放画布</span>
            <span className="rounded-full bg-white px-4 py-2">右键连线可直接删除</span>
            {selectedRun ? (
              <span className="rounded-full bg-emerald-100 px-4 py-2 text-emerald-800">
                当前显示 Run #{selectedRun.id} / {selectedRun.status}
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-4 py-2 text-slate-600">
                当前展示模板层节点状态
              </span>
            )}
            {linkSourceId ? (
              <span className="rounded-full bg-amber-100 px-4 py-2 text-amber-800">
                正在从 #{linkSourceId} 拉线，点击目标节点完成连接
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap items-start justify-end gap-3">
            {selectedRun && selectedRun.status !== "completed" ? (
              <div data-node-control="true">
                <ExecuteWorkflowRunButton
                  workspaceId={workspaceId}
                  projectId={projectId}
                  workflowRunId={selectedRun.id}
                  label={
                    selectedRun.status === "queued"
                      ? "继续执行 Workflow"
                      : "执行整个 Workflow"
                  }
                />
              </div>
            ) : null}

            <div className="flex items-center gap-3 rounded-full bg-white px-3 py-2 text-sm text-slate-700">
              <button
                type="button"
                onClick={() => setZoom((current) => Math.max(0.5, current - 0.1))}
                className="rounded-full bg-slate-100 px-3 py-1 transition hover:bg-slate-200"
              >
                -
              </button>
              <span>{Math.round(zoom * 100)}%</span>
              <button
                type="button"
                onClick={() => setZoom((current) => Math.min(2, current + 0.1))}
                className="rounded-full bg-slate-100 px-3 py-1 transition hover:bg-slate-200"
              >
                +
              </button>
            </div>
          </div>
        </div>

        <div
          ref={viewportRef}
          onWheelCapture={handleWheel}
          onWheel={handleWheel}
          onPointerDown={handleViewportPointerDown}
          className={`overflow-scroll overscroll-none rounded-[24px] border border-slate-200 bg-white/60 p-4 ${
            spacePressed ? "cursor-grab" : "cursor-default"
          }`}
          style={{ height: VIEWPORT_HEIGHT }}
        >
          <div
            className="relative"
            style={{
              width: `${canvasWidth * zoom}px`,
              height: `${canvasHeight * zoom}px`,
            }}
          >
            <div
              className="absolute left-0 top-0 origin-top-left rounded-[24px] bg-[linear-gradient(180deg,_rgba(255,255,255,0.65)_0%,_rgba(241,245,249,0.85)_100%)]"
              style={{
                width: `${canvasWidth}px`,
                height: `${canvasHeight}px`,
                transform: `scale(${zoom})`,
              }}
            >
              <svg
                className="absolute inset-0"
                width={canvasWidth}
                height={canvasHeight}
                viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
                fill="none"
              >
                <defs>
                  <marker
                    id="workflow-arrow"
                    markerWidth="12"
                    markerHeight="12"
                    refX="10"
                    refY="6"
                    orient="auto"
                  >
                    <path d="M0,0 L12,6 L0,12 z" fill="#0f172a" />
                  </marker>
                  <marker
                    id="workflow-preview-arrow"
                    markerWidth="12"
                    markerHeight="12"
                    refX="10"
                    refY="6"
                    orient="auto"
                  >
                    <path d="M0,0 L12,6 L0,12 z" fill="#f59e0b" />
                  </marker>
                </defs>

                {nodes.flatMap((task) =>
                  task.task_dependencies.map((dependencyId) => {
                    const source = taskMap.get(dependencyId);
                    const target = taskMap.get(task.id);
                    if (!source || !target) {
                      return [];
                    }

                    const startX = source.canvas_x + NODE_WIDTH;
                    const startY = source.canvas_y + NODE_HEIGHT / 2;
                    const endX = target.canvas_x;
                    const endY = target.canvas_y + NODE_HEIGHT / 2;
                    const midX = (startX + endX) / 2;

                    return (
                      <path
                        key={`${dependencyId}-${task.id}`}
                        d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX - 14} ${endY}`}
                        stroke="#0f172a"
                        strokeWidth="2.5"
                        markerEnd="url(#workflow-arrow)"
                        opacity="0.75"
                        className="cursor-pointer"
                        onContextMenu={(event) => {
                          event.preventDefault();
                          void handleRemoveEdge(dependencyId, task.id);
                        }}
                      />
                    );
                  }),
                )}

                {linkSourceId && (hoveredLinkTargetId || previewPoint) ? (() => {
                  const source = taskMap.get(linkSourceId);
                  if (!source) {
                    return null;
                  }
                  const hoveredTarget =
                    hoveredLinkTargetId ? taskMap.get(hoveredLinkTargetId) : null;
                  const startX = source.canvas_x + NODE_WIDTH;
                  const startY = source.canvas_y + NODE_HEIGHT / 2;
                  const endX = hoveredTarget
                    ? hoveredTarget.canvas_x
                    : (previewPoint?.x ?? startX);
                  const endY = hoveredTarget
                    ? hoveredTarget.canvas_y + NODE_HEIGHT / 2
                    : (previewPoint?.y ?? startY);
                  const midX = (startX + endX) / 2;
                  const targetX = hoveredTarget ? endX - 14 : endX;

                  return (
                    <path
                      d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${targetX} ${endY}`}
                      stroke="#f59e0b"
                      strokeWidth="3"
                      strokeDasharray="10 8"
                      markerEnd="url(#workflow-preview-arrow)"
                      opacity="0.9"
                    />
                  );
                })() : null}

                {marqueeState ? (
                  <rect
                    x={Math.min(marqueeState.start.x, marqueeState.current.x)}
                    y={Math.min(marqueeState.start.y, marqueeState.current.y)}
                    width={Math.abs(marqueeState.start.x - marqueeState.current.x)}
                    height={Math.abs(marqueeState.start.y - marqueeState.current.y)}
                    fill="rgba(14,165,233,0.12)"
                    stroke="#0ea5e9"
                    strokeDasharray="8 6"
                  />
                ) : null}
              </svg>

              {nodes.map((task) => {
                const taskRun = taskRunMap.get(task.id) ?? null;
                const runtimeStatus = optimisticRunningTaskIds.includes(task.id)
                  ? "in_progress"
                  : getRuntimeStatus(
                      task,
                      taskRun,
                      selectedRun?.status ?? null,
                    );
                const outputText =
                  taskRun?.output_payload &&
                  typeof taskRun.output_payload.text === "string"
                    ? taskRun.output_payload.text
                    : null;
                const latestActivityMessage = getLatestActivityMessage(taskRun);

                return (
                  <article
                    key={task.id}
                    data-node-card="true"
                    onPointerDown={(event) => handleCardPointerDown(event, task.id)}
                    onClick={() => {
                      void handleNodeClick(task.id);
                    }}
                    onPointerEnter={() => {
                      if (linkSourceId && linkSourceId !== task.id) {
                        setHoveredLinkTargetId(task.id);
                      }
                    }}
                    onPointerLeave={() => {
                      setHoveredLinkTargetId((current) =>
                        current === task.id ? null : current,
                      );
                    }}
                    className={`absolute cursor-grab rounded-[24px] border p-4 shadow-[0_18px_40px_rgba(15,23,42,0.08)] active:cursor-grabbing ${
                      selectedIds.includes(task.id)
                        ? "border-sky-400 ring-2 ring-sky-200"
                        : linkSourceId === task.id
                          ? "border-amber-400 ring-2 ring-amber-200"
                          : hoveredLinkTargetId === task.id
                            ? "border-amber-300 ring-2 ring-amber-100"
                          : getRuntimeCardTone(runtimeStatus)
                    }`}
                    style={{
                      left: `${task.canvas_x}px`,
                      top: `${task.canvas_y}px`,
                      width: `${NODE_WIDTH}px`,
                      minHeight: `${NODE_HEIGHT}px`,
                    }}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs uppercase tracking-[0.22em] text-slate-400">
                        {task.node_type === "start"
                          ? "Start"
                          : task.node_type === "end"
                            ? "End"
                            : "Task"}{" "}
                        #{task.id}
                      </span>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(runtimeStatus)}`}
                      >
                        {runtimeStatus}
                      </span>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${priorityTone(task.priority)}`}
                      >
                        {task.priority}
                      </span>
                      {taskRun ? (
                        <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-600">
                          Run: {taskRun.status}
                        </span>
                      ) : null}
                    </div>

                    <h3 className="mt-3 text-lg font-semibold text-slate-950">{task.title}</h3>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
                      {task.description || "这个节点还没有填写描述。"}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span className="rounded-full bg-white/80 px-3 py-1">
                        顺序 {task.display_order}
                      </span>
                      <span className="rounded-full bg-white/80 px-3 py-1">
                        依赖 {task.task_dependencies.length}
                      </span>
                      {taskRun?.assigned_agent_name ? (
                        <span className="rounded-full bg-white/80 px-3 py-1">
                          Agent {taskRun.assigned_agent_name}
                        </span>
                      ) : null}
                      {taskRun ? (
                        <span className="rounded-full bg-white/80 px-3 py-1">
                          Attempts {taskRun.attempt_count}
                        </span>
                      ) : null}
                      {savingTaskIds.includes(task.id) ? (
                        <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">
                          保存中
                        </span>
                      ) : null}
                    </div>

                    {taskRun?.error_message ? (
                      <p className="mt-4 rounded-2xl bg-rose-100 px-3 py-2 text-xs leading-6 text-rose-700">
                        {taskRun.error_message}
                      </p>
                    ) : null}

                    {latestActivityMessage ? (
                      <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/80 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-sky-500">
                          Activity
                        </p>
                        <p className="mt-1 line-clamp-3 text-xs leading-6 text-sky-900">
                          {latestActivityMessage}
                        </p>
                      </div>
                    ) : null}

                    {outputText ? (
                      <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          Output
                        </p>
                        <p className="mt-1 line-clamp-3 text-xs leading-6 text-slate-600">
                          {outputText}
                        </p>
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        data-node-control="true"
                        onClick={(event) => {
                          event.stopPropagation();
                          setEditingTaskId(task.id);
                        }}
                        className="rounded-2xl bg-slate-950 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
                      >
                        配置节点
                      </button>
                      <button
                        type="button"
                        data-node-control="true"
                        onClick={(event) => {
                          event.stopPropagation();
                          setLinkSourceId((current) => (current === task.id ? null : task.id));
                          setHoveredLinkTargetId(null);
                          setPreviewPoint(null);
                        }}
                        className="rounded-2xl bg-slate-100 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-200"
                      >
                        {linkSourceId === task.id ? "取消连线" : "开始连线"}
                      </button>
                      {selectedRun &&
                      taskRun &&
                      (taskRun.status === "ready" || taskRun.status === "failed") &&
                      taskRun.assigned_agent_id ? (
                        <div
                          data-node-control="true"
                          onPointerDown={(event) => event.stopPropagation()}
                          onClick={(event) => event.stopPropagation()}
                          className="w-full"
                        >
                          <ExecuteTaskRunButton
                            workspaceId={workspaceId}
                            projectId={projectId}
                            workflowRunId={selectedRun.id}
                            taskRunId={taskRun.id}
                            taskId={task.id}
                            label={taskRun.status === "failed" ? "重试这个 Task Run" : "执行这个 Task Run"}
                          />
                        </div>
                      ) : null}
                    </div>

                    <div className="mt-4 text-xs text-slate-400">
                      x:{Math.round(task.canvas_x)} y:{Math.round(task.canvas_y)}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {editingTask ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/20 backdrop-blur-[1px]">
          <button
            type="button"
            aria-label="关闭节点配置"
            onClick={() => setEditingTaskId(null)}
            className="absolute inset-0 cursor-default"
          />

          <section className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-[-30px_0_80px_rgba(15,23,42,0.16)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-500">Node Config</p>
                <h3 className="mt-1 text-xl font-semibold text-slate-950">
                  配置 #{editingTask.id} {editingTask.title}
                </h3>
                <p className="mt-2 text-sm text-slate-600">
                  这里调整的是模板层节点配置；运行态状态会随当前选中的 Workflow Run 自动映射到画布上。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingTaskId(null)}
                className="rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
              >
                关闭
              </button>
            </div>

            {selectedRun ? (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                当前查看 Run #{selectedRun.id}
                {taskRunMap.get(editingTask.id) ? (
                  <span>
                    {" "}
                    / 节点运行态{" "}
                    {getRuntimeStatus(
                      editingTask,
                      taskRunMap.get(editingTask.id) ?? null,
                      selectedRun.status,
                    )}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-2">
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(editingTask.status)}`}
              >
                {editingTask.status}
              </span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${priorityTone(editingTask.priority)}`}
              >
                {editingTask.priority}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {editingTask.node_type}
              </span>
            </div>

            <form onSubmit={handleSaveConfig} className="mt-6 grid gap-4">
              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">节点名称</span>
                <input
                  name="title"
                  required
                  defaultValue={editingTask.title}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">节点描述</span>
                <textarea
                  name="description"
                  rows={4}
                  defaultValue={editingTask.description ?? ""}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">依赖节点 ID</span>
                <input
                  name="task_dependencies"
                  defaultValue={editingTask.task_dependencies.join(",")}
                  disabled={editingTask.node_type === "start"}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300 disabled:bg-slate-100"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">分配 Agent</span>
                <select
                  name="agent_id"
                  defaultValue={editingTask.agent_id ?? ""}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
                >
                  <option value="">暂不分配</option>
                  {enabledAgents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} / {agent.provider_model_label}
                    </option>
                  ))}
                </select>
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">模板状态</span>
                  <select
                    name="status"
                    defaultValue={editingTask.status}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
                  >
                    <option value="todo">todo</option>
                    <option value="in_progress">in_progress</option>
                    <option value="done">done</option>
                  </select>
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">优先级</span>
                  <select
                    name="priority"
                    defaultValue={editingTask.priority}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </label>
              </div>

              <button
                type="submit"
                className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                保存节点配置
              </button>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
