import Link from "next/link";
import type { ReactNode } from "react";

import {
  createTaskAction,
  deleteProjectAction,
  updateProjectAction,
} from "@/lib/actions";
import { getProject, getWorkspace, listTasks } from "@/lib/api";
import type { Agent, Project, Task, Workspace } from "@/lib/types";
import { formatDate, priorityTone, statusTone } from "@/lib/ui";

import { AiProjectPlannerForm } from "./ai-project-planner-form";
import TaskRowActionsClient from "./task-row-actions-client";

export type ProjectPageData = {
  workspace: Workspace;
  project: Project;
  tasks: Task[];
  workspaceId: number;
  projectId: number;
};

export async function getProjectPageData(
  workspaceId: number,
  projectId: number,
): Promise<ProjectPageData> {
  const [workspace, project, tasks] = await Promise.all([
    getWorkspace(workspaceId),
    getProject(workspaceId, projectId),
    listTasks(workspaceId, projectId),
  ]);

  return {
    workspace,
    project,
    tasks,
    workspaceId,
    projectId,
  };
}

export function unresolvedDependencyCount(
  task: { task_dependencies: number[] },
  tasks: { id: number; status: string }[],
) {
  const taskMap = new Map(tasks.map((item) => [item.id, item]));

  return task.task_dependencies.filter(
    (dependencyId) => taskMap.get(dependencyId)?.status !== "done",
  ).length;
}

type ProjectShellProps = ProjectPageData & {
  activeView: "list" | "workflow";
  asideContent?: ReactNode;
  children: ReactNode;
};

export function ProjectShell({
  workspace,
  project,
  tasks,
  workspaceId,
  projectId,
  activeView,
  asideContent,
  children,
}: ProjectShellProps) {
  const enabledAgents = workspace.agents.filter((agent) => agent.is_enabled);

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,_#eff6ff_0%,_#ffffff_35%,_#fff7ed_100%)] px-4 py-8 text-slate-900 md:px-8">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">
        <section className="rounded-[32px] border border-white/70 bg-white/90 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)] md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/"
                  className="inline-flex rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
                >
                  返回首页
                </Link>
                <Link
                  href={`/workspaces/${workspace.id}`}
                  className="inline-flex rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
                >
                  返回 {workspace.name}
                </Link>
              </div>

              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.26em] text-sky-600">
                  Project Detail
                </p>
                <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
                  {project.name}
                </h1>
              </div>

              <p className="max-w-3xl text-base leading-8 text-slate-600">
                {project.description || "这个 project 还没有描述。"}
              </p>

              <div className="flex flex-wrap gap-3 pt-2">
                <Link
                  href={`/workspaces/${workspaceId}/projects/${projectId}/list`}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activeView === "list"
                      ? "bg-slate-950 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  List / Table
                </Link>
                <Link
                  href={`/workspaces/${workspaceId}/projects/${projectId}/workflow`}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activeView === "workflow"
                      ? "bg-slate-950 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  Workflow
                </Link>
              </div>
            </div>

            <div className="flex flex-col items-stretch gap-3">
              <div className="grid gap-3 rounded-[24px] bg-slate-950 p-5 text-sm text-slate-100">
                <div className="flex items-center justify-between gap-4">
                  <span>Project Status</span>
                  <span className="capitalize">{project.status}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Tasks</span>
                  <span>{tasks.length}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Enabled Agents</span>
                  <span>{enabledAgents.length}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Updated</span>
                  <span>{formatDate(project.updated_at)}</span>
                </div>
              </div>

              <details className="rounded-[24px] border border-slate-200 bg-white p-3 shadow-[0_12px_30px_rgba(15,23,42,0.06)]">
                <summary className="flex cursor-pointer list-none items-center justify-between rounded-[18px] px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                  <span>Project 操作</span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-base leading-none text-slate-900">
                    ...
                  </span>
                </summary>

                <div className="mt-3 grid gap-2 border-t border-slate-200 pt-3">
                  <details className="rounded-[16px] bg-slate-50 p-3">
                    <summary className="cursor-pointer list-none rounded-xl bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-sky-500">
                      编辑
                    </summary>

                    <form
                      action={updateProjectAction.bind(null, workspaceId, projectId)}
                      className="mt-3 grid gap-3"
                    >
                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">名称</span>
                        <input
                          name="name"
                          required
                          defaultValue={project.name}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-sky-300"
                        />
                      </label>

                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">描述</span>
                        <textarea
                          name="description"
                          rows={4}
                          defaultValue={project.description ?? ""}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-sky-300"
                        />
                      </label>

                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">状态</span>
                        <select
                          name="status"
                          defaultValue={project.status}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-sky-300"
                        >
                          <option value="active">active</option>
                          <option value="paused">paused</option>
                          <option value="done">done</option>
                        </select>
                      </label>

                      <button
                        type="submit"
                        className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
                      >
                        保存修改
                      </button>
                    </form>
                  </details>

                  <details className="rounded-[16px] bg-slate-50 p-3">
                    <summary className="cursor-pointer list-none rounded-xl bg-rose-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-rose-500">
                      删除
                    </summary>

                    <form
                      action={deleteProjectAction.bind(null, workspaceId, projectId)}
                      className="mt-3 grid gap-3"
                    >
                      <p className="text-sm text-slate-600">确认删除当前 project 吗？</p>
                      <button
                        type="submit"
                        className="rounded-2xl bg-rose-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-rose-500"
                      >
                        确认删除
                      </button>
                    </form>
                  </details>
                </div>
              </details>
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="rounded-[28px] border border-sky-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
            <AiProjectPlannerForm
              workspaceId={workspaceId}
              projectId={projectId}
              plannerAgents={enabledAgents}
            />

            <div className="mb-5">
              <p className="text-sm font-medium text-slate-500">Create Task</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                在这个 Project 里添加任务
              </h2>
            </div>

            <form
              action={createTaskAction.bind(null, workspaceId, projectId)}
              className="space-y-4"
            >
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">标题</span>
                <input
                  name="title"
                  required
                  placeholder="例如：生成研究提纲"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">描述</span>
                <textarea
                  name="description"
                  rows={4}
                  placeholder="补充任务目标和输出要求"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">分配 Agent</span>
                <select
                  name="agent_id"
                  defaultValue=""
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                >
                  <option value="">暂不分配</option>
                  {enabledAgents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} / {agent.provider_model_label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">依赖任务 ID</span>
                <input
                  name="task_dependencies"
                  placeholder="例如：1,2"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                />
                <p className="text-xs leading-6 text-slate-500">
                  使用英文逗号分隔。只有依赖任务全部完成后，这个任务才能开始。
                </p>
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-700">状态</span>
                  <select
                    name="status"
                    defaultValue="todo"
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                  >
                    <option value="todo">todo</option>
                    <option value="in_progress">in_progress</option>
                    <option value="done">done</option>
                  </select>
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-700">优先级</span>
                  <select
                    name="priority"
                    defaultValue="medium"
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300 focus:bg-white"
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </label>
              </div>

              <button
                type="submit"
                className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                创建 Task
              </button>
            </form>

            {asideContent ? (
              <div className="mt-6 border-t border-slate-200 pt-6">{asideContent}</div>
            ) : null}
          </aside>

          <section>{children}</section>
        </section>
      </div>
    </main>
  );
}

export function TaskMetaBadges({ task, tasks }: { task: Task; tasks: Task[] }) {
  const unresolvedCount = unresolvedDependencyCount(task, tasks);

  return (
    <div className="flex flex-wrap gap-2 text-xs text-slate-600">
      <span className="rounded-full bg-slate-100 px-3 py-1">
        依赖: {task.task_dependencies.length > 0 ? task.task_dependencies.join(", ") : "无"}
      </span>
      <span className="rounded-full bg-slate-100 px-3 py-1">节点: {task.node_type}</span>
      {task.agent_name ? (
        <span className="rounded-full bg-violet-100 px-3 py-1 text-violet-800">
          Agent: {task.agent_name}
        </span>
      ) : (
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-500">
          Agent: 未分配
        </span>
      )}
      {unresolvedCount > 0 ? (
        <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">
          仍有 {unresolvedCount} 个依赖未完成
        </span>
      ) : (
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">
          已可执行
        </span>
      )}
    </div>
  );
}

export function TaskStatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(status)}`}>
      {status}
    </span>
  );
}

export function TaskPriorityBadge({ priority }: { priority: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${priorityTone(priority)}`}
    >
      {priority}
    </span>
  );
}

type TaskRowActionsProps = {
  task: Task;
  agents: Agent[];
  workspaceId: number;
  projectId: number;
};

export function TaskRowActions({
  task,
  agents,
  workspaceId,
  projectId,
}: TaskRowActionsProps) {
  return (
    <TaskRowActionsClient
      agents={agents}
      task={task}
      workspaceId={workspaceId}
      projectId={projectId}
    />
  );
}
