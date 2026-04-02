"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type ExecuteWorkflowRunButtonProps = {
  workspaceId: number;
  projectId: number;
  workflowRunId: number;
  label?: string;
};

type WorkflowRunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

type WorkflowRunDetail = {
  id: number;
  status: WorkflowRunStatus;
  task_runs: Array<{
    task_id: number;
    status: string;
  }>;
};

async function getWorkflowRunDetail(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
): Promise<WorkflowRunDetail> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to load workflow run ${workflowRunId}`);
  }

  return (await response.json()) as WorkflowRunDetail;
}

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function executeWorkflowRunRequest(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
): Promise<WorkflowRunDetail> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}/execute`,
    {
      method: "POST",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    let message = `Request failed: ${response.status} ${response.statusText}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Fall back to status text when the response body cannot be parsed.
    }

    throw new Error(message);
  }

  return (await response.json()) as WorkflowRunDetail;
}

export function ExecuteWorkflowRunButton({
  workspaceId,
  projectId,
  workflowRunId,
  label = "执行整个 Workflow",
}: ExecuteWorkflowRunButtonProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleExecute = async () => {
    setPending(true);
    setErrorMessage(null);
    let activeTaskId: number | null = null;

    try {
      for (let attempt = 0; attempt < 120; attempt += 1) {
        const runBefore = await getWorkflowRunDetail(
          workspaceId,
          projectId,
          workflowRunId,
        );
        const nextReadyTaskRun = runBefore.task_runs.find(
          (taskRun) => taskRun.status === "ready",
        );
        if (nextReadyTaskRun) {
          activeTaskId = nextReadyTaskRun.task_id;
          window.dispatchEvent(
            new CustomEvent("workflow-task-run-start", {
              detail: { taskId: nextReadyTaskRun.task_id },
            }),
          );
        }
        const run = await executeWorkflowRunRequest(
          workspaceId,
          projectId,
          workflowRunId,
        );
        if (nextReadyTaskRun) {
          window.dispatchEvent(
            new CustomEvent("workflow-task-run-end", {
              detail: { taskId: nextReadyTaskRun.task_id },
            }),
          );
          activeTaskId = null;
        }
        router.refresh();

        if (run.status === "completed" || run.status === "failed" || run.status === "cancelled") {
          break;
        }

        await new Promise((resolve) => window.setTimeout(resolve, 700));
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "执行 Workflow 失败",
      );
    } finally {
      if (activeTaskId) {
        window.dispatchEvent(
          new CustomEvent("workflow-task-run-end", {
            detail: { taskId: activeTaskId },
          }),
        );
      }
      setPending(false);
      router.refresh();
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => {
          void handleExecute();
        }}
        disabled={pending}
        className="rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-emerald-300"
      >
        {pending ? "执行中..." : label}
      </button>

      {errorMessage ? (
        <p className="max-w-sm rounded-2xl bg-rose-100 px-4 py-3 text-sm text-rose-700">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
