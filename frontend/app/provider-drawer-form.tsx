"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  createProviderAction,
  validateProviderAction,
} from "@/lib/actions";
import { DEFAULT_FORM_FEEDBACK_STATE } from "@/lib/action-state";

type ProviderDrawerFormProps = {
  providersCount: number;
};

export default function ProviderDrawerForm({
  providersCount,
}: ProviderDrawerFormProps) {
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const [validationState, validationAction, validationPending] = useActionState(
    validateProviderAction,
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
      <summary className="list-none rounded-full bg-violet-100 px-4 py-2 text-sm font-medium text-violet-700 transition hover:cursor-pointer hover:bg-violet-200">
        添加 Provider
      </summary>

      <div className="pointer-events-none fixed inset-0 z-40 hidden bg-slate-950/30 opacity-0 transition group-open:block group-open:opacity-100" />
      <div className="pointer-events-none fixed inset-y-0 right-0 z-50 hidden w-full max-w-md translate-x-full border-l border-slate-200 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.16)] transition duration-300 group-open:block group-open:translate-x-0">
        <div className="pointer-events-auto flex h-full flex-col">
          <div className="border-b border-slate-200 px-6 py-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-500">Provider 配置</p>
                <h3 className="mt-1 text-2xl font-semibold text-slate-950">
                  添加新的平台账号
                </h3>
              </div>
              <div className="flex items-center gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                  {providersCount} 个
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
            <form action={createProviderAction} className="space-y-4">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">平台</span>
                <select
                  name="platform"
                  defaultValue="openai"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="custom">Custom</option>
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">名称</span>
                <input
                  name="label"
                  required
                  placeholder="例如：OpenAI 主账号"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">API Key</span>
                <input
                  name="api_key"
                  required
                  type="password"
                  placeholder="输入你的 API Key"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Base URL</span>
                <input
                  name="base_url"
                  placeholder="可选，例如：https://api.openai.com/v1"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono outline-none transition focus:border-orange-300 focus:bg-white"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">状态</span>
                <select
                  name="is_enabled"
                  defaultValue="true"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-orange-300 focus:bg-white"
                >
                  <option value="true">enabled</option>
                  <option value="false">disabled</option>
                </select>
              </label>

              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-medium text-slate-700">API 检测</p>
                <p className="mt-2 text-xs leading-6 text-slate-500">
                  保存前可先检测当前 API Key 和 Base URL 是否可用。
                </p>
                <button
                  type="submit"
                  formAction={validationAction}
                  disabled={validationPending}
                  className="mt-4 w-full rounded-2xl bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {validationPending ? "检测中..." : "检测 API 是否有效"}
                </button>
              </div>

              <button
                type="submit"
                className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
              >
                添加 Provider
              </button>
            </form>
          </div>
        </div>
      </div>
    </details>
  );
}
