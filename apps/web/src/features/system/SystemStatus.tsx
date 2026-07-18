import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, LoaderCircle, RefreshCw } from "lucide-react";

import { fetchHealth } from "../../services/health";

export function SystemStatus() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
  });

  const connected = healthQuery.isSuccess;
  const checking = healthQuery.isPending || healthQuery.isFetching;
  const title = connected
    ? "系统已就绪"
    : healthQuery.isError
      ? "本地服务未连接"
      : "正在检查系统";
  const subtitle = connected
    ? "前端已连接到本地服务"
    : healthQuery.isError
      ? "请确认 FastAPI 服务已启动，然后重新检查"
      : "正在验证 API 和数据库状态";

  return (
    <main className="system-main">
      <section className="status-panel" aria-labelledby="system-title">
        <header className="status-panel__header">
          <h1 id="system-title">{title}</h1>
          <p>{subtitle}</p>
        </header>

        <div
          className={`connection-banner connection-banner--${connected ? "connected" : healthQuery.isError ? "error" : "checking"}`}
          role="status"
          aria-live="polite"
        >
          <span className="connection-banner__icon">
            {connected ? (
              <Check size={22} strokeWidth={2.8} />
            ) : healthQuery.isError ? (
              <AlertTriangle size={22} strokeWidth={2.3} />
            ) : (
              <LoaderCircle className="spin" size={22} strokeWidth={2.3} />
            )}
          </span>
          <span>
            {connected
              ? "后端连接正常"
              : healthQuery.isError
                ? "后端连接失败"
                : "正在连接后端"}
          </span>
        </div>

        <dl className="system-details">
          <div>
            <dt>API</dt>
            <dd>/api/health</dd>
          </div>
          <div>
            <dt>数据库</dt>
            <dd>
              {connected
                ? `SQLite · ${healthQuery.data.database.journal_mode.toUpperCase()}`
                : "SQLite · WAL"}
            </dd>
          </div>
          <div>
            <dt>环境</dt>
            <dd>
              {connected && healthQuery.data.environment === "development"
                ? "开发模式"
                : connected
                  ? healthQuery.data.environment
                  : "开发模式"}
            </dd>
          </div>
        </dl>

        <button
          className="retry-button"
          type="button"
          onClick={() => void healthQuery.refetch()}
          disabled={checking}
        >
          <RefreshCw className={checking ? "spin" : undefined} size={19} />
          {checking ? "检查中" : "重新检查"}
        </button>
      </section>
      <p className="phase-label">第 0 阶段 · 基础架构</p>
    </main>
  );
}
