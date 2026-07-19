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

| 检查                    | 结果                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| Ruff / pytest           | 通过，37 个后端测试                                                                              |
| ESLint / Vitest / build | 通过，6 个前端测试与生产构建                                                                     |
| Alembic 既有库          | 升级到 `20260718_0006`，历史 7 个 completed 回合确定性编号                                       |
| Alembic 空库往返        | base→head、0006→0005→0006 通过；FTS5、state 与全部正式表存在                                     |
| 冻结 20 回合            | 7 个既有真实回合 + 13 个真实 `gpt-5.6-sol` 回合，只创建 1—20 唯一 Job                            |
| 失败恢复                | 首次真实输出三次严格校验失败，按 10/30 秒重试并停止；旧记忆/增量/版本均未改变                    |
| 手动重试与真实 Worker   | 收紧精确 Schema 后通过 retry 完成；Job `8b55a280…`，attempt 4，memory version 1                  |
| 内容保真修复            | 发现模型压缩丢失指令后新增逐字保真校验；以版本化编辑恢复，错误 revision 保留审计，当前 version 2 |
| consumed/正式 revision  | delta `1cc1758f…` → Job `8b55a280…`；当前正式 revision `1174aa86…`                               |
| 下一回合实际注入        | 回合 `25aee974…` 回复“已记录。”，trace 精确记录 revision `1174aa86…`                             |
| Playwright 桌面/移动    | 真实记忆、revision 历史、consumed 链、后台批次与右栏状态正确；控制台 0 error/warning，API 0 失败 |

本阶段开发前完整读取根目录最新 44 页 PDF，SHA-256 为 `3D5635A699B3C1365A2A89FCC6EC71F1E4DD5A9405E8D6E3873E11968CBC6DCA`，并视觉核对第 6 阶段、并发、阶段安排与递归改进补充页。真实后台模型角色已设置为非敏感配置 `https://api.a6api.com/v1` + `gpt-5.6-sol`；密钥只由用户后端进程的环境变量提供。浏览器证据位于本地忽略目录 `output/playwright/phase6-activity-*.png`。

## 第 7 阶段：Skill 演化

状态：已完成

- [x] 7A Skill Registry：真实创建、检索、更新、合并、锁定、归档、不可变 Revision、来源与回滚。
- [x] Worker 只接受严格 Skill JSON 操作；自动新建要求三次复用或用户明确保存，锁定与 expected revision 由确定性代码校验。
- [x] 单轮最多动态加载 3 个 Skill、合计 8,000 字符；成功 trace 与 `skill_usage` 保存实际 Revision IDs。
- [x] 7B Candidate/Stable/Rejected/Superseded 生命周期与同一稳定版本最多一个候选。
- [x] 候选固定 9:1 可重放路由，至少 5 次有效使用，并按 60/20/15/5 固定权重与硬阈值评估。
- [x] 自动晋升、连续失败拒绝、晋升后观察期自动回滚，以及用户暂停/晋升/拒绝/锁定/回滚优先权。
- [x] quality feedback 准确归因实际 Revision；评价修改重算统计，survival reward 仍独立且不重复发放。
- [x] Skill 页面和后台活动页使用真实 API，显示稳定/候选、使用次数、满意率、Token 均值、版本与完整事件链。

## 第 7 阶段验收证据

| 检查                    | 结果                                                                                |
| ----------------------- | ----------------------------------------------------------------------------------- |
| Ruff / pytest           | 通过，45 个后端测试                                                                 |
| ESLint / Vitest / build | 通过，7 个前端测试与生产构建                                                        |
| Alembic 空库往返        | base→0007、0007→0006→0007 通过；实际库升级到 `20260718_0007`                        |
| 7A 版本与阈值           | 单次任务禁止自动碎片化；用户创建、编辑、锁定、归档、恢复、Revision 与审计通过       |
| trace 与动态加载        | 真实回合只注入稳定 Revision `d7815129…`，trace 与 usage 精确一致                    |
| 确定性 9:1              | 第 10 次选择 Candidate 可重放；不匹配任务不加载；每轮不超过 3 个/8,000 字符         |
| 7B 竞争                 | 5 次前不晋升；质量高 10 点、客观不降、Token≤150% 后晋升；两次失败拒绝               |
| 回滚保护                | 晋升观察期连续两次不满意自动恢复上一稳定 Revision；历史不删除                       |
| 反馈/奖励分离           | 修改质量评价重算 Skill 统计；既有 108% 幂等测试全部继续通过                         |
| 真实模型                | `gpt-5.6-sol` 回答“第7阶段 Skill 注入成功”，结构化流与 SQLite 持久化通过            |
| 内置浏览器桌面          | `/skills` 列表、演化详情、锁定→解锁、`/activity` 审计链通过，控制台 0 error/warning |
| 内置浏览器移动 390×844  | `scrollWidth = clientWidth = 390`，无横向溢出、裁切或框架错误层                     |

本阶段开发前由新接力对话完整读取根目录 44 页 PDF，文件 SHA-256 为 `3D5635A699B3C1365A2A89FCC6EC71F1E4DD5A9405E8D6E3873E11968CBC6DCA`，并核对 HEAD `78c5c7c` 与干净工作树。真实验收 Skill 为 `99bfca25-1510-4b4d-aded-e9b9bdd8ac85`，稳定 Revision 为 `d7815129-9294-4072-b673-1a89d250f3dd`，回答回合为 `b0a6a398-7fec-4041-85bc-5ebc8fa5e8c9`。API Key 仅存在于用户后端进程环境变量，未写入数据库、日志、测试、契约或 Git。

## 第 8 阶段：稳定性和完整测试

状态：已完成

- [x] Worker 使用 SQLite `BEGIN IMMEDIATE` 原子领取；双 Session 并发只能领取一次。
- [x] 记忆与 Skill 乐观版本继续返回 409；Worker conflict 以 10/30 秒自动重读最新 payload，第三次失败后等待用户重试。
- [x] 查询跳过未到期重试任务，后续 ready Job 不被队头阻塞；前台第 21 回合不等待 1—20 后台整理。
- [x] 新进程启动立即回收上一进程遗留的 running/validating/committing 领取；已提交 WAL 事务、账本和版本保持完整。
- [x] 设置页可下载 19 表同一 WAL 读快照 JSON；密钥环境字段排除，所有字符串/嵌套 JSON 统一脱敏。
- [x] `app.log`、`agent.log`、`worker.log`、`error.log` 使用轮转、固定上下文和统一脱敏；SQLite busy 返回安全 503。
- [x] 独立进程 22 回合 E2E 覆盖 20 回合触发、21 回合继续、22 回合新记忆、108% 幂等反馈、导出和重启持久化。
- [x] 未提前实现第 9 阶段 Tauri、PyInstaller、Sidecar、空闲端口或 Windows 安装包。

## 第 8 阶段验收证据

| 检查                    | 结果                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| Ruff / pytest           | 通过，54 个后端测试，含独立进程完整 E2E                                                       |
| ESLint / Vitest / build | 通过，8 个前端测试与生产构建                                                                  |
| 双 Worker 并发          | 同一 Durable Job 两个线程竞争，只有一个 claim 成功                                            |
| conflict / 重试         | conflict 可观察并按 10/30 秒重新领取；未来 retry 不阻塞 ready Job                             |
| 崩溃与重开              | 启动恢复旧领取；引擎 dispose/reopen 后记录存在，`PRAGMA integrity_check=ok`                   |
| 22 回合 E2E             | 20 回合创建 1—20 Job；21 回合完成；整理后 22 回合读取新正式记忆；重开后 44 条消息存在         |
| 反馈分离                | 第 22 回合满意首次奖励，重复满意 `granted_now=false`；quality feedback 不改变奖励幂等键       |
| 真实模型                | `gpt-5.6-sol` 回答“稳定性验收通过”；回合 `c79b3d24-49be-41a8-a185-bb7b4e066e50`，663/9 tokens |
| 真实导出                | 设置页下载 102,023 bytes、19 表 JSON；key shape/Bearer/secret assignment 三类扫描均 0 命中    |
| Playwright 桌面/移动    | 1440×900 与 390×844 设置页、下载、状态栏通过；console 0 error/warning，无横向溢出             |

本阶段开发前新接力对话完整读取根目录最新 44 页 PDF，文件 SHA-256 为 `3D5635A699B3C1365A2A89FCC6EC71F1E4DD5A9405E8D6E3873E11968CBC6DCA`，核对 HEAD `f870035` 与干净工作树。真实后端保持 `https://api.a6api.com/v1` + `gpt-5.6-sol`；API Key 只存在于用户启动的后端环境变量。本阶段没有 Schema 变化，Alembic head 仍为 `20260718_0007`。

## 第 9 阶段：Tauri 桌面封装

状态：功能与本地桌面链路已通过；等待用户在图形设置页写入真实 API Key 后完成最终真实模型复验。

- [x] Tauri 2 Shell 与生产 React 资源，运行时动态 REST/WebSocket loopback 地址。
- [x] PyInstaller 6.16.0 `--onedir` windowed Sidecar、启动前 Alembic、四个 `%APPDATA%` 用户目录。
- [x] 自动空闲端口、三次重试、30 秒健康门禁、随机关闭令牌、8 秒优雅退出与无残留进程。
- [x] Windows 凭据管理器 API Key 保存；SQLite、日志、参数、导出、安装资源与 Git 均不保存密钥。
- [x] NSIS x64 当前用户安装器、真实安装、双击图形启动、重开数据保留。
- [x] 收紧 Cognitive Worker 提示词中的 Memory/Skill 独立字段契约，并增加错误字段混用回归测试；严格拒绝未知字段的安全边界保持不变。
- [ ] 用户在桌面设置页保存真实密钥并重开后，完成 `gpt-5.6-sol` 最终桌面流式回合。

## 第 9 阶段验收证据

| 检查                    | 结果                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| PDF / 基线              | 完整读取 44 页，SHA-256 `3D5635…CBC6DCA`；基线 HEAD `9e5b09e` 干净                                 |
| Ruff / pytest           | 通过，57 个后端测试                                                                                |
| ESLint / Vitest / build | 通过，8 个前端测试与生产构建                                                                       |
| Cargo                   | 2 个 Rust 单元测试通过；debug/release 原生链接通过                                                 |
| Alembic                 | 空库 base→`20260719_0008`、0008→0007→0008 通过；默认 a6api + `gpt-5.6-sol`                         |
| PyInstaller E2E         | `PHASE9_SIDECAR_OK`：健康、四目录、拒绝无令牌关闭、优雅退出、重开 SQLite 保留                      |
| NSIS                    | `Survival Agent_0.1.0_x64-setup.exe` 真实生成并当前用户安装；最终 hash 在发布产物中核验            |
| 代理                    | 环境/npm 未配置代理；发现并验证 Windows 用户本机代理后，仅对失败的 NSIS 下载进程临时使用，未持久化 |
| 桌面 UI                 | Computer Use 验收 1440×900 三栏、设置页系统凭据、a6api/sol、创建会话、关闭、重开后会话存在         |
| 进程                    | 主窗口无控制台；Sidecar 是直接子进程且仅监听随机 `127.0.0.1` 端口；关闭后两者均退出                |
| 用户数据                | `%APPDATA%/SurvivalAgent/{data,logs,workspace,backups}` 与真实 SQLite 创建，升级重开保留           |
| 安全                    | Sidecar 参数无 API Key；凭据只走 Windows Credential Manager；安装包未签名，公开发布前需签名证书    |

本阶段没有伪造凭据验收。用户当前桌面数据库和安装程序均已保留；最后一个真实模型检查需要用户亲自在桌面设置页输入密钥，避免密钥进入自动化工具参数或执行记录。
