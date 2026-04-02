"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  setDefaultProviderModelAction,
  submitDeleteProviderModelAction,
  submitUpdateProviderModelAction,
  toggleProviderModelAction,
} from "@/lib/actions";
import { DEFAULT_FORM_FEEDBACK_STATE } from "@/lib/action-state";
import type { Provider, ProviderModel } from "@/lib/types";
import { formatDate } from "@/lib/ui";

type ProviderModelCardProps = {
  model: ProviderModel;
  providers: Provider[];
};

export default function ProviderModelCard({
  model,
  providers,
}: ProviderModelCardProps) {
  const editPanelRef = useRef<HTMLDetailsElement>(null);
  const [editState, editAction] = useActionState(
    submitUpdateProviderModelAction.bind(null, model.id),
    DEFAULT_FORM_FEEDBACK_STATE,
  );
  const [deleteState, deleteAction, deletePending] = useActionState(
    submitDeleteProviderModelAction.bind(null, model.id),
    DEFAULT_FORM_FEEDBACK_STATE,
  );

  useEffect(() => {
    if (!editState.message) {
      return;
    }

    if (editState.ok && editPanelRef.current) {
      editPanelRef.current.open = false;
    }

    window.alert(editState.message);
  }, [editState]);

  useEffect(() => {
    if (!deleteState.message) {
      return;
    }
    window.alert(deleteState.message);
  }, [deleteState]);

  return (
    <article className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,_#ffffff_0%,_#ecfeff_100%)] p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
            {model.provider_platform} / {model.provider_label}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">
            {model.label}
          </h3>
          <p className="mt-1 font-mono text-sm text-slate-500">
            {model.model_name}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              model.is_enabled
                ? "bg-emerald-100 text-emerald-800"
                : "bg-slate-100 text-slate-600"
            }`}
          >
            {model.is_enabled ? "enabled" : "disabled"}
          </span>
          {model.is_default ? (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              default
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <div className="flex items-center justify-between gap-4">
          <span>Temperature</span>
          <span className="font-mono">{model.temperature ?? "-"}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span>Max Output Tokens</span>
          <span className="font-mono">{model.max_output_tokens ?? "-"}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span>Tools</span>
          <span>{model.supports_tools ? "supported" : "no"}</span>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between text-sm text-slate-500">
        <span>{formatDate(model.updated_at)}</span>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {!model.is_default ? (
            <form action={setDefaultProviderModelAction.bind(null, model.id)}>
              <button
                type="submit"
                className="rounded-full bg-amber-100 px-3 py-2 text-sm text-amber-800 transition hover:bg-amber-200"
              >
                设为默认
              </button>
            </form>
          ) : null}

          <form
            action={toggleProviderModelAction.bind(
              null,
              model.id,
              !model.is_enabled,
            )}
          >
            <button
              type="submit"
              className="rounded-full bg-slate-100 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-200"
            >
              {model.is_enabled ? "禁用" : "启用"}
            </button>
          </form>
        </div>
      </div>

      <details ref={editPanelRef} className="mt-4 rounded-[20px] border border-slate-200 bg-white p-3">
        <summary className="cursor-pointer list-none rounded-xl bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-sky-500">
          编辑配置
        </summary>

        <form action={editAction} className="mt-3 grid gap-3">
          <input type="hidden" name="provider_id" value={model.provider_id} />

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Provider</span>
            <select
              defaultValue={model.provider_id}
              disabled
              className="w-full rounded-2xl border border-slate-200 bg-slate-100 px-4 py-3 outline-none"
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label} ({provider.platform})
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">显示名称</span>
            <input
              name="label"
              required
              defaultValue={model.label}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">模型名</span>
            <input
              name="model_name"
              required
              defaultValue={model.model_name}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-sky-300"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">Temperature</span>
              <input
                name="temperature"
                type="number"
                min="0"
                max="2"
                step="0.1"
                defaultValue={model.temperature ?? ""}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">Max Output Tokens</span>
              <input
                name="max_output_tokens"
                type="number"
                min="1"
                defaultValue={model.max_output_tokens ?? ""}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">支持 Tools</span>
              <select
                name="supports_tools"
                defaultValue={model.supports_tools ? "true" : "false"}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
              >
                <option value="false">no</option>
                <option value="true">yes</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">状态</span>
              <select
                name="is_enabled"
                defaultValue={model.is_enabled ? "true" : "false"}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
              >
                <option value="true">enabled</option>
                <option value="false">disabled</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">默认模型</span>
              <select
                name="is_default"
                defaultValue={model.is_default ? "true" : "false"}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-sky-300"
              >
                <option value="false">no</option>
                <option value="true">yes</option>
              </select>
            </label>
          </div>

          <button
            type="submit"
            className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            保存配置
          </button>
        </form>
      </details>

      <form action={deleteAction} className="mt-3">
        <button
          type="submit"
          disabled={deletePending}
          className="w-full rounded-2xl bg-rose-100 px-4 py-3 text-sm font-medium text-rose-700 transition hover:bg-rose-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {deletePending ? "删除中..." : "删除配置"}
        </button>
      </form>
    </article>
  );
}
