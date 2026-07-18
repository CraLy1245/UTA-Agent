# End-to-end tests

第 8 阶段端到端覆盖：

- `phase8_backend_flow.py` 在全新 Alembic SQLite 数据库和独立进程中完成 22 回合链路。
- 第 20 回合触发 Durable Job，第 21 回合不被后台整理阻塞，第 22 回合读取新正式记忆。
- 满意奖励精确执行且重复反馈不重复奖励，导出覆盖完整数据。
- 关闭并重新打开应用 lifespan 后，会话、记忆和后台任务仍然存在。
- 图形前端使用 Playwright CLI 对真实后端进行桌面与移动浏览器验收；命令和结果记录在
  `docs/development-status.md`。
