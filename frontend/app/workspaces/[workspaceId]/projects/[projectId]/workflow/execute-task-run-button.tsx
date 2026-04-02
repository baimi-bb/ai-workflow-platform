"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type ExecuteTaskRunButtonProps = {
  workspaceId: number;
  projectId: number;
  workflowRunId: number;
  taskRunId: number;
  taskId: number;
  label?: string;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function executeTaskRunRequest(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
  taskRunId: number,
) {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}/task-runs/${taskRunId}/execute`,
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
}

export function ExecuteTaskRunButton({
  workspaceId,
  projectId,
  workflowRunId,
  taskRunId,
  taskId,
  label = "执行这个 Task Run",
}: ExecuteTaskRunButtonProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleExecute = async () => {
    setPending(true);
    setErrorMessage(null);

    try {
      window.dispatchEvent(
        new CustomEvent("workflow-task-run-start", {
          detail: { taskId },
        }),
      );
      await executeTaskRunRequest(workspaceId, projectId, workflowRunId, taskRunId);
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "执行 Task Run 失败",
      );
    } finally {
      window.dispatchEvent(
        new CustomEvent("workflow-task-run-end", {
          detail: { taskId },
        }),
      );
      setPending(false);
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
        className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
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
