import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Save, Settings } from "lucide-react";
import { useEffect, useState } from "react";

import { chatApi } from "../../services/chat";
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
  base_url: "https://api.openai.com/v1",
  model: "gpt-5.6",
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
  const [form, setForm] = useState<ModelForm>(emptyForm);
  const [saved, setSaved] = useState(false);
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
    mutationFn: chatApi.updateModelSetting,
    onSuccess: () => {
      setSaved(true);
      void queryClient.invalidateQueries({
        queryKey: ["model-setting", "main"],
      });
      window.setTimeout(() => setSaved(false), 1800);
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
                setting.data?.has_api_key ? "key-status ready" : "key-status"
              }
            >
              <KeyRound />
              {setting.data?.has_api_key
                ? "环境密钥已就绪"
                : "缺少 OPENAI_API_KEY"}
            </span>
          </div>
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
              <b>密钥只从环境变量读取</b>
              <p>
                在项目 `.env` 中设置 `OPENAI_API_KEY`，然后重启后端。设置 API
                不接收密钥字段，SQLite 也不会保存明文密钥。
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
            数据目录
            <input value="%APPDATA%/SurvivalAgent/data" readOnly />
          </label>
          <label className="toggle-row">
            <span>
              <b>启用本地文件工具</b>
              <small>工具路径将在第 3 阶段限制到 Workspace 内。</small>
            </span>
            <input type="checkbox" disabled />
          </label>
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
