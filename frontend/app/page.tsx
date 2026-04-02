import Link from "next/link";

import {
  deleteProviderAction,
  deleteWorkspaceAction,
  toggleProviderAction,
  updateWorkspaceAction,
  createWorkspaceAction,
} from "@/lib/actions";
import ModelDrawerForm from "@/app/model-drawer-form";
import ProviderModelCard from "@/app/provider-model-card";
import ProviderDrawerForm from "@/app/provider-drawer-form";
import {
  apiBaseUrl,
  getHealth,
  listProviderModels,
  listProviders,
  listWorkspaces,
} from "@/lib/api";
import { formatDate, statusTone } from "@/lib/ui";

export default async function Home() {
  const [health, workspaces, providers, providerModels] = await Promise.all([
    getHealth(),
    listWorkspaces(),
    listProviders(),
    listProviderModels(),
  ]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,247,237,0.95)_0%,_rgba(255,255,255,1)_40%,_rgba(239,246,255,0.9)_100%)] px-4 py-8 text-slate-900 md:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <section className="overflow-hidden rounded-[32px] border border-orange-100 bg-white/90 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)] backdrop-blur md:p-10">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="max-w-3xl space-y-4">
              <p className="text-sm font-semibold uppercase tracking-[0.3em] text-orange-600">
                AI Workflow Platform
              </p>
              <h1 className="text-4xl font-semibold tracking-tight text-slate-950 md:text-6xl">
                Workspace 首页
              </h1>
              <p className="max-w-2xl text-base leading-8 text-slate-600 md:text-lg">
                这里展示已有 workspace，并提供创建入口。每个 workspace 都绑定一个本地目录，
                后续 project、task 和 agent 的文件读写都会以它作为根路径展开。
              </p>
            </div>

            <div className="grid gap-3 rounded-[24px] bg-slate-950 p-5 text-sm text-slate-100 shadow-xl">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  API Base
                </p>
                <p className="mt-1 font-mono">{apiBaseUrl}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Backend
                </p>
                <p className="mt-1">
                  {health ? `${health.status} / DB ${health.database}` : "Unavailable"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Providers / Models
                </p>
                <p className="mt-1">
                  {providers.length} / {providerModels.length}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="rounded-[28px] border border-orange-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
            <div className="mb-5">
              <p className="text-sm font-medium text-slate-500">创建 Workspace</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                新建一个工作空间
              </h2>
            </div>

            <form action={createWorkspaceAction} className="space-y-4">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">名称</span>
                <input
                  name="name"
                  required
                  placeholder="例如：市场调研工作台"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">描述</span>
                <textarea
                  name="description"
                  rows={4}
                  placeholder="简单说明这个 workspace 的用途"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Workspace 路径</span>
                <input
                  name="root_path"
                  required
                  placeholder="例如：D:\\AI\\market-research"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-orange-300 focus:bg-white"
                />
                <p className="text-xs leading-6 text-slate-500">
                  这里填写本地目录路径，后续 project 和 task 的文件读写都以这个目录作为根路径。
                </p>
              </label>

              <button
                type="submit"
                className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                创建 Workspace
              </button>
            </form>
          </aside>

          <section className="grid gap-6">
            <section className="rounded-[28px] border border-violet-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-500">Provider 列表</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                    已添加的平台账号
                  </h2>
                </div>
                <ProviderDrawerForm providersCount={providers.length} />
              </div>

              {providers.length === 0 ? (
                <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
                  还没有 Provider，可点击右上角添加你的 AI 平台配置。
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {providers.map((provider) => (
                    <article
                      key={provider.id}
                      className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,_#ffffff_0%,_#faf5ff_100%)] p-5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                            {provider.platform}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-slate-950">
                            {provider.label}
                          </h3>
                        </div>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            provider.is_enabled
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {provider.is_enabled ? "enabled" : "disabled"}
                        </span>
                      </div>

                      <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                            API Key
                          </p>
                          <p className="mt-1 font-mono">{provider.api_key_preview}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                            Base URL
                          </p>
                          <p className="mt-1 break-all font-mono">
                            {provider.base_url || "默认平台地址"}
                          </p>
                        </div>
                      </div>

                      <div className="mt-5 flex items-center justify-between text-sm text-slate-500">
                        <span>{formatDate(provider.updated_at)}</span>
                        <div className="flex items-center gap-2">
                          <form
                            action={toggleProviderAction.bind(
                              null,
                              provider.id,
                              !provider.is_enabled,
                            )}
                          >
                            <button
                              type="submit"
                              className="rounded-full bg-slate-100 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
                            >
                              {provider.is_enabled ? "禁用" : "启用"}
                            </button>
                          </form>

                          <form action={deleteProviderAction.bind(null, provider.id)}>
                            <button
                              type="submit"
                              className="rounded-full bg-rose-100 px-3 py-2 text-sm text-rose-700 transition hover:bg-rose-200"
                            >
                              删除
                            </button>
                          </form>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-[28px] border border-cyan-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-500">Model 配置层</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                    Provider 下的模型配置
                  </h2>
                </div>
                <ModelDrawerForm providers={providers} providerModels={providerModels} />
              </div>

              {providerModels.length === 0 ? (
                <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
                  还没有 Model 配置，可点击右上角为某个 Provider 添加模型。
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {providerModels.map((model) => (
                    <ProviderModelCard
                      key={model.id}
                      model={model}
                      providers={providers}
                    />
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-[28px] border border-sky-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-500">Workspace 列表</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                    已有工作空间
                  </h2>
                </div>
                <div className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                  {workspaces.length} 个
                </div>
              </div>

              {workspaces.length === 0 ? (
                <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
                  还没有 workspace，可以先在左侧创建第一个。
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {workspaces.map((workspace) => (
                    <article
                      key={workspace.id}
                      className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] p-5 transition hover:-translate-y-1 hover:border-orange-200 hover:shadow-[0_20px_40px_rgba(15,23,42,0.08)]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                            Workspace #{workspace.id}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-slate-950">
                            {workspace.name}
                          </h3>
                        </div>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone("active")}`}
                        >
                          Ready
                        </span>
                      </div>

                      <p className="mt-4 min-h-[4.5rem] text-sm leading-7 text-slate-600">
                        {workspace.description || "这个 workspace 还没有填写描述。"}
                      </p>

                      <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                          Root Path
                        </p>
                        <p className="mt-2 break-all font-mono text-sm text-slate-700">
                          {workspace.root_path || "未设置"}
                        </p>
                      </div>

                      <div className="mt-6 flex items-center justify-between text-sm text-slate-500">
                        <span>{workspace.projects.length} 个 projects</span>
                        <span>{formatDate(workspace.updated_at)}</span>
                      </div>

                      <div className="mt-5 flex items-center justify-between gap-3">
                        <Link
                          href={`/workspaces/${workspace.id}`}
                          className="inline-flex rounded-full bg-slate-950 px-4 py-2 text-sm text-white transition hover:bg-slate-800"
                        >
                          进入 Workspace
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
                                action={updateWorkspaceAction.bind(null, workspace.id)}
                                className="mt-3 grid gap-3"
                              >
                                <label className="space-y-2">
                                  <span className="text-sm font-medium text-slate-700">
                                    名称
                                  </span>
                                  <input
                                    name="name"
                                    required
                                    defaultValue={workspace.name}
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
                                    defaultValue={workspace.description ?? ""}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
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
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-sky-300"
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

                            <details className="rounded-[16px] bg-white p-3">
                              <summary className="cursor-pointer list-none rounded-xl bg-rose-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-rose-500">
                                删除
                              </summary>

                              <form
                                action={deleteWorkspaceAction.bind(null, workspace.id)}
                                className="mt-3 grid gap-3"
                              >
                                <p className="text-sm text-slate-600">
                                  确认删除这个 workspace 吗？
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
        </section>
      </div>
    </main>
  );
}
