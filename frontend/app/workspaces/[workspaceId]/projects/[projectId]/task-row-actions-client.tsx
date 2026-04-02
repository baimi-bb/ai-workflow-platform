"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  submitDeleteTaskAction,
  submitTaskEditFormAction,
  submitTaskStatusFormAction,
  type TaskActionState,
} from "@/lib/actions";
import type { Agent, Task } from "@/lib/types";

const INITIAL_ACTION_STATE: TaskActionState = {
  ok: false,
  message: null,
};

type TaskRowActionsClientProps = {
  task: Task;
  agents: Agent[];
  workspaceId: number;
  projectId: number;
};

export default function TaskRowActionsClient({
  task,
  agents,
  workspaceId,
  projectId,
}: TaskRowActionsClientProps) {
  const statusSelectRef = useRef<HTMLSelectElement>(null);
  const actionsPanelRef = useRef<HTMLDetailsElement>(null);
  const editPanelRef = useRef<HTMLDetailsElement>(null);

  const [statusState, statusAction, statusPending] = useActionState(
    submitTaskStatusFormAction.bind(null, workspaceId, projectId, task.id),
    INITIAL_ACTION_STATE,
  );
  const [editState, editAction, editPending] = useActionState(
    submitTaskEditFormAction.bind(null, workspaceId, projectId, task.id),
    INITIAL_ACTION_STATE,
  );
  const [deleteState, deleteAction, deletePending] = useActionState(
    submitDeleteTaskAction.bind(null, workspaceId, projectId, task.id),
    INITIAL_ACTION_STATE,
  );

  useEffect(() => {
    if (!statusState.message) {
      return;
    }

    if (!statusState.ok && statusSelectRef.current) {
      statusSelectRef.current.value = task.status;
    }

    window.alert(statusState.message);
  }, [statusState, task.status]);

  useEffect(() => {
    if (!editState.message) {
      return;
    }

    if (editState.ok) {
      if (editPanelRef.current) {
        editPanelRef.current.open = false;
      }

      if (actionsPanelRef.current) {
        actionsPanelRef.current.open = false;
      }
      return;
    }

    window.alert(editState.message);
  }, [editState]);

  useEffect(() => {
    if (!deleteState.message) {
      return;
    }

    if (deleteState.ok) {
      if (actionsPanelRef.current) {
        actionsPanelRef.current.open = false;
      }
      return;
    }

    window.alert(deleteState.message);
  }, [deleteState]);

  const isProtectedNode = task.node_type === "start" || task.node_type === "end";
  const enabledAgents = agents.filter((agent) => agent.is_enabled);

  return (
    <div className="flex min-w-72 flex-col gap-3">
      <form
        action={statusAction}
        className="grid gap-3 rounded-[20px] border border-slate-200 bg-slate-50 p-4"
      >
        <label className="space-y-2">
          <span className="text-sm font-medium text-slate-700">更新状态</span>
          <select
            ref={statusSelectRef}
            name="status"
            defaultValue={task.status}
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-orange-300"
          >
            <option value="todo">todo</option>
            <option value="in_progress">in_progress</option>
            <option value="done">done</option>
          </select>
        </label>

        <button
          type="submit"
          disabled={statusPending}
          className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {statusPending ? "更新中..." : "确认更新状态"}
        </button>
      </form>

      <details
        ref={actionsPanelRef}
        className="rounded-[20px] border border-slate-200 bg-slate-50 p-2"
      >
        <summary className="flex cursor-pointer list-none items-center justify-center rounded-[14px] px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-white">
          <span className="font-mono text-base leading-none">...</span>
        </summary>

        <div className="mt-2 grid gap-2 border-t border-slate-200 pt-3">
          <details ref={editPanelRef} className="rounded-[16px] bg-white p-3">
            <summary className="cursor-pointer list-none rounded-xl bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-sky-500">
              编辑
            </summary>

            <form action={editAction} className="mt-3 grid gap-3">
              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">标题</span>
                <input
                  name="title"
                  required
                  defaultValue={task.title}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">描述</span>
                <textarea
                  name="description"
                  rows={3}
                  defaultValue={task.description ?? ""}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">分配 Agent</span>
                <select
                  name="agent_id"
                  defaultValue={task.agent_id ?? ""}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                >
                  <option value="">暂不分配</option>
                  {enabledAgents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} / {agent.provider_model_label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">依赖任务 ID</span>
                <input
                  name="task_dependencies"
                  defaultValue={task.task_dependencies.join(",")}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">优先级</span>
                <select
                  name="priority"
                  defaultValue={task.priority}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                >
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
              </label>

              <button
                type="submit"
                disabled={editPending}
                className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {editPending ? "保存中..." : "确认编辑"}
              </button>
            </form>
          </details>

          <details className="rounded-[16px] bg-white p-3">
            <summary className="cursor-pointer list-none rounded-xl bg-rose-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-rose-500">
              删除
            </summary>

            {isProtectedNode ? (
              <p className="mt-3 text-sm text-slate-600">
                {task.node_type === "start"
                  ? "Start 节点由系统自动创建，不能删除。"
                  : "End 节点由系统自动创建，不能删除。"}
              </p>
            ) : (
              <form
                action={deleteAction}
                className="mt-3 grid gap-3"
              >
                <p className="text-sm text-slate-600">确认删除这个 task 吗？</p>
                <button
                  type="submit"
                  disabled={deletePending}
                  className="rounded-2xl bg-rose-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {deletePending ? "删除中..." : "确认删除"}
                </button>
              </form>
            )}
          </details>
        </div>
      </details>
    </div>
  );
}
