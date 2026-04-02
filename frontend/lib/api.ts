import { notFound } from "next/navigation";

import type {
  Agent,
  Provider,
  ProviderValidationResult,
  ProviderModel,
  ProviderModelValidationResult,
  Project,
  ProjectPlanResult,
  Task,
  WorkflowRun,
  WorkflowRunDetail,
  Workspace,
  WorkspaceFileList,
} from "@/lib/types";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    cache: "no-store",
    headers:
      options.body === undefined
        ? undefined
        : {
            "Content-Type": "application/json",
          },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 404) {
    notFound();
  }

  if (!response.ok) {
    let message = `Request failed: ${response.status} ${response.statusText}`;

    try {
      const contentType = response.headers.get("content-type") ?? "";

      if (contentType.includes("application/json")) {
        const payload = (await response.json()) as {
          detail?: string;
          message?: string;
          details?: Array<{ message?: string }>;
        };
        if (payload.detail) {
          message = payload.detail;
        } else if (payload.message) {
          message = payload.message;
        } else if (payload.details?.[0]?.message) {
          message = payload.details[0].message;
        }
      } else {
        const text = (await response.text()).trim();
        if (text) {
          message = text;
        }
      }
    } catch {
      // Keep the fallback status-based message when the error body cannot be read.
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getHealth() {
  try {
    return await request<{ status: string; database: string }>(
      "/api/v1/health/",
    );
  } catch {
    return null;
  }
}

export async function listWorkspaces() {
  return request<Workspace[]>("/api/v1/workspaces/");
}

export async function listProviders() {
  return request<Provider[]>("/api/v1/providers/");
}

export async function listProviderModels() {
  return request<ProviderModel[]>("/api/v1/provider-models/");
}

export async function listAgents(workspaceId: number) {
  return request<Agent[]>(`/api/v1/workspaces/${workspaceId}/agents`);
}

export async function getWorkspace(workspaceId: number) {
  return request<Workspace>(`/api/v1/workspaces/${workspaceId}`);
}

export async function listWorkspaceFiles(workspaceId: number, path?: string) {
  const suffix = path ? `?path=${encodeURIComponent(path)}` : "";
  return request<WorkspaceFileList>(`/api/v1/workspaces/${workspaceId}/files${suffix}`);
}

export async function getProject(workspaceId: number, projectId: number) {
  return request<Project[]>(
    `/api/v1/workspaces/${workspaceId}/projects`,
  ).then((projects) => {
    const project = projects.find((item) => item.id === projectId);

    if (!project) {
      notFound();
    }

    return project;
  });
}

export async function listTasks(workspaceId: number, projectId: number) {
  return request<Task[]>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks`,
  );
}

export async function createWorkspace(payload: {
  name: string;
  description?: string;
  root_path: string;
}) {
  return request<Workspace>("/api/v1/workspaces/", {
    method: "POST",
    body: payload,
  });
}

export async function updateWorkspace(
  workspaceId: number,
  payload: { name?: string; description?: string; root_path?: string },
) {
  return request<Workspace>(`/api/v1/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function deleteWorkspace(workspaceId: number) {
  return request<void>(`/api/v1/workspaces/${workspaceId}`, {
    method: "DELETE",
  });
}

export async function createProvider(payload: {
  platform: Provider["platform"];
  label: string;
  api_key: string;
  base_url?: string;
  is_enabled?: boolean;
}) {
  return request<Provider>("/api/v1/providers/", {
    method: "POST",
    body: payload,
  });
}

export async function updateProvider(
  providerId: number,
  payload: {
    label?: string;
    api_key?: string;
    base_url?: string;
    is_enabled?: boolean;
  },
) {
  return request<Provider>(`/api/v1/providers/${providerId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function validateProvider(payload: {
  platform: Provider["platform"];
  api_key: string;
  base_url?: string;
}) {
  return request<ProviderValidationResult>("/api/v1/providers/validate", {
    method: "POST",
    body: payload,
  });
}

export async function deleteProvider(providerId: number) {
  return request<void>(`/api/v1/providers/${providerId}`, {
    method: "DELETE",
  });
}

export async function createProviderModel(payload: {
  provider_id: number;
  label: string;
  model_name: string;
  is_enabled?: boolean;
  is_default?: boolean;
  temperature?: number;
  max_output_tokens?: number;
  supports_tools?: boolean;
}) {
  return request<ProviderModel>("/api/v1/provider-models/", {
    method: "POST",
    body: payload,
  });
}

export async function updateProviderModel(
  providerModelId: number,
  payload: {
    label?: string;
    model_name?: string;
    is_enabled?: boolean;
    is_default?: boolean;
    temperature?: number;
    max_output_tokens?: number;
    supports_tools?: boolean;
  },
) {
  return request<ProviderModel>(`/api/v1/provider-models/${providerModelId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function validateProviderModel(payload: {
  provider_id: number;
  model_name: string;
}) {
  return request<ProviderModelValidationResult>("/api/v1/provider-models/validate", {
    method: "POST",
    body: payload,
  });
}

export async function deleteProviderModel(providerModelId: number) {
  return request<void>(`/api/v1/provider-models/${providerModelId}`, {
    method: "DELETE",
  });
}

export async function createAgent(
  workspaceId: number,
  payload: {
    provider_model_id: number;
    name: string;
    description?: string;
    system_prompt?: string;
    is_enabled?: boolean;
    max_concurrency?: number;
  },
) {
  return request<Agent>(`/api/v1/workspaces/${workspaceId}/agents`, {
    method: "POST",
    body: payload,
  });
}

export async function updateAgent(
  workspaceId: number,
  agentId: number,
  payload: {
    provider_model_id?: number;
    name?: string;
    description?: string;
    system_prompt?: string;
    is_enabled?: boolean;
    max_concurrency?: number;
  },
) {
  return request<Agent>(`/api/v1/workspaces/${workspaceId}/agents/${agentId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function deleteAgent(workspaceId: number, agentId: number) {
  return request<void>(`/api/v1/workspaces/${workspaceId}/agents/${agentId}`, {
    method: "DELETE",
  });
}

export async function createProject(
  workspaceId: number,
  payload: { name: string; description?: string; status?: string },
) {
  return request<Project>(`/api/v1/workspaces/${workspaceId}/projects`, {
    method: "POST",
    body: payload,
  });
}

export async function updateProject(
  workspaceId: number,
  projectId: number,
  payload: { name?: string; description?: string; status?: string },
) {
  return request<Project>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function deleteProject(workspaceId: number, projectId: number) {
  return request<void>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}`,
    {
      method: "DELETE",
    },
  );
}

export async function planProject(
  workspaceId: number,
  projectId: number,
  payload: {
    planner_agent_id: number;
  },
) {
  return request<ProjectPlanResult>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/plan`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function createTask(
  workspaceId: number,
  projectId: number,
  payload: {
    agent_id?: number;
    title: string;
    description?: string;
    node_type?: "start" | "task";
    status?: string;
    priority?: string;
    display_order?: number;
    canvas_x?: number;
    canvas_y?: number;
    task_dependencies?: number[];
  },
) {
  return request<Task>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function updateTask(
  workspaceId: number,
  projectId: number,
  taskId: number,
  payload: {
    agent_id?: number | null;
    title?: string;
    description?: string;
    status?: string;
    priority?: string;
    display_order?: number;
    canvas_x?: number;
    canvas_y?: number;
    task_dependencies?: number[];
  },
) {
  return request<Task>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks/${taskId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function updateTaskStatus(
  workspaceId: number,
  projectId: number,
  taskId: number,
  payload: { status: string },
) {
  return request<Task>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks/${taskId}/status`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function deleteTask(
  workspaceId: number,
  projectId: number,
  taskId: number,
) {
  return request<void>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks/${taskId}`,
    {
      method: "DELETE",
    },
  );
}

export async function createWorkflowRun(
  workspaceId: number,
  projectId: number,
  payload?: {
    trigger_type?: "manual" | "api" | "schedule" | "retry";
    input_payload?: Record<string, unknown>;
  },
) {
  return request<WorkflowRunDetail>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs`,
    {
      method: "POST",
      body: payload ?? {},
    },
  );
}

export async function listWorkflowRuns(workspaceId: number, projectId: number) {
  return request<WorkflowRun[]>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs`,
  );
}

export async function getWorkflowRun(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
) {
  return request<WorkflowRunDetail>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}`,
  );
}

export async function deleteWorkflowRun(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
) {
  return request<void>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}`,
    {
      method: "DELETE",
    },
  );
}

export async function executeTaskRun(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
  taskRunId: number,
) {
  return request<WorkflowRunDetail>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}/task-runs/${taskRunId}/execute`,
    {
      method: "POST",
    },
  );
}

export async function executeWorkflowRun(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
) {
  return request<WorkflowRunDetail>(
    `/api/v1/workspaces/${workspaceId}/projects/${projectId}/runs/${workflowRunId}/execute`,
    {
      method: "POST",
    },
  );
}

export { apiBaseUrl };
