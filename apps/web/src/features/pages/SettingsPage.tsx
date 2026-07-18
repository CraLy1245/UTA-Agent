import { Save, Settings } from "lucide-react";
import { PageScaffold } from "./PageScaffold";

export function SettingsPage() {
  return (
    <PageScaffold
      title="设置"
      description="配置模型、工具与本地数据选项。第 1 阶段仅保存 Mock 状态。"
      icon={Settings}
      action={
        <button className="primary-button">
          <Save />
          保存设置
        </button>
      }
    >
      <form
        className="settings-form"
        onSubmit={(event) => event.preventDefault()}
      >
        <section>
          <h2>主对话模型</h2>
          <div className="form-grid">
            <label>
              API Base URL
              <input defaultValue="https://api.openai.com/v1" />
            </label>
            <label>
              模型名称
              <input defaultValue="gpt-5" />
            </label>
            <label>
              最大输出 Token
              <input type="number" defaultValue="8192" />
            </label>
            <label>
              API Key
              <input type="password" placeholder="仅存于本地环境" />
            </label>
          </div>
        </section>
        <section>
          <h2>本地工作区</h2>
          <label className="wide-field">
            数据目录
            <input defaultValue="%APPDATA%/SurvivalAgent/data" />
          </label>
          <label className="toggle-row">
            <span>
              <b>启用本地文件工具</b>
              <small>工具路径将在第 3 阶段限制到 Workspace 内。</small>
            </span>
            <input type="checkbox" defaultChecked />
          </label>
        </section>
        <section className="danger-zone">
          <h2>危险操作</h2>
          <p>重置 Token、记忆或所有本地数据前必须二次确认。</p>
          <button type="button">打开重置选项</button>
        </section>
      </form>
    </PageScaffold>
  );
}
