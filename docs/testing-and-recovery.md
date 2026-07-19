# 测试与恢复

## 自动化矩阵

- 后端：`uv run pytest -q`，覆盖对话、工具、账本、实时/正式记忆、Worker、Skill、并发、恢复、导出与脱敏。
- 前端：`npm run test:web`，覆盖结构化流、反馈、管理页和设置页真实下载动作。
- 独立 E2E：后端测试启动 `tests/e2e/phase8_backend_flow.py`，在全新 Alembic SQLite 和独立应用进程中跑 22 回合闭环。
- 浏览器：Playwright CLI 连接真实 8000 后端与 5173 前端，验收桌面/390px 设置页、真实下载及 0 console error。
- 桌面：`phase9_sidecar_flow.py` 启动真实 PyInstaller 进程；Cargo 测试空闲端口/目录；Computer Use 验收安装后的 Tauri 图形窗口、重开持久化和进程回收。

## 崩溃恢复语义

1. assistant final 事务提交前退出：没有半截 assistant、账本或 trace；回合保持未完成状态。
2. Worker 模型调用期间退出：Job 已 durable 领取，下一进程启动恢复为 pending，正式记忆仍是旧版本。
3. Worker 原子提交成功后退出：Revision、Snapshot、consumed delta、memory version 与 completed Job 同时存在。
4. 用户编辑与 Worker 冲突：Worker 不覆盖新 revision，Job 标记 conflict 并在 10/30 秒后重新读取；第三次失败等待手动重试。
5. SQLite 临时繁忙：连接等待 5 秒；仍繁忙时 API 返回 503 和 `Retry-After: 1`，客户端可安全重试。

## 人工恢复检查

```powershell
uv run alembic current
uv run pytest tests/backend/test_phase8_stability.py -q
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

健康响应必须为 `journal_mode=wal`。不要复制正在写入的 `.db-wal`/`.db-shm` 单文件；设置页导出使用一致读快照，是推荐的可移植恢复材料。桌面数据位于 `%APPDATA%/SurvivalAgent`，其中 `backups/` 为正式备份目标目录；卸载应用前后都应保留这一用户目录。

## 桌面恢复检查

```powershell
npm run build:sidecar
uv run python tests/e2e/phase9_sidecar_flow.py
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

若桌面窗口未出现，先查看 `%APPDATA%/SurvivalAgent/logs/desktop-launch.log`，再检查四个目录权限和安装资源中的 `resources/sidecar/survival-agent-api.exe`。不要把 API Key 或代理凭据复制进日志；密钥应由设置页写入 Windows 凭据管理器。
