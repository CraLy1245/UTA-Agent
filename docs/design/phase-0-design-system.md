# 第 0 阶段视觉基准

概念图：`phase-0-status-concept.png`

## Design tokens

- Rail：`#071B38` 深海军蓝。
- Main background：`#F8FAFC` 冷浅灰，内容面板为 `#FFFFFF`。
- Primary text：`#0F172A`；secondary text：`#64748B`。
- Success：`#15945B`，成功背景 `#F0FBF5`。
- Border：`#D7DEE8`；圆角 16px；轻微冷色阴影。
- 字体：系统中文无衬线，标题 48px/700，正文 18px，控件 15px/600。

## 组件

- 品牌 Rail：固定宽度，阶段 1 可扩展为会话侧栏。
- Status panel：单一焦点面板，不使用卡片网格。
- Status banner：支持 loading、connected、disconnected 三种语义状态。
- Detail rows：开放式分隔列表。
- Retry button：明确键盘焦点和 disabled 状态。

该基准只约束第 0 阶段连接页，不代表第 1 阶段完整信息架构已经确定。
