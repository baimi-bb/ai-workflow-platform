"use client";

import { useActionState } from "react";

import { submitPlanProjectAction } from "@/lib/actions";
import {
  DEFAULT_FORM_FEEDBACK_STATE,
  type FormFeedbackState,
} from "@/lib/action-state";
import type { Agent } from "@/lib/types";

type AiProjectPlannerFormProps = {
  workspaceId: number;
  projectId: number;
  plannerAgents: Agent[];
};

export function AiProjectPlannerForm({
  workspaceId,
  projectId,
  plannerAgents,
}: AiProjectPlannerFormProps) {
  const [state, formAction, pending] = useActionState<FormFeedbackState, FormData>(
    submitPlanProjectAction.bind(null, workspaceId, projectId),
    DEFAULT_FORM_FEEDBACK_STATE,
  );

  return (
    <div className="mb-6 rounded-[24px] border border-sky-100 bg-[linear-gradient(180deg,_#eff6ff_0%,_#ffffff_100%)] p-5 shadow-[0_12px_30px_rgba(14,165,233,0.10)]">
      <div className="mb-4">
        <p className="text-sm font-medium text-sky-700">AI 自动规划 Workflow</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-950">
          基于当前项目自动生成任务与流程
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          规划 Agent 会直接读取当前项目的名称和描述，自动补出一组新的
          tasks、依赖关系和可分配的 Agent。
        </p>
      </div>

      <form action={formAction} className="space-y-4">
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700">规划 Agent</span>
          <select
            name="planner_agent_id"
            required
            defaultValue={plannerAgents[0]?.id ? String(plannerAgents[0].id) : ""}
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-sky-300"
          >
            {plannerAgents.length === 0 ? (
              <option value="">当前没有可用的 Agent</option>
            ) : null}
            {plannerAgents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name} / {agent.provider_model_label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="submit"
          disabled={pending || plannerAgents.length === 0}
          className="w-full rounded-2xl bg-sky-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {pending ? "正在生成..." : "用 AI 生成任务与 Workflow"}
        </button>
      </form>

      {state.message ? (
        <p
          className={`mt-4 rounded-2xl px-4 py-3 text-sm ${
            state.ok ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
          }`}
        >
          {state.message}
        </p>
      ) : null}
    </div>
  );
}
