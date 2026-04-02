export type Task = {
  id: number;
  project_id: number;
  agent_id: number | null;
  agent_name: string | null;
  title: string;
  description: string | null;
  node_type: "start" | "task" | "end";
  status: string;
  priority: string;
  display_order: number;
  canvas_x: number;
  canvas_y: number;
  task_dependencies: number[];
  created_at: string;
  updated_at: string;
};

export type WorkflowRun = {
  id: number;
  project_id: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  trigger_type: "manual" | "api" | "schedule" | "retry";
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskRun = {
  id: number;
  workflow_run_id: number;
  task_id: number;
  assigned_agent_id: number | null;
  assigned_agent_name: string | null;
  title_snapshot: string;
  node_type: "start" | "task" | "end";
  status:
    | "pending"
    | "ready"
    | "running"
    | "waiting_human"
    | "completed"
    | "failed"
    | "skipped"
    | "cancelled";
  executor_type: "system" | "agent" | "human";
  task_dependencies_snapshot: number[];
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  attempt_count: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRunDetail = WorkflowRun & {
  task_runs: TaskRun[];
};

export type Provider = {
  id: number;
  platform: "openai" | "anthropic" | "google" | "deepseek" | "openrouter" | "custom";
  label: string;
  api_key_preview: string;
  base_url: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type ProviderValidationResult = {
  is_valid: boolean;
  message: string;
  resolved_base_url: string | null;
};

export type ProviderModel = {
  id: number;
  provider_id: number;
  provider_label: string;
  provider_platform: string;
  label: string;
  model_name: string;
  is_enabled: boolean;
  is_default: boolean;
  temperature: number | null;
  max_output_tokens: number | null;
  supports_tools: boolean;
  created_at: string;
  updated_at: string;
};

export type ProviderModelValidationResult = {
  is_valid: boolean;
  message: string;
  resolved_model_name: string | null;
};

export type Agent = {
  id: number;
  workspace_id: number;
  provider_model_id: number;
  provider_model_label: string;
  provider_model_name: string;
  provider_label: string;
  provider_platform: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  is_enabled: boolean;
  max_concurrency: number;
  created_at: string;
  updated_at: string;
};

export type WorkspaceFileEntry = {
  name: string;
  relative_path: string;
  entry_type: "directory" | "file";
  size: number | null;
  modified_at: string | null;
};

export type WorkspaceFileList = {
  workspace_id: number;
  root_path: string;
  current_path: string;
  entries: WorkspaceFileEntry[];
};

export type Project = {
  id: number;
  workspace_id: number;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  tasks: Task[];
};

export type ProjectPlanTask = {
  id: number;
  title: string;
  assigned_agent_id: number | null;
  assigned_agent_name: string | null;
  priority: "low" | "medium" | "high";
  task_dependencies: number[];
};

export type ProjectPlanResult = {
  summary: string;
  created_task_count: number;
  created_tasks: ProjectPlanTask[];
};

export type Workspace = {
  id: number;
  name: string;
  description: string | null;
  root_path: string | null;
  agents: Agent[];
  created_at: string;
  updated_at: string;
  projects: Project[];
};
