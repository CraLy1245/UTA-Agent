import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  Brain,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Settings,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { BrandMark } from "../../components/BrandMark";
import { chatApi } from "../../services/chat";
import { useUiStore } from "../../stores/uiStore";

const navigation = [
  { to: "/chat/new", label: "聊天", icon: MessageSquare },
  { to: "/memory", label: "记忆", icon: Brain },
  { to: "/skills", label: "技能", icon: Sparkles },
  { to: "/activity", label: "活动", icon: Activity },
  { to: "/settings", label: "设置", icon: Settings },
];

export function ConversationSidebar() {
  const collapsed = useUiStore((state) => state.conversationsCollapsed);
  const toggle = useUiStore((state) => state.toggleConversations);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: chatApi.listConversations,
  });
  const createConversation = useMutation({
    mutationFn: () => chatApi.createConversation(),
    onSuccess: (conversation) => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate(`/chat/${conversation.id}`);
    },
  });
  const renameConversation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      chatApi.renameConversation(id, title),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
  const deleteConversation = useMutation({
    mutationFn: chatApi.deleteConversation,
    onSuccess: (_, id) => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (location.pathname === `/chat/${id}`) navigate("/chat/new");
    },
  });
  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return (conversations.data ?? []).filter((item) =>
      item.title.toLocaleLowerCase().includes(needle),
    );
  }, [conversations.data, search]);

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
        <button
          className="new-chat-button"
          type="button"
          onClick={() => createConversation.mutate()}
          disabled={createConversation.isPending}
        >
          <Plus size={18} />
          <span>{createConversation.isPending ? "创建中…" : "新建对话"}</span>
        </button>
        <label className="conversation-search">
          <Search size={17} />
          <input
            aria-label="搜索对话"
            placeholder="搜索对话"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="conversation-list">
          {conversations.isLoading ? (
            <p className="sidebar-empty">正在读取…</p>
          ) : null}
          {filtered.map((conversation) => (
            <div className="conversation-item" key={conversation.id}>
              <NavLink to={`/chat/${conversation.id}`}>
                <span>{conversation.title}</span>
                <time>
                  {new Date(conversation.updated_at).toLocaleDateString(
                    "zh-CN",
                    { month: "numeric", day: "numeric" },
                  )}
                </time>
              </NavLink>
              <div className="conversation-item__actions">
                <button
                  type="button"
                  aria-label={`重命名 ${conversation.title}`}
                  onClick={() => {
                    const title = window
                      .prompt("输入新的对话名称", conversation.title)
                      ?.trim();
                    if (title)
                      renameConversation.mutate({ id: conversation.id, title });
                  }}
                >
                  <Pencil />
                </button>
                <button
                  type="button"
                  aria-label={`删除 ${conversation.title}`}
                  onClick={() => {
                    if (
                      window.confirm(
                        `确定删除“${conversation.title}”及其消息吗？`,
                      )
                    )
                      deleteConversation.mutate(conversation.id);
                  }}
                >
                  <Trash2 />
                </button>
              </div>
            </div>
          ))}
          {!conversations.isLoading && filtered.length === 0 ? (
            <p className="sidebar-empty">暂无对话</p>
          ) : null}
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
