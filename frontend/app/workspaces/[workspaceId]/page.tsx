import Link from "next/link";

import {
  createAgentAction,
  createProjectAction,
  deleteAgentAction,
  deleteProjectAction,
  deleteWorkspaceAction,
  toggleAgentAction,
  updateProjectAction,
  updateWorkspaceAction,
} from "@/lib/actions";
import { getWorkspace, listProviderModels, listWorkspaceFiles } from "@/lib/api";
import { formatDate, statusTone } from "@/lib/ui";

type PageProps = {
  params: Promise<{
    workspaceId: string;
  }>;
  searchParams?: Promise<{
    path?: string;
  }>;
};

function formatBytes(size: number | null) {
  if (size === null) {
    return "-";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function buildBreadcrumbs(path: string) {
  if (!path) {
    return [];
  }

  const parts = path.split("/").filter(Boolean);
  return parts.map((part, index) => ({
    label: part,
    path: parts.slice(0, index + 1).join("/"),
  }));
}

function getParentPath(path: string) {
  if (!path) {
    return "";
  }

  const parts = path.split("/").filter(Boolean);
  return parts.slice(0, -1).join("/");
}

export default async function WorkspacePage({ params, searchParams }: PageProps) {
  const { workspaceId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const currentPath = resolvedSearchParams.path ?? "";
  const numericWorkspaceId = Number(workspaceId);

  const [workspace, workspaceFiles, providerModels] = await Promise.all([
    getWorkspace(numericWorkspaceId),
    listWorkspaceFiles(numericWorkspaceId, currentPath),
    listProviderModels(),
  ]);

  const availableProviderModels = providerModels.filter((item) => item.is_enabled);
  const breadcrumbs = buildBreadcrumbs(workspaceFiles.current_path);
  const parentPath = getParentPath(workspaceFiles.current_path);

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,_#fff7ed_0%,_#ffffff_35%,_#eff6ff_100%)] px-4 py-8 text-slate-900 md:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <section className="rounded-[32px] border border-white/70 bg-white/90 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)] md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <Link
                href="/"
                className="inline-flex rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
              >
                返回 Workspace 首页
              </Link>

              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.26em] text-orange-600">
                  Workspace Detail
                </p>
                <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
                  {workspace.name}
                </h1>
              </div>

              <p className="max-w-3xl text-base leading-8 text-slate-600">
                {workspace.description || "这个 workspace 暂时还没有描述。"}
              </p>

              <div className="max-w-3xl rounded-[22px] border border-slate-200 bg-slate-50 px-5 py-4">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                  Workspace Root Path
                </p>
                <p className="mt-2 break-all font-mono text-sm leading-7 text-slate-700">
                  {workspace.root_path || "未设置"}
                </p>
              </div>
            </div>

            <div className="flex flex-col items-stretch gap-3">
              <div className="grid gap-3 rounded-[24px] bg-slate-950 p-5 text-sm text-slate-100">
                <div className="flex items-center justify-between gap-4">
                  <span>Projects</span>
                  <span>{workspace.projects.length}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Agents</span>
                  <span>{workspace.agents.length}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Updated</span>
                  <span>{formatDate(workspace.updated_at)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>Files</span>
                  <span>{workspaceFiles.entries.length}</span>
                </div>
              </div>

              <details className="rounded-[24px] border border-slate-200 bg-white p-3 shadow-[0_12px_30px_rgba(15,23,42,0.06)]">
                <summary className="flex cursor-pointer list-none items-center justify-between rounded-[18px] px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                  <span>Workspace 操作</span>
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
                      action={updateWorkspaceAction.bind(null, workspace.id)}
                      className="mt-3 grid gap-3"
                    >
                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">名称</span>
                        <input
                          name="name"
                          required
                          defaultValue={workspace.name}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-orange-300"
                        />
                      </label>

                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">描述</span>
                        <textarea
                          name="description"
                          rows={4}
                          defaultValue={workspace.description ?? ""}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-orange-300"
                        />
                      </label>

                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">
                          Workspace 路径
                        </span>
                        <input
                          name="root_path"
                          required
                          defaultValue={workspace.root_path ?? ""}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 font-mono outline-none transition focus:border-orange-300"
                        />
                      </label>

                      <button
                        type="submit"
                        className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
                      >
                        确认编辑
                      </button>
                    </form>
                  </details>

                  <details className="rounded-[16px] bg-slate-50 p-3">
                    <summary className="cursor-pointer list-none rounded-xl bg-rose-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-rose-500">
                      删除
                    </summary>

                    <form
                      action={deleteWorkspaceAction.bind(null, workspace.id)}
                      className="mt-3 grid gap-3"
                    >
                      <p className="text-sm text-slate-600">
                        确认删除当前 workspace 吗？
                      </p>
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

        <section className="rounded-[28px] border border-violet-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Agents</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                Workspace Agents
              </h2>
            </div>

            <details className="w-full max-w-xl rounded-[22px] border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer list-none rounded-[16px] bg-slate-950 px-4 py-3 text-center text-sm font-medium text-white transition hover:bg-slate-800">
                新增 Agent
              </summary>

              <form
                action={createAgentAction.bind(null, workspace.id)}
                className="mt-4 grid gap-3"
              >
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">ModelConfig</span>
                  <select
                    name="provider_model_id"
                    required
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-violet-300"
                  >
                    <option value="">请选择模型配置</option>
                    {availableProviderModels.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.provider_label} / {item.label} / {item.model_name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">Agent 名称</span>
                  <input
                    name="name"
                    required
                    placeholder="例如：Research Agent"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-violet-300"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">描述</span>
                  <textarea
                    name="description"
                    rows={3}
                    placeholder="说明这个 agent 的职责"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-violet-300"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">System Prompt</span>
                  <textarea
                    name="system_prompt"
                    rows={5}
                    placeholder="默认提示词"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-violet-300"
                  />
                </label>

                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    name="is_enabled"
                    value="true"
                    defaultChecked
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  创建后立即启用
                </label>

                <button
                  type="submit"
                  className="rounded-2xl bg-violet-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-violet-500"
                >
                  创建 Agent
                </button>
              </form>
            </details>
          </div>

          {workspace.agents.length === 0 ? (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
              这个 workspace 里还没有 agent，请先从上方选择 ModelConfig 创建一个。
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {workspace.agents.map((agent) => (
                <article
                  key={agent.id}
                  className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                        Agent #{agent.id}
                      </p>
                      <h3 className="mt-2 text-xl font-semibold text-slate-950">
                        {agent.name}
                      </h3>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        agent.is_enabled
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {agent.is_enabled ? "enabled" : "disabled"}
                    </span>
                  </div>

                  <p className="mt-4 min-h-[3.5rem] text-sm leading-7 text-slate-600">
                    {agent.description || "这个 agent 还没有描述。"}
                  </p>

                  <div className="mt-4 space-y-2 rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                    <p>
                      ModelConfig:{" "}
                      <span className="font-medium text-slate-900">
                        {agent.provider_model_label}
                      </span>
                    </p>
                    <p>
                      Model Name:{" "}
                      <span className="font-mono text-slate-900">
                        {agent.provider_model_name}
                      </span>
                    </p>
                    <p>
                      Provider:{" "}
                      <span className="font-medium text-slate-900">
                        {agent.provider_label}
                      </span>
                    </p>
                    <p>
                      并发上限:{" "}
                      <span className="font-medium text-slate-900">
                        {agent.max_concurrency}
                      </span>
                    </p>
                  </div>

                  <div className="mt-5 flex flex-wrap items-center gap-3">
                    <form
                      action={toggleAgentAction.bind(
                        null,
                        workspace.id,
                        agent.id,
                        !agent.is_enabled,
                      )}
                    >
                      <button
                        type="submit"
                        className="rounded-full bg-slate-950 px-4 py-2 text-sm text-white transition hover:bg-slate-800"
                      >
                        {agent.is_enabled ? "禁用 Agent" : "启用 Agent"}
                      </button>
                    </form>

                    <form action={deleteAgentAction.bind(null, workspace.id, agent.id)}>
                      <button
                        type="submit"
                        className="rounded-full bg-rose-100 px-4 py-2 text-sm text-rose-700 transition hover:bg-rose-200"
                      >
                        删除 Agent
                      </button>
                    </form>

                    <span className="ml-auto text-sm text-slate-400">
                      更新于 {formatDate(agent.updated_at)}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="rounded-[28px] border border-orange-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
            <div className="mb-5">
              <p className="text-sm font-medium text-slate-500">创建 Project</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                往这个 Workspace 里加项目
              </h2>
            </div>

            <form action={createProjectAction.bind(null, workspace.id)} className="space-y-4">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">名称</span>
                <input
                  name="name"
                  required
                  placeholder="例如：前端重构"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">描述</span>
                <textarea
                  name="description"
                  rows={4}
                  placeholder="简单说明这个 project 的目标"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">状态</span>
                <select
                  name="status"
                  defaultValue="active"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                >
                  <option value="active">active</option>
                  <option value="paused">paused</option>
                  <option value="done">done</option>
                </select>
              </label>

              <button
                type="submit"
                className="w-full rounded-2xl bg-orange-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-orange-400"
              >
                创建 Project
              </button>
            </form>
          </aside>

          <section className="rounded-[28px] border border-sky-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-500">Project 列表</p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                  当前 Workspace 下的项目
                </h2>
              </div>
              <div className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                {workspace.projects.length} 个
              </div>
            </div>

            {workspace.projects.length === 0 ? (
              <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
                这里还没有 project，可以先在左侧创建。
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {workspace.projects.map((project) => (
                  <article
                    key={project.id}
                    className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] p-5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                          Project #{project.id}
                        </p>
                        <h3 className="mt-2 text-xl font-semibold text-slate-950">
                          {project.name}
                        </h3>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(project.status)}`}
                      >
                        {project.status}
                      </span>
                    </div>

                    <p className="mt-4 min-h-[4.5rem] text-sm leading-7 text-slate-600">
                      {project.description || "这个 project 还没有填写描述。"}
                    </p>

                    <div className="mt-6 flex items-center justify-between text-sm text-slate-500">
                      <span>{project.tasks.length} 个 tasks</span>
                      <span>{formatDate(project.updated_at)}</span>
                    </div>

                    <div className="mt-5 flex items-center justify-between gap-3">
                      <Link
                        href={`/workspaces/${workspace.id}/projects/${project.id}`}
                        className="inline-flex rounded-full bg-slate-950 px-4 py-2 text-sm text-white transition hover:bg-slate-800"
                      >
                        进入 Project 页面
                      </Link>

                      <details className="rounded-[20px] border border-slate-200 bg-slate-50 p-2">
                        <summary className="flex cursor-pointer list-none items-center justify-center rounded-[14px] px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-white">
                          <span className="font-mono text-base leading-none">...</span>
                        </summary>

                        <div className="mt-2 grid min-w-64 gap-2 border-t border-slate-200 pt-3">
                          <details className="rounded-[16px] bg-white p-3">
                            <summary className="cursor-pointer list-none rounded-xl bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-sky-500">
                              编辑
                            </summary>

                            <form
                              action={updateProjectAction.bind(
                                null,
                                workspace.id,
                                project.id,
                              )}
                              className="mt-3 grid gap-3"
                            >
                              <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">
                                  名称
                                </span>
                                <input
                                  name="name"
                                  required
                                  defaultValue={project.name}
                                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                                />
                              </label>

                              <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">
                                  描述
                                </span>
                                <textarea
                                  name="description"
                                  rows={3}
                                  defaultValue={project.description ?? ""}
                                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
                                />
                              </label>

                              <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">
                                  状态
                                </span>
                                <select
                                  name="status"
                                  defaultValue={project.status}
                                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
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
                                确认编辑
                              </button>
                            </form>
                          </details>

                          <details className="rounded-[16px] bg-white p-3">
                            <summary className="cursor-pointer list-none rounded-xl bg-rose-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-rose-500">
                              删除
                            </summary>

                            <form
                              action={deleteProjectAction.bind(
                                null,
                                workspace.id,
                                project.id,
                              )}
                              className="mt-3 grid gap-3"
                            >
                              <p className="text-sm text-slate-600">
                                确认删除这个 project 吗？
                              </p>
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
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>

        <section className="rounded-[28px] border border-emerald-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-500">Workspace 文件</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                当前目录内容
              </h2>
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
              {workspaceFiles.entries.length} 项
            </div>
          </div>

          <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-5 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
              Listing Root
            </p>
            <p className="mt-2 break-all font-mono text-sm leading-7 text-slate-700">
              {workspaceFiles.root_path}
            </p>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2 rounded-[22px] border border-slate-200 bg-white px-4 py-3">
            <Link
              href={`/workspaces/${workspace.id}`}
              className={`rounded-full px-3 py-1 text-sm transition ${
                !workspaceFiles.current_path
                  ? "bg-slate-950 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              根目录
            </Link>

            {breadcrumbs.map((crumb) => (
              <Link
                key={crumb.path}
                href={`/workspaces/${workspace.id}?path=${encodeURIComponent(crumb.path)}`}
                className={`rounded-full px-3 py-1 text-sm transition ${
                  crumb.path === workspaceFiles.current_path
                    ? "bg-slate-950 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {crumb.label}
              </Link>
            ))}

            {workspaceFiles.current_path ? (
              <Link
                href={
                  parentPath
                    ? `/workspaces/${workspace.id}?path=${encodeURIComponent(parentPath)}`
                    : `/workspaces/${workspace.id}`
                }
                className="ml-auto rounded-full bg-emerald-100 px-3 py-1 text-sm text-emerald-800 transition hover:bg-emerald-200"
              >
                返回上级
              </Link>
            ) : null}
          </div>

          {workspaceFiles.entries.length === 0 ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
              这个目录下暂时没有可展示的文件或文件夹。
            </div>
          ) : (
            <div className="mt-5 overflow-hidden rounded-[24px] border border-slate-200">
              <div className="grid grid-cols-[140px_minmax(0,1fr)_140px_180px] gap-4 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <span>Type</span>
                <span>Name</span>
                <span>Size</span>
                <span>Modified</span>
              </div>

              <div className="divide-y divide-slate-200 bg-white">
                {workspaceFiles.entries.map((entry) => (
                  <div
                    key={entry.relative_path}
                    className="grid grid-cols-[140px_minmax(0,1fr)_140px_180px] gap-4 px-5 py-4 text-sm text-slate-700"
                  >
                    <span
                      className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-medium ${
                        entry.entry_type === "directory"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-sky-100 text-sky-800"
                      }`}
                    >
                      {entry.entry_type === "directory" ? "Folder" : "File"}
                    </span>

                    <div className="min-w-0">
                      {entry.entry_type === "directory" ? (
                        <Link
                          href={`/workspaces/${workspace.id}?path=${encodeURIComponent(entry.relative_path)}`}
                          className="truncate font-medium text-slate-900 underline-offset-4 hover:text-emerald-700 hover:underline"
                        >
                          {entry.name}
                        </Link>
                      ) : (
                        <p className="truncate font-medium text-slate-900">{entry.name}</p>
                      )}
                      <p className="truncate font-mono text-xs text-slate-500">
                        {entry.relative_path}
                      </p>
                    </div>

                    <span className="font-mono text-slate-500">
                      {formatBytes(entry.size)}
                    </span>

                    <span className="text-slate-500">
                      {entry.modified_at ? formatDate(entry.modified_at) : "-"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
