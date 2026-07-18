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

## 第 1 阶段：Hermes 风格前端骨架

状态：已完成

- [x] 三栏桌面布局：会话导航、对话区、Agent 状态栏。
- [x] 会话搜索、新建对话与 Mock 会话切换。
- [x] 对话消息、工具调用折叠、复制、满意/不满意和输入状态。
- [x] 记忆、Skill、后台活动和设置独立页面。
- [x] 左右侧栏折叠与小屏自适应。
- [x] 使用 Mock 数据，不连接真实模型。

## 第 1 阶段验收证据

| 检查                 | 结果                                                |
| -------------------- | --------------------------------------------------- |
| `npm run lint:web`   | 通过                                                |
| `npm run test:web`   | 通过，4 个测试                                      |
| `npm run build:web`  | 通过                                                |
| 1536×1024 桌面浏览器 | 三栏完整，无横向溢出                                |
| 390×844 移动浏览器   | 导航折叠，无横向溢出                                |
| 页面路由             | Chat、Memory、Skills、Activity、Settings 全部可访问 |
| Mock 交互            | 工具展开、满意状态、左右侧栏折叠均通过              |
| 浏览器运行时         | 控制台 0 error/warning                              |

视觉概念保存在 `docs/design/phase-1-chat-concept.png`。浏览器验证使用本机已有 Playwright CLI；Codex 内置浏览器技能存在，但本任务环境没有提供其可调用入口。

## 第 2 阶段：真实对话

状态：已完成

- [x] 非敏感模型配置持久化，API Key 仅从环境变量读取。
- [x] OpenAI 兼容 Chat Completions SSE Provider。
- [x] 会话创建、切换、重命名和删除。
- [x] 消息与回合 SQLite 持久化。
- [x] 结构化 WebSocket 流式输出。
- [x] 停止生成、失败状态和重新生成。
- [x] 页面刷新后消息恢复，模型错误不导致前端崩溃。
- [x] 使用真实外部端点与 `gpt-5.6-sol` 完成模型回答。

## 第 2 阶段当前验收证据

| 检查                   | 结果                                      |
| ---------------------- | ----------------------------------------- |
| `uv run ruff check .`  | 通过                                      |
| `uv run pytest`        | 通过，12 个后端测试                       |
| `npm run lint:web`     | 通过                                      |
| `npm run test:web`     | 通过，5 个前端测试                        |
| `npm run build:web`    | 通过                                      |
| Alembic 空库升级       | 通过，创建 main/memory/skill 三个模型角色 |
| 跨进程 OpenAI 兼容 SSE | 通过，三段 delta + usage + completed      |
| 浏览器 1536×1024       | 新建、发送、流式完成、刷新恢复均通过      |
| 浏览器 390×844         | 无横向溢出或裁切                          |
| 浏览器运行时           | 控制台 0 error/warning                    |
| 真实外部模型           | `gpt-5.6-sol` 流式回答成功，刷新后保持    |
| 真实回合持久化         | completed，input 6591 / output 12 tokens  |

Codex 内置浏览器技能可见但当前没有提供可调用的浏览器入口，因此沿用第 1 阶段已验证的本机 Playwright 路径。受控 QA 使用独立 SQLite 和跨进程 OpenAI 兼容服务；真实验收使用 `https://api.a6api.com/v1` 与 `gpt-5.6-sol`，验证了真实流式回答、SQLite 持久化和刷新恢复。API Key 未写入数据库、日志或 Git。

## 第 3 阶段：工具能力

状态：已完成

- [x] 主模型可结构化调用列目录、读取 UTF-8 文本和写入文件三个本地工具。
- [x] 工具调用结果按原始调用 ID 回传模型，模型继续循环并生成最终回答。
- [x] 工具执行过程通过 `tool.started`、`tool.completed`、`tool.failed` WebSocket 事件显示。
- [x] 参数、结果、状态和错误由真实 SQLite/Alembic `tool_executions` 表持久化，刷新后恢复。
- [x] 所有路径限制在配置的 Workspace；拒绝绝对路径、父目录穿越和解析后的链接逃逸。
- [x] 写入已有文件必须显式 `overwrite=true`，并使用同目录临时文件原子替换。
- [x] API Key 仍仅来自环境变量，未进入工具参数、数据库、日志或 Git。

## 第 3 阶段验收证据

| 检查                     | 结果                                                             |
| ------------------------ | ---------------------------------------------------------------- |
| `uv run ruff check .`    | 通过                                                             |
| `uv run pytest -q`       | 通过，18 个后端测试                                              |
| `npm run lint:web`       | 通过                                                             |
| `npm run test:web`       | 通过，5 个前端测试                                               |
| `npm run build:web`      | 通过                                                             |
| Alembic 既有库与空库升级 | 通过，升级到 `20260718_0003`                                     |
| 真实模型三步工具循环     | `gpt-5.6-sol` 依次写入、读取、列目录并生成最终回答               |
| SQLite/API 复核          | 3 条 completed 工具记录与磁盘文件内容一致，刷新后仍显示          |
| Workspace 越界           | `read_file ../outside.txt` 被拒绝并持久化为 failed，模型正确解释 |
| 桌面浏览器 1536×1024     | 工具详情、折叠、最终回答均正常，无横向溢出                       |
| 移动浏览器 390×844       | 工具卡片与输入区自适应，无横向溢出                               |
| 浏览器运行时             | 控制台 0 error                                                   |

本阶段开发前完整读取根目录更新版 PDF（44 页），提取文本 SHA-256 为 `b4b50d3975e33f944cb3b008b6b48998ac7594ec22907ab32aebf73127572a56`。Codex 内置浏览器和 Chrome 扩展访问本机地址时均被客户端策略以 `ERR_BLOCKED_BY_CLIENT` 阻止，因此沿用已验证的 Playwright 浏览器路径完成真实桌面与移动验收。真实文件保存在本地忽略的 `workspace/phase3/real-tool-loop.txt`，内容为 `phase3-real-ok`。

## 第 4 阶段：Token 生存账本

状态：已完成

- [x] 读取 1,000,000,000 Token、输出 100,000,000 Token 的初始账户由 Alembic 初始化。
- [x] 统一 UsageNormalizer 保存 Provider raw usage 与 normalized usage，不重复计算 cache/reasoning 明细。
- [x] 100 Units = 1 Token，所有扣款与 108% 奖励使用整数计算。
- [x] 每个成功最终回合原子保存消息、Usage、两条扣款、余额和不可变 execution trace。
- [x] 每轮模型动态看到当前读取/输出余额，余额不足不自动拒绝任务。
- [x] 满意首次精确返还两类消耗的 108%，重复满意不重复奖励；不满意不返还。
- [x] quality_feedback 与 survival_reward 通道分离，评价可修改、历史保留、已发奖励不撤销。
- [x] 右侧状态栏显示余额、本轮消耗和交易历史；回答支持满意、不满意与 2,000 字文字反馈。
- [x] API Key 未写入账户、交易、反馈、execution trace、日志或 Git。

## 第 4 阶段验收证据

| 检查                     | 结果                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `uv run ruff check .`    | 通过                                                                                 |
| `uv run pytest -q`       | 通过，24 个后端测试                                                                  |
| `npm run lint:web`       | 通过                                                                                 |
| `npm run test:web`       | 通过，6 个前端测试                                                                   |
| `npm run build:web`      | 通过                                                                                 |
| Alembic 既有库与空库升级 | 通过，升级到 `20260718_0004` 并初始化两类账户                                        |
| UsageNormalizer          | raw/normalized 同时保存；cache/reasoning 不重复扣除；缺字段安全归零并标记 incomplete |
| 真实模型回合             | `gpt-5.6-sol` 成功完成；raw usage = input 4,772 / output 12                          |
| 真实扣款                 | read -477,200 Units，output -1,200 Units，余额与交易前后值一致                       |
| 首次满意 108%            | read +515,376 Units，output +1,296 Units，无浮点误差                                 |
| 重复满意                 | 奖励交易仍为 2 条，余额与交易数均不再变化                                            |
| 修改为不满意             | 追加负反馈和文字记录，不返还新 Token，也不撤销已发奖励                               |
| execution trace          | 模型、raw/normalized Usage、4,580ms 延迟、completed 状态与空 revision IDs 均持久化   |
| 刷新恢复                 | 余额、4 条交易、最终不满意选中态及文字反馈全部恢复                                   |
| 桌面浏览器 1280×720      | 三栏、两类余额、反馈编辑与交易状态正常                                               |
| 移动浏览器 390×844       | 无横向溢出，`scrollWidth = clientWidth = 390`                                        |
| 浏览器运行时             | Codex 内置浏览器直接完成验收，桌面/移动控制台 0 error/warning                        |

本阶段开发前完整读取根目录最新版 44 页 PDF，并视觉核对 Token、反馈分离、execution trace 与阶段安排页；带页标记的提取文本 SHA-256 为 `c2fb82052b220ddb9037ada3435576e3f5ccf0981f37b81b538bb7a254d73a09`。真实验收会话为 `db83c033-85ac-4547-8dd5-cb2fb1474517`，执行轨迹为 `674d21d5-73f2-4e33-8c12-a432a6d1eb91`。早期阶段回合不追溯扣款，避免伪造 raw Usage；账本从第 4 阶段迁移后的真实完成回合开始。

## 第 5 阶段：实时记忆

状态：已完成

- [x] 确定性检测“请记住”“以后”“以后不要”、明确偏好与纠正语义，不额外调用模型。
- [x] `memory_delta` 使用真实 SQLite/Alembic 保存原始表达、来源回合、优先级、状态、Unicode 字符数和 revision ID。
- [x] 新指令从因果顺序中的下一回合开始动态注入，当前回合与重新生成的同源回合不会自注入。
- [x] execution trace 只保存本轮实际注入的 memory revision IDs。
- [x] 有效实时增量最多 2,000 字符；重复项合并占用，近期纠正优先，溢出记录保留为 deferred。
- [x] 记忆页使用真实 API 显示占用、搜索、状态、来源回合和 revision；右侧栏显示实时占用。
- [x] 未实现第 6 阶段正式记忆、20 回合 Job、Worker、Revision/Snapshot 或第 7 阶段 Skill。

## 第 5 阶段验收证据

| 检查                     | 结果                                                                            |
| ------------------------ | ------------------------------------------------------------------------------- |
| `uv run ruff check .`    | 通过                                                                            |
| `uv run pytest -q`       | 通过，29 个后端测试                                                             |
| `npm run lint:web`       | 通过                                                                            |
| `npm run test:web`       | 通过，6 个前端测试                                                              |
| `npm run build:web`      | 通过                                                                            |
| Alembic 既有库与空库升级 | 通过，升级到 `20260718_0005` 并创建 `memory_delta`                              |
| 下一回合动态注入         | 当前回合 trace 为空；后续独立会话 trace 精确包含 revision `8d022682…`           |
| 真实模型跨会话验收       | `gpt-5.6-sol` 仅凭实时记忆回答 `CLI`，input 662 / output 100 tokens             |
| 误触发边界               | 引用“以后不要”的元问句最初暴露误判；规则修复、回归测试通过，QA 误记录已精确删除 |
| 2,000 字符容量与重复合并 | 有效占用不超限；近期纠正优先；deferred/duplicate 记录完整保留                   |
| 刷新/独立进程恢复        | 记忆内容、20 字符占用、来源和 revision 均从 SQLite 恢复                         |
| 桌面 Chrome 1280×720     | 记忆页 1 条真实记录、右侧占用一致，`scrollWidth = clientWidth = 1280`           |
| 移动 Chrome 390×844      | 卡片、筛选与来源信息自适应，`scrollWidth = clientWidth = 390`                   |
| 浏览器运行时             | 控制台 0 error/warning、网络请求 0 个失败                                       |

本阶段开发前完整读取根目录 44 页更新版 PDF，文件 SHA-256 为 `3D5635A699B3C1365A2A89FCC6EC71F1E4DD5A9405E8D6E3873E11968CBC6DCA`，并视觉核对记忆、实时增量、阶段安排和 execution trace 补充页。应用内浏览器连接成功但客户端以 `ERR_BLOCKED_BY_CLIENT` 阻止本地地址，因此按前端测试技能回退到本机已有 Chrome + Playwright，不安装浏览器或项目依赖。真实记忆来源回合为 `96368903-4390-4fc0-9b83-2c3f4afc6efa`，跨会话回答回合为 `bbbe00d2-10e9-42ae-ab01-70c04dd76c93`。

## 第 6 阶段：20 回合认知整理

状态：已完成

- [x] 只有 assistant final、消息、账本和 trace 原子成功提交后才计入完整回合；取消/失败/工具/反馈不计。
- [x] 每 20 回合创建唯一冻结范围的 Durable Job；Worker 网络调用不持写锁，启动可恢复超时任务。
- [x] 后台模型输出严格 JSON；确定性校验 Schema、真实 ID、来源、锁定、乐观版本、字符预算、显式增量保真与空 Skill 操作。
- [x] 自动重试 10/30 秒，第三次停止 failed；用户可手动 retry；失败不改变旧正式记忆、不 consume 增量。
- [x] 正式记忆 18,000 + 实时增量 2,000；历史/归档不计额度且不永久删除。
- [x] memory item/revision/snapshot/version、consumed Job、FTS5 检索与实际注入 trace 全部使用真实 SQLite/Alembic。
- [x] 记忆管理支持搜索、锁定、编辑 API、归档、恢复、历史与回滚；后台活动显示范围、状态、尝试、结果、错误与重试。
- [x] 第 7 阶段 Skill Registry/演化/版本竞争未实现，后台 `skill_index` 与 `skill_operations` 固定为空。

## 第 6 阶段验收证据

| 检查 | 结果 |
| --- | --- |
| Ruff / pytest | 通过，37 个后端测试 |
| ESLint / Vitest / build | 通过，6 个前端测试与生产构建 |
| Alembic 既有库 | 升级到 `20260718_0006`，历史 7 个 completed 回合确定性编号 |
| Alembic 空库往返 | base→head、0006→0005→0006 通过；FTS5、state 与全部正式表存在 |
| 冻结 20 回合 | 7 个既有真实回合 + 13 个真实 `gpt-5.6-sol` 回合，只创建 1—20 唯一 Job |
| 失败恢复 | 首次真实输出三次严格校验失败，按 10/30 秒重试并停止；旧记忆/增量/版本均未改变 |
| 手动重试与真实 Worker | 收紧精确 Schema 后通过 retry 完成；Job `8b55a280…`，attempt 4，memory version 1 |
| 内容保真修复 | 发现模型压缩丢失指令后新增逐字保真校验；以版本化编辑恢复，错误 revision 保留审计，当前 version 2 |
| consumed/正式 revision | delta `1cc1758f…` → Job `8b55a280…`；当前正式 revision `1174aa86…` |
| 下一回合实际注入 | 回合 `25aee974…` 回复“已记录。”，trace 精确记录 revision `1174aa86…` |
| Playwright 桌面/移动 | 真实记忆、revision 历史、consumed 链、后台批次与右栏状态正确；控制台 0 error/warning，API 0 失败 |

本阶段开发前完整读取根目录最新 44 页 PDF，SHA-256 为 `3D5635A699B3C1365A2A89FCC6EC71F1E4DD5A9405E8D6E3873E11968CBC6DCA`，并视觉核对第 6 阶段、并发、阶段安排与递归改进补充页。真实后台模型角色已设置为非敏感配置 `https://api.a6api.com/v1` + `gpt-5.6-sol`；密钥只由用户后端进程的环境变量提供。浏览器证据位于本地忽略目录 `output/playwright/phase6-activity-*.png`。
