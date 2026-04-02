"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  createProviderModelAction,
  validateProviderModelAction,
} from "@/lib/actions";
import { DEFAULT_FORM_FEEDBACK_STATE } from "@/lib/action-state";
import type { Provider, ProviderModel } from "@/lib/types";

type ModelDrawerFormProps = {
  providers: Provider[];
  providerModels: ProviderModel[];
};

export default function ModelDrawerForm({
  providers,
  providerModels,
}: ModelDrawerFormProps) {
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const [validationState, validationAction, validationPending] = useActionState(
    validateProviderModelAction,
    DEFAULT_FORM_FEEDBACK_STATE,
  );

  useEffect(() => {
    if (!validationState.message) {
      return;
    }
    window.alert(validationState.message);
  }, [validationState]);

  return (
    <details ref={detailsRef} className="group">
      <summary className="list-none rounded-full bg-cyan-100 px-4 py-2 text-sm font-medium text-cyan-700 transition hover:cursor-pointer hover:bg-cyan-200">
        添加 Model
      </summary>

      <div className="pointer-events-none fixed inset-0 z-40 hidden bg-slate-950/30 opacity-0 transition group-open:block group-open:opacity-100" />
      <div className="pointer-events-none fixed inset-y-0 right-0 z-50 hidden w-full max-w-md translate-x-full border-l border-slate-200 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.16)] transition duration-300 group-open:block group-open:translate-x-0">
        <div className="pointer-events-auto flex h-full flex-col">
          <div className="border-b border-slate-200 px-6 py-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-500">Model 配置</p>
                <h3 className="mt-1 text-2xl font-semibold text-slate-950">
                  添加 Provider 模型
                </h3>
              </div>
              <div className="flex items-center gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                  {providerModels.length} 个
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (detailsRef.current) {
                      detailsRef.current.open = false;
                    }
                  }}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-xl leading-none text-slate-700 transition hover:bg-slate-200"
                  aria-label="关闭抽屉"
                >
                  ×
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <form action={createProviderModelAction} className="space-y-4">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Provider</span>
                <select
                  name="provider_id"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                >
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.label} ({provider.platform})
                    </option>
                  ))}
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">显示名称</span>
                <input
                  name="label"
                  required
                  placeholder="例如：Fast Default"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">模型名</span>
                <input
                  name="model_name"
                  required
                  placeholder="例如：gpt-4.1-mini"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-cyan-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Temperature</span>
                <input
                  name="temperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  placeholder="例如：0.3"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Max Output Tokens</span>
                <input
                  name="max_output_tokens"
                  type="number"
                  min="1"
                  placeholder="例如：4000"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">支持工具调用</span>
                <select
                  name="supports_tools"
                  defaultValue="false"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                >
                  <option value="false">no</option>
                  <option value="true">yes</option>
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">启用状态</span>
                <select
                  name="is_enabled"
                  defaultValue="true"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                >
                  <option value="true">enabled</option>
                  <option value="false">disabled</option>
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">默认模型</span>
                <select
                  name="is_default"
                  defaultValue="false"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-cyan-300 focus:bg-white"
                >
                  <option value="false">no</option>
                  <option value="true">yes</option>
                </select>
              </label>

              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-medium text-slate-700">模型检测</p>
                <p className="mt-2 text-xs leading-6 text-slate-500">
                  保存前可先检查当前 Provider 下是否真的可用这个模型名。
                </p>
                <button
                  type="submit"
                  formAction={validationAction}
                  disabled={validationPending}
                  className="mt-4 w-full rounded-2xl bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {validationPending ? "检测中..." : "检测模型是否可用"}
                </button>
              </div>

              <button
                type="submit"
                className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                添加 Model
              </button>
            </form>
          </div>
        </div>
      </div>
    </details>
  );
}
