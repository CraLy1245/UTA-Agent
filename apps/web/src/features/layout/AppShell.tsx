import { Outlet } from "react-router-dom";

import { ConversationSidebar } from "../conversations/ConversationSidebar";
import { AgentSidebar } from "../survival/AgentSidebar";

export function AppShell() {
  return (
    <div className="workspace-shell">
      <ConversationSidebar />
      <main className="workspace-main">
        <Outlet />
      </main>
      <AgentSidebar />
    </div>
  );
}
