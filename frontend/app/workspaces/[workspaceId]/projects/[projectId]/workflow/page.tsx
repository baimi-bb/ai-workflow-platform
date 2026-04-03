import Link from "next/link";

import {
  connectTaskAction,
  createWorkflowRunAction,
  deleteWorkflowRunAction,
} from "@/lib/actions";
import { getWorkflowRun, listWorkflowRuns } from "@/lib/api";

import { ProjectShell, getProjectPageData } from "../project-view";
import { ExecuteTaskRunButton } from "./execute-task-run-button";
import { ExecuteWorkflowRunButton } from "./execute-workflow-run-button";
import { WorkflowCanvas } from "./workflow-canvas";

type PageProps = {
  params: Promise<{
    workspaceId: string;
    projectId: string;
  }>;
  searchParams?: Promise<{
    runId?: string;
  }>;
};

type FileEntry = {
  path: string;
  source?: string;
};

type ActivityEntry = {
  timestamp: string;
  stage: string;
  message: string;
};

function buildTaskLevels(
  tasks: { id: number; task_dependencies: number[] }[],
): Map<number, number> {
  const taskMap = new Map(tasks.map((task) => [task.id, task]));
  const depthCache = new Map<number, number>();

  const getDepth = (taskId: number): number => {
    if (depthCache.has(taskId)) {
      return depthCache.get(taskId) ?? 0;
    }

    const task = taskMap.get(taskId);
    if (!task || task.task_dependencies.length === 0) {
      depthCache.set(taskId, 0);
      return 0;
    }

    const depth =
      Math.max(...task.task_dependencies.map((dependencyId) => getDepth(dependencyId))) +
      1;
    depthCache.set(taskId, depth);
    return depth;
  };

  tasks.forEach((task) => {
    getDepth(task.id);
  });

  return depthCache;
}

function getFileEntries(
  payload: Record<string, unknown> | null,
  key: "files" | "artifacts",
): FileEntry[] {
  const entries = payload?.[key];
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries
    .map((entry) => {
      if (typeof entry === "object" && entry !== null && "path" in entry) {
        return {
          path: String(entry.path),
          source:
            "source" in entry && typeof entry.source === "string"
              ? entry.source
              : undefined,
        };
      }
      return null;
    })
    .filter((entry): entry is FileEntry => entry !== null);
}

function getActivityEntries(payload: Record<string, unknown> | null): ActivityEntry[] {
  const entries = payload?.activity_log;
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries
    .map((entry) => {
      if (typeof entry !== "object" || entry === null) {
        return null;
      }

      const timestamp = "timestamp" in entry ? String(entry.timestamp) : "";
      const stage = "stage" in entry ? String(entry.stage) : "";
      const message = "message" in entry ? String(entry.message) : "";
      if (!timestamp || !message) {
        return null;
      }

      return { timestamp, stage, message };
    })
    .filter((entry): entry is ActivityEntry => entry !== null);
}

export default async function ProjectWorkflowPage({
  params,
  searchParams,
}: PageProps) {
  const { workspaceId, projectId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const requestedRunId = resolvedSearchParams.runId ? Number(resolvedSearchParams.runId) : null;
  const workspaceIdValue = Number(workspaceId);
  const projectIdValue = Number(projectId);
  const data = await getProjectPageData(workspaceIdValue, projectIdValue);
  const workflowRuns = await listWorkflowRuns(workspaceIdValue, projectIdValue);

  const selectedRun =
    requestedRunId && Number.isInteger(requestedRunId) && requestedRunId > 0
      ? await getWorkflowRun(workspaceIdValue, projectIdValue, requestedRunId)
      : workflowRuns.length > 0
        ? await getWorkflowRun(workspaceIdValue, projectIdValue, workflowRuns[0].id)
        : null;

  const sortedTasks = [...data.tasks].sort((left, right) => {
    if (left.node_type !== right.node_type) {
      return left.node_type === "start" ? -1 : 1;
    }
    if (left.display_order !== right.display_order) {
      return left.display_order - right.display_order;
    }
    return left.id - right.id;
  });

  const taskLevels = buildTaskLevels(sortedTasks);
  const stageCount = Math.max(0, ...taskLevels.values()) + 1;
  const relationCount = data.tasks.reduce(
    (count, task) => count + task.task_dependencies.length,
    0,
  );

  const connectPanel = (
    <section className="space-y-6">
      <section className="space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-500">Connect Nodes</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">添加连线</h3>
        </div>

        <form
          action={connectTaskAction.bind(null, workspaceIdValue, projectIdValue)}
          className="grid gap-3"
        >
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">起点节点</span>
            <select
              name="source_task_id"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
            >
              {sortedTasks.map((task) => (
                <option key={task.id} value={task.id}>
                  #{task.id} {task.title}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">终点节点</span>
            <select
              name="target_task_id"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-emerald-300"
            >
              {sortedTasks
                .filter((task) => task.node_type !== "start")
                .map((task) => (
                  <option key={task.id} value={task.id}>
                    #{task.id} {task.title}
                  </option>
                ))}
            </select>
          </label>

          <button
            type="submit"
            className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            添加依赖连线
          </button>
        </form>
      </section>

      <section className="space-y-4 border-t border-slate-200 pt-6">
        <div>
          <p className="text-sm font-medium text-slate-500">Run Control</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">运行 Workflow</h3>
        </div>

        <form action={createWorkflowRunAction.bind(null, workspaceIdValue, projectIdValue)}>
          <button
            type="submit"
            className="w-full rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            创建新的 Workflow Run
          </button>
        </form>

        {workflowRuns.length > 0 ? (
          <div className="space-y-2">
            {workflowRuns.slice(0, 6).map((run) => (
              <Link
                key={run.id}
                href={`/workspaces/${workspaceIdValue}/projects/${projectIdValue}/workflow?runId=${run.id}`}
                className={`block rounded-2xl border px-4 py-3 text-sm transition ${
                  selectedRun?.id === run.id
                    ? "border-slate-950 bg-slate-950 text-white"
                    : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
                }`}
              >
                Run #{run.id} / {run.status}
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
            还没有 workflow run。
          </div>
        )}
      </section>
    </section>
  );

  return (
    <ProjectShell {...data} activeView="workflow" asideContent={connectPanel}>
      <div className="space-y-6">
        <section className="rounded-[28px] border border-emerald-100 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Workflow</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                画布展示节点、连线与执行路径
              </h2>
            </div>

            <div className="grid gap-3 rounded-[24px] bg-slate-950 px-5 py-4 text-sm text-slate-100 sm:grid-cols-3">
              <div className="space-y-1">
                <div className="text-slate-400">Nodes</div>
                <div className="text-lg font-semibold">{data.tasks.length}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-400">Stages</div>
                <div className="text-lg font-semibold">{stageCount}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-400">Relations</div>
                <div className="text-lg font-semibold">{relationCount}</div>
              </div>
            </div>
          </div>
        </section>

        {data.tasks.length > 0 ? (
          <WorkflowCanvas
            workspaceId={workspaceIdValue}
            projectId={projectIdValue}
            tasks={sortedTasks}
            agents={data.workspace.agents}
            selectedRun={selectedRun}
          />
        ) : null}

        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Run Detail</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                当前 Workflow Run
              </h2>
            </div>

            {selectedRun ? (
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700">
                  Run #{selectedRun.id} / {selectedRun.status}
                </div>
                <form
                  action={deleteWorkflowRunAction.bind(
                    null,
                    workspaceIdValue,
                    projectIdValue,
                    selectedRun.id,
                  )}
                >
                  <button
                    type="submit"
                    className="rounded-full bg-rose-100 px-4 py-2 text-sm text-rose-700 transition hover:bg-rose-200"
                  >
                    删除 Run
                  </button>
                </form>
                {selectedRun.status !== "completed" ? (
                  <ExecuteWorkflowRunButton
                    workspaceId={workspaceIdValue}
                    projectId={projectIdValue}
                    workflowRunId={selectedRun.id}
                    label="执行整个 Workflow"
                  />
                ) : null}
              </div>
            ) : null}
          </div>

          {!selectedRun ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center text-slate-500">
              还没有可查看的 workflow run，先在左侧创建一次运行。
            </div>
          ) : (
            <div className="mt-5 grid gap-4">
              {selectedRun.task_runs.map((taskRun) => {
                const inputFiles = getFileEntries(taskRun.input_payload, "files");
                const outputFiles = getFileEntries(taskRun.output_payload, "artifacts");
                const activityEntries = [
                  ...getActivityEntries(taskRun.input_payload),
                  ...getActivityEntries(taskRun.output_payload),
                ];
                const dedupedActivityEntries = activityEntries.filter(
                  (entry, index, list) =>
                    list.findIndex(
                      (candidate) =>
                        candidate.timestamp === entry.timestamp &&
                        candidate.stage === entry.stage &&
                        candidate.message === entry.message,
                    ) === index,
                );
                const latestActivity =
                  dedupedActivityEntries.length > 0
                    ? dedupedActivityEntries[dedupedActivityEntries.length - 1]
                    : null;

                return (
                  <article
                    key={taskRun.id}
                    className="rounded-[22px] border border-slate-200 bg-slate-50 p-5"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-slate-950 px-3 py-1 text-xs text-white">
                            TaskRun #{taskRun.id}
                          </span>
                          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
                            {taskRun.status}
                          </span>
                          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
                            {taskRun.executor_type}
                          </span>
                        </div>
                        <h3 className="text-lg font-semibold text-slate-950">
                          {taskRun.title_snapshot}
                        </h3>
                        <div className="flex flex-wrap gap-2 text-sm text-slate-600">
                          <span className="rounded-full bg-white px-3 py-1">
                            Agent: {taskRun.assigned_agent_name || "未分配"}
                          </span>
                          <span className="rounded-full bg-white px-3 py-1">
                            Attempts: {taskRun.attempt_count}
                          </span>
                          {latestActivity ? (
                            <span className="rounded-full bg-sky-50 px-3 py-1 text-sky-700">
                              Activity: {latestActivity.message}
                            </span>
                          ) : null}
                        </div>
                        {taskRun.error_message ? (
                          <p className="rounded-2xl bg-rose-100 px-4 py-3 text-sm text-rose-700">
                            {taskRun.error_message}
                          </p>
                        ) : null}
                        {taskRun.output_payload?.text || inputFiles.length > 0 || outputFiles.length > 0 ? (
                          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-600">
                            {inputFiles.length > 0 ? (
                              <div className="mb-3">
                                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                                  Input Files
                                </p>
                                <div className="grid gap-2">
                                  {inputFiles.map((inputFile, index) => (
                                    <div
                                      key={`${taskRun.id}-input-${index}`}
                                      className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600"
                                    >
                                      <p className="font-mono">{inputFile.path}</p>
                                      {inputFile.source ? (
                                        <p className="mt-1 text-[11px] text-slate-400">
                                          Source: {inputFile.source}
                                        </p>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                            {taskRun.output_payload?.text ? (
                              <>
                                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                                  Output
                                </p>
                                <p className="whitespace-pre-wrap">
                                  {String(taskRun.output_payload.text)}
                                </p>
                              </>
                            ) : null}
                            {outputFiles.length > 0 ? (
                              <div className="mt-3 border-t border-slate-200 pt-3">
                                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                                  Artifacts
                                </p>
                                <div className="grid gap-2">
                                  {outputFiles.map((artifact, index) => (
                                    <p
                                      key={`${taskRun.id}-artifact-${index}`}
                                      className="rounded-xl bg-slate-50 px-3 py-2 font-mono text-xs text-slate-600"
                                    >
                                      {artifact.path}
                                    </p>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                            {dedupedActivityEntries.length > 0 ? (
                              <div className="mt-3 border-t border-slate-200 pt-3">
                                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                                  Activity
                                </p>
                                <div className="grid gap-2">
                                  {dedupedActivityEntries.map((entry, index) => (
                                    <div
                                      key={`${taskRun.id}-activity-${index}`}
                                      className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600"
                                    >
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="rounded-full bg-white px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                                          {entry.stage}
                                        </span>
                                        <span className="text-[11px] text-slate-400">
                                          {entry.timestamp}
                                        </span>
                                      </div>
                                      <p className="mt-2 leading-6">{entry.message}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>

                      {(taskRun.status === "ready" || taskRun.status === "failed") &&
                      taskRun.assigned_agent_id ? (
                        <ExecuteTaskRunButton
                          workspaceId={workspaceIdValue}
                          projectId={projectIdValue}
                          workflowRunId={selectedRun.id}
                          taskRunId={taskRun.id}
                          taskId={taskRun.task_id}
                          label={
                            taskRun.status === "failed"
                              ? "重试这个 Task Run"
                              : "执行这个 Task Run"
                          }
                        />
                      ) : (
                        <div className="rounded-2xl bg-white px-4 py-3 text-sm text-slate-500">
                          {taskRun.assigned_agent_id
                            ? "当前状态不可执行"
                            : "未分配 Agent，无法执行"}
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </ProjectShell>
  );
}
