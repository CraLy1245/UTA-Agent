import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, KeyRound, Save, Settings } from "lucide-react";
import { useEffect, useState } from "react";

import { chatApi } from "../../services/chat";
import {
  desktopHasSecureApiKey,
  isDesktopRuntime,
  storeDesktopApiKey,
} from "../../services/desktop";
import { PageScaffold } from "./PageScaffold";

type ModelForm = {
  base_url: string;
  model: string;
  timeout_seconds: number;
  max_output_tokens: number;
  temperature: number | null;
  enabled: boolean;
};

const emptyForm: ModelForm = {
  base_url: "https://api.a6api.com/v1",
  model: "gpt-5.6-sol",
  timeout_seconds: 120,
  max_output_tokens: 8192,
  temperature: null,
  enabled: true,
};

export function SettingsPage() {
  const queryClient = useQueryClient();
  const setting = useQuery({
    queryKey: ["model-setting", "main"],
    queryFn: chatApi.getModelSetting,
  });
  const toolStatus = useQuery({
    queryKey: ["tool-status"],
    queryFn: chatApi.getToolStatus,
  });
  const [form, setForm] = useState<ModelForm>(emptyForm);
  const [saved, setSaved] = useState(false);
  const [exported, setExported] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const desktop = isDesktopRuntime();
  useEffect(() => {
    if (!setting.data) return;
    setForm({
      base_url: setting.data.base_url,
      model: setting.data.model,
      timeout_seconds: setting.data.timeout_seconds,
      max_output_tokens: setting.data.max_output_tokens,
      temperature: setting.data.temperature,
      enabled: setting.data.enabled,
    });
  }, [setting.data]);
  const save = useMutation({
    mutationFn: async (values: ModelForm) => {
      const result = await chatApi.updateModelSetting(values);
      if (desktop && apiKey) await storeDesktopApiKey(apiKey);
      return result;
    },
    onSuccess: () => {
      setSaved(true);
      setApiKey("");
      void queryClient.invalidateQueries({
        queryKey: ["model-setting", "main"],
      });
      window.setTimeout(() => setSaved(false), 1800);
    },
  });
  const exportData = useMutation({
    mutationFn: chatApi.exportData,
    onSuccess: ({ blob, filename }) => {
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
      setExported(true);
      window.setTimeout(() => setExported(false), 1800);
    },
  });

  return (
    <PageScaffold
      title="设置"
      description="配置 OpenAI 兼容模型与本地数据选项。密钥不会写入数据库。"
      icon={Settings}
      action={
        <button
          className="primary-button"
          type="button"
          onClick={() => save.mutate(form)}
          disabled={save.isPending}
        >
          <Save />
          {save.isPending ? "保存中…" : saved ? "已保存" : "保存设置"}
        </button>
      }
    >
      <form
        className="settings-form"
        onSubmit={(event) => event.preventDefault()}
      >
        <section>
          <div className="settings-section-heading">
            <h2>主对话模型</h2>
            <span
              className={
                setting.data?.has_api_key || desktopHasSecureApiKey()
                  ? "key-status ready"
                  : "key-status"
              }
            >
              <KeyRound />
              {setting.data?.has_api_key || desktopHasSecureApiKey()
                ? desktop
                  ? "系统凭据密钥已就绪"
                  : "环境密钥已就绪"
                : desktop
                  ? "尚未保存系统凭据"
                  : "缺少 OPENAI_API_KEY"}
            </span>
          </div>
          {desktop ? (
            <label className="wide-field">
              API Key（Windows 凭据管理器）
              <input
                type="password"
                autoComplete="new-password"
                value={apiKey}
                placeholder="输入后随模型设置一起保存"
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
          ) : null}
          <div className="form-grid">
            <label>
              API Base URL
              <input
                value={form.base_url}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    base_url: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              模型名称
              <input
                value={form.model}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    model: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              最大输出 Token
              <input
                type="number"
                value={form.max_output_tokens}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    max_output_tokens: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              超时（秒）
              <input
                type="number"
                value={form.timeout_seconds}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    timeout_seconds: Number(event.target.value),
                  }))
                }
              />
            </label>
          </div>
          <div className="credential-note">
            <CheckCircle2 />
            <div>
              <b>
                {desktop ? "密钥保存在操作系统凭据库" : "密钥只从环境变量读取"}
              </b>
              <p>
                {desktop
                  ? "桌面端不会把密钥写入 SQLite、日志或 Sidecar 参数。首次保存后重新打开应用即可加载。"
                  : "在项目 `.env` 中设置 `OPENAI_API_KEY`，然后重启后端。设置 API 不接收密钥字段，SQLite 也不会保存明文密钥。"}
              </p>
            </div>
          </div>
        </section>
        <section>
          <h2>后续模型角色</h2>
          <p className="settings-copy">
            数据库已为后台记忆模型与 Skill
            整理模型保留独立角色；它们将在对应阶段接入，可继续复用当前主模型配置。
          </p>
        </section>
        <section>
          <h2>本地工作区</h2>
          <label className="wide-field">
            Workspace 路径
            <input
              value={toolStatus.data?.workspace_path ?? "加载中…"}
              readOnly
            />
          </label>
          <label className="toggle-row">
            <span>
              <b>启用本地文件工具</b>
              <small>
                只提供列目录、读文件和写文件；绝对路径与越界访问会被拒绝。
              </small>
            </span>
            <input
              type="checkbox"
              checked={toolStatus.data?.enabled ?? false}
              readOnly
              aria-label="本地文件工具启用状态"
            />
          </label>
          <p className="settings-copy">
            可用工具：
            {toolStatus.data?.available_tools.join("、") || "无"}
          </p>
        </section>
        <section>
          <h2>数据导出</h2>
          <p className="settings-copy">
            导出当前 SQLite 中的会话、账本、记忆、后台任务与 Skill
            版本。导出在同一 WAL 读快照内生成，并自动清理密钥和 Authorization
            信息。
          </p>
          <button
            className="secondary-button export-button"
            type="button"
            disabled={exportData.isPending}
            onClick={() => exportData.mutate()}
          >
            <Download />
            {exportData.isPending
              ? "导出中…"
              : exported
                ? "导出完成"
                : "导出 JSON"}
          </button>
          {exportData.isError ? (
            <p className="form-error">导出失败，请稍后重试。</p>
          ) : null}
        </section>
        <section className="danger-zone">
          <h2>危险操作</h2>
          <p>
            重置
            Token、记忆或所有本地数据前必须二次确认；这些操作将在相应阶段实现。
          </p>
          <button type="button" disabled>
            打开重置选项
          </button>
        </section>
      </form>
    </PageScaffold>
  );
}
