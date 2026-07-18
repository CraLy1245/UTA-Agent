import {
  Activity,
  Bot,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Plus,
  Search,
  Settings,
  Sparkles,
  Brain,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { BrandMark } from "../../components/BrandMark";
import { useUiStore } from "../../stores/uiStore";

const navigation = [
  { to: "/chat/mock-1", label: "聊天", icon: MessageSquare },
  { to: "/memory", label: "记忆", icon: Brain },
  { to: "/skills", label: "技能", icon: Sparkles },
  { to: "/activity", label: "活动", icon: Activity },
  { to: "/settings", label: "设置", icon: Settings },
];

const conversations = [
  ["mock-1", "产品开发规划", "刚刚"],
  ["mock-2", "本地文件整理方案", "11:24"],
  ["mock-3", "长程记忆设计讨论", "昨天"],
  ["mock-4", "工具安全边界检查", "周三"],
];

export function ConversationSidebar() {
  const collapsed = useUiStore((state) => state.conversationsCollapsed);
  const toggle = useUiStore((state) => state.toggleConversations);

  return (
    <aside
      className={`conversation-sidebar ${collapsed ? "is-collapsed" : ""}`}
    >
      <div className="brand-row">
        <BrandMark />
        <div className="brand-copy">
          <strong>Survival Agent</strong>
          <span>
            <i />
            本地模式
          </span>
        </div>
      </div>

      <nav className="primary-nav" aria-label="主导航">
        {navigation.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <Icon size={19} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="conversation-section">
        <div className="section-title">
          <span>对话</span>
          <Bot size={16} />
        </div>
        <button className="new-chat-button" type="button">
          <Plus size={18} />
          <span>新建对话</span>
        </button>
        <label className="conversation-search">
          <Search size={17} />
          <input aria-label="搜索对话" placeholder="搜索对话" />
        </label>
        <div className="conversation-list">
          {conversations.map(([id, title, time], index) => (
            <NavLink
              key={id}
              to={`/chat/${id}`}
              className={index === 0 ? "selected" : ""}
            >
              <span>{title}</span>
              <time>{time}</time>
            </NavLink>
          ))}
        </div>
      </div>

      <button
        className="collapse-control"
        type="button"
        onClick={toggle}
        aria-label={collapsed ? "展开会话栏" : "折叠会话栏"}
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        <span>折叠侧栏</span>
      </button>
    </aside>
  );
}
