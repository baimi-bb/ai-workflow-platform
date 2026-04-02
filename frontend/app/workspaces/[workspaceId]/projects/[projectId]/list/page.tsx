import { bulkUpdateTaskStatusAction } from "@/lib/actions";
import { formatDate } from "@/lib/ui";

import {
  ProjectShell,
  TaskMetaBadges,
  TaskPriorityBadge,
  TaskRowActions,
  TaskStatusBadge,
  getProjectPageData,
} from "../project-view";

type PageProps = {
  params: Promise<{
    workspaceId: string;
    projectId: string;
  }>;
  searchParams: Promise<{
    q?: string;
    status?: string;
    priority?: string;
  }>;
};

const BULK_FORM_ID = "bulk-task-status-form";

export default async function ProjectListPage({
  params,
  searchParams,
}: PageProps) {
  const { workspaceId, projectId } = await params;
  const { q = "", status = "all", priority = "all" } = await searchParams;
  const workspaceIdValue = Number(workspaceId);
  const projectIdValue = Number(projectId);

  const data = await getProjectPageData(workspaceIdValue, projectIdValue);
  const keyword = q.trim().toLowerCase();
  const filteredTasks = data.tasks.filter((task) => {
    const matchesKeyword =
      keyword.length === 0 ||
      task.title.toLowerCase().includes(keyword) ||
      task.description?.toLowerCase().includes(keyword);
    const matchesStatus = status === "all" || task.status === status;
    const matchesPriority = priority === "all" || task.priority === priority;

    return matchesKeyword && matchesStatus && matchesPriority;
  });

  return (
    <ProjectShell {...data} activeView="list">
      <div className="space-y-6">
        <section className="rounded-[28px] border border-orange-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">List / Table</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                用表格快速管理任务
              </h2>
            </div>

            <form className="grid gap-3 md:grid-cols-[minmax(0,1.5fr)_180px_180px_auto]">
              <input
                type="text"
                name="q"
                defaultValue={q}
                placeholder="搜索任务标题或描述"
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300"
              />
              <select
                name="status"
                defaultValue={status}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300"
              >
                <option value="all">全部状态</option>
                <option value="todo">todo</option>
                <option value="in_progress">in_progress</option>
                <option value="done">done</option>
              </select>
              <select
                name="priority"
                defaultValue={priority}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300"
              >
                <option value="all">全部优先级</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
              <button
                type="submit"
                className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                筛选
              </button>
            </form>
          </div>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <form
            id={BULK_FORM_ID}
            action={bulkUpdateTaskStatusAction.bind(
              null,
              workspaceIdValue,
              projectIdValue,
            )}
          />

          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Bulk Action</p>
              <h3 className="mt-1 text-xl font-semibold text-slate-950">
                批量修改状态
              </h3>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <select
                name="status"
                form={BULK_FORM_ID}
                defaultValue="in_progress"
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300"
              >
                <option value="todo">todo</option>
                <option value="in_progress">in_progress</option>
                <option value="done">done</option>
              </select>
              <button
                type="submit"
                form={BULK_FORM_ID}
                className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                应用到已勾选任务
              </button>
            </div>
          </div>

          {filteredTasks.length === 0 ? (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
              当前筛选条件下没有任务。
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-y-3">
                <thead>
                  <tr className="text-left text-sm text-slate-500">
                    <th className="px-4 py-2">选择</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">状态</th>
                    <th className="px-4 py-2">Agent</th>
                    <th className="px-4 py-2">优先级</th>
                    <th className="px-4 py-2">创建时间</th>
                    <th className="px-4 py-2">更新时间</th>
                    <th className="px-4 py-2">依赖</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTasks.map((task) => (
                    <tr key={task.id} className="align-top">
                      <td className="rounded-l-[20px] border border-r-0 border-slate-200 bg-slate-50 px-4 py-4">
                        <input
                          type="checkbox"
                          name="task_ids"
                          value={task.id}
                          form={BULK_FORM_ID}
                          className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400"
                        />
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4">
                        <div className="space-y-2">
                          <div className="font-semibold text-slate-950">{task.title}</div>
                          <div className="text-sm leading-6 text-slate-600">
                            {task.description || "暂无描述"}
                          </div>
                          <div className="text-xs text-slate-400">Task #{task.id}</div>
                        </div>
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4">
                        <TaskStatusBadge status={task.status} />
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
                        {task.agent_name || "未分配"}
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4">
                        <TaskPriorityBadge priority={task.priority} />
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
                        {formatDate(task.created_at)}
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
                        {formatDate(task.updated_at)}
                      </td>
                      <td className="border border-r-0 border-slate-200 bg-slate-50 px-4 py-4">
                        <TaskMetaBadges task={task} tasks={data.tasks} />
                      </td>
                      <td className="rounded-r-[20px] border border-slate-200 bg-slate-50 px-4 py-4">
                        <TaskRowActions
                          agents={data.workspace.agents}
                          task={task}
                          workspaceId={workspaceIdValue}
                          projectId={projectIdValue}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </ProjectShell>
  );
}
