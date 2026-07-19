# 桌面打包与发布

## 构建链

1. `npm run build:web` 生成 React 生产资源。
2. `npm run build:sidecar` 使用固定 PyInstaller 6.16.0 生成 `--onedir`、windowed Python Sidecar，并复制到 Tauri resources。
3. `npm --workspace @survival-agent/desktop run build` 编译 Tauri release 并生成当前用户 NSIS 安装器。

合并命令是 `npm run desktop:build`。安装器输出到
`apps/desktop/src-tauri/target/release/bundle/nsis/Survival Agent_0.1.0_x64-setup.exe`。
构建缓存、Sidecar 二进制、release 产物和安装包不提交 Git。

若机器已有代理，只把现有、已验证可用的代理放进当前构建进程的 `HTTP_PROXY/HTTPS_PROXY`；不要把地址或凭据写入 npm 配置、源码、脚本、日志或文档。未配置代理且直连可用时无需新增代理。

## 启动与退出

- Tauri 绑定 `127.0.0.1:0` 获取候选空闲端口，释放后启动 Sidecar；若竞态导致失败，重新选端口，最多三次。
- Sidecar 创建四个用户目录、设置 SQLite/日志/Workspace 环境并执行 Alembic head。
- `/api/health` 在 30 秒内成功后 Shell 才完成启动；失败原因追加到用户日志，不包含密钥。
- 正常关闭发送带随机令牌的本地 shutdown 请求，等待最多 8 秒后才强制回收。Sidecar 由 `CREATE_NO_WINDOW` 启动，不显示命令行窗口。

## 密钥

开发模式只读取 `OPENAI_API_KEY`/`SURVIVAL_AGENT_OPENAI_API_KEY`。桌面设置页通过 Tauri command 写入 Windows 凭据管理器的 `SurvivalAgent / OPENAI_API_KEY` 条目；首次保存后重开应用加载。密钥不进入 Sidecar 参数、数据库、日志、导出、测试快照、安装包或 Git。

## 发布前检查

- 空库 Migration upgrade/downgrade/upgrade。
- 56 个后端测试、8 个前端测试、生产构建、Cargo 测试。
- 真实 PyInstaller 启停、未授权关闭拒绝、重开持久化。
- NSIS 安装、双击启动、无控制台、随机端口、关闭无残留进程。
- `%APPDATA%/SurvivalAgent` 四目录、SQLite WAL 与数据重开。
- 真实模型流、工具、Token、记忆、Worker、Skill 和设置页系统凭据。

当前本地安装包没有代码签名。内部测试可使用，但面向其他用户分发前应取得 Windows Authenticode 证书并在 CI 中签名安装器与主程序；证书私钥不得进入仓库。
