# 开发状态

最后更新：2026-07-18（Asia/Shanghai）

## 第 0 阶段：仓库和规范

状态：已完成

- [x] 建立独立 `survival-agent` Git 仓库与 Monorepo 目录。
- [x] 初始化 React + TypeScript + Vite 图形前端。
- [x] 初始化 FastAPI 后端。
- [x] 配置 SQLite、SQLAlchemy、WAL、Foreign Keys、Busy Timeout。
- [x] 配置 Alembic，并通过 migration 创建基础元数据表。
- [x] 创建 `GET /api/health`。
- [x] 前端显示后端连接、检查中和断开状态，可手动重试。
- [x] 配置 Vitest、pytest、ESLint、Ruff、Prettier。
- [x] 创建架构、数据库和开发状态文档及 `.env.example`。
- [x] 完成前端构建、后端测试、迁移和健康检查验证。

## 验收证据

| 检查                          | 结果                                           |
| ----------------------------- | ---------------------------------------------- |
| `npm run build:web`           | 通过                                           |
| `npm run lint:web`            | 通过                                           |
| `npm run test:web`            | 通过                                           |
| `uv run ruff check .`         | 通过                                           |
| `uv run pytest`               | 通过                                           |
| `uv run alembic upgrade head` | 通过                                           |
| `GET /api/health`             | HTTP 200，数据库状态 healthy，journal mode wal |
| 桌面浏览器 1536×1024          | 通过，连接状态与概念图一致，控制台 0 error     |
| 移动浏览器 390×844            | 通过，无横向溢出或内容裁切                     |
| “重新检查”交互                | 通过，重新请求后保持健康状态                   |

浏览器验证先尝试 Codex 内置浏览器，但其客户端策略阻止访问本机 `localhost`；因此按前端验证规则回退到 Playwright CLI。最终截图保存在 `docs/design/phase-0-status-implementation.png`。

## 下一阶段

第 1 阶段将实现 Hermes 风格三栏图形前端骨架和独立页面，使用 Mock 数据完成交互，但不连接真实模型。进入前必须保持第 0 阶段验证持续通过。
