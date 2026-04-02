"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  createAgent,
  createProvider,
  createProviderModel,
  createProject,
  planProject,
  createTask,
  executeTaskRun,
  executeWorkflowRun,
  createWorkflowRun,
  createWorkspace,
  deleteAgent,
  deleteProvider,
  deleteProviderModel,
  deleteWorkflowRun,
  deleteProject,
  deleteTask,
  deleteWorkspace,
  listTasks,
  updateProject,
  updateProvider,
  updateProviderModel,
  updateAgent,
  updateTask,
  updateTaskStatus,
  updateWorkspace,
  validateProvider,
  validateProviderModel,
} from "@/lib/api";
import { DEFAULT_FORM_FEEDBACK_STATE } from "@/lib/action-state";
import type { FormFeedbackState } from "@/lib/action-state";

function readText(formData: FormData, key: string) {
  const value = formData.get(key);

  if (typeof value !== "string") {
    return "";
  }

  return value.trim();
}

function readTaskDependencies(formData: FormData, key: string) {
  const rawValue = readText(formData, key);

  if (!rawValue) {
    return [];
  }

  return Array.from(
    new Set(
      rawValue
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((item) => Number.isInteger(item) && item > 0),
    ),
  );
}

function readOptionalNumber(formData: FormData, key: string) {
  const rawValue = readText(formData, key);

  if (!rawValue) {
    return undefined;
  }

  const value = Number(rawValue);
  return Number.isInteger(value) ? value : undefined;
}

export type TaskActionState = {
  ok: boolean;
  message: string | null;
};

const DEFAULT_TASK_ACTION_STATE: TaskActionState = {
  ok: false,
  message: null,
};

function getActionErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Operation failed";
}

export async function createWorkspaceAction(formData: FormData) {
  const name = readText(formData, "name");
  const description = readText(formData, "description");
  const rootPath = readText(formData, "root_path");

  if (!name) {
    throw new Error("Workspace name is required");
  }
  if (!rootPath) {
    throw new Error("Workspace root path is required");
  }

  await createWorkspace({
    name,
    description: description || undefined,
    root_path: rootPath,
  });

  revalidatePath("/");
}

export async function updateWorkspaceAction(
  workspaceId: number,
  formData: FormData,
) {
  const name = readText(formData, "name");
  const description = readText(formData, "description");
  const rootPath = readText(formData, "root_path");

  if (!name) {
    throw new Error("Workspace name is required");
  }
  if (!rootPath) {
    throw new Error("Workspace root path is required");
  }

  await updateWorkspace(workspaceId, {
    name,
    description: description || undefined,
    root_path: rootPath,
  });

  revalidatePath("/");
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function deleteWorkspaceAction(workspaceId: number) {
  await deleteWorkspace(workspaceId);

  revalidatePath("/");
  redirect("/");
}

export async function createProviderAction(formData: FormData) {
  const platform = readText(formData, "platform");
  const label = readText(formData, "label");
  const apiKey = readText(formData, "api_key");
  const baseUrl = readText(formData, "base_url");
  const isEnabled = readText(formData, "is_enabled");

  if (!label) {
    throw new Error("Provider label is required");
  }
  if (!apiKey) {
    throw new Error("Provider API key is required");
  }

  await createProvider({
    platform:
      platform === "anthropic" ||
      platform === "google" ||
      platform === "deepseek" ||
      platform === "openrouter" ||
      platform === "custom"
        ? platform
        : "openai",
    label,
    api_key: apiKey,
    base_url: baseUrl || undefined,
    is_enabled: isEnabled !== "false",
  });

  revalidatePath("/");
}

export async function validateProviderAction(
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
  formData: FormData,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    const platform = readText(formData, "platform");
    const apiKey = readText(formData, "api_key");
    const baseUrl = readText(formData, "base_url");

    if (!apiKey) {
      throw new Error("Provider API key is required");
    }

    const result = await validateProvider({
      platform:
        platform === "anthropic" ||
        platform === "google" ||
        platform === "deepseek" ||
        platform === "openrouter" ||
        platform === "custom"
          ? platform
          : "openai",
      api_key: apiKey,
      base_url: baseUrl || undefined,
    });

    return {
      ok: result.is_valid,
      message: result.message,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function toggleProviderAction(
  providerId: number,
  nextEnabled: boolean,
) {
  await updateProvider(providerId, { is_enabled: nextEnabled });
  revalidatePath("/");
}

export async function deleteProviderAction(providerId: number) {
  await deleteProvider(providerId);
  revalidatePath("/");
}

export async function createProviderModelAction(formData: FormData) {
  const providerId = Number(readText(formData, "provider_id"));
  const label = readText(formData, "label");
  const modelName = readText(formData, "model_name");
  const isEnabled = readText(formData, "is_enabled");
  const isDefault = readText(formData, "is_default");
  const temperatureValue = readText(formData, "temperature");
  const maxOutputTokensValue = readText(formData, "max_output_tokens");
  const supportsTools = readText(formData, "supports_tools");

  if (!Number.isInteger(providerId) || providerId <= 0) {
    throw new Error("Provider is required");
  }
  if (!label) {
    throw new Error("Model label is required");
  }
  if (!modelName) {
    throw new Error("Model name is required");
  }

  const temperature = temperatureValue ? Number(temperatureValue) : undefined;
  const maxOutputTokens = maxOutputTokensValue
    ? Number(maxOutputTokensValue)
    : undefined;

  const validationResult = await validateProviderModel({
    provider_id: providerId,
    model_name: modelName,
  });
  if (!validationResult.is_valid) {
    throw new Error(validationResult.message);
  }

  await createProviderModel({
    provider_id: providerId,
    label,
    model_name: modelName,
    is_enabled: isEnabled !== "false",
    is_default: isDefault === "true",
    temperature: Number.isFinite(temperature) ? temperature : undefined,
    max_output_tokens:
      Number.isInteger(maxOutputTokens) && maxOutputTokens > 0
        ? maxOutputTokens
        : undefined,
    supports_tools: supportsTools === "true",
  });

  revalidatePath("/");
}

export async function validateProviderModelAction(
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
  formData: FormData,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    const providerId = Number(readText(formData, "provider_id"));
    const modelName = readText(formData, "model_name");

    if (!Number.isInteger(providerId) || providerId <= 0) {
      throw new Error("Provider is required");
    }
    if (!modelName) {
      throw new Error("Model name is required");
    }

    const result = await validateProviderModel({
      provider_id: providerId,
      model_name: modelName,
    });

    return {
      ok: result.is_valid,
      message: result.message,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function createAgentAction(workspaceId: number, formData: FormData) {
  const providerModelId = Number(readText(formData, "provider_model_id"));
  const name = readText(formData, "name");
  const description = readText(formData, "description");
  const systemPrompt = readText(formData, "system_prompt");
  const isEnabled = readText(formData, "is_enabled");

  if (!Number.isInteger(providerModelId) || providerModelId <= 0) {
    throw new Error("Model config is required");
  }
  if (!name) {
    throw new Error("Agent name is required");
  }

  await createAgent(workspaceId, {
    provider_model_id: providerModelId,
    name,
    description: description || undefined,
    system_prompt: systemPrompt || undefined,
    is_enabled: isEnabled !== "false",
    max_concurrency: 1,
  });

  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function toggleAgentAction(
  workspaceId: number,
  agentId: number,
  nextEnabled: boolean,
) {
  await updateAgent(workspaceId, agentId, { is_enabled: nextEnabled });
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function deleteAgentAction(workspaceId: number, agentId: number) {
  await deleteAgent(workspaceId, agentId);
  revalidatePath(`/workspaces/${workspaceId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects`);
}

export async function toggleProviderModelAction(
  providerModelId: number,
  nextEnabled: boolean,
) {
  await updateProviderModel(providerModelId, { is_enabled: nextEnabled });
  revalidatePath("/");
}

export async function setDefaultProviderModelAction(providerModelId: number) {
  await updateProviderModel(providerModelId, { is_default: true });
  revalidatePath("/");
}

export async function updateProviderModelAction(
  providerModelId: number,
  formData: FormData,
) {
  const providerId = Number(readText(formData, "provider_id"));
  const label = readText(formData, "label");
  const modelName = readText(formData, "model_name");
  const isEnabled = readText(formData, "is_enabled");
  const isDefault = readText(formData, "is_default");
  const temperatureValue = readText(formData, "temperature");
  const maxOutputTokensValue = readText(formData, "max_output_tokens");
  const supportsTools = readText(formData, "supports_tools");

  if (!Number.isInteger(providerId) || providerId <= 0) {
    throw new Error("Provider is required");
  }
  if (!label) {
    throw new Error("Model label is required");
  }
  if (!modelName) {
    throw new Error("Model name is required");
  }

  const validationResult = await validateProviderModel({
    provider_id: providerId,
    model_name: modelName,
  });
  if (!validationResult.is_valid) {
    throw new Error(validationResult.message);
  }

  const temperature = temperatureValue ? Number(temperatureValue) : undefined;
  const maxOutputTokens = maxOutputTokensValue
    ? Number(maxOutputTokensValue)
    : undefined;

  await updateProviderModel(providerModelId, {
    label,
    model_name: modelName,
    is_enabled: isEnabled !== "false",
    is_default: isDefault === "true",
    temperature: Number.isFinite(temperature) ? temperature : undefined,
    max_output_tokens:
      Number.isInteger(maxOutputTokens) && maxOutputTokens > 0
        ? maxOutputTokens
        : undefined,
    supports_tools: supportsTools === "true",
  });

  revalidatePath("/");
}

export async function submitUpdateProviderModelAction(
  providerModelId: number,
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
  formData: FormData,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    await updateProviderModelAction(providerModelId, formData);
    return {
      ok: true,
      message: "Model config updated",
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function deleteProviderModelAction(providerModelId: number) {
  await deleteProviderModel(providerModelId);
  revalidatePath("/");
}

export async function submitDeleteProviderModelAction(
  providerModelId: number,
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    await deleteProviderModelAction(providerModelId);
    return {
      ok: true,
      message: "Model config deleted",
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function createProjectAction(
  workspaceId: number,
  formData: FormData,
) {
  const name = readText(formData, "name");
  const description = readText(formData, "description");
  const status = readText(formData, "status");

  if (!name) {
    throw new Error("Project name is required");
  }

  await createProject(workspaceId, {
    name,
    description: description || undefined,
    status: status || "active",
  });

  revalidatePath(`/workspaces/${workspaceId}`);
  revalidatePath("/");
}

export async function updateProjectAction(
  workspaceId: number,
  projectId: number,
  formData: FormData,
) {
  const name = readText(formData, "name");
  const description = readText(formData, "description");
  const status = readText(formData, "status");

  if (!name) {
    throw new Error("Project name is required");
  }

  await updateProject(workspaceId, projectId, {
    name,
    description: description || undefined,
    status: status || "active",
  });

  revalidatePath("/");
  revalidatePath(`/workspaces/${workspaceId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
}

export async function deleteProjectAction(
  workspaceId: number,
  projectId: number,
) {
  await deleteProject(workspaceId, projectId);

  revalidatePath("/");
  revalidatePath(`/workspaces/${workspaceId}`);
  redirect(`/workspaces/${workspaceId}`);
}

export async function createTaskAction(
  workspaceId: number,
  projectId: number,
  formData: FormData,
) {
  const rawAgentId = readText(formData, "agent_id");
  const title = readText(formData, "title");
  const description = readText(formData, "description");
  const status = readText(formData, "status");
  const priority = readText(formData, "priority");
  const displayOrder = readOptionalNumber(formData, "display_order");
  const taskDependencies = readTaskDependencies(formData, "task_dependencies");

  if (!title) {
    throw new Error("Task title is required");
  }

  await createTask(workspaceId, projectId, {
    agent_id:
      Number.isInteger(Number(rawAgentId)) && Number(rawAgentId) > 0
        ? Number(rawAgentId)
        : undefined,
    title,
    description: description || undefined,
    node_type: "task",
    status: status || "todo",
    priority: priority || "medium",
    display_order: displayOrder,
    task_dependencies: taskDependencies,
  });

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function planProjectAction(
  workspaceId: number,
  projectId: number,
  formData: FormData,
) {
  const plannerAgentId = Number(readText(formData, "planner_agent_id"));

  if (!Number.isInteger(plannerAgentId) || plannerAgentId <= 0) {
    throw new Error("请选择规划 Agent");
  }

  await planProject(workspaceId, projectId, {
    planner_agent_id: plannerAgentId,
  });

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function submitPlanProjectAction(
  workspaceId: number,
  projectId: number,
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
  formData: FormData,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    const plannerAgentId = Number(readText(formData, "planner_agent_id"));

    if (!Number.isInteger(plannerAgentId) || plannerAgentId <= 0) {
      throw new Error("请选择规划 Agent");
    }

    const result = await planProject(workspaceId, projectId, {
      planner_agent_id: plannerAgentId,
    });

    revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
    revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
    revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
    revalidatePath(`/workspaces/${workspaceId}`);

    return {
      ok: true,
      message: `已生成 ${result.created_task_count} 个任务。${result.summary}`,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function updateTaskAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  formData: FormData,
) {
  const rawAgentId = readText(formData, "agent_id");
  const title = readText(formData, "title");
  const description = readText(formData, "description");
  const status = readText(formData, "status");
  const priority = readText(formData, "priority");
  const displayOrder = readOptionalNumber(formData, "display_order");
  const taskDependencies = readTaskDependencies(formData, "task_dependencies");

  if (!title) {
    throw new Error("Task title is required");
  }

  await updateTask(workspaceId, projectId, taskId, {
    agent_id:
      rawAgentId === ""
        ? null
        : Number.isInteger(Number(rawAgentId)) && Number(rawAgentId) > 0
          ? Number(rawAgentId)
          : undefined,
    title,
    description: description || undefined,
    status: status || "todo",
    priority: priority || "medium",
    display_order: displayOrder,
    task_dependencies: taskDependencies,
  });

  revalidatePath(`/workspaces/${workspaceId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
}

export async function updateTaskStatusAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  formData: FormData,
) {
  const status = readText(formData, "status");

  if (!status) {
    throw new Error("Task status is required");
  }

  await updateTaskStatus(workspaceId, projectId, taskId, { status });

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function submitTaskStatusFormAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  previousState: TaskActionState = DEFAULT_TASK_ACTION_STATE,
  formData: FormData,
): Promise<TaskActionState> {
  void previousState;

  try {
    await updateTaskStatusAction(workspaceId, projectId, taskId, formData);
    return {
      ok: true,
      message: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function bulkUpdateTaskStatusAction(
  workspaceId: number,
  projectId: number,
  formData: FormData,
) {
  const status = readText(formData, "status");
  const taskIds = Array.from(
    new Set(
      formData
        .getAll("task_ids")
        .map((item) => Number(item))
        .filter((item) => Number.isInteger(item) && item > 0),
    ),
  );

  if (!status) {
    throw new Error("Task status is required");
  }

  if (taskIds.length === 0) {
    throw new Error("At least one task must be selected");
  }

  await Promise.all(
    taskIds.map((taskId) =>
      updateTaskStatus(workspaceId, projectId, taskId, { status }),
    ),
  );

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}`);
}

export async function submitTaskEditFormAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  previousState: TaskActionState = DEFAULT_TASK_ACTION_STATE,
  formData: FormData,
): Promise<TaskActionState> {
  void previousState;

  try {
    await updateTaskAction(workspaceId, projectId, taskId, formData);
    return {
      ok: true,
      message: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function deleteTaskAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
) {
  await deleteTask(workspaceId, projectId, taskId);

  revalidatePath(`/workspaces/${workspaceId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
}

export async function submitDeleteTaskAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  previousState: TaskActionState = DEFAULT_TASK_ACTION_STATE,
): Promise<TaskActionState> {
  void previousState;

  try {
    await deleteTaskAction(workspaceId, projectId, taskId);
    return {
      ok: true,
      message: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function connectTaskAction(
  workspaceId: number,
  projectId: number,
  formData: FormData,
) {
  const sourceTaskId = Number(formData.get("source_task_id"));
  const targetTaskId = Number(formData.get("target_task_id"));

  if (!Number.isInteger(sourceTaskId) || sourceTaskId <= 0) {
    throw new Error("Source task is required");
  }

  if (!Number.isInteger(targetTaskId) || targetTaskId <= 0) {
    throw new Error("Target task is required");
  }

  if (sourceTaskId === targetTaskId) {
    throw new Error("Source and target task cannot be the same");
  }

  const tasks = await listTasks(workspaceId, projectId);
  const targetTask = tasks.find((task) => task.id === targetTaskId);

  if (!targetTask) {
    throw new Error("Target task not found");
  }

  const taskDependencies = Array.from(
    new Set([...targetTask.task_dependencies, sourceTaskId]),
  );

  await updateTask(workspaceId, projectId, targetTaskId, {
    title: targetTask.title,
    description: targetTask.description ?? undefined,
    status: targetTask.status,
    priority: targetTask.priority,
    display_order: targetTask.display_order,
    task_dependencies: taskDependencies,
  });

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}

export async function moveTaskOrderAction(
  workspaceId: number,
  projectId: number,
  taskId: number,
  direction: "up" | "down",
) {
  const tasks = await listTasks(workspaceId, projectId);
  const movableTasks = tasks
    .filter((task) => task.node_type !== "start")
    .sort((left, right) => left.display_order - right.display_order);
  const currentIndex = movableTasks.findIndex((task) => task.id === taskId);

  if (currentIndex === -1) {
    throw new Error("Task not found for reorder");
  }

  const nextIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
  if (nextIndex < 0 || nextIndex >= movableTasks.length) {
    return;
  }

  const currentTask = movableTasks[currentIndex];
  const swapTask = movableTasks[nextIndex];

  await Promise.all([
    updateTask(workspaceId, projectId, currentTask.id, {
      title: currentTask.title,
      description: currentTask.description ?? undefined,
      status: currentTask.status,
      priority: currentTask.priority,
      display_order: swapTask.display_order,
      task_dependencies: currentTask.task_dependencies,
    }),
    updateTask(workspaceId, projectId, swapTask.id, {
      title: swapTask.title,
      description: swapTask.description ?? undefined,
      status: swapTask.status,
      priority: swapTask.priority,
      display_order: currentTask.display_order,
      task_dependencies: swapTask.task_dependencies,
    }),
  ]);

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}

export async function createWorkflowRunAction(
  workspaceId: number,
  projectId: number,
  formData?: FormData,
) {
  const triggerType = formData ? readText(formData, "trigger_type") : "";
  const rawInputPayload = formData ? readText(formData, "input_payload") : "";

  let inputPayload: Record<string, unknown> | undefined;
  if (rawInputPayload) {
    try {
      inputPayload = JSON.parse(rawInputPayload) as Record<string, unknown>;
    } catch {
      throw new Error("Input payload must be valid JSON");
    }
  }

  await createWorkflowRun(workspaceId, projectId, {
    trigger_type:
      triggerType === "api" ||
      triggerType === "schedule" ||
      triggerType === "retry"
        ? triggerType
        : "manual",
    input_payload: inputPayload,
  });

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}

export async function deleteWorkflowRunAction(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
) {
  await deleteWorkflowRun(workspaceId, projectId, workflowRunId);

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
  redirect(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
}

export async function executeTaskRunAction(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
  taskRunId: number,
) {
  await executeTaskRun(workspaceId, projectId, workflowRunId, taskRunId);

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}

export async function executeWorkflowRunAction(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
) {
  await executeWorkflowRun(workspaceId, projectId, workflowRunId);

  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/workflow`);
  revalidatePath(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}

export async function submitExecuteTaskRunAction(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
  taskRunId: number,
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    await executeTaskRunAction(workspaceId, projectId, workflowRunId, taskRunId);
    return {
      ok: true,
      message: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}

export async function submitExecuteWorkflowRunAction(
  workspaceId: number,
  projectId: number,
  workflowRunId: number,
  previousState: FormFeedbackState = DEFAULT_FORM_FEEDBACK_STATE,
): Promise<FormFeedbackState> {
  void previousState;

  try {
    await executeWorkflowRunAction(workspaceId, projectId, workflowRunId);
    return {
      ok: true,
      message: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: getActionErrorMessage(error),
    };
  }
}
