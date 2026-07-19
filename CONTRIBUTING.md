# 参与贡献

感谢关注 Survival Agent。项目目前处于 `0.1.0-alpha`，优先接受可复现的问题报告、小范围修复和测试改进。

## 提交问题

请先搜索已有 Issue，并提供：

- Windows、Node.js、Python 和应用版本；
- 最小复现步骤、预期结果和实际结果；
- 已脱敏的错误信息；
- 是否能在新建 SQLite 数据库和空 Workspace 中复现。

不要在 Issue、截图或日志中提交 API Key、Authorization Header、代理凭据、私人对话、数据库或 Workspace 内容。安全漏洞请按 [`SECURITY.md`](SECURITY.md) 私下报告。

## 本地验证

```powershell
npm install
uv sync --dev
uv run alembic upgrade head
npm run lint:web
npm run test:web
npm run build:web
uv run ruff check .
uv run pytest
```

涉及桌面端时还应执行：

```powershell
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
npm run build:sidecar
uv run python tests/e2e/phase9_sidecar_flow.py
```

## Pull Request

- 一个 PR 只解决一个主题，并说明根因、行为变化和验证证据。
- 数据库变更必须提供 Alembic 迁移，并验证空库升级及必要的降级路径。
- 不得降低 Workspace 路径限制、密钥隔离、严格结构校验或历史可恢复性。
- 不提交生成目录、安装包、数据库、日志、Workspace、真实凭据或个人绝对路径。
- 新行为应包含与风险相称的自动化测试和文档更新。

当前仓库未授予通用开源许可。提交贡献前，请确认你有权提供相关内容；维护者合并贡献不代表对仓库其他内容授予额外许可。
